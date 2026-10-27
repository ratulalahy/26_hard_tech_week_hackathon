// Facts derived in the browser from the grid profile (observed). No number here is typed in.
import { fmtHour } from './format';
import type { Json } from './data';

/** The rush: hours of day holding ≥ 10% of the year's top-100 net-load hours (PACE). Returns [start, end). */
export function rushHours(grid: Json): [number, number] {
  const counts: number[][] = grid.pace_top100_net_load.counts_month_hour.value;
  const k: number = grid.pace_top100_net_load.k.value;
  const byHour = Array.from({ length: 24 }, (_, h) => counts.reduce((s, row) => s + row[h], 0));
  const hot = byHour.map((n) => n >= 0.1 * k);
  const s = hot.indexOf(true), e = hot.lastIndexOf(true);
  return s < 0 ? [19, 22] : [s, e + 1];
}
export function hourCounts(grid: Json): number[] {
  const counts: number[][] = grid.pace_top100_net_load.counts_month_hour.value;
  return Array.from({ length: 24 }, (_, h) => counts.reduce((s, row) => s + row[h], 0));
}
/** Start hour of the cleanest contiguous 8-hour stretch of a 24-hour curve (no wrap). */
export function cleanest(curve: (number | null)[], H = 8): [number, number] {
  let best = Infinity, at = 0;
  for (let s = 0; s + H <= 24; s++) {
    const w = curve.slice(s, s + H);
    if (w.some((v) => v == null)) continue;
    const m = (w as number[]).reduce((a, b) => a + b, 0) / H;
    if (m < best) { best = m; at = s; }
  }
  return [at, at + H];
}
export const spanLabel = ([s, e]: [number, number]) => `${fmtHour(s).replace(' ', ' ')}–${fmtHour(e).replace(' ', ' ')}`;
export const argmax = (a: (number | null)[]) => a.reduce<number>((bi, v, i) => ((v ?? -Infinity) > (a[bi] ?? -Infinity) ? i : bi), 0);
