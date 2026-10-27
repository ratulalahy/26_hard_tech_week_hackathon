import { readFileSync } from 'fs';
const src = readFileSync('oklch.mjs', 'utf8').split('\n// carbon')[0];
const toHex = eval(src.replace('const toHex =', '(').trim().replace(/;$/, '') + ')');
const g = [[0.88, 0.06, 140], [0.78, 0.10, 145], [0.67, 0.12, 150], [0.56, 0.12, 155]];   // light → dark green (clean)
const mid = [0.955, 0.022, 85];
const r = [[0.86, 0.075, 62], [0.73, 0.14, 50], [0.57, 0.17, 38], [0.38, 0.14, 27]];      // peach → Utah orange → brick → canyon red
console.log('scale', [...g.slice().reverse(), mid, ...r].map(s => toHex(...s)).join(','));
console.log('greens', g.map(s => toHex(...s)).join(','));
console.log('reds', r.map(s => toHex(...s)).join(','));
console.log('route', toHex(0.46, 0.14, 255), 'route-soft', toHex(0.94, 0.03, 255));
