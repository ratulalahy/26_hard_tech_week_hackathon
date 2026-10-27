// "Plan a run": an in-browser illustration over one month's typical day (EIA consumption-basis CI,
// modeled). It is NOT the registered result (that is metrics.json). Labelled "illustrative · modeled".
// A move applies the manifest's transfer rules: the job starts transfer_time_s later at the
// destination, and transfer_energy_fraction of the run's energy is drawn in Utah at arrival.
import { DESTS, asNum, dayCurve, type Core, type Dest, type Json } from './data';

export interface Plan {
  a: number; H: number; now: number;
  wait: { s: number; d: number; v: number };
  /** effective g/kWh of the run's energy for a move, transfer included */
  moves: Record<Dest, number>;
  transferH: number; transferFrac: number;
  kwh: number; kw: number; pue: number;
  cut: (v: number) => number; kg: (v: number) => number;
  patience: number[]; // best cut from waiting, by allowed wait 0..24 h
}

/** Mean of an hourly curve over [s, s + H) hours, s fractional, wrapping at midnight. */
function wmean(cv: number[], s: number, H: number) {
  let t = 0, left = H, x = s;
  while (left > 1e-9) {
    const h = Math.floor(x), step = Math.min(left, h + 1 - x);
    t += cv[((h % 24) + 24) % 24] * step;
    x += step; left -= step;
  }
  return t / H;
}
const filled = (cv: (number | null)[]) => cv.map((v, i) => v ?? cv[(i + 23) % 24] ?? 0) as number[];

export function makePlan(r: { grid: Json; manifest: Json }, o: { month: string; hour: number; hours: number; gpus: number; maxWait: number }): Plan {
  const cur = (ba: Core) => filled(dayCurve(r.grid, ba, o.month));
  const P = cur('PACE');
  const a = o.hour, H = o.hours;
  const A = r.manifest.assumptions;
  const transferH = (asNum(A.transfer_time_s) ?? 0) / 3600;
  const transferFrac = asNum(A.transfer_energy_fraction) ?? 0;
  const now = wmean(P, a, H);
  let wait = { s: a, d: 0, v: now };
  for (let d = 0; d <= o.maxWait; d++) { const v = wmean(P, (a + d) % 24, H); if (v < wait.v - 1e-9) wait = { s: (a + d) % 24, d, v }; }
  // per kWh of the run: execution at the destination after the transfer, plus the transfer's share drawn in Utah
  const moves = Object.fromEntries(DESTS.map((k) => [k, wmean(cur(k), a + transferH, H) + transferFrac * wmean(P, a, Math.max(transferH, 1 / 60))])) as Record<Dest, number>;
  const kw = asNum(A.kw_per_gpu) ?? NaN;
  const pue = asNum(A.pue) ?? NaN;
  const kwh = o.gpus * H * kw * pue;
  const patience: number[] = [];
  let best = now;
  for (let d = 0; d <= 24; d++) { best = Math.min(best, wmean(P, (a + d) % 24, H)); patience.push(Math.max(0, 1 - best / now)); }
  return { a, H, now, wait, moves, transferH, transferFrac, kwh, kw, pue, cut: (v) => 1 - v / now, kg: (v) => (kwh * v) / 1000, patience };
}
