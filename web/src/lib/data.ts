// Results loading and selectors. Every number the UI shows comes from results/*.json (copied to
// public/data/results by scripts/copy-data.mjs) and keeps its §11 envelope, so its evidence label
// travels with it. A null value is shown with its reason, never as 0.
import { TEST_LINE, VALIDATION_LINE, type EvalWindow } from './copy';

export type Evidence = 'observed' | 'measured' | 'forecast' | 'modeled' | 'assumed' | 'simulated';
export interface Env<T = number> {
  value: T | null;
  unit: string;
  evidence: Evidence;
  provenance_id: string;
  status: 'ok' | 'not_run' | 'not_evaluated' | 'unavailable';
  reason: string | null;
}
/* eslint-disable @typescript-eslint/no-explicit-any */
export type Json = any;

export interface Results {
  metrics: Json;
  manifest: Json;
  forecast: Json;
  jobs: Json;
  grid: Json;
  workload: Json;
  /** results/extensions.json (Stage 3 T10, D-058); null if the file is absent. */
  ext: Json | null;
  /** results/storage.json (Stage 3 T10b, D-061; illustrative); null if the file is absent. */
  storage: Json | null;
  /** results/scenario-flows.json (Stage 3 T15, D-064); null if the file is absent. */
  flows: Json | null;
  /** results/flexibility-budget.json (Stage 3 T15, D-064); null if the file is absent. */
  budget: Json | null;
  /** results/water.json (Stage 3 T14, D-063; illustrative); null if the file is absent. */
  water: Json | null;
  /** results/case-days.json (Stage 3 T16, D-066; illustrative); null if the file is absent. */
  caseDays: Json | null;
}

const base = import.meta.env?.BASE_URL ?? './'; // './' (relative deployment base)
/** results/*.json (validation) or results/test/*.json (the sealed test year, once it is run). */
const dir = (w: EvalWindow) => (w === 'test' ? 'data/results/test/' : 'data/results/');
async function get(name: string, w: EvalWindow = 'validation'): Promise<Json> {
  const url = `${base}${dir(w)}${name}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`);
  return r.json();
}
export async function loadResults(w: EvalWindow = 'validation'): Promise<Results> {
  const v = w === 'validation';  // the D-058 extensions, the T10b storage piece, the T15 scenario flows and budget, the T14 water piece and the T16 toughest days are validation-only
  const [metrics, manifest, forecast, jobs, grid, workload, ext, storage, flows, budget, water, caseDays] = await Promise.all([
    get('metrics.json', w), get('manifest.json', w), get('forecast-replay.json', w), get('job-replay.json', w), get('grid-profile.json', w), get('workload-profile.json', w),
    v ? get('extensions.json').catch(() => null) : Promise.resolve(null),
    v ? get('storage.json').catch(() => null) : Promise.resolve(null),
    v ? get('scenario-flows.json').catch(() => null) : Promise.resolve(null),
    v ? get('flexibility-budget.json').catch(() => null) : Promise.resolve(null),
    v ? get('water.json').catch(() => null) : Promise.resolve(null),
    v ? get('case-days.json').catch(() => null) : Promise.resolve(null),
  ]);
  if (w === 'test' && (metrics.window !== 'test' || manifest.window !== 'test')) throw new Error('results/test/ does not hold test-window results');
  return { metrics, manifest, forecast, jobs, grid, workload, ext, storage, flows, budget, water, caseDays };
}
/** What copy-data found: the test option is enabled only when results/test/manifest.json exists. */
export interface ResultsIndex { files: string[]; test?: { available: boolean; files: string[]; frozen_at: string | null } }
export async function loadIndex(): Promise<ResultsIndex> {
  try { return await get('index.json'); } catch { return { files: [] }; }
}

export const CORE = ['PACE', 'BPAT', 'CISO', 'NEVP'] as const;
export type Core = (typeof CORE)[number];
export const DESTS = ['BPAT', 'CISO', 'NEVP'] as const;
export type Dest = (typeof DESTS)[number];
export const REGION: Record<Core, { name: string; full: string }> = {
  PACE: { name: 'Utah', full: 'PacifiCorp East' },
  BPAT: { name: 'Northwest hydro', full: 'Bonneville Power Administration' },
  CISO: { name: 'California', full: 'California ISO' },
  NEVP: { name: 'Nevada', full: 'NV Energy' },
};
/** One name per policy, everywhere (lead ruling R1). Roles come from metrics.policies[p].note. */
export const NAME: Record<string, string> = {
  U: 'U local (stay in Utah)',
  G: 'G earliest-finish (carbon-blind)',
  S: 'S static clean-region ranking',
  K: 'K climatology (seasonal average)',
  W: 'W weekly profile',
  L: 'L learned model',
  H: 'H hindsight (diagnostic)',
  W_time: 'W wait-only',
  L_time: 'L wait-only',
};
export const pname = (p: string) => NAME[p] ?? p;

/** The F12.5 qualifiers, in the one wording every headline view uses (control room, cockpit, story 5). */
export const FRAME_LINE = 'Replay of a measured GPU-cluster trace mapped onto Utah · deadlines relative to the baseline, met by construction · exact declared runtimes; runtime uncertainty untested.';
export const DEADLINES_MET = 'deadlines met by construction (baseline bookings)';
/** The deadline rule (A4), as the drawer and the cockpit state it. */
export const DEADLINE_RULE = "A job's deadline is the later of (a) its run-now finish plus its allowed delay and (b) its finish in the stay-in-Utah baseline (baseline-relative).";

/** The month the weekday-load profile covers, read from the data (grid-profile `pace_july_weekday.month`, "2025-07"). */
export function loadMonth(grid: Json): { short: string; long: string } {
  const ym: string | undefined = grid.pace_july_weekday?.month;
  if (!ym) return { short: 'typical', long: 'typical' };
  const [y, mo] = ym.split('-').map(Number);
  const name = new Intl.DateTimeFormat('en-US', { month: 'long', timeZone: 'UTC' }).format(new Date(Date.UTC(y, mo - 1, 15)));
  return { short: name, long: `${name} ${y}` };
}
/** Plain-language rule of each policy, for hover titles (N9). */
const ROLE: Record<string, string> = {
  U: 'Runs every job at its Utah reservation, first come, first served. The baseline.',
  G: 'Runs each job wherever it would finish earliest. Ignores carbon.',
  S: 'Sends work to the cleanest site by a fixed ranking from past years.',
  K: 'Searches for the cleanest time and site, using a seasonal-average forecast of carbon.',
  W: 'Searches for the cleanest time and site, using a weekly-profile forecast of carbon.',
  L: 'Searches for the cleanest time and site, using the learned forecast model.',
  H: 'The same search with perfect hindsight of actual carbon. A check, never a contender.',
  W_time: 'Like W weekly profile, but may only wait in Utah, never move.',
  L_time: 'Like L learned model, but may only wait in Utah, never move.',
};
export const pnote = (_m: Json, p: string): string => ROLE[p] ?? '';
export const POLICY_ORDER = ['U', 'G', 'S', 'K', 'W', 'L', 'H', 'W_time', 'L_time'];

/** Plain-language limitations (lead ruling R7). Matched on the manifest text; the verbatim text stays behind "Source text". */
const PLAIN: [RegExp, string][] = [
  [/^Publication-lagged replay/i, "Forecasts were replayed on today's revised copy of EIA's historical data, with publication delays applied. The exact data available on each past day were not reconstructed, and the delay rules are our assumptions. The two-hour delay assumed for EIA's adjusted demand has not been checked against EIA's own timing."],
  [/imports from Canada and Mexico/i, 'Electricity imported from Canada and Mexico is counted at the US average carbon rate, as EIA does.'],
  [/emission factors may be a provisional/i, "EIA's emission factors for 2025–26 may still be provisional."],
  [/^Baseline bookings/i, 'Every job holds an advance reservation at its home site, built from the baseline run. This is a planning scenario, not a replay of a real online scheduler.'],
  [/^Missing truth hours/i, 'Hours with no published carbon value are filled by rules fixed in advance, and those gaps are treated as known ahead of time.'],
  [/^Zero deadline misses/i, 'No job misses its deadline because each keeps its home reservation as a fallback. That is a property of the scenario, not evidence of how a real system would perform.'],
  [/effect on realized savings is not signed/i, 'We have not measured whether those reservations raise or lower the savings.'],
  [/shadow-U sensitivity/i, 'What is possible without advance reservations has not been tested yet.'],
  [/^Validation results are development evidence/i, VALIDATION_LINE],
  [/phases 49 and 98 are workload-alignment sensitivities/i, 'The headline uses one workload starting offset. Two other offsets were run as checks and are reported beside it, never pooled with it.'],
  [/^Test-year results: the sealed test year was opened once/i, TEST_LINE],
  [/workload phase 0/i, 'The workload was replayed from one starting offset; two other offsets are still to run.'],
];
export const stripCodes = (s: string) => s.replace(/\s*\((?:F\d[\d.]*|§\s*\d[\d.]*)(?:[,;][^)]*)?\)/g, '').replace(/§\s*\d[\d.]*/g, '').replace(/\bF\d+(?:\.\d+)?\b/g, '').replace(/\s{2,}/g, ' ').trim();
export const plainLimitation = (s: string) => PLAIN.find(([re]) => re.test(s))?.[1] ?? stripCodes(s);
/** The plain limitations list; the validation-year (or test-year) line is stated once, in its own place, so it is left out here. */
export const plainLimitations = (ls: string[]) => ls.map(plainLimitation).filter((t) => t !== VALIDATION_LINE && t !== TEST_LINE);

export interface Contrast {
  candidate: string;
  reference: string;
  saving: Env;
  saving_ci95: Env<[number, number]>;
  diff_kg: Env;
  diff_kg_ci95: Env<[number, number]>;
  n_weeks: Env;
}
export function contrast(m: Json, cand: string, ref = 'U', b = '4'): Contrast | null {
  const c = m.contrasts.find((x: Json) => x.candidate === cand && x.reference === ref);
  if (!c) return null;
  const k = c.blocks[b];
  return { candidate: cand, reference: ref, saving: k.saving, saving_ci95: k.saving_ci95, diff_kg: k.diff_kg, diff_kg_ci95: k.diff_kg_ci95, n_weeks: k.n_weeks };
}

/** The registered headline (validation): the four placement policies and the two time-only runs vs U, b = 4. */
export function headline(m: Json) {
  const group = (ps: string[]) => {
    const cs = ps.map((p) => contrast(m, p)!).filter(Boolean);
    const pts = cs.map((c) => c.saving.value as number);
    const los = cs.map((c) => (c.saving_ci95.value as [number, number])[0]);
    const his = cs.map((c) => (c.saving_ci95.value as [number, number])[1]);
    return { policies: ps, contrasts: cs, lo: Math.min(...pts), hi: Math.max(...pts), ciLo: Math.min(...los), ciHi: Math.max(...his), evidence: cs[0].saving.evidence };
  };
  return { placement: group(['S', 'K', 'W', 'L']), timing: group(['W_time', 'L_time']), nWeeks: contrast(m, 'S')!.n_weeks };
}

/** One policy's own registered estimate and interval vs U (F10: the headline is never a span across policies). */
export function own(m: Json, p = 'S') {
  const c = contrast(m, p);
  if (!c || c.saving.value == null) return null;
  const [lo, hi] = c.saving_ci95.value as [number, number];
  return { v: c.saving.value as number, lo, hi, evidence: c.saving.evidence };
}
/** "about 22.5": a saving rounded to the nearest half percent, for spoken-style headlines (F06). */
export const aboutPct = (x: number) => String(Math.round(x * 200) / 2);
/** The wait-only runs as one phrase: "under 1%" when both are, else their range (F06). */
export function waitPhrase(m: Json) {
  const xs = ['W_time', 'L_time'].map((p) => contrast(m, p)?.saving.value).filter((v): v is number => typeof v === 'number');
  if (!xs.length) return 'not run';
  if (Math.min(...xs) >= 0 && Math.max(...xs) < 0.01) return 'under 1%';
  const f = (x: number) => (x * 100).toFixed(1).replace('-', '−');
  return Math.min(...xs).toFixed(3) === Math.max(...xs).toFixed(3) ? `${f(xs[0])}%` : `${f(Math.min(...xs))}–${f(Math.max(...xs))}%`;
}

/** One BA's 24-hour tier-1 consumed CI for a month (America/Denver hours): EIA's estimate, modeled. */
export function dayCurve(grid: Json, ba: Core, month: string): (number | null)[] {
  const i = grid.months.indexOf(month);
  return grid.ci.by_ba[ba].month_hour.value[i];
}
export const curveEnv = (grid: Json, ba: Core): Env<(number | null)[][]> => grid.ci.by_ba[ba].month_hour;
export const yearMean = (grid: Json, ba: Core): Env => grid.ci.by_ba[ba].year_mean;

export const asNum = (e: Env | undefined | null): number | null => (e && typeof e.value === 'number' ? e.value : null);
