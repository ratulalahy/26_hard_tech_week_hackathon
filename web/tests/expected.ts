// Expected on-screen strings, computed straight from the committed results/*.json (not from the app's code).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const results = join(here, '..', 'public', 'data', 'results');
export const metrics = JSON.parse(readFileSync(join(results, 'metrics.json'), 'utf8'));

type Env = { value: number | number[] | null };
const pct = (x: number) => (x * 100).toFixed(1);

function saving(cand: string, ref = 'U'): number {
  const c = metrics.contrasts.find((x: { candidate: string; reference: string }) => x.candidate === cand && x.reference === ref);
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

/** T17 (D-068): results/assumptions.json, checked against numbers computed here from metrics.json
 * and extensions.json (not from the notebook's sentences). */
export const assumptions = JSON.parse(readFileSync(join(results, 'assumptions.json'), 'utf8'));
export const nRegister: number = assumptions.register.length;
const ci = (cand: string, ref = 'U') => {
  const c = metrics.contrasts.find((x: { candidate: string; reference: string }) => x.candidate === cand && x.reference === ref);
  const [lo, hi] = c.blocks['4'].saving_ci95.value as number[];
  return `${pct(saving(cand, ref))}% [${pct(lo)}, ${pct(hi)}]`;
};
/** "Perfect carbon foresight (H) saves 22.6% [18.4, 26.8]" and S's own saving, as the weather point prints them. */
export const weatherH = `(H) saves ${ci('H')}`;
export const weatherS = `ranking S saves ${ci('S')}`;
/** Waiting in Utah, as the negative-results list prints it: "save 0.7% [0.5, 0.9] (W_time)". */
export const waitW = `save ${ci('W_time')} (W_time)`;
/** The mobility row: "W saves 3.9% [2.6, 5.4]". */
export const mobilityW = `W saves ${cell(ext.sensitivities.mobility_le_8gpus.policies.W.vs_U['4'])}`;
