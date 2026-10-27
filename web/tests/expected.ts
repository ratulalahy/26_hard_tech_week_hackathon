// Expected on-screen strings, computed straight from the committed results/*.json (not from the app's code).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const results = join(here, '..', 'public', 'data', 'results');
export const metrics = JSON.parse(readFileSync(join(results, 'metrics.json'), 'utf8'));
/** The synthetic results/test fixture (T11): served by a route in the test-year checks, never under public/. */
export const FIXTURE_DIR = join(here, 'fixtures', 'results-test');
export const fixtureMetrics = JSON.parse(readFileSync(join(FIXTURE_DIR, 'metrics.json'), 'utf8'));
export const fixtureManifest = JSON.parse(readFileSync(join(FIXTURE_DIR, 'manifest.json'), 'utf8'));

type Env = { value: number | number[] | null };
const pct = (x: number) => (x * 100).toFixed(1);

function saving(cand: string, ref = 'U', m = metrics): number {
  const c = m.contrasts.find((x: { candidate: string; reference: string }) => x.candidate === cand && x.reference === ref);
  return (c.blocks['4'].saving as Env).value as number;
}

const place = ['S', 'K', 'W', 'L'].map((p) => saving(p));
const time = ['W_time', 'L_time'].map((p) => saving(p));
// lowest–highest at one decimal; a single value when both ends round the same
const range = (xs: number[]) => (pct(Math.min(...xs)) === pct(Math.max(...xs)) ? `${pct(xs[0])}%` : `${pct(Math.min(...xs))}–${pct(Math.max(...xs))}%`);
/** e.g. "22.4–22.6%": the placement policies' registered savings vs U (b = 4). */
export const placementRange = range(place);
/** e.g. "0.7%": waiting in Utah only (destination capacity 0). */
export const timeOnlyRange = range(time);
/** CO₂ of policy S in tonnes, as the method drawer's table prints it. */
export const sTonnes = (metrics.policies.S.metrics.co2_kg.value / 1000).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
export const uTonnes = (metrics.policies.U.metrics.co2_kg.value / 1000).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** T10: results/extensions.json. S's production-basis saving vs U (b = 4) and its interval, as the
 * extensions table prints it: "25.5% [20.8, 30.1]". */
export const ext = JSON.parse(readFileSync(join(results, 'extensions.json'), 'utf8'));
const cell = (b: { saving: Env; saving_ci95: Env }) => {
  const [lo, hi] = b.saving_ci95.value as number[];
  return `${pct(b.saving.value as number)}% [${pct(lo)}, ${pct(hi)}]`;
};
export const sProduction = cell(ext.repricing.by_policy.S.production.vs_U['4']);
const sav = (b: { vs_U: Record<string, { saving: Env }> }) => b.vs_U['4'].saving.value as number;
const SWL = ['S', 'W', 'L'];
/** Story 6's robustness span: consumption-basis checks only (fix r1 I-2), e.g. "20.2–23.2%". */
const consumption = [
  ...SWL.map((p) => sav(ext.common_support.by_policy[p])),
  ...['phase_49', 'phase_98'].flatMap((n) => SWL.map((p) => sav(ext.phases[n].policies[p]))),
  ...['transfer_120min', 'batch_delay_24h'].flatMap((n) => SWL.map((p) => sav(ext.sensitivities[n].policies[p]))),
];
export const consumptionSpan = range(consumption);
/** The control-room caveat (fix r1 M-14): S–L under 8-GPU mobility, whole percent, e.g. "3–4%". */
const mob = SWL.map((p) => Math.round(100 * sav(ext.sensitivities.mobility_le_8gpus.policies[p])));
export const mobilityAbout = `about ${Math.min(...mob) === Math.max(...mob) ? mob[0] : `${Math.min(...mob)}–${Math.max(...mob)}`}%`;
export const lCommonSupport = cell(ext.common_support.by_policy.L.vs_U['4']);

/** T10b: results/storage.json. The story's storage headline and combined number, as printed. */
export const storage = JSON.parse(readFileSync(join(results, 'storage.json'), 'utf8'));
const sz: number[] = storage.assumptions.sizes_mwh.value;
const E: number = storage.headline.e_mwh.value, iE = sz.indexOf(E);
const cutA: number = storage.cases.U.strategies.A['0.85'].cut_frac.value[iE];
/** e.g. "A 4 MWh, 1 MW battery cuts the Utah cluster's CO₂ by 3.5%" */
export const storageHeadline = `${/^(8|11|18)/.test(String(E)) ? 'An' : 'A'} ${E} MWh, ${E * storage.assumptions.p_over_e.value} MW battery cuts the Utah cluster's CO₂ by ${pct(cutA)}%`;
export const storageCombined = `cuts ${pct(storage.combined.move_and_store_cut_frac.A.value[iE])}%`;
export const storageRushN = String(storage.rush.n_hours.value);
export const storageRushDays = String(storage.rush.n_days.value);
/** two significant figures, as the beat rounds "about X t" */
const flat = -storage.cases.U.strategies.A['0.85'].flat_marginal_cut_t.value[iE];
const p10 = Math.pow(10, Math.floor(Math.log10(Math.abs(flat))) - 1);
export const storageFlatT = (Math.round(flat / p10) * p10).toLocaleString('en-US');

/** The same ranges from the synthetic test fixture (its savings are halved, so they differ from validation). */
export const testPlacementRange = range(['S', 'K', 'W', 'L'].map((p) => saving(p, 'U', fixtureMetrics)));
export const testTimeOnlyRange = range(['W_time', 'L_time'].map((p) => saving(p, 'U', fixtureMetrics)));
/** F10 (T15): S's own saving in the synthetic test fixture, as the hero prints it. */
export const testSOwn = `${pct(saving('S', 'U', fixtureMetrics))}%`;

/** F10: S's own registered estimate and its own interval, e.g. "22.6%" and "18.4–26.8%". */
const sB4 = metrics.contrasts.find((x: { candidate: string; reference: string }) => x.candidate === 'S' && x.reference === 'U').blocks['4'];
export const sOwn = `${pct(sB4.saving.value)}%`;
export const sOwnCI = `${pct(sB4.saving_ci95.value[0])}–${pct(sB4.saving_ci95.value[1])}%`;
/** F06: "about 22.5" (S to the nearest half percent). */
export const sAbout = String(Math.round(sB4.saving.value * 200) / 2);

/** T15: results/scenario-flows.json and results/flexibility-budget.json. */
export const flows = JSON.parse(readFileSync(join(results, 'scenario-flows.json'), 'utf8'));
export const budget = JSON.parse(readFileSync(join(results, 'flexibility-budget.json'), 'utf8'));
const flow = (id: string, p = 'S') => flows.scenarios.find((s: { id: string }) => s.id === id).policies[p];
/** S under "only jobs of 8 GPUs or fewer may move", e.g. "3.2%". */
export const sMobility = `${pct(flow('mobility_le_8gpus').saving_vs_U.saving.value)}%`;
/** S's replay-week GPU-hours to BPAT in a scenario, as the rows print them ("17,168"). */
export const bpatGpuH = (id: string) => Math.round(flow(id).week_arcs.find((a: { to: string }) => a.to === 'BPAT').gpu_h.value).toLocaleString('en-US');
const bs = budget.policies.S;
/** The flexibility budget's one-sentence headline for S. */
export const budgetHeadline = `${Math.round(bs.flexible_mobile_share.value * 100)}% of the energy sits in jobs flagged movable (${Math.round(bs.fits_remote_share.value * 100)}% fit a remote site); ${Math.round(bs.must_stay_share.value * 100)}% must stay in Utah.`;
/** I1: S's registered remote share on the execution basis, as the remote line prints it ("30.9%"). */
export const sRemoteExec = `${pct(flow('registered').remote_execution_share.value)}%`;
export const sMovedExec = `${pct(flow('registered').moved_share_energy.value)}%`;
/** I7: a percentage that is not the end of a span ("22.6%" but not "22.4–22.6%"). */
export const exact = (s: string) => new RegExp(`(?<![–\\d.])${s.replace(/[.]/g, '\\.')}`);
/** Each wait-only policy's own saving in the synthetic test fixture (M9). */
export const testOwn = (p: string) => `${pct(saving(p, 'U', fixtureMetrics))}%`;
const wp = (xs: number[]) => (Math.min(...xs) >= 0 && Math.max(...xs) < 0.01 ? 'under 1%' : null);
export const testWaitPhrase = wp(['W_time', 'L_time'].map((p) => saving(p, 'U', fixtureMetrics))) ?? testTimeOnlyRange;
/** T14: results/water.json. The story's water line, as printed: signed million gallons, two decimals. */
export const water = JSON.parse(readFileSync(join(results, 'water.json'), 'utf8'));
const smg = (g: number) => (g > 0 ? '+' : g < 0 ? '−' : '') + (Math.abs(g) / 1e6).toFixed(2);
const mspan = (r: number[]) => (smg(r[0]) === smg(r[1]) ? smg(r[0]) : `${smg(r[0])} to ${smg(r[1])}`);
export const waterExSpan = mspan(water.headline.change_ex_hydro_gal.value);
export const waterWithSpan = mspan(water.headline.change_with_hydro_gal.value);
export const waterCaveats: string[] = water.caveats;
/** the window in days, as the UI rounds it (not annualised) */
export const waterDays = String(Math.round(water.window.n_hours.value / 24));

/** T16: results/case-days.json. Per day: the date button, the rank, the peak and the Utah-cluster numbers, as printed. */
export const caseDays = JSON.parse(readFileSync(join(results, 'case-days.json'), 'utf8'));
const hr = (h: number) => `${h % 12 === 0 ? 12 : h % 12} ${h < 12 ? 'AM' : 'PM'}`;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const caseExpect = (caseDays.days as any[]).map((d) => ({
  button: new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric' }).format(new Date(d.date + 'T12:00:00Z')),
  rank: `Rank ${d.rank.value} of ${caseDays.days_considered.n.value} days`,
  cluster: `${hr(d.peak.hour_index.value)} peak hour, ${d.policies.U.utah_cluster_at_peak_mw.value.toFixed(2)} → ${d.policies.S.utah_cluster_at_peak_mw.value.toFixed(2)} MW`,
  peak: `net load peaked at ${Number(d.peak.net_load_mw.value).toLocaleString('en-US')} MW at ${hr(d.peak.hour_index.value)}`,
  slc: `${Math.round(d.weather.PACE_SLC.tmax_f.value)} °F high`,
  context: (d.context as { kind: string; sentence: string }[]).find((c) => c.kind === 'none')?.sentence ?? '',
  scale: (() => {
    const u: number = d.policies.U.utah_cluster_at_peak_mw.value;
    const peak: number = d.peak.net_load_mw.value; // unrounded, as the story line prints it (T20 merge fix)
    return `Scale: about ${u < 1.5 ? u.toFixed(1) : Math.round(u)} MW against a ${peak.toLocaleString('en-US')} MW peak; illustrative.`;
  })(),
  // the Sep 2 caveat: a Utah workload under 60% of the other chosen days'
  small: (() => {
    const e = (x: any) => Object.values(x.policies.U.energy_mwh_by_site).reduce((a: number, v: any) => a + v.value, 0) as number;
    const others = (caseDays.days as any[]).filter((x) => x.date !== d.date).map(e);
    return e(d) / Math.max(...others) < 0.6;
  })(),
}));
