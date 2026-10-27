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
}

const base = import.meta.env.BASE_URL; // './' (relative deployment base)
async function get(name: string): Promise<Json> {
  const url = `${base}data/results/${name}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`);
  return r.json();
}
export async function loadResults(): Promise<Results> {
  const [metrics, manifest, forecast, jobs, grid] = await Promise.all([
    get('metrics.json'), get('manifest.json'), get('forecast-replay.json'), get('job-replay.json'), get('grid-profile.json'),
  ]);
  return { metrics, manifest, forecast, jobs, grid };
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
export const POLICY: Record<string, { name: string; role: string }> = {
  U: { name: 'U', role: 'Run local: every job at its home-site booking (the baseline)' },
  G: { name: 'G', role: 'Greedy lowest current carbon' },
  S: { name: 'S', role: 'Static clean-region priority (training-year mean)' },
  K: { name: 'K', role: 'Carbon search on a persistence forecast' },
  W: { name: 'W', role: 'Carbon search on a weekly-profile forecast' },
  L: { name: 'L', role: 'Carbon search on the learned forecast' },
  H: { name: 'H', role: 'Hindsight diagnostic (realised truth; not a contender)' },
  W_time: { name: 'W time-only', role: 'W allowed to wait, not move (destination capacity 0)' },
  L_time: { name: 'L time-only', role: 'L allowed to wait, not move (destination capacity 0)' },
};
export const POLICY_ORDER = ['U', 'G', 'S', 'K', 'W', 'L', 'H', 'W_time', 'L_time'];

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
