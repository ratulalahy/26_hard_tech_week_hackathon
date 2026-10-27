// Colour roles from docs/design/tokens.md (the source of truth). One meaning per colour.
export const CARBON = ['#298954', '#59aa6d', '#8fc990', '#c3e2bc', '#f7efe0', '#f5c79f', '#ed8b51', '#c6481c', '#7c1213'];
// Diverging midpoint: the US average CO2 intensity, 2024 (EIA), read from grid-profile.json at load (tokens.md).
export let CI_MID = 356;
export function setMid(v: number | null | undefined) { if (v != null && Number.isFinite(v)) CI_MID = v; }
export const CI_MAX = 750;

export const C = {
  ink: '#2d1d14', ink2: '#5b493f', ink3: '#6c594f',
  hair: 'rgba(110,62,30,.14)', hair2: 'rgba(110,62,30,.07)',
  rush: '#4a3a30', rushFill: '#eadfd3',
  solar: '#f4d846', solarMark: '#ddbc1a', solarInk: '#6b4708',
  route: '#1157a4', routeSoft: '#dfedfe',
  sky0: '#fdf9f4', sky1: '#faf2ea', sky2: '#f6ebdf', surface: '#fffdfa',
  sand0: '#8c6a4f',
} as const;

const toLin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const toSrgb = (c: number) => (c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055);
type Lab = [number, number, number];
function hexToOklab(h: string): Lab {
  const [r, g, b] = [1, 3, 5].map((i) => toLin(parseInt(h.slice(i, i + 2), 16) / 255));
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s, 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s];
}
function oklabToHex([L, a, b]: Lab): string {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3, m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3, s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const rgb = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s];
  return '#' + rgb.map((v) => Math.round(Math.max(0, Math.min(1, toSrgb(v))) * 255).toString(16).padStart(2, '0')).join('');
}
const LAB = CARBON.map(hexToOklab);
const MIDI = (CARBON.length - 1) / 2;
const ci2t = (v: number) => {
  v = Math.max(0, Math.min(CI_MAX, v));
  return v <= CI_MID ? (v / CI_MID) * MIDI : MIDI + ((v - CI_MID) / (CI_MAX - CI_MID)) * MIDI;
};
/** Carbon intensity (g/kWh) to its colour on the diverging scale, interpolated in OKLab. */
export function ci2c(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '#ffffff';
  const t = ci2t(v), i = Math.min(CARBON.length - 2, Math.floor(t)), f = t - i;
  return oklabToHex(LAB[i].map((x, k) => x + (LAB[i + 1][k] - x) * f) as Lab);
}
export function luminance(h: string) {
  const [r, g, b] = [1, 3, 5].map((i) => toLin(parseInt(h.slice(i, i + 2), 16) / 255));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
/** Ink that sits on a data fill (text never wears a data colour; it sits on one). */
export const onFill = (h: string) => (luminance(h) > 0.22 ? C.ink : '#ffffff');
