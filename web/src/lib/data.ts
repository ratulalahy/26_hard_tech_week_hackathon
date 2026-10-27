// Results loading and selectors. Every number the UI shows comes from results/*.json (copied to
// public/data/results by scripts/copy-data.mjs) and keeps its §11 envelope, so its evidence label
// travels with it. A null value is shown with its reason, never as 0.
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
}

const base = import.meta.env.BASE_URL; // './' (relative deployment base)
async function get(name: string): Promise<Json> {
  const url = `${base}data/results/${name}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`);
  return r.json();
}
export async function loadResults(): Promise<Results> {
  const [metrics, manifest, forecast, jobs, grid, workload] = await Promise.all([
    get('metrics.json'), get('manifest.json'), get('forecast-replay.json'), get('job-replay.json'), get('grid-profile.json'), get('workload-profile.json'),
  ]);
  return { metrics, manifest, forecast, jobs, grid, workload };
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
export const pnote = (m: Json, p: string): string => m.policies?.[p]?.note ?? '';
export const POLICY_ORDER = ['U', 'G', 'S', 'K', 'W', 'L', 'H', 'W_time', 'L_time'];

/** Plain-language limitations (lead ruling R7). Matched on the manifest text; the verbatim text stays behind "Source text". */
const PLAIN: [RegExp, string][] = [
  [/^Publication-lagged replay/i, "Forecasts were replayed on today's revised copy of EIA's historical data, with publication delays applied. The exact data available on each past day were not reconstructed, and the delay rules are our assumptions."],
  [/imports from Canada and Mexico/i, 'Electricity imported from Canada and Mexico is counted at the US average carbon rate, as EIA does.'],
  [/emission factors may be a provisional/i, "EIA's emission factors for 2025–26 may still be provisional."],
  [/^Baseline bookings/i, 'Every job holds an advance reservation at its home site, built from the baseline run. This is a planning scenario, not a replay of a real online scheduler.'],
  [/^Missing truth hours/i, 'Hours with no published carbon value are filled by rules fixed in advance, and those gaps are treated as known ahead of time.'],
  [/^Zero deadline misses/i, 'No job misses its deadline because each keeps its home reservation as a fallback. That is a property of the scenario, not evidence of how a real system would perform.'],
  [/effect on realized savings is not signed/i, 'We have not measured whether those reservations raise or lower the savings.'],
  [/shadow-U sensitivity/i, 'What is possible without advance reservations has not been tested yet.'],
  [/workload phase 0/i, 'The workload was replayed from one starting offset; two other offsets are still to run.'],
];
export const stripCodes = (s: string) => s.replace(/\s*\((?:F\d[\d.]*|§\s*\d[\d.]*)(?:[,;][^)]*)?\)/g, '').replace(/§\s*\d[\d.]*/g, '').replace(/\bF\d+(?:\.\d+)?\b/g, '').replace(/\s{2,}/g, ' ').trim();
export const plainLimitation = (s: string) => PLAIN.find(([re]) => re.test(s))?.[1] ?? stripCodes(s);

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

/** One BA's 24-hour tier-1 consumed CI for a month (America/Denver hours), observed. */
export function dayCurve(grid: Json, ba: Core, month: string): (number | null)[] {
  const i = grid.months.indexOf(month);
  return grid.ci.by_ba[ba].month_hour.value[i];
}
export const curveEnv = (grid: Json, ba: Core): Env<(number | null)[][]> => grid.ci.by_ba[ba].month_hour;
export const yearMean = (grid: Json, ba: Core): Env => grid.ci.by_ba[ba].year_mean;

export const asNum = (e: Env | undefined | null): number | null => (e && typeof e.value === 'number' ? e.value : null);
