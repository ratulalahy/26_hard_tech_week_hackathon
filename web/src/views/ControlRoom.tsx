import { useEffect, useRef, useState } from 'react';
import { TestTag, testFacts } from '../components/testYear';
import { IntervalChart, Panel, PolicyTable, Strip, useWidth } from '../components/charts';
import { BudgetBar, BudgetHeadline, NoChangeNote, RemoteLine, ScenarioToggle, budgetFacts, flowOf, kindOf, savingOf, scenarioOf } from '../components/flows';
import { Ev, EvCI, Icon } from '../components/ui';
import { C, CI_MAX, CI_MID, ci2c } from '../lib/color';
import { CORE, DEADLINES_MET, DESTS, FRAME_LINE, REGION, asNum, contrast, dayCurve, headline, loadMonth, own, pname, pnote, waitPhrase, yearMean, type Dest } from '../lib/data';
import { cap, heroHeadline } from '../lib/copy';
import { useCopy } from '../lib/useCopy';
import { argmax, cleanest, rushHours, spanLabel } from '../lib/derive';
import { fmt, fmtDate, fmtHour, monthLabel, pct, pctRange } from '../lib/format';
import { useApp } from '../lib/store';
import type { Viewport } from '../lib/useViewport';
import { useViewport } from '../lib/useViewport';

export const dims = (vp: Viewport) => ({
  left: vp.w >= 1400 ? 416 : 336,
  right: vp.w >= 1600 ? 376 : 344,
  tl: vp.h >= 1000 ? 184 : 164,
});
export const controlPadding = (vp: Viewport) => {
  const d = dims(vp);
  return { top: 72 + (vp.w < 1600 ? 64 : 88), bottom: 40 + d.tl + 24, left: 16 + d.left + 32, right: 16 + d.right + 16 + 56 };
};

export function ControlRoom() {
  const vp = useViewport();
  const d = dims(vp);
  return (
    <section aria-label="Control room" className="fixed inset-0 z-10 pointer-events-none">
      <div className="pointer-events-auto absolute" style={{ top: 72, left: 16, width: d.left, bottom: 40 + d.tl + 16 }}><ResultDock compact={vp.h < 1000} /></div>
      <div className="pointer-events-auto absolute" style={{ top: 72, right: 16, width: d.right, bottom: 40 + d.tl + 16 }}><RouterDock compact={vp.h < 1000} /></div>
      <div className="pointer-events-auto absolute" style={{ left: 16, right: 16, bottom: 40, height: d.tl }}><Timeline /></div>
      <div className="pointer-events-none absolute flex justify-center" style={{ top: 72, left: 16 + d.left + 16, right: 16 + d.right + 16 }}>
        <div data-map-avoid className="pointer-events-auto panel over-map" style={{ padding: '8px 12px', borderRadius: 14 }}><ScenarioToggle /></div>
      </div>
      <MapCaption left={16 + d.left + 16} bottom={40 + d.tl + 16} />
    </section>
  );
}

function ResultDock({ compact }: { compact: boolean }) {
  const { data, hour, month, dest, arcPolicy, scenario, set } = useApp();
  const m = data!.metrics, g = data!.grid;
  const reg = own(m, 'S')!;
  const sc = scenarioOf(data!.flows, scenario);
  const f = flowOf(data!.flows, scenario, arcPolicy);
  // the hero is the selected policy's own estimate in the toggled scenario (F10), registered S by default
  const regP = own(m, arcPolicy) ?? reg;
  const hero = savingOf(f) ?? regP;
  const mob = savingOf(flowOf(data!.flows, 'mobility_le_8gpus', 'S'));
  // the test year has no scenario flows; its mobility check comes from results/test/extras.json
  const tmob = mob ? null : testFacts(data!.extras, m)?.mob ?? null;
  const pm = asNum(yearMean(g, 'PACE'))!;
  const wt = (['W_time', 'L_time'] as const).map((p) => [p, contrast(m, p)] as const);
  const nWeeks = contrast(m, 'S')!.n_weeks;
  // the headline now carries the frame line, so below 1200 px the four sites drop their day strips (the timeline below still shows Utah's)
  const strips = useViewport().h >= 1200;
  const copy = useCopy();
  return (
    <Panel over className="flex flex-col" style={{ height: '100%', padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: compact ? '12px 16px 10px' : 16 }}>
        <h1 className="t-20" style={{ margin: 0 }} data-testid="hero-title">{heroHeadline(copy, headline(m), reg)}</h1>
        <div data-testid="hero-placement" style={{ marginTop: compact ? 8 : 12 }}>
          <div className="t-11 ink-2 fw-500" data-testid="hero-kind">{sc ? `${sc.label} · ${kindOf(sc)}` : copy.validationReadings ? 'registered result' : 'registered result · test year (sealed, opened once)'}</div>
          <div key={`${scenario}-${arcPolicy}`} className="flex items-baseline gap-2 swap">
            <span className="t-hero">{pct(Math.abs(hero.v))}%</span>
            <span className="t-13 ink-2">{hero.v < 0 ? 'more' : 'less'} attributed CO₂, {pname(arcPolicy)}</span>
          </div>
          <div className="t-12 ink-2" style={{ marginTop: 4 }}>
            Its own 95% interval {pct(hero.lo)}–{pct(hero.hi)}%, vs U local (stay in Utah): same jobs, {DEADLINES_MET}{strips ? '' : '; attributed CO₂, transfer included'}.{sc && !sc.registered ? <> Registered: {pct(regP.v)}%.</> : null} <Ev e="simulated" />
          </div>
          <NoChangeNote f={f} p={arcPolicy} />
          {strips && <div className="t-11 ink-3" style={{ marginTop: 4 }}>
            Attributed operational CO₂ (EIA consumption basis, modeled){sc?.registered !== false ? `, including ${transferMWh(m, arcPolicy)} MWh of simulated transfer energy` : ', including transfer energy'}.
          </div>}
          <div className="t-12 ink-2" style={{ marginTop: 4 }} data-testid="hero-frame">{FRAME_LINE}</div>
        </div>
        <div data-testid="hero-timing" className="t-13" style={{ marginTop: compact ? 6 : 8 }}>
          Waiting for cleaner hours in Utah alone: <b className="fw-600">{waitPhrase(m)}</b>{compact ? null : <span className="t-12 ink-3"> ({wt.map(([p, c]) => c ? `${pname(p)} ${pct(c.saving.value as number)}%` : null).filter(Boolean).join(', ')})</span>}
        </div>
        {mob ? <div data-testid="hero-mobility" className="t-12 ink-2" style={{ marginTop: 4 }}>
          The cut depends on moving large multi-node jobs: {pname('S')} <b className="fw-600">{pct(reg.v)}% → {pct(mob.v)}%</b> if only jobs of 8 GPUs or fewer may move (scenario estimate). <Ev e="simulated" />
        </div> : tmob ? <div data-testid="hero-mobility" className="t-12 ink-2" style={{ marginTop: 4 }}>
          The cut depends on moving large multi-node jobs: if only jobs of 8 GPUs or fewer may move, {pname('S')}, {pname('W')} and {pname('L')} cut <b className="fw-600">{pctRange(tmob.lo, tmob.hi)}%</b> (scenario estimates). <TestTag /> <Ev e="simulated" />
        </div> : null}
      </div>
      <div style={{ padding: '0 16px 8px' }}>
        <div className="flex items-baseline justify-between t-12 ink-2" style={{ marginBottom: 4 }}>
          <span className="fw-500 whitespace-nowrap" style={{ color: C.ink }}>Saving vs U, 95% interval</span>
          <span className="t-11 ink-3 whitespace-nowrap">{fmt(nWeeks.value as number)} weeks, registered <Ev e="simulated" /></span>
        </div>
        <IntervalChart m={m} rows={['S', 'K', 'W', 'L', 'W_time', 'L_time']} stacked rowH={compact ? 24 : 26} />
      </div>
      <hr className="rule" />
      {compact ? null : (<>
      <div className="flex items-baseline justify-between" style={{ padding: '12px 16px 4px' }}>
        <span className="t-15 whitespace-nowrap">The four sites, {fmtHour(hour)}</span>
        <EvCI />
      </div>
      <ul className="flex flex-col" style={{ listStyle: 'none', margin: 0, padding: '0 8px 4px', gap: 0, overflow: 'auto', flex: 1 }}>
        {CORE.map((c) => {
          const curve = dayCurve(g, c, month);
          const ym = asNum(yearMean(g, c))!;
          const isDest = (DESTS as readonly string[]).includes(c);
          const inner = (
            <div className="grid items-center" style={{ gridTemplateColumns: '24px minmax(0, 1fr) auto', gap: '4px 8px' }}>
              <span className="grid place-items-center" style={{ width: 24, height: 24, borderRadius: 8, background: c === dest ? C.route : ci2c(curve[hour]), color: c === dest ? '#fff' : C.ink, boxShadow: 'inset 0 0 0 1px rgba(110,62,30,.12)' }}>
                <Icon name={c === dest ? 'route' : c === 'BPAT' ? 'drop' : 'bolt'} size={14} />
              </span>
              <span className="t-13 fw-600" title={`${cap(copy.yearMean)} ${fmt(ym)} g/kWh`}>{REGION[c].name} <span className="t-12 ink-3 fw-400">{c} · {c === 'PACE' ? `${copy.yearShort} ${fmt(ym)}` : `${pct(1 - ym / pm, 0)}% cleaner`}</span></span>
              <span className="t-15 num">{curve[hour] == null ? '–' : Math.round(curve[hour]!)}<span className="unit">g/kWh</span></span>
              {strips && <span />}
              {strips && <div style={{ gridColumn: '2 / 4' }}><Strip curve={curve} hour={hour} h={10} label={`${REGION[c].name} typical day carbon`} /></div>}

            </div>
          );
          return (
            <li key={c}>
              {isDest ? <button className="rowbtn" style={strips ? undefined : { padding: '4px 8px' }} aria-pressed={dest === c} onClick={() => set({ dest: c as Dest })}>{inner}</button> : <div style={{ padding: strips ? 8 : '4px 8px' }}>{inner}</div>}
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
  const { data, hour, month, arcPolicy, scenario } = useApp();
  const wk = data!.jobs.week;
  const sc = scenarioOf(data!.flows, scenario);
  return (
    <div data-map-avoid className="pointer-events-auto absolute panel over-map t-11 ink-2" style={{ left, bottom, padding: '8px 12px', borderRadius: 12, maxWidth: 440 }}>
      The four sites are coloured by carbon at {fmtHour(hour)} on a typical {monthLabel(month, true)} day <EvCI />; other regions are context only.
      Arcs are a static weekly flow, not tied to that hour: GPU-hours {pname(arcPolicy)} ran outside Utah in the replay week {weekSpan(wk)}{sc && !sc.registered ? ` (${sc.label}: ${kindOf(sc)})` : ''}, wider for more <Ev e="simulated" />. Scroll or pinch to zoom; drag to pan.
    </div>
  );
}

const weekSpan = (wk: { start: string; end: string }) => `${fmtDate(wk.start, { month: 'short', day: 'numeric' })}–${fmtDate(new Date(new Date(wk.end).getTime() - 1).toISOString(), { month: 'short', day: 'numeric', year: 'numeric' })}`;
const SHORT_NAME: Record<string, string> = { S: 'S clean-region ranking', W: 'W weekly profile', L: 'L learned model' };
/** Transfer energy of one registered policy, MWh (simulated). */
function transferMWh(m: { policies: Record<string, { metrics: { transfer_kwh: { value: number } } }> }, p: string) {
  return fmt(Math.round(m.policies[p].metrics.transfer_kwh.value / 1000));
}

export function Legend({ width, short = false }: { width?: number; short?: boolean }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const W = width ?? w;
  const n = 48;
  return (
    <div ref={ref}>
      {!short && <div className="t-11 ink-2" style={{ marginBottom: 4 }}>Carbon intensity, g CO₂/kWh. Green is cleaner, red dirtier; the midpoint is the 2024 US average. <Ev e="observed">midpoint: EIA</Ev></div>}
      {W > 0 && (
        <svg width={W} height={26} style={{ display: 'block' }} role="img" aria-label="Carbon colour scale from 0 to 750 grams per kilowatt-hour">
          {Array.from({ length: n }, (_, i) => <rect key={i} x={(i * W) / n} y={0} width={W / n + 0.6} height={8} fill={ci2c((i / (n - 1)) * CI_MAX)} />)}
          <rect x={0} y={0} width={W} height={8} rx={2} fill="none" stroke="rgba(110,62,30,.12)" />
          <line x1={(CI_MID / CI_MAX) * W} x2={(CI_MID / CI_MAX) * W} y1={-1} y2={10} stroke={C.ink} strokeWidth={1.25} />
          {[0, CI_MID, CI_MAX].map((v) => (
            <text key={v} x={Math.min(Math.max((v / CI_MAX) * W, 0), W)} y={22} fontSize={11} fill={v === CI_MID ? C.ink : C.ink3} textAnchor={v === 0 ? 'start' : v === CI_MAX ? 'end' : 'middle'}>{v === CI_MID ? `${Math.round(v)} · US avg 2024 (EIA)` : v}</text>
          ))}
        </svg>
      )}
    </div>
  );
}

function RouterDock({ compact }: { compact: boolean }) {
  const copy = useCopy();
  const { data, arcPolicy, dest, scenario, set } = useApp();
  const m = data!.metrics;
  const wk = data!.jobs.week;
  const sc = scenarioOf(data!.flows, scenario);
  const f = flowOf(data!.flows, scenario, arcPolicy);
  const arcs = f?.week_arcs ?? wk.policies[arcPolicy].arcs;
  const slots = data!.manifest.assumptions;
  const destSlots = sc && !sc.registered ? asNum(sc.knobs?.dest_slots) : asNum(slots.destination_slots.BPAT);
  const bf = budgetFacts(data!.budget, arcPolicy);
  const vpw = useViewport().w;
  return (
    <Panel over className="flex flex-col" style={{ height: '100%', padding: 0, overflow: 'hidden' }}>
      {bf ? <div style={{ padding: compact ? '12px 16px 8px' : 16, overflow: 'auto', minHeight: 0, flexShrink: 1 }}>
        <h2 className="t-15" style={{ margin: 0 }} data-testid="budget-title">Flexibility budget (registered run): {pname(bf.policy)}</h2>
        {sc && !sc.registered ? <div className="t-12 fw-500" style={{ marginTop: 2, color: C.ink }} data-testid="budget-toggle-note">The toggle does not change this bar.</div> : null}
        <div className="t-13" style={{ marginTop: 4 }}><BudgetHeadline p={arcPolicy} /></div>
        {!compact && bf ? <div className="t-12 ink-2" style={{ marginTop: 2 }}>Registered cohort, {fmt(bf.total)} MWh of execution energy, sized by energy rather than job count.</div> : null}
        <div style={{ marginTop: 8 }}><BudgetBar p={arcPolicy} testId="budget-control" /></div>
        <div className="flex gap-3 flex-wrap" style={{ marginTop: 6 }}><Ev e="simulated">outcomes, registered run</Ev><Ev e="assumed">flexible and mobile flags</Ev></div>
      </div> : <div style={{ padding: compact ? '12px 16px 8px' : 16, overflow: 'auto', minHeight: 0, flexShrink: 1 }}>
        {/* a window with no flexibility budget (the test year) keeps the policy table */}
        <h2 className="t-15" style={{ margin: 0 }}>Every policy did the same work; deadlines met by construction</h2>
        <div style={{ marginTop: 8 }}><PolicyTable m={m} compact testId="policy-table-compact" /></div>
        <div className="flex gap-3 flex-wrap" style={{ marginTop: 8 }}><Ev e="simulated">outcomes simulated</Ev><Ev e="measured">job sizes measured</Ev></div>
      </div>}
      <hr className="rule" />
      <div style={{ padding: compact ? '12px 16px' : 16, flex: compact ? 'none' : 1, minHeight: compact ? 156 : 140, overflow: 'auto' }}>
        <div className="flex items-center justify-between gap-2">
          <h2 className="t-15 whitespace-nowrap" style={{ margin: 0 }}>Where the work went</h2>
          <select className="sel" style={{ maxWidth: '55%', minWidth: 0 }} aria-label="Policy shown on the map" value={arcPolicy} onChange={(e) => set({ arcPolicy: e.target.value as 'S' | 'W' | 'L' })} title={pnote(m, arcPolicy)}>
            {(['S', 'W', 'L'] as const).map((p) => <option key={p} value={p}>{vpw < 1600 ? SHORT_NAME[p] : pname(p)}</option>)}
          </select>
        </div>
        {!compact && <div className="t-12 ink-2" style={{ marginTop: 4 }}>
          Replay week {weekSpan(wk)}{sc && !sc.registered ? `, ${kindOf(sc)}` : ''}: GPU-hours run outside Utah ({fmt(asNum(slots.home_slots) ?? 0)} GPU slots) at sites of {fmt(destSlots ?? 0)} slots each <Ev e="assumed">slots assumed</Ev> <Ev e="simulated" />
        </div>}
        <div className="flex flex-col swap" key={`${scenario}-${arcPolicy}`} style={{ marginTop: 8, gap: 2 }} data-testid="work-rows">
          {DESTS.map((dd) => {
            const a = arcs.find((x: { to: string }) => x.to === dd);
            return (
              <button key={dd} className="rowbtn flex items-baseline justify-between gap-2" style={{ padding: '6px 8px' }} aria-pressed={dest === dd} onClick={() => set({ dest: dd })}>
                <span className="t-13 fw-500 whitespace-nowrap">{REGION[dd].name} <span className="ink-3 fw-400 t-12">{dd}</span></span>
                <span className="t-13 num fw-600 whitespace-nowrap">{a ? fmt(a.gpu_h.value) : '–'}<span className="unit">GPU-h</span><span className="t-11 ink-3 fw-400"> · {a ? fmt(a.jobs.value) : 0} jobs</span></span>
              </button>
            );
          })}
        </div>
        {!compact && f ? <div className="t-12 ink-2" style={{ marginTop: 8 }}><RemoteLine f={f} p={arcPolicy} over={cap(copy.overYear)} /> <Ev e="simulated" /></div> : null}
        {!compact && !f ? <div className="t-12 ink-2" style={{ marginTop: 8 }}>
          {cap(copy.overYear)}, {pname(arcPolicy)} ran {pct(m.policies[arcPolicy].metrics.remote_energy_share.value)}% of the energy outside Utah; the ledger's broader “moved”, which also counts retiming in Utah, is {pct(m.policies[arcPolicy].metrics.moved_share_energy.value)}%. {fmt(m.policies[arcPolicy].metrics.late_jobs.value)} late jobs, {fmt(m.policies[arcPolicy].metrics.capacity_violations.value)} capacity violations. <Ev e="simulated" />
        </div> : null}
      </div>
    </Panel>
  );
}

/** Bottom timeline: Utah's weekday load for the profile's month (observed) over the typical-day carbon strip; drives the map's hour. */
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
  const jul = g.pace_july_weekday, lm = loadMonth(g);
  const dem: number[] = jul.demand_mw.value, net: number[] = jul.net_load_mw.value, sol: number[] = jul.solar_mw.value;
  const curve = dayCurve(g, 'PACE', month);
  const rush = rushHours(g), clean = cleanest(curve);
  const peak = argmax(net), dpeak = argmax(dem);
  const lx = 112, cw = w > 0 ? (w - lx - 64) / 24 : 0, X = (i: number) => lx + i * cw;
  const yR = 22, hR = 8, yL = yR + hR + 4, yC = h - 46, hC = 20, hL = Math.max(20, yC - 8 - yL), yA = h - 6;
  const mx = Math.ceil(Math.max(...dem) / 3000) * 3000;
  const ticks = Array.from({ length: mx / 3000 + 1 }, (_, k) => k * 3000);
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
            {ticks.map((v) => <g key={v}><line x1={lx} x2={X(24)} y1={Y(v)} y2={Y(v)} stroke={C.hair2} /><text x={lx - 6} y={Y(v) + 4} textAnchor="end" fontSize={11} fill={C.ink3}>{v ? `${v / 1000}k` : '0'}</text></g>)}
            <path d={`M${X(0) + cw / 2},${Y(0)} L${pts(sol)} L${X(23) + cw / 2},${Y(0)} Z`} fill={C.solar} fillOpacity={0.8} />
            <path d={`M${pts(dem)}`} fill="none" stroke={C.ink3} strokeWidth={1.25} />
            <path d={`M${pts(net)}`} fill="none" stroke={C.ink} strokeWidth={2} strokeLinejoin="round" />
            <circle cx={X(peak) + cw / 2} cy={Y(net[peak])} r={3.5} fill={C.ink} stroke="#fff" strokeWidth={1.5} />
            
            <circle cx={X(dpeak) + cw / 2} cy={Y(dem[dpeak])} r={3} fill={C.ink3} stroke="#fff" strokeWidth={1.5} />
            <text x={X(24) + 4} y={Math.min(Y(dem[23]) + 4, Y(net[23]) - 8)} fontSize={11} fill={C.ink2}>Demand</text>
            <text x={X(24) + 4} y={Math.max(Y(net[23]) + 4, Y(dem[23]) + 16)} fontSize={11} fill={C.ink} fontWeight={600}>Net load</text>
            <text x={X(13)} y={Y(sol[13] * 0.45)} textAnchor="middle" fontSize={11} fill={C.solarInk} fontWeight={600}>Solar</text>
            <text x={0} y={yL + 10} fontSize={12} fill={C.ink} fontWeight={500}>Load, MW</text>
            <text x={0} y={yL + 24} fontSize={11} fill={C.ink3}>{lm.short} weekday</text>
            <text x={0} y={yL + 38} fontSize={11} fill={C.ink3}>observed</text>
            <text x={0} y={yC + 6} fontSize={12} fill={C.ink} fontWeight={500}>Carbon, g/kWh</text>
            <text x={0} y={yC + 20} fontSize={11} fill={C.ink3}>modeled · EIA est.</text>
            {curve.map((v, i) => (
              <rect key={i} x={X(i) + 1} y={yC} width={cw - 2} height={hC} rx={3} fill={v == null ? '#fff' : ci2c(v)}>
                <title>{`${fmtHour(i)} in Utah: carbon ${v == null ? '–' : Math.round(v)} g/kWh (modeled, EIA estimate, typical ${monthLabel(month)} day); net load ${fmt(net[i])} MW (observed, ${lm.short} weekday)`}</title>
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

