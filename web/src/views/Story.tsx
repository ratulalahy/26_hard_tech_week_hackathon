import { useEffect, useMemo, useRef } from 'react';
import { IntervalChart, Panel } from '../components/charts';
import { CONSUMPTION_CHECKS, PHRASE, extRows, listJoin, placementSpan } from '../components/extensions';
import { BudgetBar, BudgetHeadline, NoChangeNote, ScenarioToggle, arcsOf, budgetFacts, flowOf, kindOf, savingOf, scenarioOf } from '../components/flows';
import { ImportChart, StorageCurve, hourSpans, storageFacts } from '../components/storage';
import { Ev, EvCI, Icon } from '../components/ui';
import { cap } from '../lib/copy';
import { useCopy } from '../lib/useCopy';
import { DEADLINES_MET, DESTS, FRAME_LINE, REGION, asNum, dayCurve, loadMonth, own, plainLimitations, pname, waitPhrase, type Core, type Json } from '../lib/data';
import { argmax, cleanest, rushHours, spanLabel } from '../lib/derive';
import { fmt, fmtDate, fmtHour, monthLabel, pct, pctRange, sig2 } from '../lib/format';
import { useViewport } from '../lib/useViewport';
import { initialStep, useApp } from '../lib/store';
import { WestMap, type ArcSpec } from '../map/WestMap';
import { CarbonRibbon, LoadChart, YearHeat } from './Ribbon';

/** Six beats in the D-064 demo order, about 45 s each, matching the spoken script (docs/pitch/narrative.md):
 * one job (in Utah's evening rush), stay, wait or move, the aggregate, lock large jobs to Utah (the
 * control-room toggle), move what you can and store for what you can't (T10b: storage and the site-power
 * curve), and the evidence. Tables, policy letters and
 * long prose live in the method drawer (F18). The visual on the left follows the step in view; #story-N deep-links. */
export function Story() {
  const { data, step, month, scenario, arcPolicy, set } = useApp();
  const m = data!.metrics, g = data!.grid, wl = data!.workload;
  const copy = useCopy();
  const curve = dayCurve(g, 'PACE', month);
  const rush = rushHours(g), clean = cleanest(curve);
  const jul = g.pace_july_weekday, lm = loadMonth(g);
  const net: number[] = jul.net_load_mw.value;
  const k: number = g.pace_top100_net_load.k.value;
  const cm: number[][] = g.pace_top100_net_load.counts_month_hour.value;
  const hotMonths = g.months.filter((_: string, i: number) => cm[i].some((c) => c > 0));
  const mName = (ym: string) => monthLabel(ym, true).split(' ')[0];
  const monthSpan = hotMonths.length ? (hotMonths.length === 1 ? mName(hotMonths[0]) : `${mName(hotMonths[0])}–${mName(hotMonths[hotMonths.length - 1])}`) : '';
  // F16: where S's remote execution energy ran over the year
  const byS = m.policies.S.metrics.execution_kwh_by_site as Record<string, { value: number }>;
  const remote = DESTS.map((d) => [d, byS?.[d]?.value ?? 0] as const);
  const remoteTot = remote.reduce((a, [, v]) => a + v, 0) || 1;
  const topDest = [...remote].sort((a, b) => b[1] - a[1])[0];

  const box = useRef<HTMLDivElement>(null);
  const ij: Json = data!.jobs.illustrative_job;
  const lit: Json = data!.jobs.illustrative_job_literal;
  const dur = (sec: number) => (sec < 3600 ? `${fmt(sec / 60, 1)} minutes` : `${fmt(sec / 3600, 1)} hours`);
  useEffect(() => {
    const st = initialStep ?? null;
    if (st && box.current) { const el = box.current.querySelector<HTMLElement>(`[data-step="${st}"]`); if (el) box.current.scrollTop = el.offsetTop - (box.current.clientHeight - el.offsetHeight) / 2; }
    const io = new IntersectionObserver((es) => {
      for (const e of es) if (e.isIntersecting) set({ step: Number((e.target as HTMLElement).dataset.step) });
    }, { root: box.current, rootMargin: '-45% 0px -45% 0px' });
    box.current?.querySelectorAll('[data-step]').forEach((s) => io.observe(s));
    return () => io.disconnect();
  }, [set]);

  const sOwn = own(m, 'S')!;
  const top1 = wl.top.find((t: Json) => Math.abs(t.fraction.value - 0.01) < 1e-9) ?? wl.top[1];
  const xr = extRows(m, data!.ext), span = placementSpan(xr, CONSUMPTION_CHECKS);
  const spanProd = placementSpan(xr, ['production']);
  const keptRun = xr.filter((r) => CONSUMPTION_CHECKS.includes(r.id) && r.status === 'ok');
  const xRun = xr.filter((r) => r.group !== 'registered' && r.status === 'ok'), xMiss = xr.filter((r) => r.status !== 'ok');
  const allOnTime = xRun.every((r) => r.late == null || r.late === 0);
  // beat 4 reads the shared toggle (D-064): the mobility scenario is the comparison it is built around
  const mobF = flowOf(data!.flows, 'mobility_le_8gpus', 'S'), mob = savingOf(mobF);
  const sc = scenarioOf(data!.flows, scenario), shown = savingOf(flowOf(data!.flows, scenario, arcPolicy));
  const bf = budgetFacts(data!.budget, 'S');
  const slots = asNum(data!.manifest.assumptions.home_slots) ?? 0;
  const sto = data!.storage, sf = sto ? storageFacts(sto) : null;
  const steps: { t: string; body: React.ReactNode; ev: React.ReactNode }[] = [
    {
      t: "One job, in Utah's evening rush",
      body: <>This is PACE, the balancing area serving much of Utah. On a {lm.short} weekday demand peaks at {fmtHour(argmax(jul.demand_mw.value))}; then, as solar fades, net load, the load the rest of the fleet must carry, keeps climbing to {fmtHour(argmax(net))} ({fmt(net[argmax(net)])} MW). {cap(copy.allYear)}, the {fmt(k)} highest net-load hours fall on {monthSpan} evenings, mostly {spanLabel(rush)}; the cleanest hours are {spanLabel(clean)}, while the sun is up. Picture a hypothetical {fmt(slots)}-GPU AI cluster here, and one of its jobs arriving.</>,
      ev: <><Ev e="observed">load: EIA-930</Ev><EvCI /><Ev e="assumed">cluster size</Ev></>,
    },
    {
      t: 'Stay, wait or move',
      body: <>A {fmt(ij.gpus.value)}-GPU {ij.job_type} job of {dur(ij.declared_duration_s.value)} ({fmt(ij.declared_gpu_h.value, ij.declared_gpu_h.value < 1 ? 2 : 1)} GPU-h). It may start up to {fmt(ij.max_delay_s.value / 3600)} h late, which buys little against a run this long. Moving it adds a transfer delay but lands it on a cleaner grid. Moving means placing a job that has not started at another site with spare GPUs; nothing migrates mid-run.{ij.disclosure ? <details className="t-12 ink-3" style={{ marginTop: 8 }}><summary className="cursor-pointer fw-500">How this job was chosen</summary><span>A rule fixed before its outcome was seen: the GPU-hour-weighted median of the eligible flexible jobs (the registered count-median job runs only {dur(lit.declared_duration_s.value)}). {ij.disclosure}</span></details> : null}</>,
      ev: <><Ev e="measured">job size</Ev><Ev e="modeled">option CO₂</Ev><Ev e="simulated">placements</Ev></>,
    },
    {
      t: copy.validationReadings ? 'The whole year: a simple ranking does well' : `${cap(copy.wholeYear)}: the aggregate`,
      body: <span data-testid="story-result">{copy.over}, {pname('S')} {sOwn.v < 0 ? 'raised' : 'cut'} attributed CO₂ by <b className="fw-600">{pct(Math.abs(sOwn.v))}%</b> (its own 95% interval {pct(sOwn.lo)}–{pct(sOwn.hi)}%) against U local (stay in Utah), with {DEADLINES_MET} and the same declared work. Waiting in Utah alone cut {waitPhrase(m)}. Compute follows cleaner power: {pct(topDest[1] / remoteTot, 0)}% of the energy S ran outside Utah ran in {REGION[topDest[0]].name === 'Northwest hydro' ? 'the Northwest' : REGION[topDest[0]].name}.{copy.validationReadings ? ' We found no demonstrated aggregate benefit from dynamic search in this replay; the forecast-driven policies land beside S.' : ''}<span className="block t-12 ink-3" style={{ marginTop: 8 }} data-testid="story-frame">{FRAME_LINE}</span></span>,
      ev: <><Ev e="simulated">{fmt(m.cohort.n_jobs.value)} jobs, 95% intervals</Ev><button className="btn" onClick={() => set({ drawer: true })}><Icon name="doc" />Every policy, in the method drawer</button></>,
    },
    {
      t: 'Lock large jobs to Utah',
      body: <span data-testid="story-lock">The largest {pct(top1.fraction.value, 0)}% of jobs use {pct(top1.energy_share.value, 0)}% of the energy. {mob && mobF ? <>If only jobs of 8 GPUs or fewer may move, {pname('S')}'s saving falls from {pct(sOwn.v)}% to <b className="fw-600">{pct(mob.v)}%</b> ({pct(mob.lo)}–{pct(mob.hi)}%, a scenario estimate), and only {pct(mobF.remote_execution_share.value, 1)}% of the execution energy runs outside Utah. </> : null}{bf ? <><BudgetHeadline p="S" /> </> : null}{!data!.flows && own(m, arcPolicy) ? <span data-testid="story-lock-own">{copy.over}, {pname(arcPolicy)} {own(m, arcPolicy)!.v < 0 ? 'raised' : 'cut'} attributed CO₂ by {pct(Math.abs(own(m, arcPolicy)!.v))}% (its own 95% interval {pct(own(m, arcPolicy)!.lo)}–{pct(own(m, arcPolicy)!.hi)}%); the mobility and capacity scenarios are not shown for this window. </span> : null}Whether large training jobs can move is the lever; in this study it is an assumption, not a measurement.{sc && shown ? <span className="block t-12 ink-2" style={{ marginTop: 8 }} data-testid="story-lock-shown">Shown: {sc.label}, {kindOf(sc)}: {pname(arcPolicy)} {pct(shown.v)}% ({pct(shown.lo)}–{pct(shown.hi)}%).</span> : null}</span>,
      ev: data!.flows ? <><Ev e="simulated">scenario runs, validation</Ev><Ev e="assumed">mobility rule</Ev></> : <Ev e="measured">job sizes</Ev>,
    },
    {
      t: "Move what you can, store for what you can't",
      body: sf ? <span data-testid="story-storage">Moving cuts {pct(sOwn.v)}% ({pname('S')}), but only if large multi-node jobs can move; {mob ? <>if only jobs of 8 GPUs or fewer may, it falls to {pct(mob.v)}% (a scenario estimate)</> : 'the small-jobs-only check did not run'}. For work that stays, a battery can shift its energy instead. <b className="fw-600" data-testid="storage-headline">{/^(8|11|18)/.test(String(sf.E)) ? 'An' : 'A'} {fmt(sf.E)} MWh, {fmt(sf.P)} MW battery cuts the Utah cluster's CO₂ by {pct(sf.cutA, 1)}%</b> on a fixed daily schedule; charging is limited to the roughly {fmt(sf.headroomLo, 1)}–{fmt(sf.headroomMid, 1)} MW the site connection leaves free. <span data-testid="storage-combined">Moving the small jobs and storing for the big ones cuts <b className="fw-600">{pct(sf.moveStoreA, 1)}%</b> against {pname('U')}.</span> <b className="fw-600 block" style={{ marginTop: 8 }} data-testid="storage-skeptic">On a flat marginal basis it may add about {sig2(sf.flatAddT)} t: storage only helps if charging carbon ÷ η &lt; displaced carbon.</b></span> : <>{copy.line}</>,
      ev: !sf ? <Ev e="assumed">illustrative</Ev> : <><span className="chip-neutral">illustrative · not the registered result</span><EvCI /><Ev e="simulated">dispatch</Ev><Ev e="assumed">battery, schedule</Ev><button className="btn" onClick={() => set({ drawer: true })}><Icon name="doc" />Method &amp; evidence</button></>,
    },
    {
      t: 'The evidence',
      body: <>This is a simulated scheduling scenario on EIA's estimated emissions, with jobs running exactly as long as declared.{span ? <span data-testid="story-checks"> We checked it {xRun.length} more ways. {listJoin(keptRun.map((r) => PHRASE[r.id] ?? r.label)).replace(/^./, (c) => c.toUpperCase())}, {pname('S')}, {pname('W')} and {pname('L')} still cut {pctRange(span[0], span[1])}%: scenario estimates, one-axis changes, not a confidence interval.{spanProd ? ` On production-basis carbon the cut is ${pctRange(spanProd[0], spanProd[1])}%; production basis flatters hydro-heavy destinations.` : ''}{allOnTime ? ' No job was late in any run.' : ''}{xMiss.length ? ` ${xMiss.length} more check${xMiss.length > 1 ? 's' : ''} did not run (${xMiss[0].reason}).` : ''}</span> : null} The full table, every assumption and the run behind each number are in the method drawer. {copy.line}</>,
      ev: <><Ev e="simulated">checks</Ev><Ev e="assumed">settings</Ev><button className="btn" onClick={() => set({ drawer: true })}><Icon name="doc" />Method &amp; evidence</button></>,
    },
  ];
  return (
    <section aria-label="Story" className="fixed z-10" style={{ top: 72, left: 0, right: 0, bottom: 28 }}>
      <div ref={box} className="h-full overflow-y-auto" style={{ scrollBehavior: 'smooth' }}>
        <div className="grid" style={{ gridTemplateColumns: 'minmax(0,1.6fr) minmax(340px,1fr)', gap: 16, padding: '0 16px 0 16px' }}>
          <div className="sticky" style={{ top: 0, height: 'calc(100vh - 72px - 28px - 16px)' }}>
            <Visual step={step} rush={rush} clean={clean} curve={curve} />
          </div>
          <div style={{ paddingBottom: '20vh' }}>
            {steps.map((s, i) => (
              <div key={i} id={`story-${i + 1}`} data-step={i + 1} className="flex flex-col justify-start" style={{ minHeight: 'calc(100vh - 100px)', paddingTop: 0 }}>
                <Panel style={{ opacity: step === i + 1 ? 1 : 0.55, transition: 'opacity 160ms var(--ease)' }}>
                  <h2 className="t-20" style={{ margin: 0 }}>{s.t}</h2>
                  <p className="t-13 ink-2" style={{ margin: '8px 0 0', maxWidth: '62ch' }}>{s.body}</p>
                  <div className="flex flex-wrap gap-3 items-center" style={{ marginTop: 12 }}>{s.ev}<span className="t-11 ink-3 ml-auto">{i + 1} of {steps.length}</span></div>
                </Panel>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

const fill = (n: React.ReactNode) => <div className="grid h-full" style={{ gridTemplateRows: 'minmax(0,1fr)' }}>{n}</div>;

function Visual({ step, rush, clean, curve }: { step: number; rush: [number, number]; clean: [number, number]; curve: (number | null)[] }) {
  const { data } = useApp();
  const jul = data!.grid.pace_july_weekday, lm = loadMonth(data!.grid);
  if (step === 2) return <JobCard />;
  if (step === 3) return <Count />;
  if (step === 4) return <LockLarge />;
  if (step === 5) return <StorageBeat />;
  if (step === 6) return <Limits />;
  return (
    <div className="grid h-full" style={{ gridTemplateRows: 'minmax(0,1.4fr) minmax(0,1fr)', gap: 16 }}>
      <Panel className="flex flex-col min-h-0" style={{ padding: '12px 0 8px' }}>
        <div className="flex items-baseline justify-between" style={{ padding: '0 16px' }}>
          <span className="t-15">Utah (PACE), a {lm.short} weekday: load in MW, carbon below</span><Ev e="observed">load</Ev>
        </div>
        <div className="flex-1 min-h-0"><LoadChart rush={rush} clean={clean} dem={jul.demand_mw.value} net={jul.net_load_mw.value} sol={jul.solar_mw.value} month={lm.short} /></div>
        <CarbonRibbon curve={curve} />
      </Panel>
      {fill(<YearHeat />)}
    </div>
  );
}

function JobCard() {
  const { data } = useApp();
  const m = data!.metrics;
  const ij: Json = data!.jobs.illustrative_job;
  const acts: Json[] = ij.available_actions;
  const stay = acts.find((a) => a.kind === 'stay');
  const pl = ij.placements as Record<string, Json>;
  return (
    <Panel className="flex flex-col" style={{ gap: 16, maxHeight: '100%', overflow: 'auto' }}>
      <div className="flex items-baseline justify-between"><span className="t-15">Job {ij.job_uid}: its options</span><Ev e="modeled">option CO₂</Ev></div>
      <table className="tbl">
        <thead><tr><th>Option</th><th>Starts (Denver)</th><th>Start delay (transfer)</th><th>CO₂ <span className="fw-400">kg</span></th><th>vs staying</th></tr></thead>
        <tbody>
          {acts.map((a) => (
            <tr key={a.site}>
              <td>{a.kind === 'stay' ? 'Stay in Utah' : `Move to ${REGION[a.site as Core]?.name ?? a.site}`} <span className="ink-3">{a.site}</span></td>
              <td>{fmtDate(a.start, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</td>
              <td>{fmt((asNum(a.wait_s) ?? 0) / 60)} min</td>
              <td>{fmt(a.co2_kg.value, a.co2_kg.value < 1 ? 3 : 1)}</td>
              <td>{a.kind === 'stay' ? '–' : `${pct(1 - a.co2_kg.value / stay.co2_kg.value, 0)}% less`}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="t-12 ink-3">A move includes {fmt((asNum(data!.manifest.assumptions.transfer_time_s) ?? 0) / 60)} minutes of transfer and its energy. <Ev e="assumed">transfer</Ev></div>
      <hr className="rule" />
      <div className="flex items-baseline justify-between"><span className="t-15">Where each policy put it</span><Ev e="simulated" /></div>
      <table className="tbl">
        <thead><tr><th>Policy</th><th>Decision</th><th>Starts (Denver)</th><th>CO₂ <span className="fw-400">kg</span></th></tr></thead>
        <tbody>
          {Object.keys(pl).map((p) => {
            const v = pl[p];
            return (
              <tr key={p}>
                <td title={m.policies?.[p]?.note}>{pname(p)}</td>
                <td>{v.site === 'PACE' ? (v.moved ? 'waited in Utah' : 'stayed in Utah') : `moved to ${REGION[v.site as Core]?.name ?? v.site}`}</td>
                <td>{v.start ? fmtDate(v.start, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '–'}</td>
                <td>{fmt(v.co2_kg.value, v.co2_kg.value < 1 ? 3 : 1)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}

/** Beat 4: the toggle, its scenario's replay-week arcs and destination rows, and the registered flexibility budget. */
function LockLarge() {
  const { data, hour, month, scenario, arcPolicy, dest } = useApp();
  const g = data!.grid;
  const sc = scenarioOf(data!.flows, scenario);
  const f = flowOf(data!.flows, scenario, arcPolicy) ?? { week_arcs: data!.jobs.week.policies[arcPolicy].arcs };
  const ci = useMemo(() => Object.fromEntries((['PACE', 'BPAT', 'CISO', 'NEVP'] as Core[]).map((c) => [c, dayCurve(g, c, month)[hour]])), [g, month, hour]);
  const context = useMemo(() => Object.fromEntries(Object.entries(g.context_year_mean_ci.by_ba).map(([k, e]) => [k, asNum(e as never)])), [g]);
  const arcs = useMemo<ArcSpec[]>(() => arcsOf(f, dest), [f, dest]);
  const shown = savingOf(flowOf(data!.flows, scenario, arcPolicy));
  const tight = useViewport().h < 1000;
  return (
    <div className="grid h-full" style={{ gridTemplateRows: 'auto minmax(0,1fr) auto', gap: tight ? 12 : 16 }}>
      <Panel style={{ padding: '10px 12px' }}><ScenarioToggle /></Panel>
      <Panel className="relative overflow-hidden" style={{ padding: 0 }}>
        <WestMap id="map-story" variant="inset" interactive={false} ci={ci} context={context} hourLabel={fmtHour(hour)} arcs={arcs}
          bounds={[[-124.6, 31.8], [-104.0, 48.9]]} padding={{ top: 72, bottom: 16, left: 150, right: 120 }} />
        <div className="absolute flex items-baseline justify-between gap-2" style={{ left: 16, right: 16, top: 16 }}>
          <span className="t-15 swap" key={`${scenario}-${arcPolicy}`}>{pname(arcPolicy)}: {shown ? `${pct(Math.abs(shown.v))}% ${shown.v < 0 ? 'more' : 'less'} CO₂` : 'saving not run'} · {sc ? kindOf(sc) : 'registered result'}</span>
          <Ev e="simulated" />
        </div>
        <div className="absolute panel over-map" style={{ left: 16, right: 16, top: 60, padding: '0 10px', borderRadius: 10, display: flowOf(data!.flows, scenario, arcPolicy)?.remote_execution_share.value === 0 && flowOf(data!.flows, scenario, arcPolicy)?.retimed_home_execution_share.value === 0 ? 'block' : 'none' }}>
          <NoChangeNote f={flowOf(data!.flows, scenario, arcPolicy)} p={arcPolicy} testId="story-nochange" />
        </div>
        <div className="absolute t-11 ink-2" style={{ left: 16, top: 40, right: 16 }}>Arcs: GPU-hours run outside Utah, replay week {fmtDate(data!.jobs.week.start, { month: 'short', day: 'numeric' })}–{fmtDate(new Date(new Date(data!.jobs.week.end).getTime() - 1).toISOString(), { day: 'numeric' })}, {fmtDate(data!.jobs.week.start, { year: 'numeric' })}, a static weekly flow · Regions: typical {monthLabel(month, true).split(' ')[0]} day, {fmtHour(hour)} <EvCI /></div>
        <div className="absolute grid t-12 swap" key={`r-${scenario}-${arcPolicy}`} style={{ left: 16, right: 16, bottom: 12, gridTemplateColumns: 'repeat(3, minmax(0,1fr))', gap: 12 }} data-testid="story-work-rows">
          {DESTS.map((d) => { const a = (f.week_arcs as Json[]).find((x) => x.to === d); return (
            <div key={d} className="panel over-map" style={{ padding: '6px 10px', borderRadius: 10 }}><div className="t-11 ink-3">{REGION[d].name} · {d}</div><div className="t-15 num">{a ? fmt(a.gpu_h.value) : 0}<span className="unit">GPU-h</span> <span className="t-11 ink-3 fw-400">{a ? fmt(a.jobs.value) : 0} jobs</span></div></div>
          ); })}
        </div>
      </Panel>
      <Panel style={{ padding: tight ? 12 : 16 }}>
        <div className="flex items-baseline justify-between gap-2"><span className="t-15">Flexibility budget (registered run): {pname('S')}{sc && !sc.registered ? <span className="t-12 fw-500" data-testid="story-budget-toggle-note"> · the toggle does not change this bar</span> : null}</span><span className="flex gap-2"><Ev e="simulated" /><Ev e="assumed">flags</Ev></span></div>
        <div className="t-13" style={{ margin: '4px 0 8px' }}><BudgetHeadline p="S" /></div>
        <BudgetBar p="S" rows={!tight} testId="budget-story" />
      </Panel>
    </div>
  );
}

/** Beat 5 (T10b): move what you can, store for what you can't. */
function StorageBeat() {
  const { data } = useApp();
  const sto = data!.storage;
  if (!sto) return <Panel><span className="t-13 ink-3">The storage illustration is not shown for this window.</span></Panel>;
  const f = storageFacts(sto);
  return (
    <div className="grid h-full" style={{ gridTemplateRows: 'minmax(0,1.15fr) minmax(0,1fr)', gap: 16 }}>
      <Panel className="flex flex-col min-h-0" style={{ gap: 8 }}>
        <div className="flex items-baseline justify-between gap-2"><span className="t-15">Utah cluster's CO₂ change by battery size, over the validation window (Nov 2024–Oct 2025)</span><Ev e="simulated" /></div>
        <div className="flex-1 min-h-0" style={{ minHeight: 160 }}><StorageCurve s={sto} /></div>
        <div className="t-12 ink-3">
          Every job in Utah ({pname('U')}), {pct(f.eta, 0)}% round trip. Solid: a fixed daily schedule set from 2022–24 data; it levels off near {fmt(f.plateau)} MWh ({pct(f.cutAplateau, 1)}%) because charging must fit under the site connection{f.sensCutA != null ? ` (+25% connection: ${pct(f.sensCutA, 1)}% at ${fmt(f.E)} MWh)` : ''}. Dashed: a hindsight heuristic that sees each day's actual carbon in advance, one possible plan, not a limit ({pct(f.cutB, 1)}%). Dotted: the same fixed schedule on a flat marginal factor, a threshold scenario. <Ev e="assumed">η, size</Ev>
        </div>
      </Panel>
      <Panel className="flex flex-col min-h-0" style={{ gap: 8 }}>
        <div className="flex items-baseline justify-between gap-2"><span className="t-15">Utah cluster's grid import, a typical day, {fmt(f.E)} MWh / {fmt(f.P)} MW</span><Ev e="simulated" /></div>
        <div className="flex-1 min-h-0" style={{ minHeight: 140 }}><ImportChart s={sto} /></div>
        <div className="t-12 ink-3">
          Charge {hourSpans(f.charge).join(', ')} (outlined), discharge {hourSpans(f.discharge).join(', ')} (shaded), energy held between (teal). Charging adds {fmt(f.rebound, 2)} MW at midday; Utah's rush hours fall mostly near 8 PM, so this carbon schedule trims them by only {fmt(f.rushBefore - f.rushAfter, 2)} MW. Scale: one 2,288-GPU cluster, about {fmt(f.peakBefore, 1)} MW at most; Utah's peak net load is about {fmt(Math.round(f.peakNet / 100) * 100)} MW. Peak relief by the router is in the method drawer. {sto.power_quality}
        </div>
      </Panel>
    </div>
  );
}

function Count() {
  const { data } = useApp();
  const m = data!.metrics;
  const tight = useViewport().h < 1000;
  return (
    <Panel className={`flex flex-col ${tight ? 'tight' : ''}`} style={{ gap: tight ? 8 : 12, maxHeight: '100%', overflow: 'auto' }}>
      <span className="t-15">Saving in attributed CO₂ vs U local (stay in Utah), each policy's own 95% interval</span>
      <IntervalChart m={m} rows={['S', 'K', 'W', 'L', 'G', 'H', 'W_time', 'L_time']} rowH={tight ? 26 : 34} />
      <div className="t-12 ink-3">Filled dots: the four placement policies, {pname('S')} first. Open dots: {pname('G')}, the dashed {pname('H')}, and the two wait-only runs. The full policy table is in the method drawer. <Ev e="simulated" /></div>
    </Panel>
  );
}

function Limits() {
  const { data } = useApp();
  const lim: string[] = data!.manifest.limitations;
  return (
    <Panel className="flex flex-col" style={{ gap: 12, overflow: 'auto', maxHeight: '100%' }}>
      <span className="t-15">What the result does not say</span>
      <ul className="t-13" style={{ margin: 0, paddingLeft: 16, columns: 2, columnGap: 32 }}>
        {plainLimitations(lim).map((l) => <li key={l} style={{ marginBottom: 8, breakInside: 'avoid' }}>{l}</li>)}
        <li style={{ breakInside: 'avoid' }}>Jobs run exactly as long as declared; what happens when runtimes are uncertain is untested.</li>
      </ul>
      <details className="t-12 ink-2">
        <summary className="cursor-pointer fw-500">Source text</summary>
        <ul style={{ margin: '8px 0 0', paddingLeft: 16 }}>{lim.map((l) => <li key={l} style={{ marginBottom: 4 }}>{l}</li>)}</ul>
      </details>
    </Panel>
  );
}
