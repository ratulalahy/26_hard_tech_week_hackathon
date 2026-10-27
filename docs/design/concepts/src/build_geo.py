"""Build extra map layers + a composited relief ground for the v2 concepts.

Same Web Mercator box as the mock data (lon -125..-101, lat 30.5..49.5, W=1000).
Reads the shared data dir (GRIDPILOT_DATA_DIR) and data.json next to this script.
Writes geo_extra.json and ground.webp next to this script. Run with the lab venv:
  lab/.venv/bin/python docs/design/concepts/src/build_geo.py
"""
import json, math, io, os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from shapely.geometry import shape, box, mapping
from shapely.ops import transform

GEO = Path(os.environ.get('GRIDPILOT_DATA_DIR', Path(__file__).resolve().parents[4] / 'data')) / 'processed/geo'
OUT = Path(__file__).parent
LON0, LON1, LAT0, LAT1 = -125.0, -101.0, 30.5, 49.5
W = 1000.0
def merc_y(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
Y0, Y1 = merc_y(LAT1), merc_y(LAT0)
H = W * (Y0 - Y1) / math.radians(LON1 - LON0)
def proj(x, y, z=None):
    x = np.asarray(x); y = np.asarray(y)
    px = (x - LON0) / (LON1 - LON0) * W
    py = (Y0 - np.log(np.tan(np.pi / 4 + np.radians(y) / 2))) / (Y0 - Y1) * H
    return px, py
clip = box(LON0 - 1, LAT0 - 1, LON1 + 1, LAT1 + 1)

def polys(g):
    if g.is_empty: return []
    if g.geom_type == 'Polygon': return [g]
    if g.geom_type in ('MultiPolygon', 'GeometryCollection'):
        return [p for p in g.geoms if p.geom_type == 'Polygon']
    return []

def to_d(g, prec=1):
    parts = []
    for p in polys(g):
        for ring in [p.exterior, *p.interiors]:
            pts = list(ring.coords)
            parts.append('M' + 'L'.join(f'{x:.{prec}f},{y:.{prec}f}' for x, y in pts) + 'Z')
    return ''.join(parts)

out = {}
# Land (US vs others) and lakes
countries = json.loads((GEO / 'basemap/countries.geojson').read_text())['features']
us, other = [], []
for f in countries:
    g = shape(f['geometry']).intersection(clip)
    if g.is_empty: continue
    g = transform(proj, g.simplify(0.02, preserve_topology=True))
    (us if f['properties'].get('adm0_a3') == 'USA' else other).append(g)
lakes = []
for f in json.loads((GEO / 'basemap/lakes.geojson').read_text())['features']:
    g = shape(f['geometry'])
    if not g.intersects(clip): continue
    if g.area < 0.03: continue
    lakes.append((f['properties'].get('name'), transform(proj, g.intersection(clip).simplify(0.01, preserve_topology=True))))
out['lakes_d'] = ''.join(to_d(g) for _, g in lakes)
out['us_d'] = ''.join(to_d(g) for g in us)
print('lakes', [n for n, _ in lakes])

# Cities for orientation
want = ['Salt Lake City', 'Portland', 'Seattle', 'Las Vegas', 'San Francisco', 'Los Angeles', 'Phoenix', 'Denver', 'Boise', 'Reno', 'Spokane', 'Albuquerque']
cities = {}
for f in json.loads((GEO / 'basemap/cities.geojson').read_text())['features']:
    n = f['properties']['name']; lon, lat = f['geometry']['coordinates']
    if n in want and LON0 < lon < LON1 and LAT0 < lat < LAT1 and n not in cities:
        x, y = proj([lon], [lat]); cities[n] = [round(float(x[0]), 1), round(float(y[0]), 1)]
out['cities'] = cities

# BA label anchors (representative points) for every western BA in the mock
data = json.loads((OUT / 'data.json').read_text())
codes = {p['code'] for p in data['map']['paths']}
anch = {}
for f in json.loads((GEO / 'ba_boundaries.geojson').read_text())['features']:
    c = f['properties'].get('code') or f['properties'].get('ba')
    if c in codes:
        g = shape(f['geometry'])
        rp = g.representative_point()
        x, y = proj([rp.x], [rp.y]); anch[c] = [round(float(x[0])), round(float(y[0]))]
out['anchors'] = anch

# Hex grid over US land in the box: each hex keeps the BA its centre falls in (or none).
from shapely.prepared import prep
from shapely.geometry import Point
ba_geoms = []
for f in json.loads((GEO / 'ba_boundaries.geojson').read_text())['features']:
    c = f['properties'].get('code') or f['properties'].get('ba')
    if c in codes:
        ba_geoms.append((c, prep(transform(proj, shape(f['geometry']).buffer(0)))))
from shapely.ops import unary_union
us_union = prep(unary_union(us))
R = 8.5                      # hex radius in map units (pointy-top)
dx, dy = math.sqrt(3) * R, 1.5 * R
hexes = []
row = 0; y = R
while y < H + R:
    x = (dx / 2 if row % 2 else 0.0)
    while x < W + dx:
        pt = Point(x, y)
        if us_union.contains(pt):
            code = next((c for c, g in ba_geoms if g.contains(pt)), None)
            hexes.append([round(x, 1), round(y, 1), code])
        x += dx
    y += dy; row += 1
out['hex'] = {'r': R, 'cells': hexes}
print('hexes', len(hexes), 'with BA', sum(1 for h in hexes if h[2]))
(OUT / 'geo_extra.json').write_text(json.dumps(out, separators=(',', ':')))

# Composited ground: lavender mist, a white sculpted US relief lifted by a soft long shadow.
S = 1.4  # px per unit
PW, PH = int(W * S), int(round(H * S))
meta = json.loads((GEO / 'basemap/relief.json').read_text())
src = Image.open(GEO / 'basemap/relief.png').convert('L')
L_, B_, R_, T_ = meta['bounds']
fy = lambda lat: (merc_y(T_) - merc_y(lat)) / (merc_y(T_) - merc_y(B_)) * src.height
crop = (round((LON0 - L_) / (R_ - L_) * src.width), round(fy(LAT1)), round((LON1 - L_) / (R_ - L_) * src.width), round(fy(LAT0)))
rel = src.crop(crop).resize((PW, PH), Image.LANCZOS)
r = np.asarray(rel, dtype=np.float32) / 255.0
flat = np.median(r)
shade = np.clip(r / flat, 0.45, 1.25)

def mask_img(geoms):
    m = Image.new('L', (PW, PH), 0); d = ImageDraw.Draw(m)
    for g in geoms:
        for p in polys(g):
            d.polygon([(x * S, y * S) for x, y in p.exterior.coords], fill=255)
            for hole in p.interiors:
                d.polygon([(x * S, y * S) for x, y in hole.coords], fill=0)
    return m
def arr(m, blur=0.8):
    return np.asarray(m.filter(ImageFilter.GaussianBlur(blur)), dtype=np.float32) / 255.0
mi_us = mask_img(us)
m_us = arr(mi_us); m_other = arr(mask_img(other)); m_lake = arr(mask_img([g for _, g in lakes]))
# long soft shadow of the US land mass, offset down-right
sh = Image.new('L', (PW, PH), 0); sh.paste(mi_us, (int(10 * S), int(18 * S)))
m_shadow = arr(sh, 16) * (1 - m_us)
hexrgb = lambda h: np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float32)
ocean = hexrgb('#eeecf9'); shadow = hexrgb('#c9c3ea'); land = hexrgb('#ffffff'); far = hexrgb('#f3f2fb'); lake = hexrgb('#e3e0f6')
tint = hexrgb('#5b4fa8')       # shade colour: a lavender-grey, not black
sh3 = shade[..., None]
dark = np.clip(1 - sh3, 0, 1); light = np.clip(sh3 - 1, 0, 1)
land_px = land * (1 - 0.95 * dark) + tint * (0.95 * dark) * 0.55 + land * 0.0
land_px = land_px * (1 - 0.0) + (255 - land_px) * light * 0.8
land_px = np.clip(land_px, 0, 255)
far_px = np.clip(far * (1 - 0.35 * dark) + tint * 0.35 * dark * 0.5, 0, 255)
img = ocean[None, None, :] * np.ones((PH, PW, 1), dtype=np.float32)
img = img * (1 - 0.55 * m_shadow[..., None]) + shadow * 0.55 * m_shadow[..., None]
img = img * (1 - m_other[..., None]) + far_px * m_other[..., None]
img = img * (1 - m_us[..., None]) + land_px * m_us[..., None]
img = img * (1 - m_lake[..., None]) + lake * m_lake[..., None]
im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), 'RGB')
for q in (82, 74, 66):
    buf = io.BytesIO(); im.save(buf, 'WEBP', quality=q, method=6)
    if buf.tell() <= 400_000: break
(OUT / 'ground.webp').write_bytes(buf.getvalue())
if os.environ.get('PREVIEW'): im.save(os.environ['PREVIEW'])
print('ground.webp bytes', buf.tell(), 'q', q, 'size', im.size)
