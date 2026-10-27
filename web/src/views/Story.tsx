import { useEffect, useRef } from 'react';
import { IntervalChart, Panel, PolicyTable } from '../components/charts';
import { Ev, Icon } from '../components/ui';
import { POLICY, REGION, asNum, dayCurve, headline, type Core, type Json } from '../lib/data';
import { argmax, cleanest, rushHours, spanLabel } from '../lib/derive';
import { fmt, fmtDate, fmtHour, pct, pctRange } from '../lib/format';
import { useApp } from '../lib/store';
import { CarbonRibbon, ForecastPanel, LoadChart, YearHeat } from './Ribbon';

/** A scroll-driven walk through the result. The visual on the left follows the step in view. */
export function Story() {
  const { data, step, month, set } = useApp();
  const m = data!.metrics, g = data!.grid;
  const h = headline(m);
  const curve = dayCurve(g, 'PACE', month);
  const rush = rushHours(g), clean = cleanest(curve);
  const jul = g.pace_july_weekday;
  const net: number[] = jul.net_load_mw.value;
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const io = new IntersectionObserver((es) => {
      for (const e of es) if (e.isIntersecting) set({ step: Number((e.target as HTMLElement).dataset.step) });
    }, { root: box.current, rootMargin: '-45% 0px -45% 0px' });
    box.current?.querySelectorAll('[data-step]').forEach((s) => io.observe(s));
    return () => io.disconnect();
  }, [set]);
  const ij: Json = data!.jobs.illustrative_job;
  const steps: { t: string; body: React.ReactNode; ev: React.ReactNode }[] = [
    {
      t: "Utah's grid has a rush hour, and it comes after sunset",
      body: <>On a July weekday demand peaks at {fmtHour(argmax(jul.demand_mw.value))}. Then the sun sets and solar drops away, so net load, the load the rest of the fleet must carry, keeps climbing to {fmtHour(argmax(net))} ({fmt(net[argmax(net)])} MW).</>,
      ev: <Ev e="observed">EIA-930, July 2025 weekdays</Ev>,
    },
    {
      t: 'The rush is predictable, and it is not when the grid is dirtiest',
      body: <>The year's 100 highest net-load hours sit between June and September evenings, mostly {fmtHour(rush[0])}–{fmtHour(rush[1])}. Utah's dirtiest hours are its coal nights; its cleanest are {spanLabel(clean)}, while the sun is up.</>,
      ev: <Ev e="observed">validation year</Ev>,
    },
    {
      t: "Tomorrow's report: forecasts catch the daily swing",
      body: <>Each day at 10 AM, three forecasts predict tomorrow's carbon in Utah from data published at least four days earlier. They follow the swing between coal nights and solar days; the learned one does not clearly beat the simple weekly profile.</>,
      ev: <><Ev e="forecast" /><Ev e="measured">errors</Ev></>,
    },
    {
      t: 'Moving the work beats waiting for clean hours',
      body: <span data-testid="story-result">Over the validation year, every placement policy cut attributed CO₂ by <b className="fw-600">{pctRange(h.placement.lo, h.placement.hi)}%</b> against running each job at home, with every deadline met and the same work done. Waiting in Utah alone cut <b className="fw-600">{pctRange(h.timing.lo, h.timing.hi)}%</b>. Forecast choice barely matters here; placement dominates.</span>,
      ev: <Ev e="simulated">{fmt(m.cohort.n_jobs.value)} jobs, 95% block-resampling intervals</Ev>,
    },
    {
      t: 'One real job, chosen by rule',
      body: <>A {fmt(ij.gpus.value)}-GPU {ij.job_type} job of {fmt(ij.declared_duration_s.value / 60, 1)} minutes, arriving {fmtDate(ij.arrival, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}: the validation job nearest the median size among flexible jobs with a remote option. Most jobs are this small; the saving comes from moving many of them.</>,
      ev: <><Ev e="measured">size</Ev><Ev e="modeled">action CO₂</Ev></>,
    },
    {
      t: 'Challenge it',
      body: <>This is a simulated advance-reservation scenario on EIA-attributed emissions, with exact declared runtimes. The method drawer lists every assumption and limitation, and the run that produced each number.</>,
      ev: <button className="btn" onClick={() => set({ drawer: true })}><Icon name="doc" />Method &amp; evidence</button>,
    },
  ];
  return (
    <section aria-label="Story" className="fixed z-10" style={{ top: 72, left: 0, right: 0, bottom: 28 }}>
      <div ref={box} className="h-full overflow-y-auto" style={{ scrollBehavior: 'smooth' }}>
        <div className="grid" style={{ gridTemplateColumns: 'minmax(0,1.5fr) minmax(360px,1fr)', gap: 24, padding: '0 24px 0 16px' }}>
          <div className="sticky" style={{ top: 0, height: 'calc(100vh - 72px - 28px - 16px)' }}>
            <Visual step={step} rush={rush} clean={clean} curve={curve} />
          </div>
          <div style={{ paddingBottom: '40vh' }}>
            {steps.map((s, i) => (
              <div key={i} data-step={i + 1} className="flex flex-col justify-center" style={{ minHeight: 'calc(100vh - 100px)' }}>
                <Panel style={{ opacity: step === i + 1 ? 1 : 0.55, transition: 'opacity 160ms var(--ease)' }}>
                  <div className="t-12 ink-3" style={{ marginBottom: 8 }}>{i + 1} of {steps.length}</div>
                  <h2 className="t-20" style={{ margin: 0 }}>{s.t}</h2>
                  <p className="t-13 ink-2" style={{ margin: '8px 0 0', maxWidth: '62ch' }}>{s.body}</p>
                  <div className="flex flex-wrap gap-3 items-center" style={{ marginTop: 12 }}>{s.ev}</div>
                </Panel>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function Visual({ step, rush, clean, curve }: { step: number; rush: [number, number]; clean: [number, number]; curve: (number | null)[] }) {
  const { data } = useApp();
  const g = data!.grid, m = data!.metrics;
  const jul = g.pace_july_weekday;
  if (step === 2) return <YearHeat />;
  if (step === 3) return <ForecastPanel />;
  if (step === 4) return (
    <Panel className="h-full flex flex-col" style={{ gap: 16 }}>
      <span className="t-15">Saving in attributed CO₂ vs running local, with 95% intervals</span>
      <IntervalChart m={m} rows={['G', 'S', 'K', 'W', 'L', 'H', 'W_time', 'L_time']} />
      <div className="t-12 ink-3">Filled dots: the four placement policies. Open dots: G (greedy), the hindsight diagnostic H and the two wait-only runs. <Ev e="simulated" /></div>
      <PolicyTable m={m} compact />
    </Panel>
  );
  if (step === 5) return <JobCard />;
  if (step === 6) return (
    <Panel className="h-full flex flex-col" style={{ gap: 8 }}>
      <span className="t-15">What the result does not say</span>
      <ul className="t-13" style={{ margin: 0, paddingLeft: 16 }}>
        {data!.manifest.limitations.map((l: string) => <li key={l} style={{ marginBottom: 8 }}>{l}</li>)}
      </ul>
    </Panel>
  );
  return (
    <Panel className="h-full flex flex-col" style={{ padding: '12px 0 8px' }}>
      <div className="flex items-baseline justify-between" style={{ padding: '0 16px' }}>
        <span className="t-15">Utah, a July weekday</span><Ev e="observed" />
      </div>
      <div className="flex-1 min-h-0"><LoadChart rush={rush} clean={clean} dem={jul.demand_mw.value} net={jul.net_load_mw.value} sol={jul.solar_mw.value} /></div>
      <CarbonRibbon curve={curve} />
    </Panel>
  );
}

function JobCard() {
  const { data } = useApp();
  const ij: Json = data!.jobs.illustrative_job;
  const acts: Json[] = ij.available_actions;
  const stay = acts.find((a) => a.kind === 'stay');
  return (
    <Panel className="h-full flex flex-col" style={{ gap: 12 }}>
      <div className="flex items-baseline justify-between"><span className="t-15">Job {ij.job_uid}: its options and where each policy put it</span><Ev e="modeled" /></div>
      <table className="tbl">
        <thead><tr><th>Option</th><th>Starts (Denver)</th><th>Wait</th><th>CO₂ <span className="fw-400">g</span></th><th>vs staying</th></tr></thead>
        <tbody>
          {acts.map((a) => (
            <tr key={a.site}>
              <td>{a.kind === 'stay' ? 'Stay in Utah' : `Move to ${REGION[a.site as Core]?.name ?? a.site}`} <span className="ink-3">{a.site}</span></td>
              <td>{fmtDate(a.start, { hour: 'numeric', minute: '2-digit' })}</td>
              <td>{fmt((asNum(a.wait_s) ?? 0) / 60)} min</td>
              <td>{fmt(a.co2_kg.value * 1000, 1)}</td>
              <td>{a.kind === 'stay' ? '–' : `${pct(1 - a.co2_kg.value / stay.co2_kg.value, 0)}% less`}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="t-12 ink-3">A move includes {fmt((asNum(data!.manifest.assumptions.transfer_time_s) ?? 0) / 60)} minutes of transfer and its energy. <Ev e="assumed" /></div>
      <hr className="rule" />
      <div className="grid t-13" style={{ gridTemplateColumns: 'repeat(3, minmax(0,1fr))', gap: 8 }}>
        {Object.entries(ij.placements as Record<string, Json>).map(([p, v]) => (
          <div key={p} className="well" style={{ padding: 8 }}>
            <div className="fw-600">{POLICY[p]?.name ?? p}</div>
            <div className="t-12 ink-2">{v.site === 'PACE' ? (v.moved ? 'waited in Utah' : 'stayed in Utah') : `moved to ${REGION[v.site as Core]?.name ?? v.site}`}</div>
            <div className="t-12 num">{fmt(v.co2_kg.value * 1000, 1)} g CO₂ <Ev e="simulated">{' '}</Ev></div>
          </div>
        ))}
      </div>
    </Panel>
  );
}
