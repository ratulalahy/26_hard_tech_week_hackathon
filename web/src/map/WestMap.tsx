// The West as a zoomable choropleth of real balancing-authority polygons (MapLibre GL, local GeoJSON,
// no tile/glyph/sprite server). Labels are HTML overlays, decluttered by zoom. Arcs are native line layers.
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

export const WEST: LngLatBoundsLike = [[-124.8, 31.2], [-103.5, 49.2]];
// Where each core region's label and arc end sit. PACE's label is anchored in Utah (its polygon's
// pole of inaccessibility lies in Wyoming); arcs run between the BAs' main load centres.
const LABEL_AT: Record<Core, [number, number]> = { PACE: [-111.1, 39.0], BPAT: [-120.6, 46.6], CISO: [-120.2, 36.9], NEVP: [-116.6, 39.6] };
const HUB: Record<Core, [number, number]> = { PACE: [-111.93, 40.78], BPAT: [-122.64, 45.63], CISO: [-118.23, 34.05], NEVP: [-115.15, 36.17] };
const LABEL_OFFSET: Record<Core, [number, number]> = { PACE: [0, 0], BPAT: [0, 0], CISO: [0, 0], NEVP: [0, 0] };
const US_CITY = new Set(['Los Angeles', 'Denver', 'San Francisco', 'Phoenix', 'San Diego', 'Seattle', 'Salt Lake City', 'Las Vegas', 'Portland', 'Boise', 'Sacramento', 'Albuquerque', 'Reno', 'Spokane', 'Tucson', 'Fresno', 'Cheyenne', 'Provo', 'Ogden', 'Eugene', 'Bakersfield', 'El Paso', 'Santa Fe', 'Colorado Springs', 'Carson City', 'Salem', 'Olympia', 'Fort Collins', 'Tacoma', 'San Jose', 'Oakland']);

export interface ArcSpec { to: Dest; weight: number; label: string; selected: boolean }
export interface MapProps {
  id: string;
  variant: 'main' | 'inset';
  interactive: boolean;
  ci: Record<string, number | null>; // core BA → CI at the selected hour (observed typical day)
  context: Record<string, number | null>; // other western BAs → modeled fuel-mix year mean
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
const BEND: Record<Dest, number> = { BPAT: -0.18, CISO: 0.2, NEVP: 0.22 };

function arcsFC(arcs: ArcSpec[]): FeatureCollection<LineString> {
  return {
    type: 'FeatureCollection',
    features: arcs.map((a) => ({ type: 'Feature', properties: { to: a.to, w: a.weight, sel: a.selected ? 1 : 0 }, geometry: { type: 'LineString', coordinates: arcLine(HUB.PACE, HUB[a.to], BEND[a.to]) } })),
  };
}

function colorExpr(ci: Record<string, number | null>, context: Record<string, number | null>) {
  const m: (string | number)[] = [];
  for (const [k, v] of Object.entries(context)) if (v != null) m.push(k, ci2c(v));
  for (const [k, v] of Object.entries(ci)) if (v != null) m.push(k, ci2c(v));
  return ['match', ['get', 'code'], ...m, '#ffffff'] as unknown as maplibregl.ExpressionSpecification;
}
function opacityExpr(ci: Record<string, number | null>, context: Record<string, number | null>, variant: MapProps['variant']) {
  const m: (string | number)[] = [];
  for (const k of Object.keys(context)) if (context[k] != null && !(k in ci)) m.push(k, variant === 'main' ? 0.38 : 0.3);
  for (const k of Object.keys(ci)) if (ci[k] != null) m.push(k, 0.86);
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

  map.addLayer({ id: 'land-other', type: 'fill', source: 'countries', filter: ['!=', ['get', 'adm0_a3'], 'USA'], paint: { 'fill-color': '#f6eee5' } });
  map.addLayer({ id: 'land-us', type: 'fill', source: 'states', paint: { 'fill-color': C.sky0 } });
  map.addLayer({ id: 'relief', type: 'raster', source: 'relief', paint: { 'raster-opacity': ['interpolate', ['linear'], ['zoom'], 4, 0.62, 7, 0.4], 'raster-fade-duration': 0, 'raster-resampling': 'linear' } });
  map.addLayer({ id: 'ba-fill', type: 'fill', source: 'ba', paint: { 'fill-color': colorExpr(p.ci, p.context), 'fill-opacity': opacityExpr(p.ci, p.context, p.variant), 'fill-color-transition': { duration: 160, delay: 0 } } });
  map.addLayer({ id: 'lakes', type: 'fill', source: 'lakes', paint: { 'fill-color': '#ece6de', 'fill-outline-color': 'rgba(91,73,63,.35)' } });
  map.addLayer({ id: 'roads', type: 'line', source: 'roads', minzoom: 5.6, paint: { 'line-color': C.sand0, 'line-opacity': 0.3, 'line-width': 0.7 } });
  map.addLayer({ id: 'state-lines', type: 'line', source: 'state-lines', paint: { 'line-color': C.ink3, 'line-opacity': 0.4, 'line-width': 0.6, 'line-dasharray': [3, 2] } });
  map.addLayer({ id: 'ba-casing', type: 'line', source: 'ba', paint: { 'line-color': '#ffffff', 'line-opacity': 0.9, 'line-width': ['interpolate', ['linear'], ['zoom'], 4, 2.5, 8, 3.5] } });
  map.addLayer({ id: 'ba-line', type: 'line', source: 'ba', paint: { 'line-color': C.ink, 'line-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 0.95, 0.5], 'line-width': ['case', ['==', ['get', 'code'], 'PACE'], 1.5, ['boolean', ['feature-state', 'hover'], false], 1.5, 1] } });
  map.addLayer({ id: 'arcs-casing', type: 'line', source: 'arcs', layout: { 'line-cap': 'round' }, paint: { 'line-color': '#ffffff', 'line-opacity': 0.95, 'line-width': ['+', 3, ['*', 8, ['get', 'w']]] } });
  map.addLayer({ id: 'arcs', type: 'line', source: 'arcs', layout: { 'line-cap': 'round' }, paint: { 'line-color': C.route, 'line-opacity': ['case', ['==', ['get', 'sel'], 1], 1, 0.7], 'line-width': ['+', 1.25, ['*', 6, ['get', 'w']]] } });
  map.addLayer({ id: 'hubs', type: 'circle', source: 'hubs', paint: { 'circle-radius': ['case', ['==', ['get', 'code'], 'PACE'], 5, 3.5], 'circle-color': ['case', ['==', ['get', 'code'], 'PACE'], '#ffffff', C.route], 'circle-stroke-color': ['case', ['==', ['get', 'code'], 'PACE'], C.route, '#ffffff'], 'circle-stroke-width': 2 } });
}

interface Lbl { el: HTMLElement; minZoom: number; marker: maplibregl.Marker }

function el(cls: string, html: string) { const d = document.createElement('div'); d.className = cls; d.innerHTML = html; return d; }

export function WestMap(p: MapProps) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const ready = useRef(false);
  const regionEls = useRef<Partial<Record<Core, HTMLElement>>>({});
  const arcEls = useRef<maplibregl.Marker[]>([]);
  const labels = useRef<Lbl[]>([]);
  const [hover, setHover] = useState<{ code: string; name: string; x: number; y: number } | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const props = useRef(p);
  props.current = p;
  const geo = useRef<Geo | null>(null);

  const fit = (animate: boolean) => {
    const m = map.current; if (!m) return;
    const q = props.current;
    m.fitBounds(q.bounds ?? WEST, { padding: q.padding ?? { top: 16, bottom: 16, left: 16, right: 16 }, duration: animate ? 400 : 0 });
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
    m.touchZoomRotate.disableRotation();
    m.keyboard.disableRotation();
    map.current = m;
    const onZoom = () => {
      const z = m.getZoom();
      for (const l of labels.current) l.el.style.display = z >= l.minZoom ? '' : 'none';
    };
    m.on('load', async () => {
      try {
        const g = await loadGeo();
        if (!alive) return;
        geo.current = g;
        addLayers(m, g, props.current);
        ready.current = true;
        // labels: state names, cities, lakes (decluttered by zoom), and the four core regions
        const add = (node: HTMLElement, ll: [number, number], minZoom: number, anchor: maplibregl.PositionAnchor = 'center', offset: [number, number] = [0, 0]) => {
          const marker = new maplibregl.Marker({ element: node, anchor, offset }).setLngLat(ll).addTo(m);
          labels.current.push({ el: node, minZoom, marker });
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
            const mz = pr.scalerank <= 2 ? 3 : pr.scalerank <= 3 ? 4.6 : pr.scalerank <= 4 ? 5.4 : 6.2;
            add(el('mk-label mk-city', `<i></i><span>${pr.name}</span>`), c, mz, 'left', [-3, 0]);
          }
          for (const f of g.lakes.features) {
            const pr = f.properties as { name: string };
            if (pr.name !== 'Great Salt Lake') continue;
            add(el('mk-label mk-lake', 'Great Salt Lake'), [-112.55, 41.12], 5.2);
          }
        }
        for (const c of CORE) {
          const node = document.createElement('div');
          node.className = 'mk-label';
          regionEls.current[c] = node;
          new maplibregl.Marker({ element: node, anchor: 'center', offset: LABEL_OFFSET[c] }).setLngLat(LABEL_AT[c]).addTo(m);
        }
        paintLabels();
        paintArcs();
        onZoom();
        setLoading(false);
      } catch (e) { setFailed(String(e)); setLoading(false); }
    });
    m.on('zoom', onZoom);
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
    const ro = new ResizeObserver(() => { m.resize(); if (props.current.variant === 'inset') fit(false); });
    ro.observe(box.current!);
    return () => { alive = false; ro.disconnect(); m.remove(); map.current = null; ready.current = false; labels.current = []; };
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
      node.innerHTML = `<div class="mk-region"><span class="sw" style="background:${swFill};color:${onFill(swFill)}">${iconSvg(icon)}</span><div><div class="t-12 fw-600" style="color:${C.ink}">${REGION[c].name} · ${c}</div><div class="t-12" style="color:${C.ink2}"><b class="fw-600" style="color:${C.ink}">${v == null ? '–' : Math.round(v)}</b> <span class="t-11" style="color:${C.ink3}">g/kWh · ${q.hourLabel}</span></div></div></div>`;
    }
  }
  function paintArcs() {
    const m = map.current; if (!m || !ready.current) return;
    const q = props.current;
    (m.getSource('arcs') as GeoJSONSource).setData(arcsFC(q.arcs));
    for (const mk of arcEls.current) mk.remove();
    arcEls.current = [];
    for (const a of q.arcs) {
      if (!a.label) continue;
      const line = arcLine(HUB.PACE, HUB[a.to], BEND[a.to]);
      const mid = line[Math.round(line.length * 0.55)];
      arcEls.current.push(new maplibregl.Marker({ element: el('mk-label mk-arc', a.label), anchor: 'center' }).setLngLat(mid).addTo(m));
    }
  }

  // data changes: recolour polygons, relabel, redraw arcs
  useEffect(() => {
    const m = map.current; if (!m || !ready.current) return;
    m.setPaintProperty('ba-fill', 'fill-color', colorExpr(p.ci, p.context));
    m.setPaintProperty('ba-fill', 'fill-opacity', opacityExpr(p.ci, p.context, p.variant));
    paintLabels();
    paintArcs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.ci, p.context, p.arcs, p.hourLabel, p.ring]);

  useEffect(() => {
    const m = map.current; if (!m) return;
    const on = p.interactive;
    for (const h of [m.scrollZoom, m.dragPan, m.doubleClickZoom, m.touchZoomRotate, m.keyboard, m.boxZoom]) (on ? h.enable() : h.disable());
  }, [p.interactive]);

  useEffect(() => { if (map.current && ready.current) fit(true); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.padding?.left, p.padding?.right, p.padding?.top, p.padding?.bottom]);

  const hv = hover && (hover.code in p.ci ? { v: p.ci[hover.code], ev: 'observed' as const, note: `typical day, ${p.hourLabel}` } : hover.code in p.context ? { v: p.context[hover.code], ev: 'modeled' as const, note: 'year mean, generation fuel mix' } : null);

  return (
    <div id={p.id} className="absolute inset-0" aria-label={p.variant === 'main' ? 'Map of the western US balancing authorities, coloured by carbon intensity' : 'Inset map: Utah and the three destinations'} role="region">
      <div ref={box} style={{ position: 'absolute', inset: 0 }} />
      {loading && <div className="absolute inset-0 grid place-items-center"><span className="t-12 ink-3">Drawing the West…</span></div>}
      {failed && <div className="absolute inset-0 grid place-items-center"><div className="panel t-13" style={{ maxWidth: 360 }}><b className="fw-600">The map layers did not load.</b><div className="t-12 ink-2" style={{ marginTop: 4 }}>{failed}. Run <code>npm run data</code> on a machine with the data directory, then rebuild. The numbers in the panels do not depend on the map.</div></div></div>}
      {hover && p.interactive && (
        <div className="tip" style={{ left: hover.x + 16, top: hover.y - 8, position: 'absolute' }}>
          <div className="fw-600">{hover.name} <span className="ink-3 fw-500">· {hover.code}</span></div>
          {hv ? (<div><b className="fw-600">{hv.v == null ? '–' : Math.round(hv.v)}</b> <span className="ink-3">g/kWh · {hv.note}</span> <Ev e={hv.ev} /></div>) : <div className="ink-3">No carbon series for this region in this build</div>}
        </div>
      )}
      {p.variant === 'main' && p.interactive && (
        <div className="absolute flex flex-col gap-2" style={{ right: (p.padding?.right ?? 16) - 48, bottom: (p.padding?.bottom ?? 16) + 0 }}>
          <button className="iconbtn" aria-label="Zoom in" onClick={() => map.current?.zoomIn({ duration: 200 })}><Icon name="plus" /></button>
          <button className="iconbtn" aria-label="Zoom out" onClick={() => map.current?.zoomOut({ duration: 200 })}><Icon name="minus" /></button>
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
