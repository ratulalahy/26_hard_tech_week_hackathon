// Local map layers (public/data/geo, from scripts/copy-data.mjs). Fetched on the main thread and
// handed to MapLibre as objects, so the map worker never resolves a URL (no tiles, glyphs or sprites).
import type { FeatureCollection } from 'geojson';

export interface Geo {
  ba: FeatureCollection; points: FeatureCollection; states: FeatureCollection; stateLines: FeatureCollection;
  countries: FeatureCollection; lakes: FeatureCollection; cities: FeatureCollection; roads: FeatureCollection;
  relief: { url: string; coordinates: [[number, number], [number, number], [number, number], [number, number]] };
}

const base = import.meta.env.BASE_URL;
const j = (f: string) => fetch(`${base}data/geo/${f}`).then((r) => { if (!r.ok) throw new Error(`geo/${f}: HTTP ${r.status}`); return r.json(); });

// Crop of the Natural Earth hillshade that the West needs, duotoned to the sandstone ramp (#8c6a4f → #fdf9f4).
export const VIEW_BOX = { w: -128, e: -97, s: 27, n: 52.5 };
const merc = (lat: number) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));

async function relief(): Promise<Geo['relief']> {
  const meta = await j('relief.json');
  const img = new Image();
  img.src = `${base}data/geo/relief.png`;
  await img.decode();
  const [L, B, R, T] = meta.bounds as [number, number, number, number];
  const W = img.naturalWidth, H = img.naturalHeight;
  const x0 = Math.floor(((VIEW_BOX.w - L) / (R - L)) * W), x1 = Math.ceil(((VIEW_BOX.e - L) / (R - L)) * W);
  const yOf = (lat: number) => ((merc(T) - merc(lat)) / (merc(T) - merc(B))) * H;
  const y0 = Math.floor(yOf(VIEW_BOX.n)), y1 = Math.ceil(yOf(VIEW_BOX.s));
  const cw = x1 - x0, ch = y1 - y0;
  const cv = document.createElement('canvas');
  cv.width = cw; cv.height = ch;
  const ctx = cv.getContext('2d', { willReadFrequently: true })!;
  ctx.drawImage(img, x0, y0, cw, ch, 0, 0, cw, ch);
  const d = ctx.getImageData(0, 0, cw, ch);
  const px = d.data;
  const hist = new Uint32Array(256);
  for (let i = 0; i < px.length; i += 4) hist[px[i]]++;
  let acc = 0, flat = 128;
  for (let v = 0; v < 256; v++) { acc += hist[v]; if (acc >= px.length / 8) { flat = Math.max(1, v); break; } }
  const g = [0xfd, 0xf9, 0xf4], s = [0x8c, 0x6a, 0x4f];
  for (let i = 0; i < px.length; i += 4) {
    const sh = Math.min(1.25, Math.max(0.45, px[i] / flat));
    const dark = Math.max(0, 1 - sh) * 1.25, light = Math.max(0, sh - 1) * 2;
    for (let k = 0; k < 3; k++) {
      const v = g[k] * (1 - dark) + s[k] * dark;
      px[i + k] = Math.round(v + (255 - v) * light * 0.6);
    }
    px[i + 3] = 255;
  }
  ctx.putImageData(d, 0, 0);
  const lonOf = (x: number) => L + (x / W) * (R - L);
  const latOf = (y: number) => { const m = merc(T) - (y / H) * (merc(T) - merc(B)); return ((2 * Math.atan(Math.exp(m)) - Math.PI / 2) * 180) / Math.PI; };
  const blob: Blob = await new Promise((res) => cv.toBlob((b) => res(b!), 'image/png'));
  const w = lonOf(x0), e = lonOf(x1), n = latOf(y0), sLat = latOf(y1);
  return { url: URL.createObjectURL(blob), coordinates: [[w, n], [e, n], [e, sLat], [w, sLat]] };
}

let cache: Promise<Geo> | null = null;
export function loadGeo(): Promise<Geo> {
  cache ??= (async () => {
    const [ba, points, states, stateLines, countries, lakes, cities, roads, rel] = await Promise.all([
      j('ba.geojson'), j('ba_points.geojson'), j('states.geojson'), j('state_lines.geojson'), j('countries.geojson'),
      j('lakes.geojson'), j('cities.geojson'), j('roads.geojson'), relief(),
    ]);
    return { ba, points, states, stateLines, countries, lakes, cities, roads, relief: rel };
  })();
  return cache;
}
