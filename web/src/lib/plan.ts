// "Plan a run": an in-browser illustration over one month's typical day (observed tier-1 CI means).
// It is NOT the registered result (that is metrics.json). Labelled "illustrative · modeled".
import { DESTS, asNum, dayCurve, type Core, type Dest, type Json } from './data';

export interface Plan {
  a: number; H: number; now: number;
  wait: { s: number; d: number; v: number };
  moves: Record<Dest, number>;
  kwh: number; kw: number; pue: number;
  cut: (v: number) => number; kg: (v: number) => number;
  patience: number[]; // best cut from waiting, by allowed wait 0..24 h
}

const wmean = (cv: number[], s: number, H: number) => { let t = 0; for (let i = 0; i < H; i++) t += cv[(s + i) % 24]; return t / H; };
const filled = (cv: (number | null)[]) => cv.map((v, i) => v ?? cv[(i + 23) % 24] ?? 0) as number[];

export function makePlan(r: { grid: Json; manifest: Json }, o: { month: string; hour: number; hours: number; gpus: number; maxWait: number }): Plan {
  const cur = (ba: Core) => filled(dayCurve(r.grid, ba, o.month));
  const P = cur('PACE');
  const a = o.hour, H = o.hours;
  const now = wmean(P, a, H);
  let wait = { s: a, d: 0, v: now };
  for (let d = 0; d <= o.maxWait; d++) { const v = wmean(P, (a + d) % 24, H); if (v < wait.v - 1e-9) wait = { s: (a + d) % 24, d, v }; }
  const moves = Object.fromEntries(DESTS.map((k) => [k, wmean(cur(k), a, H)])) as Record<Dest, number>;
  const kw = asNum(r.manifest.assumptions.kw_per_gpu) ?? NaN;
  const pue = asNum(r.manifest.assumptions.pue) ?? NaN;
  const kwh = o.gpus * H * kw * pue;
  const patience: number[] = [];
  let best = now;
  for (let d = 0; d <= 24; d++) { best = Math.min(best, wmean(P, (a + d) % 24, H)); patience.push(Math.max(0, 1 - best / now)); }
  return { a, H, now, wait, moves, kwh, kw, pue, cut: (v) => 1 - v / now, kg: (v) => (kwh * v) / 1000, patience };
}
