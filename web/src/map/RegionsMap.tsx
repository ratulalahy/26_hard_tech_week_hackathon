// The ten-region overview map (T18): the same MapLibre setup as WestMap (local GeoJSON handed over as
// objects; no tile, glyph or sprite server) on a lower-48 extent. Each overview region wears its
// year-mean carbon intensity on the diverging scale; labels are HTML markers, the table is the
// accessible equivalent of every value.
import * as maplibregl from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import type { FeatureCollection } from 'geojson';
import type { Map as MLMap, MapLayerMouseEvent } from 'maplibre-gl';
import { useEffect, useRef, useState } from 'react';
import { C, ci2c } from '../lib/color';
import { Ev } from '../components/ui';

maplibregl.setWorkerUrl(new URL(workerUrl, location.href).href);

const base = import.meta.env.BASE_URL;
const j = (f: string): Promise<FeatureCollection> => fetch(`${base}data/geo/${f}`).then((r) => { if (!r.ok) throw new Error(`geo/${f}: HTTP ${r.status}`); return r.json(); });
let cache: Promise<{ ba: FeatureCollection; pts: FeatureCollection; states: FeatureCollection; countries: FeatureCollection }> | null = null;
const loadUs = () => (cache ??= Promise.all([j('ba_overview.geojson'), j('ba_overview_points.geojson'), j('states_us.geojson'), j('countries.geojson')])
  .then(([ba, pts, states, countries]) => ({ ba, pts, states, countries })));

const US: [[number, number], [number, number]] = [[-124.8, 25.2], [-69.5, 49.4]];

export interface RegionsMapProps {
  /** BA → year-mean consumed CO2 intensity, g/kWh (EIA estimate, modeled) */
  ci: Record<string, number | null>;
  names: Record<string, string>;
  selected: string | null;
  onPick: (code: string) => void;
}

function fillExpr(ci: Record<string, number | null>) {
  const m: (string)[] = [];
  for (const [k, v] of Object.entries(ci)) m.push(k, v == null ? '#ffffff' : ci2c(v));
  return ['match', ['get', 'code'], ...m, '#ffffff'] as unknown as maplibregl.ExpressionSpecification;
}

export function RegionsMap(p: RegionsMapProps) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const ready = useRef(false);
  const marks = useRef<Record<string, HTMLElement>>({});
  const props = useRef(p);
  props.current = p;
  const [hover, setHover] = useState<{ code: string; x: number; y: number } | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const m = new maplibregl.Map({
      container: box.current!,
      style: { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#f1e9df' } }] },
      bounds: US, fitBoundsOptions: { padding: 12 }, attributionControl: false, interactive: true, dragPan: false, scrollZoom: false, boxZoom: false,
      doubleClickZoom: false, touchZoomRotate: false, keyboard: false, dragRotate: false, touchPitch: false,
      renderWorldCopies: false, fadeDuration: 0,
    });
    map.current = m;
    m.on('load', async () => {
      try {
        const g = await loadUs();
        if (!alive) return;
        m.addSource('countries', { type: 'geojson', data: g.countries });
        m.addSource('states', { type: 'geojson', data: g.states });
        m.addSource('ba', { type: 'geojson', data: g.ba, promoteId: 'code' });
        m.addLayer({ id: 'land-other', type: 'fill', source: 'countries', filter: ['!=', ['get', 'adm0_a3'], 'USA'], paint: { 'fill-color': '#f6eee5', 'fill-antialias': false } });
        m.addLayer({ id: 'land-us', type: 'fill', source: 'states', paint: { 'fill-color': C.sky0 } });
        m.addLayer({ id: 'ba-fill', type: 'fill', source: 'ba', paint: { 'fill-color': fillExpr(props.current.ci), 'fill-opacity': 0.9 } });
        m.addLayer({ id: 'state-lines', type: 'line', source: 'states', paint: { 'line-color': C.ink3, 'line-opacity': 0.35, 'line-width': 0.6, 'line-dasharray': [3, 2] } });
        m.addLayer({ id: 'ba-casing', type: 'line', source: 'ba', paint: { 'line-color': '#ffffff', 'line-opacity': 0.9, 'line-width': 2.5 } });
        m.addLayer({ id: 'ba-line', type: 'line', source: 'ba', paint: {
          'line-color': ['case', ['==', ['get', 'code'], props.current.selected ?? ''], C.route, C.ink],
          'line-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 0.95, 0.55],
          'line-width': ['case', ['==', ['get', 'code'], props.current.selected ?? ''], 2.5, 1] } });
        for (const f of g.pts.features) {
          const pr = f.properties as { code: string; label_lon: number; label_lat: number };
          const node = document.createElement('div');
          node.className = 'mk-label mk-ov';
          marks.current[pr.code] = node;
          new maplibregl.Marker({ element: node, anchor: 'center' }).setLngLat([pr.label_lon, pr.label_lat]).addTo(m);
        }
        ready.current = true;
        paint();
        setLoading(false);
      } catch (e) { setFailed(String(e)); setLoading(false); }
    });
    m.on('mousemove', 'ba-fill', (e: MapLayerMouseEvent) => {
      const code = String(e.features?.[0]?.properties?.code ?? '');
      if (!code) return;
      m.getCanvas().style.cursor = 'pointer';
      setHover((h) => {
        if (h && h.code !== code) m.setFeatureState({ source: 'ba', id: h.code }, { hover: false });
        m.setFeatureState({ source: 'ba', id: code }, { hover: true });
        return { code, x: e.point.x, y: e.point.y };
      });
    });
    m.on('mouseleave', 'ba-fill', () => { setHover((h) => { if (h) m.setFeatureState({ source: 'ba', id: h.code }, { hover: false }); return null; }); m.getCanvas().style.cursor = ''; });
    m.on('click', 'ba-fill', (e: MapLayerMouseEvent) => { const code = String(e.features?.[0]?.properties?.code ?? ''); if (code) props.current.onPick(code); });
    const ro = new ResizeObserver(() => { m.resize(); m.fitBounds(US, { padding: 12, duration: 0 }); });
    ro.observe(box.current!);
    return () => { alive = false; ro.disconnect(); m.remove(); map.current = null; ready.current = false; marks.current = {}; };
  }, []);

  function paint() {
    const m = map.current; if (!m || !ready.current) return;
    const q = props.current;
    m.setPaintProperty('ba-fill', 'fill-color', fillExpr(q.ci));
    const sel = q.selected ?? '';
    m.setPaintProperty('ba-line', 'line-color', ['case', ['==', ['get', 'code'], sel], C.route, C.ink]);
    m.setPaintProperty('ba-line', 'line-width', ['case', ['==', ['get', 'code'], sel], 2.5, 1]);
    for (const [code, node] of Object.entries(marks.current)) {
      const v = q.ci[code];
      node.innerHTML = `<span class="fw-600">${code}</span> <span class="ov-v">${v == null ? '–' : Math.round(v)}</span>`;
      node.classList.toggle('sel', code === sel);
    }
  }
  useEffect(() => { paint(); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.ci, p.selected]);

  const hv = hover ? p.ci[hover.code] : null;
  return (
    <div className="absolute inset-0" role="region" aria-label="Map of the ten overview regions, coloured by year-mean carbon intensity; the table below lists every value">
      <div ref={box} style={{ position: 'absolute', inset: 0 }} />
      {loading && <div className="absolute inset-0 grid place-items-center"><span className="t-12 ink-3">Drawing the regions…</span></div>}
      {failed && <div className="absolute inset-0 grid place-items-center"><div className="panel t-13" style={{ maxWidth: 360 }}><b className="fw-600">The map layers did not load.</b><div className="t-12 ink-2" style={{ marginTop: 4 }}>{failed}. Run <code>npm run data</code> on a machine with the data directory, then rebuild. The table does not depend on the map.</div></div></div>}
      {hover && (
        <div className="tip" style={{ left: hover.x + 16, top: hover.y - 8, position: 'absolute' }}>
          <div className="fw-600">{p.names[hover.code] ?? hover.code} <span className="ink-3 fw-500">· {hover.code}</span></div>
          <div><b className="fw-600">{hv == null ? '–' : Math.round(hv)}</b> <span className="ink-3">g/kWh, validation-year mean</span> <Ev e="modeled">modeled · EIA estimate</Ev></div>
        </div>
      )}
    </div>
  );
}
