// The cockpit's planner (T9 A10): a move's transfer energy is priced half at Utah's carbon intensity and half at the
// destination's, in the arrival hour; a missing hour takes the previous hour's value, never 0. Pure functions, no browser.
import { expect, test } from '@playwright/test';
import { filled, makePlan } from '../src/lib/plan';

const flat = (v: number) => Array.from({ length: 24 }, () => v);
const grid = (pace: (number | null)[], dest: number) => ({
  months: ['2025-07'],
  ci: { by_ba: { PACE: { month_hour: { value: [pace] } }, BPAT: { month_hour: { value: [flat(dest)] } }, CISO: { month_hour: { value: [flat(dest)] } }, NEVP: { month_hour: { value: [flat(dest)] } } } },
});
const manifest = {
  assumptions: {
    transfer_time_s: { value: 3600 }, transfer_energy_fraction: { value: 0.05 }, kw_per_gpu: { value: 0.6 }, pue: { value: 1.2 },
  },
};
const opts = { month: '2025-07', hour: 10, hours: 2, gpus: 8, maxWait: 0 };

test('a gap takes the previous non-null hour, never 0', () => {
  const cv = flat(400) as (number | null)[];
  cv[4] = 300; cv[5] = null; cv[6] = null;
  const f = filled(cv);
  expect(f[5]).toBe(300);
  expect(f[6]).toBe(300);
  expect(f.every((v) => v > 0)).toBe(true);
  const wrap = flat(250) as (number | null)[];
  wrap[0] = null; // hour 0 looks back across midnight to hour 23
  expect(filled(wrap)[0]).toBe(250);
  expect(filled(flat(1).map(() => null)).every(Number.isNaN)).toBe(true);
});

test('a move prices its transfer energy half at Utah and half at the destination', () => {
  const p = makePlan({ grid: grid(flat(400), 100), manifest } as never, opts);
  // execution at the destination (100) plus 5% of the run's energy, half at 400 and half at 100
  expect(p.moves.BPAT).toBeCloseTo(100 + 0.05 * 0.5 * (400 + 100), 9);
  expect(p.now).toBeCloseTo(400, 9);
});

test('the transfer is priced in the arrival hour', () => {
  const pace = flat(400); pace[10] = 200; pace[11] = 900; // arrival at 10: only hour 10 counts
  const p = makePlan({ grid: grid(pace, 100), manifest } as never, opts);
  expect(p.moves.CISO).toBeCloseTo(100 + 0.05 * 0.5 * (200 + 100), 9);
});
