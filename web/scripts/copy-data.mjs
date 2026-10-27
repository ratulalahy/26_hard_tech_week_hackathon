// Copy the dashboard's inputs into web/public/data/ (committed, so a fresh clone builds with no data/ dir).
//   node scripts/copy-data.mjs        (npm run data)
// 1. results/*.json (Task 7 run + grid-profile.json) -> public/data/results/   (copied byte for byte)
//    results/test/*.json (the sealed test year, once T13 has run it) -> public/data/results/test/, separately.
//    index.json records both; the dashboard enables its test option only when results/test/manifest.json
//    exists. A stale public/data/results/test/ is removed when results/test/ has no completed run, and the
//    synthetic fixture in web/tests/fixtures is never copied here.
// 2. the local map layers from $GRIDPILOT_DATA_DIR/processed/geo -> public/data/geo/, clipped to the
//    western US view box and rounded to 3 decimals (about 100 m) to keep them small. Natural Earth
//    (public domain) and Electricity Maps BA geometry (AGPL-3.0) attributions are written next to them.
// Validation results only: this script never reads the sealed test window (it copies files).
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
// COPY_DATA_REPO points the copy at another checkout (web/tests/copy-data.spec.ts uses a temp one)
const repo = process.env.COPY_DATA_REPO ? resolve(process.env.COPY_DATA_REPO) : resolve(here, '..', '..');
const out = join(repo, 'web', 'public', 'data');
const dataDir = process.env.GRIDPILOT_DATA_DIR ?? join(repo, 'data');
const geo = join(dataDir, 'processed', 'geo');
const BOX = [-130, 27, -97, 52.5]; // lon0, lat0, lon1, lat1: the West plus a margin

const kb = (p) => (statSync(p).size / 1024).toFixed(0) + ' KB';

// ---------------------------------------------------------------- results
mkdirSync(join(out, 'results'), { recursive: true });
const results = readdirSync(join(repo, 'results')).filter((f) => f.endsWith('.json')).sort();
for (const f of results) {
  copyFileSync(join(repo, 'results', f), join(out, 'results', f));
  console.log('results/' + f, kb(join(out, 'results', f)));
}
// the sealed test year: copied on its own, only once a completed test run exists (T11 B6)
const testSrc = join(repo, 'results', 'test'), testOut = join(out, 'results', 'test');
const testDone = existsSync(join(testSrc, 'manifest.json'));
rmSync(testOut, { recursive: true, force: true });
let test = { available: false, files: [], frozen_at: null };
if (testDone) {
  const man = JSON.parse(readFileSync(join(testSrc, 'manifest.json'), 'utf8'));
  if (man.window !== 'test' || man.fixture) throw new Error('results/test/manifest.json is not a real test-window manifest');
  const files = readdirSync(testSrc).filter((f) => f.endsWith('.json')).sort();
  // M8: every artifact must match the sha256 the entry point logged in its last export line
  const logPath = join(repo, 'results', 'test_reads.jsonl');
  const exports = existsSync(logPath)
    ? readFileSync(logPath, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l)).filter((r) => r.event === 'export')
    : [];
  const logged = exports.length ? exports[exports.length - 1].artifacts_sha256 ?? {} : null;
  if (!logged) throw new Error('results/test_reads.jsonl has no export line for results/test/');
  const sha = (f) => createHash('sha256').update(readFileSync(join(testSrc, f))).digest('hex');
  const bad = [...files.filter((f) => logged[f] !== sha(f)), ...Object.keys(logged).filter((f) => !files.includes(f))];
  if (bad.length) throw new Error(`results/test/ does not match the logged export: ${bad.join(', ')}`);
  mkdirSync(testOut, { recursive: true });
  for (const f of files) {
    copyFileSync(join(testSrc, f), join(testOut, f));
    console.log('results/test/' + f, kb(join(testOut, f)));
  }
  test = { available: true, files, frozen_at: man.freeze?.wallclock_frozen_at ?? null };
} else {
  console.log('results/test: no completed test run; the dashboard keeps the test year sealed');
}
writeFileSync(join(out, 'results', 'index.json'), JSON.stringify({ files: results, test }, null, 1) + '\n');

// ---------------------------------------------------------------- geo
if (!existsSync(geo)) {
  console.log(`no ${geo}: kept the committed public/data/geo layers`);
  process.exit(0);
}
mkdirSync(join(out, 'geo'), { recursive: true });

const round = (c) => (typeof c[0] === 'number' ? [Math.round(c[0] * 1e3) / 1e3, Math.round(c[1] * 1e3) / 1e3] : c.map(round));
function bbox(coords, b = [Infinity, Infinity, -Infinity, -Infinity]) {
  if (typeof coords[0] === 'number') {
    b[0] = Math.min(b[0], coords[0]); b[1] = Math.min(b[1], coords[1]);
    b[2] = Math.max(b[2], coords[0]); b[3] = Math.max(b[3], coords[1]);
    return b;
  }
  for (const c of coords) bbox(c, b);
  return b;
}
const hits = (b) => !(b[2] < BOX[0] || b[0] > BOX[2] || b[3] < BOX[1] || b[1] > BOX[3]);
// drop consecutive duplicate points created by rounding
function dedupe(coords) {
  if (typeof coords[0] === 'number') return coords;
  if (typeof coords[0][0] === 'number') {
    const o = [coords[0]];
    for (let i = 1; i < coords.length; i++) {
      const p = o[o.length - 1], q = coords[i];
      if (p[0] !== q[0] || p[1] !== q[1]) o.push(q);
    }
    return o;
  }
  return coords.map(dedupe);
}

function layer(src, dst, { keep = () => true, props = null } = {}) {
  const g = JSON.parse(readFileSync(join(geo, src), 'utf8'));
  const features = [];
  for (const f of g.features) {
    if (!f.geometry || !keep(f)) continue;
    if (!hits(bbox(f.geometry.coordinates))) continue;
    const p = props ? Object.fromEntries(props.filter((k) => k in f.properties).map((k) => [k, f.properties[k]])) : f.properties;
    features.push({ type: 'Feature', properties: p, geometry: { type: f.geometry.type, coordinates: dedupe(round(f.geometry.coordinates)) } });
  }
  const path = join(out, 'geo', dst);
  writeFileSync(path, JSON.stringify({ type: 'FeatureCollection', features }));
  console.log('geo/' + dst, features.length, 'features', kb(path));
}

layer('ba_boundaries.geojson', 'ba.geojson', { props: ['code', 'name', 'region', 'approximate'] });
layer('ba_points.geojson', 'ba_points.geojson', { props: ['code', 'name', 'label_lon', 'label_lat'] });
layer('basemap/states.geojson', 'states.geojson', { props: ['name', 'postal', 'label_lon', 'label_lat'] });
layer('basemap/state_lines.geojson', 'state_lines.geojson', { props: [] });
layer('basemap/countries.geojson', 'countries.geojson', { props: ['adm0_a3', 'name'] });
layer('basemap/lakes.geojson', 'lakes.geojson', { props: ['name', 'scalerank'], keep: (f) => f.properties.scalerank <= 6 });
layer('basemap/cities.geojson', 'cities.geojson', { props: ['name', 'adm0_a3', 'adm1name', 'pop_max', 'scalerank', 'labelrank'] });
layer('basemap/roads.geojson', 'roads.geojson', { props: ['level', 'scalerank'], keep: (f) => f.properties.sov_a3 === 'USA' && f.properties.level === 'Interstate' });

copyFileSync(join(geo, 'basemap', 'relief.png'), join(out, 'geo', 'relief.png'));
const relief = JSON.parse(readFileSync(join(geo, 'basemap', 'relief.json'), 'utf8'));
writeFileSync(join(out, 'geo', 'relief.json'), JSON.stringify(relief, null, 1) + '\n');
console.log('geo/relief.png', kb(join(out, 'geo', 'relief.png')));

// attributions, from the committed source manifests
const man = (n) => { const p = join(repo, 'data', 'manifests', n); return existsSync(p) ? JSON.parse(readFileSync(p, 'utf8')) : {}; };
const ba = man('geo_ba_boundaries.json'), ne = man('geo_natural_earth.json');
writeFileSync(join(out, 'geo', 'ATTRIBUTION.txt'), [
  'Map layers bundled with the GridPilot dashboard (offline; clipped and rounded by web/scripts/copy-data.mjs).',
  '',
  'Balancing-authority boundaries (ba.geojson, ba_points.geojson):',
  '  ' + (ba.attribution ?? 'Electricity Maps contributors, AGPL-3.0; BA codes: U.S. EIA Form EIA-930.'),
  '  License: ' + (ba.license ?? 'AGPL-3.0'),
  '',
  'Basemap (states, state lines, countries, lakes, cities, roads, relief):',
  '  ' + (ne.attribution ?? 'Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com.'),
  '  License: ' + (ne.license ?? 'public domain (Natural Earth)'),
  '',
].join('\n'));
console.log('geo/ATTRIBUTION.txt');
