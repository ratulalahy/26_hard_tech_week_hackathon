import { useMemo } from 'react';
import { TestTag, TestToughDays } from '../components/testYear';
import { EChart } from '../components/EChart';
import { Panel, Strip, useWidth } from '../components/charts';
import { Ev, EvCI } from '../components/ui';
import { ToughDays } from '../components/caseDays';
import { Legend } from './ControlRoom';
import { C, ci2c } from '../lib/color';
import { CORE, REGION, asNum, dayCurve, loadMonth, own, pname, yearMean, type Json } from '../lib/data';
import { argmax, cleanest, rushHours, spanLabel } from '../lib/derive';
import { fmt, fmtDate, fmtHour, monthLabel, pct } from '../lib/format';
import { cap } from '../lib/copy';
import { useApp } from '../lib/store';
import { useCopy } from '../lib/useCopy';

const LX = 112, RX = 96; // shared margins: the load chart and the carbon ribbon line up hour for hour

export function Ribbon() {
  const copy = useCopy();
  const { data, month } = useApp();
  const g = data!.grid;
  const curve = dayCurve(g, 'PACE', month);
  const rush = rushHours(g), clean = cleanest(curve);
  const jul = g.pace_july_weekday, lm = loadMonth(g);
  const net: number[] = jul.net_load_mw.value, dem: number[] = jul.demand_mw.value;
  const delayH = (asNum(data!.manifest.assumptions.allowed_delay_s.SFT) ?? 0) / 3600;
  const night = curve.slice(0, 7) as number[];
  const k: number = g.pace_top100_net_load.k.value;
  return (
    <section aria-label="Day ribbon" className="fixed z-10 grid" style={{ top: 72, left: 16, right: 16, bottom: 32, gridTemplateRows: 'auto minmax(0,1.15fr) minmax(0,1fr)', gap: 16 }}>
      <div className="flex items-end justify-between gap-6" style={{ padding: '0 8px' }}>
        <div>
          <h1 className="t-20" style={{ margin: 0 }}>In Utah, the clean hours aren't the rush hours</h1>
          <p className="t-13 ink-2" style={{ margin: '4px 0 0', maxWidth: '84ch' }}>
            On a {lm.short} weekday, carbon is lowest {spanLabel(clean)} while the sun is up. The grid's rush comes as solar fades: net load peaks at {fmtHour(argmax(net))} at {fmt(net[argmax(net)])} MW, and {fmtHour(rush[0])}–{fmtHour(rush[1])} holds most of {copy.yearPoss} {fmt(k)} highest net-load hours.
            Night hours, midnight to 7 AM, run {fmt(Math.min(...night))}–{fmt(Math.max(...night))} g/kWh.
          </p>
        </div>
        <div data-testid="ribbon-timing" className="panel flex-none" style={{ padding: '8px 12px', maxWidth: 460 }}>
          <div className="t-12 ink-2">Saved by waiting in Utah alone, {copy.allYear}; each policy's own estimate{copy.validationReadings ? null : <> <TestTag /></>}</div>
          <div className="flex items-baseline gap-4" style={{ marginTop: 2 }}>
            {(['W_time', 'L_time'] as const).map((p) => { const o = own(data!.metrics, p); return o ? (
              <span key={p} className="flex items-baseline gap-1" data-testid={`ribbon-own-${p}`}><span className="t-hero" style={{ fontSize: 28 }}>{pct(o.v)}%</span><span className="t-11 ink-2">{pname(p)} <span className="ink-3">[{pct(o.lo)}, {pct(o.hi)}]</span></span></span>
            ) : null; })}
          </div>
          <div className="t-11 ink-3">A flexible job may wait {fmt(delayH)} h, which rarely reaches the midday solar stretch from an evening or night start. Brackets: 95% intervals. <Ev e="simulated" /></div>
        </div>
      </div>

      <div className="grid min-h-0" style={{ gridTemplateColumns: data!.caseDays || data!.extras?.toughest_days?.status === 'ok' ? 'minmax(0,1fr) minmax(600px,0.8fr)' : 'minmax(0,1fr)', gap: 16 }}>
      <Panel className="flex flex-col min-h-0" style={{ padding: '12px 0 8px' }}>
        <div className="flex items-baseline justify-between" style={{ padding: '0 16px' }}>
          <span className="t-15">Utah · PacifiCorp East, a {lm.short} weekday</span>
          <span className="flex gap-4"><Ev e="observed">load in MW: EIA-930, {fmt(jul.n_days.value)} weekdays</Ev><EvCI extra="carbon, typical day" /></span>
        </div>
        <div className="flex-1 min-h-0"><LoadChart rush={rush} clean={clean} dem={dem} net={net} sol={jul.solar_mw.value} month={lm.short} /></div>
        <CarbonRibbon curve={curve} />
      </Panel>
      {data!.caseDays ? <div className="flex min-h-0"><ToughDays /></div> : data!.extras ? <div className="flex min-h-0"><TestToughDays x={data!.extras} /></div> : null}
      </div>

      <div className="grid min-h-0" style={{ gridTemplateColumns: '1.25fr 1fr 1fr', gap: 16 }}>
        <ForecastPanel />
        <Neighbours />
        <YearHeat />
      </div>
    </section>
  );
}

export function LoadChart({ rush, clean, dem, net, sol, month }: { rush: [number, number]; clean: [number, number]; dem: number[]; net: number[]; sol: number[]; month: string }) {
  const option = useMemo(() => {
    const at = (a: number[]) => a.map((v, i) => [i + 0.5, v]);
    const pk = argmax(net), dk = argmax(dem);
    const ymax = Math.ceil((Math.max(...dem) + 1500) / 3000) * 3000;
    const yb = ymax * 0.94, tick = ymax * 0.03;
    const sk = sol.indexOf(Math.max(...sol));
    return {
      grid: { left: LX, right: RX, top: 16, bottom: 8 },
      xAxis: { type: 'value', min: 0, max: 24, axisLabel: { show: false }, axisLine: { show: false }, splitLine: { show: false }, axisPointer: { label: { show: false } } },
      yAxis: { type: 'value', min: 0, max: ymax, interval: 3000, axisLabel: { formatter: (v: number) => (v ? `${v / 1000}k` : '0') } },
      tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${fmt(v)} MW`, formatter: (ps: { value: [number, number]; seriesName: string; marker: string }[]) => `${fmtHour(Math.floor(ps[0].value[0]))}<br/>${ps.map((q) => `${q.marker}${q.seriesName} ${fmt(q.value[1])} MW`).join('<br/>')}` },
      series: [
        { name: 'Solar', type: 'line', data: at(sol.map((v) => Math.max(0, v))), areaStyle: { color: C.solar, opacity: 0.8 }, lineStyle: { width: 0 }, symbol: 'none', z: 1,
          markPoint: { symbol: 'circle', symbolSize: 0, label: { show: true, formatter: 'Solar', color: C.solarInk, fontSize: 12, fontWeight: 600, position: 'inside' }, data: [{ coord: [sk + 0.5, Math.max(...sol) * 0.45] }] },
          markArea: { silent: true, itemStyle: { color: 'rgba(234,223,211,.45)' }, label: { show: true, position: 'insideTop', color: C.ink, fontSize: 11, fontWeight: 600, formatter: `Rush ${spanLabel(rush)}` }, data: [[{ xAxis: rush[0] }, { xAxis: rush[1] }]] } },
        { name: 'Demand', type: 'line', data: at(dem), lineStyle: { color: C.ink3, width: 1.5 }, symbol: 'none', z: 3, endLabel: { show: true, formatter: 'Demand', color: C.ink2, fontSize: 12, offset: [8, 0] },
          markPoint: { symbol: 'circle', symbolSize: 7, itemStyle: { color: C.ink3, borderColor: '#fff', borderWidth: 2 }, label: { show: true, position: 'bottom', color: C.ink2, fontSize: 11, formatter: `Demand peaks ${fmtHour(dk)}` }, data: [{ coord: [dk + 0.5, dem[dk]] }] } },
        { name: 'Net load', type: 'line', data: at(net), lineStyle: { color: C.ink, width: 2.25 }, symbol: 'none', z: 4, endLabel: { show: true, formatter: 'Net load', color: C.ink, fontSize: 12, fontWeight: 600, offset: [8, 0] },
          markPoint: { symbol: 'circle', symbolSize: 8, itemStyle: { color: C.ink, borderColor: '#fff', borderWidth: 2 }, label: { show: true, position: 'left', distance: 8, color: C.ink, fontSize: 11, fontWeight: 600, formatter: `Net load peaks ${fmtHour(pk)} · ${fmt(net[pk])} MW` }, data: [{ coord: [pk + 0.5, net[pk]] }] },
          // the cleanest stretch as a bracket, so it never tints the data
          markLine: { silent: true, symbol: 'none', lineStyle: { color: C.ink3, width: 1, type: 'solid' }, label: { show: false },
            data: [
              [{ coord: [clean[0], yb], label: { show: true, position: 'middle', formatter: `Cleanest 8 hours ${spanLabel(clean)}`, color: C.ink, fontSize: 11, fontWeight: 600, distance: 4 } }, { coord: [clean[1], yb] }],
              [{ coord: [clean[0], yb] }, { coord: [clean[0], yb - tick] }],
              [{ coord: [clean[1], yb] }, { coord: [clean[1], yb - tick] }],
            ] } },
      ],
    };
  }, [rush, clean, dem, net, sol]);
  return <EChart option={option} className="h-full w-full" label={`Utah ${month} weekday demand, net load and solar by hour, in MW`} />;
}

export function CarbonRibbon({ curve }: { curve: (number | null)[] }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const cw = (w - LX - RX) / 24;
  return (
    <div ref={ref} style={{ height: 64 }}>
      {w > 0 && (
        <svg width={w} height={64} role="img" aria-label="Utah carbon intensity by hour, typical day">
          <text x={LX - 12} y={22} textAnchor="end" fontSize={12} fontWeight={500} fill={C.ink}>Carbon</text>
          <text x={LX - 12} y={36} textAnchor="end" fontSize={11} fill={C.ink3}>g CO₂/kWh</text>
          {curve.map((v, i) => {
            const f = v == null ? '#fff' : ci2c(v);
            return (
              <g key={i}>
                <rect x={LX + i * cw + 1} y={4} width={cw - 2} height={36} rx={4} fill={f}><title>{`${fmtHour(i)}: ${v == null ? '–' : Math.round(v)} g/kWh (modeled, EIA estimate)`}</title></rect>
                {i % 3 === 0 && v != null && <text x={LX + i * cw + cw / 2} y={26} textAnchor="middle" fontSize={11} fontWeight={500} fill={(v > 560 || v < 120) ? '#fff' : C.ink}>{Math.round(v)}</text>}
                {i % 3 === 0 && <text x={LX + i * cw + cw / 2} y={58} textAnchor="middle" fontSize={11} fill={C.ink3}>{fmtHour(i)}</text>}
              </g>
            );
          })}
          <text x={w - RX + 8} y={20} fontSize={11} fill={C.ink3}>green is</text>
          <text x={w - RX + 8} y={34} fontSize={11} fill={C.ink3}>cleaner</text>
        </svg>
      )}
    </div>
  );
}

export function ForecastPanel() {
  const { data } = useApp();
  const fr: Json = data!.forecast;
  const hours: string[] = fr.hours;
  const obs: (number | null)[] = fr.truth.value;
  const MODELS = ['K', 'W', 'L'] as const;
  const maes = MODELS.map((k) => fr.week_errors[k].mae.value as number);
  const maeL: number = fr.week_errors.L.mae.value;
  const option = useMemo(() => {
    const lab = hours.map((t) => fmtDate(t, { weekday: 'short', hour: 'numeric' }));
    const style: Record<string, [string, number[] | 'solid', number]> = { K: [C.ink3, [1, 3], 1.5], W: [C.ink3, [5, 3], 1.5], L: [C.ink2, 'solid', 1.5] };
    const L: (number | null)[] = fr.forecasts.L.value;
    return {
      grid: { left: 56, right: 12, top: 12, bottom: 24 },
      xAxis: { type: 'category', data: lab, boundaryGap: false, axisLabel: { interval: 23, formatter: (v: string) => v.split(',')[0] } },
      yAxis: { type: 'value', min: (e: { min: number }) => Math.floor((e.min - 20) / 200) * 200, max: (e: { max: number }) => Math.ceil((e.max + 20) / 200) * 200, interval: 200,
        name: 'g CO₂/kWh', nameLocation: 'middle', nameRotate: 90, nameGap: 40, nameTextStyle: { color: C.ink3, fontSize: 11 } },
      tooltip: { trigger: 'axis', valueFormatter: (v: number) => (v == null ? '–' : `${Math.round(v)} g/kWh`) },
      series: [
        // L ± its week MAE, drawn as a stacked band (the lower edge is invisible)
        { name: 'band-lo', type: 'line', data: L.map((v) => (v == null ? null : Math.max(0, v - maeL))), stack: 'band', symbol: 'none', lineStyle: { width: 0 }, silent: true, tooltip: { show: false } },
        { name: `L ± ${Math.round(maeL)}: retrospective ±week MAE; not a prediction interval`, type: 'line', data: L.map((v) => (v == null ? null : v - Math.max(0, v - maeL) + maeL)), stack: 'band', symbol: 'none', lineStyle: { width: 0 }, areaStyle: { color: 'rgba(91,73,63,.12)' }, silent: true, tooltip: { show: false } },
        ...MODELS.map((k) => ({ name: pname(k), type: 'line', data: fr.forecasts[k].value, symbol: 'none', lineStyle: { color: style[k][0], type: style[k][1], width: style[k][2] } })),
        { name: 'Actual', type: 'line', data: obs, symbol: 'none', lineStyle: { color: C.ink, width: 2 }, z: 5 },
      ],
    };
  }, [fr, hours, obs, maeL]);
  return (
    <Panel className="flex flex-col min-h-0" style={{ padding: '12px 8px 4px 16px' }}>
      <div className="flex items-baseline justify-between gap-2" style={{ paddingRight: 8 }}>
        <span className="t-15">Day-ahead forecasts catch Utah's daily swing, off by {fmt(Math.min(...maes))}–{fmt(Math.max(...maes))} g/kWh</span>
      </div>
      <div className="t-11 ink-3 flex flex-wrap gap-x-3" style={{ marginTop: 2 }}>
        <span>Replay week {fmtDate(fr.week.start, { month: 'short', day: 'numeric' })}–{fmtDate(new Date(new Date(fr.week.end).getTime() - 1).toISOString(), { month: 'short', day: 'numeric', year: 'numeric' })}, issued 10 AM the day before. Error is the week's mean absolute error.</span>
        <Ev e="forecast" /><EvCI extra="actual" /><Ev e="measured">errors measured</Ev>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 t-11 ink-2" style={{ marginTop: 4 }} aria-hidden="true">
        <span className="flex items-center gap-1"><svg width="20" height="6"><line x1="0" x2="20" y1="3" y2="3" stroke={C.ink} strokeWidth="2" /></svg>actual</span>
        <span className="flex items-center gap-1"><svg width="20" height="8"><rect x="0" y="0" width="20" height="8" fill="rgba(91,73,63,.12)" /><line x1="0" x2="20" y1="4" y2="4" stroke={C.ink2} strokeWidth="1.5" /></svg>{pname('L')} ± {fmt(maeL)}: retrospective ±week MAE; not a prediction interval</span>
        <span className="flex items-center gap-1"><svg width="20" height="6"><line x1="0" x2="20" y1="3" y2="3" stroke={C.ink3} strokeWidth="1.5" strokeDasharray="5 3" /></svg>{pname('W')}</span>
        <span className="flex items-center gap-1"><svg width="20" height="6"><line x1="0" x2="20" y1="3" y2="3" stroke={C.ink3} strokeWidth="1.5" strokeDasharray="1 3" /></svg>{pname('K')}</span>
      </div>
      <EChart option={option} className="flex-1 min-h-0" testId="forecast-chart" label="Utah's actual carbon intensity and the K, W and L day-ahead forecasts for the replay week" />
    </Panel>
  );
}

export function Neighbours() {
  const copy = useCopy();
  const { data, month, hour } = useApp();
  const g = data!.grid;
  const pm = asNum(yearMean(g, 'PACE'))!;
  return (
    <Panel className="flex flex-col min-h-0">
      <div className="flex items-baseline justify-between"><span className="t-15">The same hours next door are far cleaner</span><EvCI /></div>
      <div className="flex flex-col flex-1" style={{ gap: 12, marginTop: 16 }}>
        {CORE.map((c) => {
          const ym = asNum(yearMean(g, c))!;
          return (
            <div key={c} className="grid items-center" style={{ gridTemplateColumns: '104px minmax(0,1fr) 72px', gap: 8 }}>
              <span className="t-13 fw-600 truncate">{REGION[c].name}<span className="block t-11 ink-3 fw-400">{c}</span></span>
              <Strip curve={dayCurve(g, c, month)} h={28} hour={hour} label={`${REGION[c].name} typical ${monthLabel(month)} day`} />
              <span className="text-right"><span className="t-13 fw-600 num">{fmt(ym)}</span><span className="block t-11 ink-3">{c === 'PACE' ? copy.yearMean : `${pct(1 - ym / pm, 0)}% cleaner`}</span></span>
            </div>
          );
        })}
        <div className="grid t-11 ink-3" style={{ gridTemplateColumns: '104px repeat(4, 1fr) 72px', gap: 8 }}><span />{[0, 6, 12, 18].map((x) => <span key={x}>{fmtHour(x)}</span>)}<span className="text-right">g/kWh</span></div>
      </div>
    </Panel>
  );
}

export function YearHeat() {
  const copy = useCopy();
  const { data } = useApp();
  const g = data!.grid;
  const [ref, w, h] = useWidth<HTMLDivElement>();
  const vals: (number | null)[][] = g.ci.by_ba.PACE.month_hour.value;
  const counts: number[][] = g.pace_top100_net_load.counts_month_hour.value;
  const lx = 32, top = 4, bottom = 18, cw = (w - lx) / 24, ch = (h - top - bottom) / 12;
  return (
    <Panel className="flex flex-col min-h-0">
      <div className="flex items-baseline justify-between gap-2"><span className="t-15">{cap(copy.allYear)}, the rush sits on the evening</span></div>
      <div className="t-11 ink-3 flex flex-wrap gap-x-3" style={{ marginTop: 2 }}>
        <span className="flex items-center gap-1"><svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="4.5" fill={C.rushFill} stroke={C.rush} strokeWidth="1.5" /></svg>{copy.yearPoss} top {fmt(g.pace_top100_net_load.k.value)} net-load hours, bigger for more <Ev e="observed" /></span>
        <span>cells: carbon by month and hour <EvCI /></span>
      </div>
      <div ref={ref} className="flex-1 min-h-0" style={{ marginTop: 8 }}>
        {w > 0 && h > 0 && (
          <svg width={w} height={h} role="img" aria-label={`Utah carbon intensity by month and hour, with ${copy.yearPoss} top 100 net-load hours circled`}>
            {vals.map((row, mi) => (
              <g key={mi}>
                {<text x={lx - 6} y={top + mi * ch + ch / 2 + 4} textAnchor="end" fontSize={11} fill={C.ink3}>{monthLabel(g.months[mi])}</text>}
                {row.map((v, hr) => {
                  const c = counts[mi][hr];
                  const r = Math.min(cw, ch) / 2 * Math.min(0.92, 0.4 + Math.sqrt(c) / 6);
                  return (
                    <g key={hr}>
                      <rect x={lx + hr * cw + 0.75} y={top + mi * ch + 0.75} width={cw - 1.5} height={ch - 1.5} rx={2} fill={v == null ? '#fff' : ci2c(v)}>
                        <title>{`${monthLabel(g.months[mi])} ${fmtHour(hr)}: ${v == null ? '–' : Math.round(v)} g/kWh; ${c} of the top-100 net-load hours`}</title>
                      </rect>
                      {c > 0 && <circle cx={lx + hr * cw + cw / 2} cy={top + mi * ch + ch / 2} r={r} fill={C.rushFill} fillOpacity={0.7} stroke={C.rush} strokeWidth={1.5} pointerEvents="none" />}
                    </g>
                  );
                })}
              </g>
            ))}
            {[0, 6, 12, 18].map((x) => <text key={x} x={lx + x * cw + cw / 2} y={h - 4} textAnchor="middle" fontSize={11} fill={C.ink3}>{fmtHour(x)}</text>)}
          </svg>
        )}
      </div>
      <div style={{ marginTop: 8 }}><Legend short /></div>
    </Panel>
  );
}
