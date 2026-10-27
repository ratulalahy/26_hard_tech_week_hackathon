import { useEffect, useMemo, useRef } from 'react';
import { IntervalChart, Panel, PolicyTable } from '../components/charts';
import { extRows, placementSpan } from '../components/extensions';
import { ImportChart, StorageCurve, hourSpans, storageFacts } from '../components/storage';
import { Ev, EvCI, Icon } from '../components/ui';
import { DEADLINES_MET, DESTS, FRAME_LINE, REGION, VALIDATION_LINE, asNum, dayCurve, headline, loadMonth, pname, type Core, type Json } from '../lib/data';
import { argmax, cleanest, rushHours, spanLabel } from '../lib/derive';
import { fmt, fmtDate, fmtHour, monthLabel, pct, pctRange, sig2 } from '../lib/format';
import { useViewport } from '../lib/useViewport';
import { initialStep, useApp } from '../lib/store';
import { WestMap, type ArcSpec } from '../map/WestMap';
import { CarbonRibbon, ForecastPanel, LoadChart, YearHeat } from './Ribbon';

/** Six beats, about 45 s each (lead ruling R8; F18): the rush, tomorrow's report, one job, place
 * the work, the count, and "move what you can, store for what you can't" (T10b: the storage
 * illustration and router peak relief; the robustness table lives in the method drawer). The
 * visual on the left follows the step in view; #story-N deep-links. */
export function Story() {
  const { data, step, month, set } = useApp();
  const m = data!.metrics, g = data!.grid, wl = data!.workload;
  const h = headline(m);
  const curve = dayCurve(g, 'PACE', month);
  const rush = rushHours(g), clean = cleanest(curve);
  const jul = g.pace_july_weekday, lm = loadMonth(g);
  const net: number[] = jul.net_load_mw.value;
  const k: number = g.pace_top100_net_load.k.value;
  const cm: number[][] = g.pace_top100_net_load.counts_month_hour.value;
  const hotMonths = g.months.filter((_: string, i: number) => cm[i].some((c) => c > 0));
  const mName = (ym: string) => monthLabel(ym, true).split(' ')[0];
  const monthSpan = hotMonths.length ? (hotMonths.length === 1 ? mName(hotMonths[0]) : `${mName(hotMonths[0])}–${mName(hotMonths[hotMonths.length - 1])}`) : '';
  // N2: where W's moved (remote) execution energy went over the year
  const byS = m.policies.W.metrics.execution_kwh_by_site as Record<string, { value: number }>;
  const remote = DESTS.map((d) => [d, byS?.[d]?.value ?? 0] as const);
  const remoteTot = remote.reduce((a, [, v]) => a + v, 0) || 1;
  const topDest = [...remote].sort((a, b) => b[1] - a[1])[0];

  const box = useRef<HTMLDivElement>(null);
  const ij: Json = data!.jobs.illustrative_job;
  const lit: Json = data!.jobs.illustrative_job_literal;
  const litDur = lit.declared_duration_s.value < 3600 ? `${fmt(lit.declared_duration_s.value / 60, 1)} minutes` : `${fmt(lit.declared_duration_s.value / 3600, 1)} hours`;
  const w = data!.jobs.week.policies.W;
  const wyear = m.policies.W.metrics;
  const weekTop = [...w.arcs].sort((a: Json, b: Json) => b.gpu_h.value - a.gpu_h.value)[0];
  useEffect(() => {
    const st = initialStep ?? null;
    if (st && box.current) { const el = box.current.querySelector<HTMLElement>(`[data-step="${st}"]`); if (el) box.current.scrollTop = el.offsetTop - (box.current.clientHeight - el.offsetHeight) / 2; }
    const io = new IntersectionObserver((es) => {
      for (const e of es) if (e.isIntersecting) set({ step: Number((e.target as HTMLElement).dataset.step) });
    }, { root: box.current, rootMargin: '-45% 0px -45% 0px' });
    box.current?.querySelectorAll('[data-step]').forEach((s) => io.observe(s));
    return () => io.disconnect();
  }, [set]);

  const top1 = wl.top.find((t: Json) => Math.abs(t.fraction.value - 0.01) < 1e-9) ?? wl.top[1];
  const xr = extRows(m, data!.ext);
  const spanMob = placementSpan(xr, ['mobility_le_8gpus']);
  const sto = data!.storage, sf = sto ? storageFacts(sto) : null;
  const steps: { t: string; body: React.ReactNode; ev: React.ReactNode }[] = [
    {
      t: "Utah's grid has a rush hour, and it comes after sunset",
      body: <>On a {lm.short} weekday demand peaks at {fmtHour(argmax(jul.demand_mw.value))}. Then the sun sets and solar drops away, so net load, the load the rest of the fleet must carry, keeps climbing to {fmtHour(argmax(net))} ({fmt(net[argmax(net)])} MW). All year, the {fmt(k)} highest net-load hours fall on {monthSpan} evenings, mostly {spanLabel(rush)}. The cleanest hours are {spanLabel(clean)}, while the sun is up.</>,
      ev: <><Ev e="observed">load: EIA-930</Ev><EvCI /></>,
    },
    {
      t: "Tomorrow's report: forecasts catch the daily swing",
      body: <>Each day at 10 AM, three forecasts predict tomorrow's carbon in Utah from data that is at least four days old: {pname('K')}, {pname('W')} and {pname('L')}. All three follow the swing between night and midday; none is clearly better than the others.</>,
      ev: <><Ev e="forecast" /><Ev e="measured">errors</Ev></>,
    },
    {
      t: 'One job: stay, wait or move',
      body: <>A {fmt(ij.gpus.value)}-GPU {ij.job_type} job of {ij.declared_duration_s.value < 3600 ? `${fmt(ij.declared_duration_s.value / 60, 1)} minutes` : `${fmt(ij.declared_duration_s.value / 3600, 1)} hours`} ({fmt(ij.declared_gpu_h.value, ij.declared_gpu_h.value < 1 ? 2 : 1)} GPU-h), arriving {fmtDate(ij.arrival, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}. It may start up to {fmt(ij.max_delay_s.value / 3600)} h late. Moving it adds a transfer delay but lands it on a cleaner grid. It was picked by a rule fixed before seeing its outcome: the GPU-hour-weighted median of the eligible flexible jobs. The registered count-median job runs only {litDur}; see how this job was chosen.{ij.disclosure ? <details className="t-12 ink-3" style={{ marginTop: 8 }}><summary className="cursor-pointer fw-500">How this job was chosen (source text)</summary><span>{ij.disclosure}</span></details> : null}</>,
      ev: <><Ev e="measured">job size</Ev><Ev e="modeled">option CO₂</Ev><Ev e="simulated">placements</Ev></>,
    },
    {
      t: `Place the work: over the year, ${pct(topDest[1] / remoteTot, 0)}% of the moved energy went to ${REGION[topDest[0]].name === 'Northwest hydro' ? 'the Northwest' : REGION[topDest[0]].name}`,
      body: <>Over the year, {pname('W')} ran {remote.map(([d, v]) => `${pct(v / remoteTot, 0)}% of its moved energy in ${REGION[d].name}`).join(', ')}. {weekTop && weekTop.to !== topDest[0] ? <>The replay week shown on the map is different: {REGION[weekTop.to as Core].name} took more GPU-hours that week. </> : null}In that week it sent {DESTS.map((d) => { const a = w.arcs.find((x: Json) => x.to === d); return a ? `${fmt(a.gpu_h.value)} GPU-h to ${REGION[d].name}` : null; }).filter(Boolean).join(', ')}. Over the year it moved {pct(wyear.moved_share_jobs.value)}% of jobs and ran {pct(wyear.remote_energy_share.value)}% of the energy outside Utah, with {fmt(wyear.late_jobs.value)} late jobs.</>,
      ev: <Ev e="simulated">energy by site, all year; arcs, one week</Ev>,
    },
    {
      t: 'The count: moving beats waiting',
      body: <span data-testid="story-result">Over the validation year, the four placement policies cut attributed CO₂ by <b className="fw-600">{pctRange(h.placement.lo, h.placement.hi)}%</b> against U local (stay in Utah), with {DEADLINES_MET} and the same work done. Waiting in Utah alone cut <b className="fw-600">{pctRange(h.timing.lo, h.timing.hi)}%</b>. Forecast choice barely matters; placement dominates. Most jobs are tiny, but most of the energy, and most of the saving, sits in a few large jobs: the largest {pct(top1.fraction.value, 0)}% of jobs use {pct(top1.energy_share.value, 0)}% of the energy and carry {pct(top1.saving_share.value, 0)}% of the saving.<span className="block t-12 ink-3" style={{ marginTop: 8 }} data-testid="story-frame">{FRAME_LINE}</span></span>,
      ev: <><Ev e="simulated">{fmt(m.cohort.n_jobs.value)} jobs, 95% intervals</Ev><Ev e="measured">job sizes</Ev></>,
    },
    {
      t: "Move what you can, store for what you can't",
      body: sf ? <span data-testid="story-storage">Moving cuts {pctRange(h.placement.lo, h.placement.hi)}%, but only if large multi-node jobs can move; {spanMob ? <>if only jobs of 8 GPUs or fewer may, it falls to {pctRange(spanMob[0], spanMob[1])}%</> : 'the small-jobs-only check did not run'}. For work that stays, a battery can shift its energy instead. <b className="fw-600" data-testid="storage-headline">{/^(8|11|18)/.test(String(sf.E)) ? 'An' : 'A'} {fmt(sf.E)} MWh, {fmt(sf.P)} MW battery cuts the Utah cluster's CO₂ by {pct(sf.cutA, 1)}%</b> on a fixed daily schedule; charging is limited to the roughly {fmt(sf.headroomLo, 1)}–{fmt(sf.headroomMid, 1)} MW the site connection leaves free. <span data-testid="storage-combined">Moving the small jobs and storing for the big ones cuts <b className="fw-600">{pct(sf.moveStoreA, 1)}%</b> against {pname('U')}.</span> <b className="fw-600 block" style={{ marginTop: 8 }} data-testid="storage-skeptic">On a flat marginal basis it may add about {sig2(sf.flatAddT)} t: storage only helps if charging carbon ÷ η &lt; displaced carbon.</b></span> : <>{VALIDATION_LINE}</>,
      ev: <><span className="chip-neutral">illustrative · not the registered result</span><EvCI /><Ev e="simulated">dispatch</Ev><Ev e="assumed">battery, schedule</Ev><button className="btn" onClick={() => set({ drawer: true })}><Icon name="doc" />Method &amp; evidence</button></>,
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
  if (step === 2) return fill(<ForecastPanel />);
  if (step === 3) return <JobCard />;
  if (step === 4) return <PlaceWork />;
  if (step === 5) return <Count />;
  if (step === 6) return <StorageBeat />;
  return (
    <div className="grid h-full" style={{ gridTemplateRows: 'minmax(0,1.4fr) minmax(0,1fr)', gap: 16 }}>
      <Panel className="flex flex-col min-h-0" style={{ padding: '12px 0 8px' }}>
        <div className="flex items-baseline justify-between" style={{ padding: '0 16px' }}>
          <span className="t-15">Utah, a {lm.short} weekday: load in MW, carbon below</span><Ev e="observed">load</Ev>
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

function PlaceWork() {
  const { data, hour, month } = useApp();
  const g = data!.grid, w = data!.jobs.week.policies.W;
  const ci = useMemo(() => Object.fromEntries((['PACE', 'BPAT', 'CISO', 'NEVP'] as Core[]).map((c) => [c, dayCurve(g, c, month)[hour]])), [g, month, hour]);
  const context = useMemo(() => Object.fromEntries(Object.entries(g.context_year_mean_ci.by_ba).map(([k, e]) => [k, asNum(e as never)])), [g]);
  const arcs = useMemo<ArcSpec[]>(() => {
    const gh = (a: Json) => a.gpu_h.value as number;
    const tot = w.arcs.map(gh).reduce((x: number, y: number) => x + y, 0) || 1, max = Math.max(...w.arcs.map(gh), 1);
    return w.arcs.filter((a: Json) => gh(a) / tot >= 0.01).map((a: Json) => ({ to: a.to, weight: Math.sqrt(gh(a) / max), label: `${fmt(gh(a))} GPU-h`, selected: a.to === 'BPAT' }));
  }, [w]);
  return (
    <div className="grid h-full" style={{ gridTemplateRows: 'minmax(0,1fr) auto', gap: 16 }}>
      <Panel className="relative overflow-hidden" style={{ padding: 0 }}>
        <WestMap id="map-story" variant="inset" interactive={false} ci={ci} context={context} hourLabel={fmtHour(hour)} arcs={arcs}
          bounds={[[-124.6, 31.8], [-104.0, 48.9]]} padding={{ top: 72, bottom: 16, left: 150, right: 120 }} />
        <div className="absolute flex items-baseline justify-between gap-2" style={{ left: 16, right: 16, top: 16 }}>
          <span className="t-15">{pname('W')}: GPU-hours moved out of Utah</span>
          <Ev e="simulated" />
        </div>
        <div className="absolute t-11 ink-2" style={{ left: 16, top: 40 }}>Regions: typical {monthLabel(month, true).split(' ')[0]} day, {fmtHour(hour)} · Arcs: replay week {fmtDate(data!.jobs.week.start, { month: 'short', day: 'numeric' })}–{fmtDate(new Date(new Date(data!.jobs.week.end).getTime() - 1).toISOString(), { day: 'numeric' })}, {fmtDate(data!.jobs.week.start, { year: 'numeric' })} <EvCI /></div>
      </Panel>
      <Panel>
        <div className="grid t-13" style={{ gridTemplateColumns: 'repeat(3, minmax(0,1fr))', gap: 16 }}>
          {DESTS.map((d) => { const a = w.arcs.find((x: Json) => x.to === d); return (
            <div key={d}><div className="t-12 ink-3">{REGION[d].name} · {d}</div><div className="t-15 num">{a ? fmt(a.gpu_h.value) : 0}<span className="unit">GPU-h</span></div><div className="t-11 ink-3">{a ? fmt(a.jobs.value) : 0} jobs</div></div>
          ); })}
        </div>
      </Panel>
    </div>
  );
}

function Count() {
  const { data } = useApp();
  const m = data!.metrics, wl = data!.workload;
  const tight = useViewport().h < 1000;
  return (
    <Panel className={`flex flex-col ${tight ? 'tight' : ''}`} style={{ gap: tight ? 8 : 12, maxHeight: '100%', overflow: 'auto' }}>
      <span className="t-15">Saving in attributed CO₂ vs U local (stay in Utah), with 95% intervals</span>
      <IntervalChart m={m} rows={['G', 'S', 'K', 'W', 'L', 'H', 'W_time', 'L_time']} rowH={tight ? 20 : 26} />
      <div className="t-12 ink-3">Filled dots: the four placement policies. Open dots: {pname('G')}, the two wait-only runs, and the dashed {pname('H')}. <Ev e="simulated" /></div>
      <div style={{ overflowX: 'auto' }}><PolicyTable m={m} /></div>
      <hr className="rule" />
      <div className="t-13">
        <span className="t-15">A few large jobs carry the result</span>
        <table className="tbl" style={{ marginTop: 8 }}>
          <thead><tr><th>Largest jobs</th><th>Share of GPU-hours</th><th>Share of energy</th><th>Share of {pname(wl.policy)}'s saving</th></tr></thead>
          <tbody>
            {wl.top.map((t: Json) => (
              <tr key={t.fraction.value}><td>top {pct(t.fraction.value, t.fraction.value < 0.01 ? 1 : 0)}% ({fmt(t.n_jobs.value)} jobs)</td><td>{pct(t.gpu_h_share.value, 0)}%</td><td>{pct(t.energy_share.value, 0)}%</td><td>{t.saving_share.value == null ? '–' : `${pct(t.saving_share.value, 0)}%`}</td></tr>
            ))}
          </tbody>
        </table>
        <div className="t-12 ink-3" style={{ marginTop: 4 }}>{pct(wl.share_jobs_under_1_gpu_h.value, 0)}% of jobs use under 1 GPU-hour; the median job uses {fmt(wl.median_gpu_h.value, 2)} GPU-hours. <Ev e="measured">sizes</Ev> <Ev e="simulated">energy and saving</Ev></div>
      </div>
    </Panel>
  );
}

function StorageBeat() {
  const { data } = useApp();
  const sto = data!.storage;
  if (!sto) return <Panel><span className="t-13 ink-3">The storage illustration was not exported (results/storage.json is missing).</span></Panel>;
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
