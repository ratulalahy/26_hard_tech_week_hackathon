import { useEffect, useRef, useState } from 'react';
import { IntervalChart, Panel, PolicyTable, Strip, useWidth } from '../components/charts';
import { Ev, Icon } from '../components/ui';
import { C, CI_MAX, CI_MID, ci2c } from '../lib/color';
import { CORE, DESTS, REGION, asNum, dayCurve, headline, yearMean, type Dest } from '../lib/data';
import { argmax, cleanest, rushHours, spanLabel } from '../lib/derive';
import { fmt, fmtDate, fmtHour, monthLabel, pct, pctRange } from '../lib/format';
import { useApp } from '../lib/store';
import type { Viewport } from '../lib/useViewport';
import { useViewport } from '../lib/useViewport';

export const dims = (vp: Viewport) => ({
  left: vp.w >= 1600 ? 368 : 336,
  right: vp.w >= 1600 ? 376 : 344,
  tl: vp.h >= 1000 ? 184 : 164,
});
export const controlPadding = (vp: Viewport) => {
  const d = dims(vp);
  return { top: 72 + 24, bottom: 40 + d.tl + 24, left: 16 + d.left + 32, right: 16 + d.right + 16 + 56 };
};

export function ControlRoom() {
  const vp = useViewport();
  const d = dims(vp);
  return (
    <section aria-label="Control room" className="fixed inset-0 z-10 pointer-events-none">
      <div className="pointer-events-auto absolute" style={{ top: 72, left: 16, width: d.left, bottom: 40 + d.tl + 16 }}><ResultDock compact={vp.h < 1000} /></div>
      <div className="pointer-events-auto absolute" style={{ top: 72, right: 16, width: d.right, bottom: 40 + d.tl + 16 }}><RouterDock /></div>
      <div className="pointer-events-auto absolute" style={{ left: 16, right: 16, bottom: 40, height: d.tl }}><Timeline /></div>
      <MapCaption left={16 + d.left + 16} bottom={40 + d.tl + 16} />
    </section>
  );
}

function ResultDock({ compact }: { compact: boolean }) {
  const { data, hour, month, dest, set } = useApp();
  const m = data!.metrics, g = data!.grid;
  const h = headline(m);
  const pm = asNum(yearMean(g, 'PACE'))!;
  return (
    <Panel over className="flex flex-col" style={{ height: '100%', padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: 16 }}>
        <h1 className="t-20" style={{ margin: 0 }}>Moving Utah's AI jobs cuts their CO₂ by a fifth. Waiting barely helps.</h1>
        <div data-testid="hero-placement" style={{ marginTop: 12 }}>
          <div className="flex items-baseline gap-2">
            <span className="t-hero">{pctRange(h.placement.lo, h.placement.hi)}%</span>
            <span className="t-13 ink-2">less attributed CO₂</span>
          </div>
          <div className="t-12 ink-2" style={{ marginTop: 4 }}>
            Placement policies S, K, W and L vs running every job at home (U), same jobs, every deadline met. 95% intervals {pct(h.placement.ciLo)}–{pct(h.placement.ciHi)}%. <Ev e="simulated" />
          </div>
        </div>
        <div data-testid="hero-timing" className="t-13" style={{ marginTop: 8 }}>
          Waiting for cleaner hours in Utah alone: <b className="fw-600">{pctRange(h.timing.lo, h.timing.hi)}%</b> <span className="t-12 ink-3">(95% {pct(h.timing.ciLo)}–{pct(h.timing.ciHi)}%)</span> <Ev e="simulated" />
        </div>
      </div>
      <div style={{ padding: '0 16px 8px' }}>
        <div className="flex items-baseline justify-between t-12 ink-2" style={{ marginBottom: 4 }}>
          <span className="fw-500 whitespace-nowrap" style={{ color: C.ink }}>Saving vs U, 95% interval</span>
          <span className="t-11 ink-3 whitespace-nowrap">{fmt(h.nWeeks.value as number)} weeks <Ev e="simulated" /></span>
        </div>
        <IntervalChart m={m} rows={['S', 'K', 'W', 'L', 'W_time', 'L_time']} />
      </div>
      <hr className="rule" />
      {compact ? (
        <div className="t-12 ink-2" style={{ padding: '12px 16px', flex: 1 }}>
          Each region's carbon at {fmtHour(hour)} is on the map; Utah's year mean is {fmt(pm)} g/kWh, the three destinations {CORE.slice(1).map((c) => `${REGION[c].name} ${fmt(asNum(yearMean(g, c))!)}`).join(', ')}. <Ev e="observed" />
        </div>
      ) : (<>
      <div className="flex items-baseline justify-between" style={{ padding: '12px 16px 4px' }}>
        <span className="t-15">The four sites, {fmtHour(hour)}</span>
        <span className="t-11 ink-3">typical {monthLabel(month, true)} day <Ev e="observed" /></span>
      </div>
      <ul className="flex flex-col" style={{ listStyle: 'none', margin: 0, padding: '0 8px 8px', gap: 2, overflow: 'auto', flex: 1 }}>
        {CORE.map((c) => {
          const curve = dayCurve(g, c, month);
          const ym = asNum(yearMean(g, c))!;
          const isDest = (DESTS as readonly string[]).includes(c);
          const inner = (
            <div className="grid items-center" style={{ gridTemplateColumns: '24px minmax(0, 1fr) auto', gap: '4px 8px' }}>
              <span className="grid place-items-center" style={{ width: 24, height: 24, borderRadius: 8, background: c === dest ? C.route : ci2c(curve[hour]), color: c === dest ? '#fff' : C.ink, boxShadow: 'inset 0 0 0 1px rgba(110,62,30,.12)' }}>
                <Icon name={c === dest ? 'route' : c === 'BPAT' ? 'drop' : 'bolt'} size={14} />
              </span>
              <span className="t-13 fw-600">{REGION[c].name} <span className="t-12 ink-3 fw-400">{c}</span></span>
              <span className="t-15 num">{curve[hour] == null ? '–' : Math.round(curve[hour]!)}<span className="unit">g/kWh</span></span>
              {!compact && <span />}
              {!compact && <div style={{ gridColumn: '2 / 4' }}><Strip curve={curve} hour={hour} h={10} label={`${REGION[c].name} typical day carbon`} /></div>}
              {!compact && <span />}
              {!compact && <span className="t-11 ink-3" style={{ gridColumn: '2 / 4' }}>Year mean {fmt(ym)} g/kWh{c === 'PACE' ? ' · home site' : ` · ${pct(1 - ym / pm, 0)}% cleaner than Utah`}</span>}
            </div>
          );
          return (
            <li key={c}>
              {isDest ? <button className="rowbtn" aria-pressed={dest === c} onClick={() => set({ dest: c as Dest })}>{inner}</button> : <div style={{ padding: 8 }}>{inner}</div>}
            </li>
          );
        })}
      </ul>
      </>)}
      <div style={{ padding: '8px 16px 12px', borderTop: '1px solid var(--hair-2)' }}><Legend /></div>
    </Panel>
  );
}

function MapCaption({ left, bottom }: { left: number; bottom: number }) {
  const { hour, month } = useApp();
  return (
    <div className="pointer-events-auto absolute panel over-map t-11 ink-2" style={{ left, bottom, padding: '8px 12px', borderRadius: 12, maxWidth: 420 }}>
      Regions coloured by carbon at {fmtHour(hour)} on a typical {monthLabel(month, true)} day <Ev e="observed" />. Faded regions: year mean of generation fuel mix <Ev e="modeled" />. Scroll or pinch to zoom; drag to pan.
    </div>
  );
}

export function Legend({ width }: { width?: number }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const W = width ?? w;
  const n = 48;
  return (
    <div ref={ref}>
      <div className="t-11 ink-2" style={{ marginBottom: 4 }}>Carbon intensity, g CO₂/kWh. Green is cleaner, red dirtier; the midpoint is the assumed US average. <Ev e="assumed">midpoint assumed</Ev></div>
      {W > 0 && (
        <svg width={W} height={26} style={{ display: 'block' }} role="img" aria-label="Carbon colour scale from 0 to 750 grams per kilowatt-hour">
          {Array.from({ length: n }, (_, i) => <rect key={i} x={(i * W) / n} y={0} width={W / n + 0.6} height={8} fill={ci2c((i / (n - 1)) * CI_MAX)} />)}
          <rect x={0} y={0} width={W} height={8} rx={2} fill="none" stroke="rgba(110,62,30,.12)" />
          <line x1={(CI_MID / CI_MAX) * W} x2={(CI_MID / CI_MAX) * W} y1={-1} y2={10} stroke={C.ink} strokeWidth={1.25} />
          {[0, CI_MID, CI_MAX].map((v) => (
            <text key={v} x={Math.min(Math.max((v / CI_MAX) * W, 0), W)} y={22} fontSize={11} fill={v === CI_MID ? C.ink : C.ink3} textAnchor={v === 0 ? 'start' : v === CI_MAX ? 'end' : 'middle'}>{v === CI_MID ? `${v} US avg` : v}</text>
          ))}
        </svg>
      )}
    </div>
  );
}

function RouterDock() {
  const { data, arcPolicy, dest, set } = useApp();
  const m = data!.metrics, j = data!.jobs;
  const wk = j.week;
  const pol = wk.policies[arcPolicy];
  const year = m.policies[arcPolicy].metrics;
  const slots = data!.manifest.assumptions;
  return (
    <Panel over className="flex flex-col" style={{ height: '100%', padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: 16 }}>
        <h2 className="t-15" style={{ margin: 0 }}>Every policy did the same work, with no late jobs</h2>
        <div className="t-12 ink-2" style={{ marginTop: 4 }}>Attributed CO₂, {fmt(m.cohort.n_jobs.value)} jobs, {fmt(m.cohort.declared_gpu_h.value / 1e6, 2)} M GPU-h. U − policy above zero: the policy emits less.</div>
        <div style={{ marginTop: 8 }}><PolicyTable m={m} compact testId="policy-table-compact" /></div>
        <div className="flex gap-3 flex-wrap" style={{ marginTop: 8 }}><Ev e="simulated">outcomes simulated</Ev><Ev e="measured">job sizes measured</Ev></div>
      </div>
      <hr className="rule" />
      <div style={{ padding: 16, flex: 1, minHeight: 0, overflow: 'auto' }}>
        <div className="flex items-center justify-between gap-2">
          <h2 className="t-15" style={{ margin: 0 }}>Where the work went</h2>
          <div className="seg" role="group" aria-label="Policy shown on the map">
            {(['S', 'W', 'L'] as const).map((p) => <button key={p} aria-pressed={arcPolicy === p} onClick={() => set({ arcPolicy: p })}>{p}</button>)}
          </div>
        </div>
        <div className="t-12 ink-2" style={{ marginTop: 4 }}>
          Replay week {fmtDate(wk.start, { month: 'short', day: 'numeric' })}–{fmtDate(new Date(new Date(wk.end).getTime() - 1).toISOString(), { month: 'short', day: 'numeric', year: 'numeric' })}: GPU-hours policy {arcPolicy} sent from Utah ({fmt(asNum(slots.home_slots) ?? 0)} GPU slots) to sites of {fmt(asNum(slots.destination_slots.BPAT) ?? 0)} slots each <Ev e="assumed">slots assumed</Ev>. Arc width is GPU-hours. <Ev e="simulated" />
        </div>
        <div className="flex flex-col" style={{ marginTop: 8, gap: 2 }}>
          {DESTS.map((dd) => {
            const a = pol.arcs.find((x: { to: string }) => x.to === dd);
            return (
              <button key={dd} className="rowbtn flex items-baseline justify-between gap-2" style={{ padding: '6px 8px' }} aria-pressed={dest === dd} onClick={() => set({ dest: dd })}>
                <span className="t-13 fw-500 whitespace-nowrap">{REGION[dd].name} <span className="ink-3 fw-400 t-12">{dd}</span></span>
                <span className="t-13 num fw-600 whitespace-nowrap">{a ? fmt(a.gpu_h.value) : '–'}<span className="unit">GPU-h</span><span className="t-11 ink-3 fw-400"> · {a ? fmt(a.jobs.value) : 0} jobs</span></span>
              </button>
            );
          })}
        </div>
        <div className="t-12 ink-2" style={{ marginTop: 8 }}>
          Over the year, {arcPolicy} moved {pct(year.moved_share_jobs.value)}% of jobs and ran {pct(year.remote_energy_share.value)}% of energy remotely; {fmt(year.late_jobs.value)} late jobs, {fmt(year.capacity_violations.value)} capacity violations. <Ev e="simulated" />
        </div>
      </div>
    </Panel>
  );
}

/** Bottom timeline: Utah's July weekday load (observed) over the typical-day carbon strip; drives the map's hour. */
function Timeline() {
  const { data, hour, month, set } = useApp();
  const g = data!.grid;
  const [ref, w, h] = useWidth<HTMLDivElement>();
  const [playing, setPlaying] = useState(false);
  const timer = useRef<number | null>(null);
  useEffect(() => {
    if (!playing) { if (timer.current) clearInterval(timer.current); return; }
    timer.current = window.setInterval(() => set({ hour: (useApp.getState().hour + 1) % 24 }), 700);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [playing, set]);
  const jul = g.pace_july_weekday;
  const dem: number[] = jul.demand_mw.value, net: number[] = jul.net_load_mw.value, sol: number[] = jul.solar_mw.value;
  const curve = dayCurve(g, 'PACE', month);
  const rush = rushHours(g), clean = cleanest(curve);
  const peak = argmax(net), dpeak = argmax(dem);
  const lx = 104, cw = w > 0 ? (w - lx - 64) / 24 : 0, X = (i: number) => lx + i * cw;
  const yR = 22, hR = 8, yL = yR + hR + 4, yC = h - 46, hC = 20, hL = Math.max(20, yC - 8 - yL), yA = h - 6;
  const mx = Math.ceil(Math.max(...dem) / 1000) * 1000;
  const Y = (v: number) => yL + hL - (Math.max(0, v) / mx) * hL;
  const pts = (a: number[]) => a.map((v, i) => `${X(i) + cw / 2},${Y(v)}`).join(' L');
  const pick = (clientX: number) => { const r = ref.current!.getBoundingClientRect(); set({ hour: Math.max(0, Math.min(23, Math.floor((clientX - r.left - lx) / cw))) }); };
  const drag = useRef(false);
  return (
    <Panel over className="flex" style={{ height: '100%', padding: '8px 16px 8px 8px', gap: 8 }}>
      <div className="flex flex-col items-center justify-center" style={{ width: 88, gap: 8, borderRight: '1px solid var(--hair-2)', paddingRight: 8 }}>
        <button className="iconbtn" style={{ width: 40, height: 40, borderRadius: 20 }} aria-label={playing ? 'Pause the day' : 'Play the day'} onClick={() => setPlaying(!playing)}><Icon name={playing ? 'pause' : 'play'} /></button>
        <div className="t-15 num" aria-live="polite">{fmtHour(hour)}</div>
        <div className="t-11 ink-3 text-center">Utah, {monthLabel(month)}<br />Denver time</div>
      </div>
      <div ref={ref} className="relative flex-1 min-w-0" style={{ cursor: 'ew-resize', touchAction: 'none' }}
        role="slider" tabIndex={0} aria-label="Hour of day" aria-valuemin={0} aria-valuemax={23} aria-valuenow={hour} aria-valuetext={fmtHour(hour)}
        onPointerDown={(e) => { drag.current = true; (e.target as Element).setPointerCapture?.(e.pointerId); pick(e.clientX); }}
        onPointerMove={(e) => drag.current && pick(e.clientX)} onPointerUp={() => (drag.current = false)}
        onKeyDown={(e) => { if (e.key === 'ArrowRight') set({ hour: (hour + 1) % 24 }); if (e.key === 'ArrowLeft') set({ hour: (hour + 23) % 24 }); }}>
        {w > 0 && h > 0 && (
          <svg width={w} height={h} style={{ position: 'absolute', inset: 0 }}>
            <defs>
              <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill={C.rushFill} fillOpacity=".6" /><line x1="0" y1="0" x2="0" y2="6" stroke={C.rush} strokeWidth="1.2" strokeOpacity=".7" /></pattern>
            </defs>
            <rect x={X(rush[0])} y={yR} width={cw * (rush[1] - rush[0])} height={yC + hC - yR} rx={4} fill={C.rushFill} fillOpacity={0.3} />
            <rect x={X(rush[0]) + 1} y={yR} width={cw * (rush[1] - rush[0]) - 2} height={hR} rx={3} fill="url(#hatch)" />
            <text x={X(rush[0]) + (cw * (rush[1] - rush[0])) / 2} y={yR - 5} textAnchor="middle" fontSize={11} fill={C.ink} fontWeight={600}>Rush {spanLabel(rush)} · net-load peak {fmtHour(peak)}, {fmt(net[peak])} MW</text>
            <path d={`M${X(clean[0]) + 2},${yR + hR - 1} v-5 H${X(clean[1]) - 2} v5`} fill="none" stroke={C.ink3} strokeWidth={1} />
            <text x={X((clean[0] + clean[1]) / 2)} y={yR - 5} textAnchor="middle" fontSize={11} fill={C.ink} fontWeight={600}>Cleanest 8 hours {spanLabel(clean)}</text>
            {[0, mx / 2, mx].map((v) => <line key={v} x1={lx} x2={X(24)} y1={Y(v)} y2={Y(v)} stroke={C.hair2} />)}
            <path d={`M${X(0) + cw / 2},${Y(0)} L${pts(sol)} L${X(23) + cw / 2},${Y(0)} Z`} fill={C.solar} fillOpacity={0.8} />
            <path d={`M${pts(dem)}`} fill="none" stroke={C.ink3} strokeWidth={1.25} />
            <path d={`M${pts(net)}`} fill="none" stroke={C.ink} strokeWidth={2} strokeLinejoin="round" />
            <circle cx={X(peak) + cw / 2} cy={Y(net[peak])} r={3.5} fill={C.ink} stroke="#fff" strokeWidth={1.5} />
            
            <circle cx={X(dpeak) + cw / 2} cy={Y(dem[dpeak])} r={3} fill={C.ink3} stroke="#fff" strokeWidth={1.5} />
            <text x={X(24) + 4} y={Math.min(Y(dem[23]) + 4, Y(net[23]) - 8)} fontSize={11} fill={C.ink2}>Demand</text>
            <text x={X(24) + 4} y={Math.max(Y(net[23]) + 4, Y(dem[23]) + 16)} fontSize={11} fill={C.ink} fontWeight={600}>Net load</text>
            <text x={X(13)} y={Y(sol[13] * 0.45)} textAnchor="middle" fontSize={11} fill={C.solarInk} fontWeight={600}>Solar</text>
            <text x={lx - 12} y={yL + 10} textAnchor="end" fontSize={12} fill={C.ink} fontWeight={500}>Load</text>
            <text x={lx - 12} y={yL + 24} textAnchor="end" fontSize={11} fill={C.ink3}>MW · July weekday</text>
            <text x={lx - 12} y={yL + 38} textAnchor="end" fontSize={11} fill={C.ink3}>observed</text>
            <text x={lx - 12} y={yC + 9} textAnchor="end" fontSize={12} fill={C.ink} fontWeight={500}>Carbon</text>
            <text x={lx - 12} y={yC + 22} textAnchor="end" fontSize={11} fill={C.ink3}>g/kWh · observed</text>
            {curve.map((v, i) => (
              <rect key={i} x={X(i) + 1} y={yC} width={cw - 2} height={hC} rx={3} fill={v == null ? '#fff' : ci2c(v)}>
                <title>{`${fmtHour(i)} in Utah: carbon ${v == null ? '–' : Math.round(v)} g/kWh (observed, typical ${monthLabel(month)} day); net load ${fmt(net[i])} MW (observed, July weekday)`}</title>
              </rect>
            ))}
            {Array.from({ length: 8 }, (_, k) => k * 3).map((i) => <text key={i} x={X(i) + cw / 2} y={yA} textAnchor="middle" fontSize={11} fill={C.ink3}>{fmtHour(i)}</text>)}
            <line x1={X(hour) + cw / 2} x2={X(hour) + cw / 2} y1={yR} y2={yC + hC + 4} stroke={C.ink} strokeWidth={1.25} />
            <circle cx={X(hour) + cw / 2} cy={Y(net[hour])} r={4} fill="#fff" stroke={C.ink} strokeWidth={1.75} />
          </svg>
        )}
      </div>
    </Panel>
  );
}

