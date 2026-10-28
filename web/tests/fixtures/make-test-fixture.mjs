// A SYNTHETIC results/test fixture for the dashboard's test-year state (Stage 3 T11, B6).
//   node tests/fixtures/make-test-fixture.mjs
// It reads the committed validation results (public/data/results/*.json) and writes
// tests/fixtures/results-test/*.json in the test-window schema the lab's `run_slice --window test` exports:
// `window: "test"`, a `freeze` record, the test-year limitation and wording, and every date moved forward
// 365 days (Nov 2024 – Oct 2025 becomes Nov 2025 – Oct 2026). Every placement and wait-only saving is
// halved, so a test asserting on test numbers cannot pass on validation numbers. These are NOT test
// results: the manifest says so in `fixture`, and copy-data refuses to copy a manifest that carries it.
// The fixture is served to the browser by tests/offline.spec.ts through a route; it is never put under public/.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, '..', '..', 'public', 'data', 'results');
const out = join(here, 'results-test');
const FILES = ['manifest.json', 'metrics.json', 'forecast-replay.json', 'job-replay.json', 'grid-profile.json', 'workload-profile.json'];
const DAY = 86400000;
export const FIXTURE_NOTE = 'SYNTHETIC test-window fixture (web/tests/fixtures): numbers derived from the committed results, savings halved; never real test results';

// the lab's test-window texts (lab/src/gridpilot/results.py LIMIT_TEST, lab/scripts/run_slice.py)
const LIMIT_TEST = 'Test-year results: the sealed test year was opened once, through the logged entry point, after the model and policy configuration was frozen at a recorded commit; nothing was selected or refitted on it. They cover the days up to the snapshot\'s availability cutoff, not a full twelve months.';
const TEXT = [
  [/^Validation results are development evidence.*$/s, LIMIT_TEST],
  [/^validation results; /, 'test-year results (sealed window, opened once after the freeze); '],
  [/^validation \(selection\) results; .*$/s, 'sealed test-window results [2025-11-01, F_test), opened once through the logged entry point after the configuration freeze; every read is in results/test_reads.jsonl'],
  [/^make slice {2}# cd lab && uv run python scripts\/run_slice.py --window validation$/, 'cd lab && uv run python scripts/run_slice.py --window test  # once, after the freeze; refuses otherwise'],
  [/^Validation: /, 'Test year: '],
  [/among validation flexible jobs/, "among the test cohort's flexible jobs"],
  [/^validation year \(eval_start to F\); the test year is sealed$/, 'test'],
  [/never read by this run$/, 'opened by this run through gridpilot.seal.sealed_read, up to F_test'],
  [/^validation$/, 'test'],
];

const shiftDate = (ymd) => new Date(Date.parse(ymd + 'T00:00:00Z') + 365 * DAY).toISOString().slice(0, 10);
function str(s) {
  for (const [re, to] of TEXT) s = s.replace(re, to);
  if (/^\d{4}-\d{2}$/.test(s)) return `${Number(s.slice(0, 4)) + 1}${s.slice(4)}`; // a month label
  return s.replace(/(?<!\d)(\d{4}-\d{2}-\d{2})(?=$|[T ]|[^\d])/g, (m) => shiftDate(m));
}
function walk(x) {
  if (Array.isArray(x)) return x.map(walk);
  if (x && typeof x === 'object') return Object.fromEntries(Object.entries(x).map(([k, v]) => [str(k), walk(v)]));
  return typeof x === 'string' ? str(x) : x;
}
const half = (e) => { if (e && e.value != null) e.value = Array.isArray(e.value) ? e.value.map((v) => v / 2) : e.value / 2; };

mkdirSync(out, { recursive: true });
const art = Object.fromEntries(FILES.map((f) => [f, walk(JSON.parse(readFileSync(join(src, f), 'utf8')))]));
const man = art['manifest.json'];
man.window = 'test';
man.fixture = FIXTURE_NOTE;
man.freeze = {
  freeze_commit: '0'.repeat(40), freeze_sha256: '0'.repeat(64), tag: 'config-freeze', wallclock_frozen_at: '2026-10-27T23:00:00Z',
  deployed_policy: 'W', test_F: man.split.F, validation_run: { run_id: man.run_id, metrics_canonical_sha256: '0'.repeat(64) },
  rerun_reason: null, read_log: 'results/test_reads.jsonl', session: 'fixture', code_commit: '0'.repeat(40),
};
const met = art['metrics.json'];
for (const c of met.contrasts) if (c.reference === 'U') for (const b of Object.values(c.blocks)) { half(b.saving); half(b.saving_ci95); half(b.diff_kg); half(b.diff_kg_ci95); }
// T15 fix r1 M17: each policy's CO2 total follows its halved saving vs U (b = 4), so the totals, the
// differences and the savings agree; contrasts against other references are rebuilt from the totals.
const co2U = met.policies.U.metrics.co2_kg.value;
for (const c of met.contrasts) if (c.reference === 'U' && met.policies[c.candidate]) met.policies[c.candidate].metrics.co2_kg.value = co2U - c.blocks['4'].diff_kg.value;
for (const c of met.contrasts) if (c.reference !== 'U' && met.policies[c.candidate] && met.policies[c.reference]) {
  for (const b of Object.values(c.blocks)) {
    const d = met.policies[c.reference].metrics.co2_kg.value - met.policies[c.candidate].metrics.co2_kg.value;
    const shift = d - b.diff_kg.value;
    b.diff_kg.value = d;
    if (Array.isArray(b.diff_kg_ci95?.value)) b.diff_kg_ci95.value = b.diff_kg_ci95.value.map((v) => v + shift);
    if (b.saving?.value != null) b.saving.value = d / met.policies[c.reference].metrics.co2_kg.value;
  }
}
const fr = art['forecast-replay.json'];
fr.test_mae = fr.selection_mae;
delete fr.selection_mae;
for (const f of ['forecast-replay.json', 'job-replay.json', 'workload-profile.json']) art[f] = { window: 'test', ...art[f] };

for (const f of FILES) {
  const text = JSON.stringify(art[f], null, 1);
  const left = text.replace(/"validation_run"/g, '').match(/[^"]*validation[^"]*/i);
  if (left) throw new Error(`${f}: validation wording left in the test fixture: ${left[0]}`);
  writeFileSync(join(out, f), text + '\n');
  console.log('fixture', f);
}
