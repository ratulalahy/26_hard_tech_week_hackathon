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
export const lCommonSupport = cell(ext.common_support.by_policy.L.vs_U['4']);
