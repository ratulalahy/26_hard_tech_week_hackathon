// OKLCH -> sRGB hex (Björn Ottosson's OKLab), gamut-clipped by reducing chroma.
const toHex = (L, C, h) => {
  for (let c = C; c >= 0; c -= 0.002) {
    const a = c * Math.cos(h * Math.PI / 180), b = c * Math.sin(h * Math.PI / 180);
    const l_ = L + 0.3963377774 * a + 0.2158037573 * b, m_ = L - 0.1055613458 * a - 0.0638541728 * b, s_ = L - 0.0894841775 * a - 1.2914855480 * b;
    const l = l_ ** 3, m = m_ ** 3, s = s_ ** 3;
    const lin = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s];
    if (lin.every(v => v >= -1e-4 && v <= 1 + 1e-4)) {
      const g = v => { v = Math.min(1, Math.max(0, v)); return v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055; };
      return '#' + lin.map(v => Math.round(g(v) * 255).toString(16).padStart(2, '0')).join('');
    }
  }
};
// carbon: 8 steps, L 0.95 -> 0.40 (monotonic), hue 150 (green) -> 95 (yellow) -> 60 (orange) -> 28 (red)
const n = 8, out = [];
const H = [150, 135, 105, 82, 62, 45, 33, 26], Cc = [0.045, 0.085, 0.105, 0.125, 0.145, 0.16, 0.165, 0.15];
for (let i = 0; i < n; i++) { const L = 0.95 - i * (0.55 / (n - 1)); out.push(toHex(L, Cc[i], H[i])); }
console.log('carbon', out.join(','));
console.log('route', toHex(0.50, 0.11, 180), 'route-soft', toHex(0.94, 0.04, 180));
console.log('brand', toHex(0.64, 0.17, 45));
console.log('solar', toHex(0.86, 0.15, 88), 'solar-mark', toHex(0.70, 0.15, 70));
console.log('ground', toHex(0.985, 0.008, 75), toHex(0.965, 0.014, 70), toHex(0.945, 0.02, 68), toHex(0.955, 0.016, 72));
console.log('ink', toHex(0.25, 0.03, 50), toHex(0.42, 0.03, 50), toHex(0.48, 0.03, 50));
