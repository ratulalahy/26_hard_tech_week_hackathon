// The West as a zoomable choropleth of real balancing-authority polygons (MapLibre GL, local GeoJSON,
// no tile/glyph/sprite server). Labels are HTML overlays, decluttered by zoom and hidden where a dock
// covers them. Only the four core regions carry the carbon scale; the rest are neutral context.
import * as maplibregl from 'maplibre-gl';
// MapLibre 6 runs its worker from a separate, self-contained module; bundle it as a local asset.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import type { GeoJSONSource, LngLatBoundsLike, Map as MLMap, MapLayerMouseEvent } from 'maplibre-gl';
import type { Feature, FeatureCollection, LineString } from 'geojson';
import { useEffect, useRef, useState } from 'react';
import { C, ci2c, onFill } from '../lib/color';
import { CORE, REGION, type Core, type Dest } from '../lib/data';
import { Ev, Icon } from '../components/ui';
import { loadGeo, type Geo } from './geo';

maplibregl.setWorkerUrl(new URL(workerUrl, location.href).href);

const still = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const CAMERA_MS = 300;

export const WEST: LngLatBoundsLike = [[-124.8, 31.2], [-103.5, 49.2]];
// Each core region's callout: a point inside the region, and the side the card sits on, chosen so
// cards stay off the arcs and off each other. Arcs run between the BAs' main load centres.
const CALLOUT: Record<Core, { at: [number, number]; side: 'above' | 'right' | 'left' }> = {
  BPAT: { at: [-120.4, 47.1], side: 'above' },
  CISO: { at: [-120.6, 37.4], side: 'left' },
  NEVP: { at: [-116.9, 40.4], side: 'above' },
  PACE: { at: [-110.4, 38.9], side: 'right' },
};
const HUB: Record<Core, [number, number]> = { PACE: [-111.93, 40.78], BPAT: [-122.64, 45.63], CISO: [-118.23, 34.05], NEVP: [-115.15, 36.17] };
const US_CITY = new Set(['Los Angeles', 'Denver', 'San Francisco', 'Phoenix', 'San Diego', 'Seattle', 'Salt Lake City', 'Las Vegas', 'Portland', 'Boise', 'Sacramento', 'Albuquerque', 'Reno', 'Spokane', 'Tucson', 'Fresno', 'Cheyenne', 'Provo', 'Ogden', 'Eugene', 'Bakersfield', 'El Paso', 'Santa Fe', 'Colorado Springs', 'Carson City', 'Salem', 'Olympia', 'Fort Collins', 'Tacoma', 'San Jose', 'Oakland', 'Helena', 'Billings', 'Missoula', 'Great Falls', 'Pocatello', 'Idaho Falls', 'St. George', 'Grand Junction', 'Flagstaff', 'Medford', 'Bend', 'Yakima', 'Twin Falls', 'Casper', 'Rock Springs']);
const NEUTRAL = '#efe5d9'; // context regions: a flat sand, never on the carbon scale

export interface ArcSpec { to: Dest; weight: number; label: string; selected: boolean }
export interface MapProps {
  id: string;
  variant: 'main' | 'inset';
  interactive: boolean;
  /** watermark: stop recolouring and relabelling until the map is shown again */
  frozen?: boolean;
  ci: Record<string, number | null>; // core BA → CI at the selected hour (EIA estimate, modeled)
  context: Record<string, number | null>; // other western BAs → modeled fuel-mix year mean (tooltip only)
  hourLabel: string;
  arcs: ArcSpec[];
  ring?: boolean; // the job held in Utah (wait)
  padding?: { top: number; bottom: number; left: number; right: number };
  bounds?: LngLatBoundsLike;
  onPick?: (code: Dest) => void;
}

function arcLine(a: [number, number], b: [number, number], bend: number): [number, number][] {
  const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, dx = b[0] - a[0], dy = b[1] - a[1];
  const cx = mx - dy * bend, cy = my + dx * bend;
  const pts: [number, number][] = [];
  for (let i = 0; i <= 48; i++) { const t = i / 48, u = 1 - t; pts.push([u * u * a[0] + 2 * u * t * cx + t * t * b[0], u * u * a[1] + 2 * u * t * cy + t * t * b[1]]); }
  return pts;
}
// CISO bends west and NEVP east, so the two southbound arcs never share a path.
const BEND: Record<Dest, number> = { BPAT: -0.18, CISO: 0.16, NEVP: -0.22 };

function arcsFC(arcs: ArcSpec[]): FeatureCollection<LineString> {
  return {
    type: 'FeatureCollection',
    features: arcs.map((a) => ({ type: 'Feature', properties: { to: a.to, w: a.weight, sel: a.selected ? 1 : 0 }, geometry: { type: 'LineString', coordinates: arcLine(HUB.PACE, HUB[a.to], BEND[a.to]) } })),
  };
}

function colorExpr(ci: Record<string, number | null>, context: Record<string, number | null>) {
  const m: (string | number)[] = [];
  for (const k of Object.keys(context)) if (!(k in ci)) m.push(k, NEUTRAL);
  for (const [k, v] of Object.entries(ci)) if (v != null) m.push(k, ci2c(v));
  return ['match', ['get', 'code'], ...m, '#ffffff'] as unknown as maplibregl.ExpressionSpecification;
}
function opacityExpr(ci: Record<string, number | null>, context: Record<string, number | null>) {
  const m: (string | number)[] = [];
  for (const k of Object.keys(context)) if (!(k in ci)) m.push(k, 0.55);
  for (const k of Object.keys(ci)) if (ci[k] != null) m.push(k, 0.88);
  return ['match', ['get', 'code'], ...m, 0] as unknown as maplibregl.ExpressionSpecification;
}

function addLayers(map: MLMap, g: Geo, p: MapProps) {
  map.addSource('relief', { type: 'image', url: g.relief.url, coordinates: g.relief.coordinates });
  map.addSource('countries', { type: 'geojson', data: g.countries });
  map.addSource('states', { type: 'geojson', data: g.states });
  map.addSource('ba', { type: 'geojson', data: g.ba, promoteId: 'code' });
  map.addSource('lakes', { type: 'geojson', data: g.lakes });
  map.addSource('state-lines', { type: 'geojson', data: g.stateLines });
  map.addSource('roads', { type: 'geojson', data: g.roads });
  map.addSource('arcs', { type: 'geojson', data: arcsFC(p.arcs) });
  map.addSource('hubs', { type: 'geojson', data: { type: 'FeatureCollection', features: CORE.map((c) => ({ type: 'Feature', properties: { code: c }, geometry: { type: 'Point', coordinates: HUB[c] } })) } });

  map.addLayer({ id: 'land-other', type: 'fill', source: 'countries', filter: ['!=', ['get', 'adm0_a3'], 'USA'], paint: { 'fill-color': '#f6eee5', 'fill-antialias': false } });
  map.addLayer({ id: 'land-us', type: 'fill', source: 'states', paint: { 'fill-color': C.sky0, 'fill-antialias': false } });
  map.addLayer({ id: 'relief', type: 'raster', source: 'relief', paint: { 'raster-opacity': ['interpolate', ['linear'], ['zoom'], 4, 0.62, 7, 0.4], 'raster-fade-duration': 0, 'raster-resampling': 'linear' } });
  map.addLayer({ id: 'ba-fill', type: 'fill', source: 'ba', paint: { 'fill-color': colorExpr(p.ci, p.context), 'fill-opacity': opacityExpr(p.ci, p.context), 'fill-color-transition': { duration: 160, delay: 0 } } });
  map.addLayer({ id: 'lakes', type: 'fill', source: 'lakes', paint: { 'fill-color': '#ece6de', 'fill-outline-color': 'rgba(91,73,63,.35)' } });
  map.addLayer({ id: 'roads', type: 'line', source: 'roads', minzoom: 5, paint: { 'line-color': C.sand0, 'line-opacity': ['interpolate', ['linear'], ['zoom'], 5, 0.18, 7, 0.35], 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 0.5, 8, 1.1] } });
  map.addLayer({ id: 'state-lines', type: 'line', source: 'state-lines', paint: { 'line-color': C.ink3, 'line-opacity': 0.4, 'line-width': 0.6, 'line-dasharray': [3, 2] } });
  map.addLayer({ id: 'ba-casing', type: 'line', source: 'ba', paint: { 'line-color': '#ffffff', 'line-opacity': 0.9, 'line-width': ['interpolate', ['linear'], ['zoom'], 4, 2.5, 8, 3.5] } });
  map.addLayer({ id: 'ba-line', type: 'line', source: 'ba', paint: { 'line-color': C.ink, 'line-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 0.95, ['match', ['get', 'code'], [...CORE], 0.7, 0.4]], 'line-width': ['case', ['match', ['get', 'code'], [...CORE], true, false], 1.5, ['boolean', ['feature-state', 'hover'], false], 1.5, 0.9] } });
  map.addLayer({ id: 'arcs-casing', type: 'line', source: 'arcs', layout: { 'line-cap': 'round' }, paint: { 'line-color': '#ffffff', 'line-opacity': 0.95, 'line-width': ['+', 3, ['*', 8, ['get', 'w']]] } });
  map.addLayer({ id: 'arcs', type: 'line', source: 'arcs', layout: { 'line-cap': 'round' }, paint: { 'line-color': C.route, 'line-opacity': ['case', ['==', ['get', 'sel'], 1], 1, 0.7], 'line-width': ['+', 1.25, ['*', 6, ['get', 'w']]] } });
  map.addLayer({ id: 'hubs', type: 'circle', source: 'hubs', paint: { 'circle-radius': ['case', ['==', ['get', 'code'], 'PACE'], 5, 3.5], 'circle-color': ['case', ['==', ['get', 'code'], 'PACE'], '#ffffff', C.route], 'circle-stroke-color': ['case', ['==', ['get', 'code'], 'PACE'], C.route, '#ffffff'], 'circle-stroke-width': 2 } });
}

interface Lbl { el: HTMLElement; minZoom: number; ll: [number, number]; always?: boolean }

function el(cls: string, html: string) { const d = document.createElement('div'); d.className = cls; d.innerHTML = html; return d; }
const ANCHOR = { above: 'bottom', right: 'left', left: 'right' } as const;

export function WestMap(p: MapProps) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const ready = useRef(false);
  const regionEls = useRef<Partial<Record<Core, HTMLElement>>>({});
  const arcEls = useRef<{ mk: maplibregl.Marker; ll: [number, number] }[]>([]);
  const labels = useRef<Lbl[]>([]);
  const [hover, setHover] = useState<{ code: string; name: string; x: number; y: number } | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const props = useRef(p);
  props.current = p;

  const fit = (animate: boolean) => {
    const m = map.current; if (!m) return;
    const q = props.current;
    m.fitBounds(q.bounds ?? WEST, { padding: q.padding ?? { top: 16, bottom: 16, left: 16, right: 16 }, duration: animate && !still() ? CAMERA_MS : 0 });
  };

  // Labels show by zoom, and only inside the window the docks leave free (no callouts under panels).
  // Labels show by zoom, only when their whole box sits in the window the docks leave free, and
  // never on top of another shown label or an overlay marked data-map-avoid (caption, zoom buttons).
  // Priority: region callouts, then arc labels, cities, states, context-region codes, the lake.
  const declutter = () => {
    const m = map.current; if (!m) return;
    const z = m.getZoom(), q = props.current;
    const H = m.getContainer().clientHeight;
    const pad = q.padding ?? { top: 0, bottom: 0, left: 0, right: 0 };
    const box0 = m.getContainer().getBoundingClientRect();
    const win = { l: box0.left + pad.left, r: box0.right - pad.right, t: box0.top + pad.top, b: box0.top + H - pad.bottom };
    const inWin = (r: DOMRect) => r.left >= win.l && r.right <= win.r && r.top >= win.t && r.bottom <= win.b;
    const inBox = (r: DOMRect) => r.left >= box0.left && r.right <= box0.right && r.top >= box0.top && r.bottom <= box0.bottom;
    const taken: DOMRect[] = q.variant === 'main' ? [...document.querySelectorAll<HTMLElement>('[data-map-avoid]')].map((e) => e.getBoundingClientRect()) : [];
    const hit = (r: DOMRect) => taken.some((t) => r.left < t.right + 2 && r.right > t.left - 2 && r.top < t.bottom + 2 && r.bottom > t.top - 2);
    const show = (node: HTMLElement, ok: boolean) => {
      node.style.display = '';
      const r = node.getBoundingClientRect();
      if (!ok || !(q.variant === 'inset' ? inBox(r) : inWin(r)) || hit(r)) { node.style.display = 'none'; return; }
      taken.push(r);
    };
    const rank = (l: Lbl) => (l.el.classList.contains('mk-callout') ? 0 : l.el.classList.contains('mk-city') ? 2 : l.el.classList.contains('mk-state') ? 3 : l.el.classList.contains('mk-ba') ? 4 : 5);
    const callouts = labels.current.filter((l) => rank(l) === 0);
    for (const l of callouts) show(l.el, z >= l.minZoom);
    for (const a of arcEls.current) show(a.mk.getElement(), true);
    for (const l of labels.current.filter((x) => rank(x) > 0).sort((x, y) => rank(x) - rank(y))) show(l.el, z >= l.minZoom);
  };

  useEffect(() => {
    let alive = true;
    const m = new maplibregl.Map({
      container: box.current!,
      style: { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#f1e9df' } }] },
      bounds: p.bounds ?? WEST,
      fitBoundsOptions: { padding: p.padding ?? 16 },
      attributionControl: false,
      interactive: p.variant === 'main',
      dragRotate: false,
      pitchWithRotate: false,
      touchPitch: false,
      renderWorldCopies: false,
      minZoom: 3,
      maxZoom: 9,
      fadeDuration: 0,
    });
    if (still()) m.scrollZoom.setWheelZoomRate(1 / 200);
    m.touchZoomRotate.disableRotation();
    m.keyboard.disableRotation();
    map.current = m;
    m.on('load', async () => {
      try {
        const g = await loadGeo();
        if (!alive) return;
        addLayers(m, g, props.current);
        ready.current = true;
        const add = (node: HTMLElement, ll: [number, number], minZoom: number, anchor: maplibregl.PositionAnchor = 'center', offset: [number, number] = [0, 0], always = false) => {
          new maplibregl.Marker({ element: node, anchor, offset }).setLngLat(ll).addTo(m);
          labels.current.push({ el: node, minZoom, ll, always });
        };
        const inset = props.current.variant === 'inset';
        if (!inset) {
          for (const f of g.states.features) {
            const pr = f.properties as { name: string; label_lon: number; label_lat: number };
            if (pr.label_lon > -102.5) continue;
            add(el('mk-label mk-state', pr.name), [pr.label_lon, pr.label_lat], 4.3);
          }
          for (const f of g.cities.features as Feature[]) {
            const pr = f.properties as { name: string; adm0_a3: string; scalerank: number };
            if (pr.adm0_a3 !== 'USA' || !US_CITY.has(pr.name)) continue;
            const c = (f.geometry as unknown as { coordinates: [number, number] }).coordinates;
            if (c[0] > -102.5) continue;
            const mz = pr.scalerank <= 2 ? 3 : pr.scalerank <= 3 ? 4.6 : pr.scalerank <= 4 ? 5 : pr.scalerank <= 6 ? 5.6 : 6.4;
            add(el('mk-label mk-city', `<i></i><span>${pr.name}</span>`), c, mz, 'left', [-3, 0]);
          }
          add(el('mk-label mk-lake', 'Great Salt Lake'), [-112.55, 41.12], 5.2);
          // context regions: names only (their modeled value is in the tooltip)
          for (const f of g.points.features) {
            const pr = f.properties as { code: string; label_lon: number; label_lat: number };
            if (!(pr.code in props.current.context) || (CORE as readonly string[]).includes(pr.code)) continue;
            add(el('mk-label mk-ba', pr.code), [pr.label_lon, pr.label_lat], 5.4);
          }
        }
        for (const c of CORE) {
          const node = document.createElement('div');
          node.className = `mk-label mk-callout side-${CALLOUT[c].side}`;
          regionEls.current[c] = node;
          add(node, CALLOUT[c].at, 0, ANCHOR[CALLOUT[c].side], [0, 0], inset);
        }
        paintLabels();
        paintArcs();
        declutter();
        setLoading(false);
      } catch (e) { setFailed(String(e)); setLoading(false); }
    });
    m.on('move', declutter);
    m.on('mousemove', 'ba-fill', (e: MapLayerMouseEvent) => {
      const f = e.features?.[0]; if (!f) return;
      const code = String(f.properties?.code);
      m.getCanvas().style.cursor = (props.current.onPick && (code === 'BPAT' || code === 'CISO' || code === 'NEVP')) ? 'pointer' : '';
      setHover((h) => {
        if (h?.code && h.code !== code) m.setFeatureState({ source: 'ba', id: h.code }, { hover: false });
        m.setFeatureState({ source: 'ba', id: code }, { hover: true });
        return { code, name: String(f.properties?.name ?? code), x: e.point.x, y: e.point.y };
      });
    });
    m.on('mouseleave', 'ba-fill', () => { setHover((h) => { if (h) m.setFeatureState({ source: 'ba', id: h.code }, { hover: false }); return null; }); m.getCanvas().style.cursor = ''; });
    m.on('click', 'ba-fill', (e: MapLayerMouseEvent) => { const code = String(e.features?.[0]?.properties?.code); if (code === 'BPAT' || code === 'CISO' || code === 'NEVP') props.current.onPick?.(code); });
    const ro = new ResizeObserver(() => { m.resize(); if (props.current.variant === 'inset') fit(false); declutter(); });
    ro.observe(box.current!);
    return () => { alive = false; ro.disconnect(); m.remove(); map.current = null; ready.current = false; labels.current = []; arcEls.current = []; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function paintLabels() {
    const q = props.current;
    for (const c of CORE) {
      const node = regionEls.current[c]; if (!node) continue;
      const v = q.ci[c];
      const fill = v == null ? '#ffffff' : ci2c(v);
      const sel = q.arcs.find((a) => a.to === c && a.selected);
      const icon = c === 'PACE' ? (q.ring ? 'moon' : 'bolt') : sel ? 'route' : c === 'BPAT' ? 'drop' : 'bolt';
      const swFill = sel ? C.route : fill;
      node.innerHTML = `<i class="lead" aria-hidden="true"></i><div class="mk-region"><span class="sw" style="background:${swFill};color:${onFill(swFill)}">${iconSvg(icon)}</span><div><div class="t-12 fw-600" style="color:${C.ink}">${REGION[c].name} · ${c}</div><div class="t-12" style="color:${C.ink2}"><b class="fw-600" style="color:${C.ink}">${v == null ? '–' : Math.round(v)}</b> <span class="t-11" style="color:${C.ink3}">g/kWh · ${q.hourLabel}</span></div></div></div>`;
    }
  }
  function paintArcs() {
    const m = map.current; if (!m || !ready.current) return;
    const q = props.current;
    (m.getSource('arcs') as GeoJSONSource).setData(arcsFC(q.arcs));
    for (const a of arcEls.current) a.mk.remove();
    arcEls.current = [];
    for (const a of q.arcs) {
      if (!a.label) continue;
      const line = arcLine(HUB.PACE, HUB[a.to], BEND[a.to]);
      const mid = line[Math.round(line.length * 0.5)];
      arcEls.current.push({ mk: new maplibregl.Marker({ element: el('mk-label mk-arc', a.label), anchor: 'center' }).setLngLat(mid).addTo(m), ll: mid });
    }
  }

  // data changes: recolour polygons, relabel, redraw arcs. A frozen (watermark) map stays as it is.
  useEffect(() => {
    const m = map.current; if (!m || !ready.current || p.frozen) return;
    m.setPaintProperty('ba-fill', 'fill-color', colorExpr(p.ci, p.context));
    m.setPaintProperty('ba-fill', 'fill-opacity', opacityExpr(p.ci, p.context));
    paintLabels();
    paintArcs();
    declutter();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.ci, p.context, p.arcs, p.hourLabel, p.ring, p.frozen]);

  useEffect(() => {
    const m = map.current; if (!m) return;
    const on = p.interactive;
    for (const h of [m.scrollZoom, m.dragPan, m.doubleClickZoom, m.touchZoomRotate, m.keyboard, m.boxZoom]) (on ? h.enable() : h.disable());
  }, [p.interactive]);

  useEffect(() => { if (map.current && ready.current) { fit(true); setTimeout(declutter, CAMERA_MS + 20); } // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.padding?.left, p.padding?.right, p.padding?.top, p.padding?.bottom]);

  const isCore = hover && hover.code in p.ci;
  const ctxV = hover && !isCore && hover.code in p.context ? p.context[hover.code] : undefined;

  return (
    <div id={p.id} className="absolute inset-0" aria-label={p.variant === 'main' ? 'Map of the western US balancing authorities; the four core regions coloured by carbon intensity' : 'Inset map: Utah and the three destinations'} role="region">
      <div ref={box} style={{ position: 'absolute', inset: 0 }} />
      {loading && <div className="absolute inset-0 grid place-items-center"><span className="t-12 ink-3">Drawing the West…</span></div>}
      {failed && <div className="absolute inset-0 grid place-items-center"><div className="panel t-13" style={{ maxWidth: 360 }}><b className="fw-600">The map layers did not load.</b><div className="t-12 ink-2" style={{ marginTop: 4 }}>{failed}. Run <code>npm run data</code> on a machine with the data directory, then rebuild. The numbers in the panels do not depend on the map.</div></div></div>}
      {hover && p.interactive && (
        <div className="tip" style={{ left: hover.x + 16, top: hover.y - 8, position: 'absolute' }}>
          <div className="fw-600">{hover.name} <span className="ink-3 fw-500">· {hover.code}</span></div>
          {isCore ? (<div><b className="fw-600">{p.ci[hover.code] == null ? '–' : Math.round(p.ci[hover.code]!)}</b> <span className="ink-3">g/kWh at {p.hourLabel}</span> <Ev e="modeled">modeled · EIA estimate</Ev></div>)
            : ctxV != null ? (<div><span className="ink-2">Context only, not on the carbon scale. Year mean of its generation fuel mix: </span><b className="fw-600">{Math.round(ctxV)}</b> <span className="ink-3">g/kWh</span> <Ev e="modeled" /></div>)
              : <div className="ink-3">No carbon series for this region in this build</div>}
        </div>
      )}
      {p.variant === 'main' && p.interactive && (
        <div data-map-avoid className="absolute flex flex-col gap-2" style={{ right: (p.padding?.right ?? 16) - 48, bottom: (p.padding?.bottom ?? 16) + 0 }}>
          <button className="iconbtn" aria-label="Zoom in" onClick={() => map.current?.zoomIn({ duration: still() ? 0 : 200 })}><Icon name="plus" /></button>
          <button className="iconbtn" aria-label="Zoom out" onClick={() => map.current?.zoomOut({ duration: still() ? 0 : 200 })}><Icon name="minus" /></button>
          <button className="iconbtn" aria-label="Reset to the West" title="Reset to the West" onClick={() => fit(true)}><Icon name="reset" /></button>
        </div>
      )}
    </div>
  );
}

const ICONS: Record<string, string> = {
  bolt: '<path d="M8.75 1.75 3.75 9h4l-.75 5.25L12.25 7h-4l.5-5.25Z"/>',
  drop: '<path d="M8 2s-4.25 4.75-4.25 7.5a4.25 4.25 0 0 0 8.5 0C12.25 6.75 8 2 8 2Z"/>',
  route: '<path d="M2.75 13.25c0-4.75 2.75-5.75 5.75-5.75h4.75"/><path d="M10.5 4.75 13.25 7.5 10.5 10.25"/>',
  moon: '<path d="M12.75 10.25A5.25 5.25 0 1 1 5.75 3.25a4.25 4.25 0 0 0 7 7Z"/>',
};
const iconSvg = (n: string) => `<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[n]}</svg>`;
