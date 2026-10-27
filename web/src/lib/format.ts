// Number formatting: tabular figures in CSS; thousands separators and honest rounding here.
export const MINUS = '−';
const nf = (d: number) => new Intl.NumberFormat('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });

export const fmt = (v: number, d = 0) => nf(d).format(v).replace('-', MINUS);
export const pct = (x: number, d = 1) => fmt(x * 100, d);
/** "22.4–22.6" from fractions */
export const pctRange = (a: number, b: number, d = 1) => (pct(a, d) === pct(b, d) ? pct(a, d) : `${pct(Math.min(a, b), d)}–${pct(Math.max(a, b), d)}`);
export const signed = (v: number, d = 0) => (v > 0 ? '+' : v < 0 ? MINUS : '') + nf(d).format(Math.abs(v));
/** two significant figures, for illustrative estimates */
export function sig2(v: number) {
  if (!Number.isFinite(v)) return '–';
  if (Math.abs(v) < 1) return v.toFixed(2);
  const p = Math.pow(10, Math.floor(Math.log10(Math.abs(v))) - 1);
  return fmt(Math.round(v / p) * p, 0);
}

export const fmtHour = (h: number) => {
  h = ((h % 24) + 24) % 24;
  const s = h < 12 ? 'AM' : 'PM', k = h % 12 === 0 ? 12 : h % 12;
  return `${k} ${s}`;
};
export const fmtSpan = (s: number, H: number) => `${fmtHour(s)}–${fmtHour(s + H)}`;

const DEN = 'America/Denver';
export const fmtDate = (iso: string, o: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric', year: 'numeric' }) =>
  new Intl.DateTimeFormat('en-US', { timeZone: DEN, ...o }).format(new Date(iso));
export const monthLabel = (ym: string, long = false) => {
  const [y, m] = ym.split('-').map(Number);
  return new Intl.DateTimeFormat('en-US', { month: long ? 'long' : 'short', year: long ? 'numeric' : undefined, timeZone: 'UTC' }).format(new Date(Date.UTC(y, m - 1, 15)));
};
