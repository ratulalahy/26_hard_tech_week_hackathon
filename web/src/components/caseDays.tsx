// "Utah's toughest grid days" (Stage 3 T16, D-066): the pre-registered top 3 validation days by PACE
// daily maximum net load, from results/case-days.json. A compact 3-day switcher; per day the net-load
// curve over the carbon strip, the Utah cluster's load under U vs S, one sentence, the temperature line
// (forecast archive, descriptive only) and the cited context line (context, never evidence).
import { useState } from 'react';
import { C, ci2c } from '../lib/color';
import { useApp } from '../lib/store';
import { fmt, fmtHour, pct } from '../lib/format';
import { Ev, EvCI } from './ui';
import { Panel, useWidth } from './charts';
import type { Json } from '../lib/data';

const day = (iso: string, o: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', ...o }).format(new Date(iso + 'T12:00:00Z'));

/** The day's sentences, built only from enveloped numbers in case-days.json (tests rebuild them). */
export function caseSentences(cd: Json, d: Json) {
  const pk: number = d.peak.hour_index.value, peak: number = d.peak.net_load_mw.value;
  const U = d.policies.U, S = d.policies.S, W = d.policies.W;
  const uMW: number = U.utah_cluster_at_peak_mw.value, sMW: number = S.utah_cluster_at_peak_mw.value;
  const lower = sMW < uMW - 1e-9;
  const story = `Rank ${d.rank.value} of ${fmt(cd.days_considered.n.value)} days. Moving work (S) ${lower ? 'lowered' : 'did not lower'} the Utah cluster in the ${fmtHour(pk)} peak hour, `
    + `${fmt(uMW, 2)} → ${fmt(sMW, 2)} MW; the day's CO₂ fell ${pct(-S.co2_change_vs_U_frac.value, 0)}% (W ${pct(-W.co2_change_vs_U_frac.value, 0)}%).`;
  const slc = d.weather.PACE_SLC;
  const temp = slc.tmax_f.value == null ? 'No archived temperature for Salt Lake City this day.'
    : `${fmt(slc.tmax_f.value)} °F high, ${fmt(slc.tmin_f.value)} °F low in Salt Lake City (${fmt(slc.cdd_65f.value)} cooling degree-days); net load peaked at ${fmt(peak)} MW at ${fmtHour(pk)}.`;
  return { story, temp, lower };
}

function DayChart({ d }: { d: Json }) {
  const [ref, w, h] = useWidth<HTMLDivElement>();
  const net: number[] = d.pace.net_load_mw.value, ci: number[] = d.pace.ci_g_kwh.value;
  const u: number[] = d.policies.U.utah_cluster_mw.value, s: number[] = d.policies.S.utah_cluster_mw.value;
  const n = net.length, pk: number = d.peak.hour_index.value;
  const lx = 50, rx = 8, cw = (w - lx - rx) / n;
  const x = (i: number) => lx + (i + 0.5) * cw;
  // three bands: net load (top), carbon strip, cluster load U vs S (bottom)
  const nTop = 10, avail = h - nTop - 4 - 14 - 30, nH = Math.max(36, avail * 0.55), sY = nTop + nH + 6, sH = 14;
  const hY = sY + sH + 12, cTop = hY + 22, cH = Math.max(24, h - 4 - cTop);
  const nMax = Math.ceil(Math.max(...net) / 1000) * 1000, nMin = Math.floor(Math.min(...net) / 1000) * 1000;
  const yN = (v: number) => nTop + nH - ((v - nMin) / (nMax - nMin)) * nH;
  const cMax = Math.ceil(Math.max(...u, ...s) * 1.15 * 10) / 10 || 1;
  const cMin = Math.max(0, Math.floor(Math.min(...u, ...s) * 0.9 * 10) / 10);
  const yC = (v: number) => cTop + cH - ((v - cMin) / (cMax - cMin || 1)) * cH;
  const path = (a: number[], y: (v: number) => number) => a.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('');
  const label = `${day(d.date, { month: 'long', day: 'numeric' })}: Utah net load by hour peaking at ${fmt(net[pk])} MW at ${fmtHour(pk)}, carbon intensity by hour, and the Utah cluster's load under U and S`;
  return (
    <div ref={ref} className="min-h-0" style={{ flex: '1 1 150px' }} data-testid="case-chart">
      {w > 0 && h > 0 && (
        <svg width={w} height={h} role="img" aria-label={label} style={{ display: 'block' }}>
          {/* the day's peak hour: a neutral rush hatch column through all three bands */}
          <rect x={lx + pk * cw} y={nTop - 2} width={cw} height={sY + sH - nTop + 4} fill={C.rushFill} opacity={0.7} />
          <rect x={lx + pk * cw} y={cTop - 2} width={cw} height={cH + 2} fill={C.rushFill} opacity={0.7} />
          <text x={lx - 6} y={nTop + 4} textAnchor="end" fontSize={11} fill={C.ink3}>{fmt(nMax / 1000)}k</text>
          <text x={lx - 6} y={nTop + nH} textAnchor="end" fontSize={11} fill={C.ink3}>{fmt(nMin / 1000)}k</text>
          <path d={path(net, yN)} fill="none" stroke={C.ink} strokeWidth={2} />
          <circle cx={x(pk)} cy={yN(net[pk])} r={3.5} fill={C.ink} stroke="#fff" strokeWidth={1.5} />
          <text x={x(pk) - 7} y={yN(net[pk]) + 4} textAnchor="end" fontSize={11} fontWeight={600} fill={C.ink}>Net load {fmt(net[pk])} MW</text>
          {ci.map((v, i) => (
            <rect key={i} x={lx + i * cw + 0.75} y={sY} width={Math.max(0, cw - 1.5)} height={sH} rx={2} fill={ci2c(v)}>
              <title>{`${fmtHour(i)}: ${Math.round(v)} g/kWh (modeled, EIA estimate)`}</title>
            </rect>
          ))}
          <text x={lx - 6} y={sY + 11} textAnchor="end" fontSize={11} fill={C.ink3}>CO₂</text>
          <text x={lx - 6} y={cTop + 8} textAnchor="end" fontSize={11} fill={C.ink3}>{fmt(cMax, 1)}</text>
          <text x={lx - 6} y={cTop + cH} textAnchor="end" fontSize={11} fill={C.ink3}>{fmt(cMin, 1)} MW</text>
          <path d={path(u, yC)} fill="none" stroke={C.ink3} strokeWidth={1.5} strokeDasharray="4 3" />
          <path d={path(s, yC)} fill="none" stroke={C.route} strokeWidth={2} />
          <text x={lx} y={cTop - 6} fontSize={11} fill={C.ink2}>Utah cluster load: <tspan fill={C.ink3}>– – U local</tspan>  <tspan fill={C.route} fontWeight={600}>— S moves work</tspan></text>
          {[0, 6, 12, 18].map((i) => <text key={i} x={lx + i * cw} y={hY} fontSize={11} fill={C.ink3}>{fmtHour(i)}</text>)}
        </svg>
      )}
    </div>
  );
}

function Context({ d }: { d: Json }) {
  const none = d.context.find((c: Json) => c.kind === 'none');
  const more = d.context.filter((c: Json) => c.kind !== 'none');
  const full = d.context.map((c: Json) => c.sentence + (c.url ? ` (${c.publisher}, ${c.published}; ${c.scope})` : '')).join(' ');
  return (
    <p className="t-11 ink-3" style={{ margin: 0, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }} title={full} data-testid="case-context">
      <span className="fw-600 ink-2">Context, not evidence: </span>
      {none ? none.sentence : ''}
      {more.map((c: Json) => (
        <span key={c.url}> {c.kind === 'month' ? 'Month: ' : 'Nearby: '}<a href={c.url} target="_blank" rel="noreferrer" className="ink-2" style={{ textDecoration: 'underline' }}>{c.title}</a> ({c.publisher.split(' (')[0]}).</span>
      ))}
    </p>
  );
}

export function ToughDays() {
  const { data } = useApp();
  const cd: Json | null = data?.caseDays ?? null;
  const [i, setI] = useState(0);
  if (!cd) return null;
  const d = cd.days[i];
  const { story, temp } = caseSentences(cd, d);
  return (
    <Panel className="flex flex-col min-h-0" style={{ padding: '12px 14px 10px', gap: 6 }}>
      <div data-testid="case-days" className="flex items-center justify-between gap-2">
        <span className="t-15" style={{ whiteSpace: 'nowrap' }}>Utah's toughest grid days</span>
        <div className="seg seg-tight" role="radiogroup" aria-label="Toughest days">
          {cd.days.map((x: Json, k: number) => (
            <button key={x.date} role="radio" aria-checked={k === i} onClick={() => setI(k)} title={`Rank ${x.rank.value}: ${fmt(x.peak.net_load_mw.value)} MW`}>
              {day(x.date, { month: 'short', day: 'numeric' })}
            </button>
          ))}
        </div>
      </div>
      <div className="t-11 ink-3 flex flex-wrap gap-x-3">
        <span>Top 3 validation days by peak net load, a rule fixed in advance</span>
        <Ev e="observed">load</Ev><EvCI /><Ev e="simulated">cluster, CO₂ (day-sliced)</Ev>
      </div>
      <DayChart d={d} />
      <p className="t-12" style={{ margin: 0, lineHeight: 1.35 }} data-testid="case-story"><span className="fw-600">{d.weekday} {day(d.date, { month: 'short', day: 'numeric' })}.</span> {story}</p>
      <p className="t-11 ink-2 flex flex-wrap items-center gap-x-2" style={{ margin: 0 }} data-testid="case-temp">{temp} <Ev e="forecast">archived forecast, descriptive</Ev></p>
      <Context d={d} />
    </Panel>
  );
}
