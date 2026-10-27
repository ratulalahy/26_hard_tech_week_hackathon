// Inline data, geo layers and the relief ground into one self-contained HTML page.
// Usage: node docs/design/concepts/src/build.mjs docs/design/concepts/index.html
// data.json: validation-year (Nov 2024–Oct 2025, pre-test) aggregates from EIA-930, exported for the mockups.
// geo_extra.json + ground.webp: made by build_geo.py.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
const here = dirname(new URL(import.meta.url).pathname);
const out = process.argv[2];
const tpl = readFileSync(join(here, 'template.html'), 'utf8');
const data = JSON.parse(readFileSync(join(here, 'data.json'), 'utf8'));
const geo = JSON.parse(readFileSync(join(here, 'geo_extra.json'), 'utf8'));
const ground = 'data:image/webp;base64,' + readFileSync(join(here, 'ground.webp')).toString('base64');
const html = tpl
  .replace('__DATA__', () => JSON.stringify(data))
  .replace('__GEO__', () => JSON.stringify({ cities: geo.cities, anchors: geo.anchors }))
  .replace('__GROUND__', () => ground);
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, html);
console.log('wrote', out, (html.length / 1024).toFixed(0), 'KB');
