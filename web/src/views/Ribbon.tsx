import { useMemo } from 'react';
import { EChart } from '../components/EChart';
import { Panel, Strip, useWidth } from '../components/charts';
import { Ev } from '../components/ui';
import { C, ci2c } from '../lib/color';
import { CORE, REGION, asNum, dayCurve, headline, yearMean, type Json } from '../lib/data';
import { argmax, cleanest, hourCounts, rushHours, spanLabel } from '../lib/derive';
import { fmt, fmtDate, fmtHour, monthLabel, pct, pctRange } from '../lib/format';
import { useApp } from '../lib/store';

const LX = 112, RX = 96; // shared margins: the load chart and the carbon ribbon line up hour for hour

export function Ribbon() {
  const { data, month } = useApp();
  const g = data!.grid;
  const curve = dayCurve(g, 'PACE', month);
  const rush = rushHours(g), clean = cleanest(curve);
  const jul = g.pace_july_weekday;
  const net: number[] = jul.net_load_mw.value, dem: number[] = jul.demand_mw.value;
  const h = headline(data!.metrics);
  const delayH = (asNum(data!.manifest.assumptions.allowed_delay_s.SFT) ?? 0) / 3600;
  const night = curve.slice(0, 7) as number[];
  return (
    <section aria-label="Day ribbon" className="fixed z-10 grid" style={{ top: 72, left: 16, right: 16, bottom: 32, gridTemplateRows: 'auto minmax(0,1.15fr) minmax(0,1fr)', gap: 16 }}>
      <div className="flex items-end justify-between gap-6" style={{ padding: '0 8px' }}>
        <div>
          <h1 className="t-20" style={{ margin: 0 }}>In Utah, the clean hours aren't the rush hours</h1>
          <p className="t-13 ink-2" style={{ margin: '4px 0 0', maxWidth: '84ch' }}>
            On a July weekday, carbon is lowest {spanLabel(clean)} while the sun is up. The grid's rush comes after sunset: net load peaks at {fmtHour(argmax(net))} at {fmt(net[argmax(net)])} MW, and {fmtHour(rush[0])}–{fmtHour(rush[1])} holds most of the year's 100 highest net-load hours.
            Coal nights run {fmt(Math.min(...night))}–{fmt(Math.max(...night))} g/kWh.
          </p>
        </div>
        <div data-testid="ribbon-timing" className="panel flex-none" style={{ padding: '8px 12px', maxWidth: 440 }}>
          <div className="flex items-baseline gap-2"><span className="t-hero" style={{ fontSize: 28 }}>{pctRange(h.timing.lo, h.timing.hi)}%</span><span className="t-12 ink-2">saved by waiting in Utah alone, all year</span></div>
          <div className="t-11 ink-3">A flexible job may wait {fmt(delayH)} h, which rarely reaches the solar stretch from a coal night. 95% {pct(h.timing.ciLo)}–{pct(h.timing.ciHi)}%. <Ev e="simulated" /></div>
        </div>
      </div>

      <Panel className="flex flex-col min-h-0" style={{ padding: '12px 0 8px' }}>
        <div className="flex items-baseline justify-between" style={{ padding: '0 16px' }}>
          <span className="t-15">Utah · PacifiCorp East, a {monthLabel(month, true).split(' ')[0]} weekday</span>
          <span className="flex gap-4"><Ev e="observed">load: EIA-930, {fmt(jul.n_days.value)} weekdays</Ev><Ev e="observed">carbon: typical day</Ev></span>
        </div>
        <div className="flex-1 min-h-0"><LoadChart rush={rush} clean={clean} dem={dem} net={net} sol={jul.solar_mw.value} /></div>
        <CarbonRibbon curve={curve} />
      </Panel>

      <div className="grid min-h-0" style={{ gridTemplateColumns: '1.25fr 1fr 1fr', gap: 16 }}>
        <ForecastPanel />
        <Neighbours />
        <YearHeat />
      </div>
    </section>
  );
}

export function LoadChart({ rush, clean, dem, net, sol }: { rush: [number, number]; clean: [number, number]; dem: number[]; net: number[]; sol: number[] }) {
  const option = useMemo(() => {
    const hours = Array.from({ length: 24 }, (_, i) => fmtHour(i));
    const pk = argmax(net), dk = argmax(dem);
    return {
      grid: { left: LX, right: RX, top: 28, bottom: 8 },
      xAxis: { type: 'category', data: hours, boundaryGap: true, axisLabel: { show: false }, axisLine: { show: false } },
      yAxis: { type: 'value', min: 0, splitNumber: 3, name: 'MW', nameLocation: 'end', nameGap: 8, axisLabel: { formatter: (v: number) => (v ? `${v / 1000}k` : '0') } },
      tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${fmt(v)} MW` },
      series: [
        { name: 'Solar', type: 'line', data: sol.map((v) => Math.max(0, v)), areaStyle: { color: C.solar, opacity: 0.8 }, lineStyle: { width: 0 }, symbol: 'none', z: 1,
          markArea: { silent: true, itemStyle: { color: 'rgba(234,223,211,.45)' }, label: { show: true, position: 'insideTop', color: C.ink, fontSize: 11, fontWeight: 600, formatter: `Rush ${spanLabel(rush)}` }, data: [[{ xAxis: rush[0] }, { xAxis: rush[1] - 1 }]] } },
        { name: 'Demand', type: 'line', data: dem, lineStyle: { color: C.ink3, width: 1.5 }, symbol: 'none', z: 3, endLabel: { show: true, formatter: 'Demand', color: C.ink2, fontSize: 12, offset: [8, 0] },
          markPoint: { symbol: 'circle', symbolSize: 7, itemStyle: { color: C.ink3, borderColor: '#fff', borderWidth: 2 }, label: { show: true, position: 'top', color: C.ink2, fontSize: 11, formatter: `Demand peaks ${fmtHour(dk)}` }, data: [{ coord: [dk, dem[dk]] }] } },
        { name: 'Net load', type: 'line', data: net, lineStyle: { color: C.ink, width: 2.25 }, symbol: 'none', z: 4, endLabel: { show: true, formatter: 'Net load', color: C.ink, fontSize: 12, fontWeight: 600, offset: [8, 0] },
          markPoint: { symbol: 'circle', symbolSize: 8, itemStyle: { color: C.ink, borderColor: '#fff', borderWidth: 2 }, label: { show: true, position: 'left', distance: 8, color: C.ink, fontSize: 11, fontWeight: 600, formatter: `Net load peaks ${fmtHour(pk)} · ${fmt(net[pk])} MW` }, data: [{ coord: [pk, net[pk]] }] },
          markArea: { silent: true, itemStyle: { color: 'rgba(255,255,255,.4)', borderColor: C.ink3, borderWidth: 0 }, label: { show: true, position: 'insideTop', color: C.ink, fontSize: 11, fontWeight: 600, formatter: `Cleanest 8 hours ${spanLabel(clean)}` }, data: [[{ xAxis: clean[0] }, { xAxis: clean[1] - 1 }]] } },
      ],
    };
  }, [rush, clean, dem, net, sol]);
  return <EChart option={option} className="h-full w-full" label="Utah July weekday demand, net load and solar by hour" />;
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
                <rect x={LX + i * cw + 1} y={4} width={cw - 2} height={36} rx={4} fill={f}><title>{`${fmtHour(i)}: ${v == null ? '–' : Math.round(v)} g/kWh (observed)`}</title></rect>
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
  const obs: (number | null)[] = fr.observed.value;
  const maes = (['W', 'L'] as const).map((k) => fr.week_errors[k].mae.value as number);
  const option = useMemo(() => {
    const lab = hours.map((t) => fmtDate(t, { weekday: 'short', hour: 'numeric' }));
    const style: Record<string, [string, number[] | 'dotted' | 'dashed' | 'solid', number]> = { W: [C.ink3, [2, 3], 1.5], L: [C.ink2, [6, 3], 1.5] };
    return {
      grid: { left: 48, right: 16, top: 16, bottom: 24 },
      xAxis: { type: 'category', data: lab, boundaryGap: false, axisLabel: { interval: 23, formatter: (v: string) => v.split(',')[0] } },
      yAxis: { type: 'value', min: 0, max: 900, interval: 300, name: 'g/kWh', nameLocation: 'end', nameGap: 6 },
      tooltip: { trigger: 'axis', valueFormatter: (v: number) => (v == null ? '–' : `${Math.round(v)} g/kWh`) },
      series: [
        ...(['W', 'L'] as const).map((k) => ({ name: `${k} forecast`, type: 'line', data: fr.forecasts[k].value, symbol: 'none', lineStyle: { color: style[k][0], type: style[k][1], width: style[k][2] } })),
        { name: 'Observed', type: 'line', data: obs, symbol: 'none', lineStyle: { color: C.ink, width: 2 }, z: 5 },
      ],
    };
  }, [fr, hours, obs]);
  return (
    <Panel className="flex flex-col min-h-0" style={{ padding: '12px 8px 4px 16px' }}>
      <div className="flex items-baseline justify-between gap-2" style={{ paddingRight: 8 }}>
        <span className="t-15">Day-ahead forecasts catch Utah's daily swing, off by {fmt(Math.min(...maes))}–{fmt(Math.max(...maes))} g/kWh</span>
      </div>
      <div className="t-11 ink-3 flex flex-wrap gap-x-3" style={{ marginTop: 2 }}>
        <span>Replay week {fmtDate(fr.week.start, { month: 'short', day: 'numeric' })}–{fmtDate(new Date(new Date(fr.week.end).getTime() - 1).toISOString(), { month: 'short', day: 'numeric', year: 'numeric' })}, issued 10 AM the day before. Mean absolute error for the week.</span>
        <Ev e="forecast" /><Ev e="observed" /><Ev e="measured">errors measured</Ev>
      </div>
      <div className="flex gap-4 t-11 ink-2" style={{ marginTop: 4 }} aria-hidden="true">
        <span className="flex items-center gap-1"><svg width="20" height="6"><line x1="0" x2="20" y1="3" y2="3" stroke={C.ink} strokeWidth="2" /></svg>observed</span>
        <span className="flex items-center gap-1"><svg width="20" height="6"><line x1="0" x2="20" y1="3" y2="3" stroke={C.ink2} strokeWidth="1.5" strokeDasharray="6 3" /></svg>L, learned forecast</span>
        <span className="flex items-center gap-1"><svg width="20" height="6"><line x1="0" x2="20" y1="3" y2="3" stroke={C.ink3} strokeWidth="1.5" strokeDasharray="2 3" /></svg>W, weekly profile</span>
      </div>
      <EChart option={option} className="flex-1 min-h-0" testId="forecast-chart" label="Utah observed carbon intensity and the K, W and L day-ahead forecasts for the replay week" />
    </Panel>
  );
}

export function Neighbours() {
  const { data, month, hour } = useApp();
  const g = data!.grid;
  const pm = asNum(yearMean(g, 'PACE'))!;
  return (
    <Panel className="flex flex-col min-h-0">
      <div className="flex items-baseline justify-between"><span className="t-15">The same hours next door are far cleaner</span><Ev e="observed" /></div>
      <div className="flex flex-col flex-1" style={{ gap: 12, marginTop: 16 }}>
        {CORE.map((c) => {
          const ym = asNum(yearMean(g, c))!;
          return (
            <div key={c} className="grid items-center" style={{ gridTemplateColumns: '104px minmax(0,1fr) 72px', gap: 8 }}>
              <span className="t-13 fw-600 truncate">{REGION[c].name}<span className="block t-11 ink-3 fw-400">{c}</span></span>
              <Strip curve={dayCurve(g, c, month)} h={28} hour={hour} label={`${REGION[c].name} typical ${monthLabel(month)} day`} />
              <span className="text-right"><span className="t-13 fw-600 num">{fmt(ym)}</span><span className="block t-11 ink-3">{c === 'PACE' ? 'year mean' : `${pct(1 - ym / pm, 0)}% cleaner`}</span></span>
            </div>
          );
        })}
        <div className="grid t-11 ink-3" style={{ gridTemplateColumns: '104px repeat(4, 1fr) 72px', gap: 8 }}><span />{[0, 6, 12, 18].map((x) => <span key={x}>{fmtHour(x)}</span>)}<span className="text-right">g/kWh</span></div>
      </div>
    </Panel>
  );
}

export function YearHeat() {
  const { data } = useApp();
  const g = data!.grid;
  const [ref, w, h] = useWidth<HTMLDivElement>();
  const vals: (number | null)[][] = g.ci.by_ba.PACE.month_hour.value;
  const counts: number[][] = g.pace_top100_net_load.counts_month_hour.value;
  const lx = 36, top = 4, bottom = 18, cw = (w - lx) / 24, ch = (h - top - bottom) / 12;
  const hc = hourCounts(g);
  return (
    <Panel className="flex flex-col min-h-0">
      <div className="flex items-baseline justify-between gap-2"><span className="t-15">All year, the rush sits on the evening</span></div>
      <div className="t-11 ink-3 flex flex-wrap gap-x-3" style={{ marginTop: 2 }}>
        <span className="flex items-center gap-1"><svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="4.5" fill={C.rushFill} stroke={C.rush} strokeWidth="1.5" /></svg>top-100 net-load hours ({fmt(hc.reduce((a, b) => a + b, 0))})</span>
        <span>cells: carbon by month and hour</span><Ev e="observed" />
      </div>
      <div ref={ref} className="flex-1 min-h-0" style={{ marginTop: 8 }}>
        {w > 0 && h > 0 && (
          <svg width={w} height={h} role="img" aria-label="Utah carbon intensity by month and hour, with the year's top 100 net-load hours circled">
            {vals.map((row, mi) => (
              <g key={mi}>
                {mi % 2 === 0 && <text x={lx - 6} y={top + mi * ch + ch / 2 + 4} textAnchor="end" fontSize={11} fill={C.ink3}>{monthLabel(g.months[mi])}</text>}
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
    </Panel>
  );
}
