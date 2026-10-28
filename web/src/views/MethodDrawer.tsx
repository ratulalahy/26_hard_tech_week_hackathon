import * as Dialog from '@radix-ui/react-dialog';
import { AssumptionsSection } from '../components/assumptions';
import { PolicyTable } from '../components/charts';
import { CONSUMPTION_CHECKS, ExtensionsTable, PHRASE, extRows, listJoin, placementSpan } from '../components/extensions';
import { ReliefTable, RushSensitivity, hourSpans, storageFacts } from '../components/storage';
import { Ev, Icon, ScrollX } from '../components/ui';
import { WaterPanel } from '../components/water';
import { useCopy } from '../lib/useCopy';
import { DEADLINE_RULE, asNum, headline, plainLimitations, pname, stripCodes, type Json } from '../lib/data';
import { fmt, fmtDate, pct, pctRange, sig2, signed } from '../lib/format';
import { useApp } from '../lib/store';

const iso = (s: string) => fmtDate(s, { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }) + ' UTC';

/** Method & evidence: reachable from every view. The claim frame is shown verbatim from manifest.json. */
export function MethodDrawer() {
  const { data, drawer, set } = useApp();
  const m = data!.metrics, man = data!.manifest, fr = data!.forecast, g = data!.grid;
  const hd = headline(m);
  const copy = useCopy();
  const a = man.assumptions;
  const h2 = m.h2;
  const h2b4 = h2.intervals['4'];
  const rb = m.relaxed_bound;
  const xr = data!.ext ? extRows(m, data!.ext) : [];
  const mob = data!.ext ? placementSpan(xr, ['mobility_le_8gpus']) : null;
  // the robustness summary (moved here from the story's last beat, F18)
  const span = placementSpan(xr, CONSUMPTION_CHECKS), spanProd = placementSpan(xr, ['production']), spanBig = placementSpan(xr, ['dest_slots_1024']);
  const keptRun = xr.filter((r) => CONSUMPTION_CHECKS.includes(r.id) && r.status === 'ok');
  const xRun = xr.filter((r) => r.group !== 'registered' && r.status === 'ok'), xMiss = xr.filter((r) => r.status !== 'ok');
  const wait0 = xr.find((r) => r.id === 'dest_slots_0' && r.status === 'ok');
  const w0 = [wait0?.cells.W?.v, wait0?.cells.L?.v].filter((v): v is number => typeof v === 'number');
  const allOnTime = xRun.every((r) => r.late == null || r.late === 0);
  const sto = data!.storage, sf = sto ? storageFacts(sto) : null;
  return (
    <Dialog.Root open={drawer} onOpenChange={(o) => set({ drawer: o })}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40" style={{ background: 'rgba(45,29,20,.18)' }} />
        <Dialog.Content className="panel fixed z-50 flex flex-col" style={{ top: 12, right: 12, bottom: 12, width: 'min(760px, calc(100vw - 24px))', padding: 0, overflow: 'hidden', background: 'var(--surface)' }} aria-describedby="method-desc">
          <div className="flex items-start justify-between gap-4" style={{ padding: 16, borderBottom: '1px solid var(--hair-2)' }}>
            <div>
              <Dialog.Title className="t-20" style={{ margin: 0 }}>Method and evidence</Dialog.Title>
              <Dialog.Description id="method-desc" className="t-12 ink-2" style={{ margin: '4px 0 0' }}>
                {copy.chip}. Run {man.run_id}, commit {String(man.git_sha).slice(0, 7)}{man.git_clean ? ' (clean)' : ' (dirty tree)'}, snapshot {man.snapshot_id}.
              </Dialog.Description>
            </div>
            <Dialog.Close className="iconbtn" aria-label="Close method and evidence"><Icon name="close" /></Dialog.Close>
          </div>
          <div className="flex flex-col gap-4" style={{ padding: 16, overflow: 'auto' }} tabIndex={0} role="region" aria-label="Method and evidence details">
            <Sec title="What this result is">
              <p className="t-13" style={{ margin: 0 }}><span className="ink-3">Claim frame, verbatim:</span> “{man.claim_frame}”.</p>
              <p className="t-13 ink-2" style={{ margin: '8px 0 0' }}>
                Every job runs either at its Utah reservation, under {pname('U')}, or where a policy places it. Every policy completes the same declared work. {DEADLINE_RULE} The allowed delay is
                up to {fmt((asNum(a.allowed_delay_s.SFT) ?? 0) / 3600)} h ({fmt((asNum(a.allowed_delay_s.Eval) ?? 0) / 3600)} h for eval jobs) <Ev e="assumed" />.
                Emissions are EIA's consumption-basis carbon intensity times energy. Differences between policies are attributed emissions, not a measured change in what the grid emitted.
              </p>
              <p className="t-13" style={{ margin: '8px 0 0' }} data-testid={copy.lineTestId}><b className="fw-600">{copy.line}</b></p>
            </Sec>
            <Sec title={copy.cohortTitle}>
              <div className="t-12 ink-2" style={{ marginBottom: 8 }}>
                Arrivals {iso(m.covered.arrivals[0])} to {iso(m.covered.arrivals[1])}; jobs then finish by {iso(m.covered.drain[1])}. U − policy is the U total minus the policy's, so positive means the policy emits less.
                Intervals: 95%, resampling 4-week blocks of the {fmt(m.cohort.n_weeks.value)} weeks. Hover a name for its rule. <Ev e="simulated" />
              </div>
              <ScrollX label="Every policy, table"><PolicyTable m={m} testId="policy-table" /></ScrollX>
            </Sec>
            <Sec title="A few large jobs carry the result">
              <ScrollX label="Largest jobs, table"><table className="tbl" data-testid="method-workload">
                <thead><tr><th>Largest jobs</th><th>Share of GPU-hours</th><th>Share of energy</th><th>Share of {pname(data!.workload.policy)}'s saving</th></tr></thead>
                <tbody>
                  {data!.workload.top.map((t: Json) => (
                    <tr key={t.fraction.value}><td>top {pct(t.fraction.value, t.fraction.value < 0.01 ? 1 : 0)}% ({fmt(t.n_jobs.value)} jobs)</td><td>{pct(t.gpu_h_share.value, 0)}%</td><td>{pct(t.energy_share.value, 0)}%</td><td>{t.saving_share.value == null ? '–' : `${pct(t.saving_share.value, 0)}%`}</td></tr>
                  ))}
                </tbody>
              </table></ScrollX>
              <div className="t-12 ink-3" style={{ marginTop: 4 }}>{pct(data!.workload.share_jobs_under_1_gpu_h.value, 0)}% of jobs use under 1 GPU-hour; the median job uses {fmt(data!.workload.median_gpu_h.value, 2)} GPU-hours. The saving column is in {pname(data!.workload.policy)}'s terms (workload-profile.json), not S's; the flexibility budget gives S's. <Ev e="measured">sizes</Ev> <Ev e="simulated">energy and saving</Ev></div>
            </Sec>
            <Sec title={copy.validationReadings ? 'Forecast choice barely matters here; placement dominates' : 'The pre-registered forecast test'}>
              <p className="t-13" style={{ margin: 0 }}>
                The pre-registered forecast test, whether {pname('L')} beats {pname('W')}, is <b className="fw-600">{h2.direction === 'inconclusive' || h2.decided === false || h2.direction == null ? 'inconclusive' : h2.direction}</b>:
                W − L = {signed(h2b4.diff_kg.value / 1000, 1)} t CO₂, 95% interval [{signed(h2b4.diff_kg_ci95.value[0] / 1000, 1)}, {signed(h2b4.diff_kg_ci95.value[1] / 1000, 1)}] t; {stripCodes(h2.reason ?? '')}. <Ev e="simulated" />
              </p>
              {copy.validationReadings ? <p className="t-13" style={{ margin: '8px 0 0' }} data-testid="method-dynamic">We found no demonstrated aggregate benefit from dynamic search in this replay: the forecast-driven policies are not distinguishable from {pname('S')} in aggregate, and only part of the flexible energy has its whole decision window inside forecast coverage.</p> : null}
              <p className="t-13 ink-2" style={{ margin: '8px 0 0' }}>
                Waiting in Utah alone saves {pctRange(hd.timing.lo, hd.timing.hi)}%{copy.validationReadings ? '; nearly all of the saving comes from moving work, mostly to the Northwest' : ''}. A per-job search, even with hindsight, is not a best plan for {copy.wholeYear}: holding scarce Northwest slots for cleaner hours can push later jobs to dirtier sites.
              </p>
            </Sec>
            {data!.ext ? <Sec title="Robustness and sensitivity checks">
              <p className="t-12 ink-2" style={{ margin: '0 0 8px' }}>
                Each row changes one choice and re-scores or re-runs the validation year; none replaces the registered result, and the two workload shifts are alignment checks on the same trace, never pooled with it. Their savings are scenario estimates, and a span across rows or policies is not a confidence interval.
                Production basis prices the same schedules on where electricity is generated rather than where it is used, which flatters hydro-heavy Northwest destinations; an hour with no production value takes, in order, the consumption value for the same hour, our fuel-mix estimate, then the mean of the same hour over the previous 7 days.
                The published-values row drops, from every policy, the {fmt(data!.ext.common_support.cohort.n_dropped.value)} jobs that touch a filled hour under any policy.
                {mob ? <> Letting only jobs of 8 GPUs or fewer move leaves {pctRange(mob[0], mob[1])}%: most of the energy, and most of the saving, sits in large multi-node jobs, so the result depends on those jobs' data being ready at the destination.</> : null}
              </p>
              {span ? <p className="t-13" style={{ margin: '0 0 8px' }} data-testid="method-checks">We checked it {xRun.length} more ways. {listJoin(keptRun.map((r) => PHRASE[r.id] ?? r.label)).replace(/^./, (c) => c.toUpperCase())}, {pname('S')}, {pname('W')} and {pname('L')} still cut <b className="fw-600">{pctRange(span[0], span[1])}%</b>.{spanProd ? ` On production-basis carbon the cut is ${pctRange(spanProd[0], spanProd[1])}%; production basis flatters hydro-heavy destinations.` : ''}{spanBig ? ` Twice the room at the destinations raises it to ${pctRange(spanBig[0], spanBig[1])}%` : ''}{w0.length ? `; with no room there, waiting alone saves ${pctRange(Math.min(...w0), Math.max(...w0))}%` : ''}.{allOnTime ? ' No job was late in any run.' : ''}{xMiss.length ? ` ${xMiss.length} more check${xMiss.length > 1 ? 's' : ''} did not run (${xMiss[0].reason}).` : ''}</p> : null}
              <ExtensionsTable m={m} ext={data!.ext} testId="method-extensions" />
            </Sec> : null}
            <Sec title="A bound, not a target">
              <p className="t-13" style={{ margin: 0 }}>
                A relaxed hindsight bound that ignores competition between jobs for capacity (each job's own limits still apply): {fmt(rb.primary.value / 1000, 0)} t when work may move, {fmt(rb.time_only.value / 1000, 0)} t when it may only wait. Every feasible policy sits above it{rb.all_feasible_policies_ok ? ' (checked)' : ''}. <Ev e="modeled" />
              </p>
            </Sec>
            <Sec title="Forecasts in the replay week">
              <p className="t-13" style={{ margin: 0 }}>
                Forecasts are issued daily at 10 AM Denver time for the next day, from data at least four days old. Mean absolute error in the replay week: {(['K', 'W', 'L'] as const).map((k, i) => <span key={k}>{i ? '; ' : ''}{pname(k)} {fmt(fr.week_errors[k].mae.value)} g/kWh</span>)}. {copy.periodMae}: {(['K', 'W', 'L'] as const).map((k, i) => <span key={k}>{i ? '; ' : ''}{pname(k)} {fmt((fr.test_mae ?? fr.selection_mae)[k].value)}</span>)}. <Ev e="measured" />
              </p>
            </Sec>
            <Sec title="Assumptions">
              <ul className="t-13" style={{ margin: 0, paddingLeft: 16 }}>
                <li>GPU slots: Utah {fmt(asNum(a.home_slots) ?? 0)}; each destination {fmt(asNum(a.destination_slots.BPAT) ?? 0)}. <Ev e="assumed" /></li>
                <li>{fmt(asNum(a.kw_per_gpu) ?? 0, 1)} kW per GPU, PUE {fmt(asNum(a.pue) ?? 0, 1)}; a move takes {fmt((asNum(a.transfer_time_s) ?? 0) / 60)} min and {pct(asNum(a.transfer_energy_fraction) ?? 0, 0)}% extra energy. <Ev e="assumed" /></li>
                <li>Flexible share: {pct(m.cohort.flex_shares.flexible.by_jobs.value)}% of jobs, {pct(m.cohort.flex_shares.flexible.by_gpu_h.value)}% of GPU-hours. <Ev e="assumed" /></li>
                <li>Colour midpoint: {fmt(asNum(g.reference?.us_avg_ci) ?? 0)} g/kWh, the 2024 US average (EIA). <Ev e="observed" /></li>
              </ul>
            </Sec>
            {data!.assumptions ? <Sec title="Assumptions & what didn't work"><AssumptionsSection a={data!.assumptions} /></Sec> : null}
            <Sec title="Limitations">
              <ul className="t-13" style={{ margin: 0, paddingLeft: 16 }}>
                {plainLimitations(man.limitations).map((l: string) => <li key={l} style={{ marginBottom: 4 }}>{l}</li>)}
                <li style={{ marginBottom: 4 }}>Jobs run exactly as long as declared; uncertain runtimes are untested.</li>
                {man.not_run?.length ? <li>Some sensitivity runs were not run (each with its reason, in the source text).</li> : null}
              </ul>
              <details className="t-12 ink-2" style={{ marginTop: 8 }}>
                <summary className="cursor-pointer fw-500">Source text</summary>
                <div style={{ marginTop: 8 }}>
                  <div className="fw-500">Limitations, as written in the results manifest</div>
                  <ul style={{ margin: '4px 0 0', paddingLeft: 16 }}>{man.limitations.map((l: string) => <li key={l} style={{ marginBottom: 4 }}>{l}</li>)}</ul>
                  {man.not_run?.length ? <><div className="fw-500" style={{ marginTop: 8 }}>Not run</div><ul style={{ margin: '4px 0 0', paddingLeft: 16 }}>{man.not_run.map((x: { item: string; reason: string }) => <li key={x.item}>{x.item}: {x.reason}</li>)}</ul></> : null}
                  <div className="fw-500" style={{ marginTop: 8 }}>Framing, as written in the metrics</div>
                  {Object.values((m.framing ?? {}) as Record<string, string>).map((t) => <p key={t} style={{ margin: '4px 0 0' }}>{t}</p>)}
                  <div className="fw-500" style={{ marginTop: 8 }}>Forecast issue rule</div>
                  <p style={{ margin: '4px 0 0' }}>{fr.issue_rule}</p>
                </div>
              </details>
            </Sec>
            {sto && sf ? <div className="well" style={{ padding: 12 }}><Sec title="Storage illustration (not the registered result)">
              <p className="t-13" style={{ margin: 0 }} data-testid="method-storage">
                {sto.note.replace(/^./, (c: string) => c.toUpperCase())}. A battery behind the meter at the Utah cluster is dispatched against the cluster's hourly energy from the registered ledgers ({pname('U')}, and {pname('W')} with only jobs of 8 GPUs or fewer allowed to move), over the registered cohort window, on the same EIA consumption-basis carbon. <span className="chip-neutral">illustrative</span> <Ev e="simulated">dispatch</Ev> <Ev e="modeled">carbon</Ev>
              </p>
              <ul className="t-13 ink-2" style={{ margin: '8px 0 0', paddingLeft: 16 }}>
                <li>Battery: sizes {VS_LIST(sto.assumptions.sizes_mwh)} MWh, power = size ÷ 4; round-trip efficiency {fmt(sf.eta, 2)} (also 0.75 and 0.90), all lost on the charging side. Charging fits under the site connection, {fmt(sf.conn, 3)} MW (2,288 GPUs × 0.60 kW × 1.20) minus the cluster's load, which leaves roughly {fmt(sf.headroomLo, 1)}–{fmt(sf.headroomMid, 1)} MW in the charging hours; discharge never exceeds the load (no export). The state of charge runs from empty through the whole window; energy left at the end ({fmt(sf.terminal, 1)} MWh at {fmt(sf.E)} MWh) is valued at zero. Degradation, self-discharge and cost are ignored; standby losses would reduce this, most at low utilisation. <Ev e="assumed" /></li>
                <li>Headline size: {fmt(sf.E)} MWh / {fmt(sf.P)} MW, an illustrative selection sized to the charging room the connection leaves ({sto.headline.rule}). It delivers {fmt(sf.throughput, 1)} MWh a day, {fmt(sf.cycles, 2)} full cycles. The curve levels off near {fmt(sf.plateau)} MWh ({pct(sf.cutAplateau, 1)}%).{sf.sensCutA != null ? ` With a 25% larger connection (${fmt(sf.sensConn ?? 0, 2)} MW) the ${fmt(sf.E)} MWh battery cuts ${pct(sf.sensCutA, 1)}%.` : ''}</li>
                <li>Fixed daily schedule: charge in the 6 local hours with the lowest mean carbon in 2022 to Oct 2024 ({hourSpans(sf.charge).join(', ')}), discharge in the 6 highest of the rest ({hourSpans(sf.discharge).join(', ')}); no forecasts, no validation data. <Ev e="assumed">schedule</Ev></li>
                <li>Hindsight heuristic: sees each day's actual carbon in advance and plans that day (a small linear program); one possible plan, not a limit. It cuts {pct(sf.cutB, 1)}% at {fmt(sf.E)} MWh.</li>
                <li data-testid="method-breakeven">Break-even: storing 1 kWh helps only if charging carbon ÷ efficiency is below the carbon it displaces. On the 2022–24 profile it is: {fmt(sf.chargeCI)} ÷ {fmt(sf.eta, 2)} = {fmt(sf.chargeOverEta)} against {fmt(sf.dischargeCI)} g/kWh. On our rough reference the charging hours are no cleaner on the margin ({fmt(sf.mCharge)} vs {fmt(sf.mDischarge)} g/kWh; {fmt(sf.ratio, 2)}× would be needed). That reference is a validation-year regression by 6-hour block, not an hourly estimate, so the marginal view is a threshold scenario: at a flat {fmt(sf.mFlat)} g/kWh the battery adds what it draws and does not deliver, about {sig2(sf.flatAddT)} t on the fixed schedule ({sig2(sf.flatAddTB)} t on the hindsight heuristic).</li>
                <li>Move small, store for big: {pname('W')} with only jobs of 8 GPUs or fewer moving cuts {pct(sf.moveOnly, 1)}% against {pname('U')} (ratio of totals); adding the {fmt(sf.E)} MWh battery to the work left in Utah gives {pct(sf.moveStoreA, 1)}% ({pct(sf.moveStoreB, 1)}% with the hindsight heuristic). Utah execution, remote execution and transfer energy are each counted once.</li>
                <li>Window: the registered cohort window, arrivals from Nov 1, 2024 until {iso(sto.window.arrivals_end)}; it runs on until the last job ends, so the cluster's load falls over the final hours (the drain).</li>
                <li>{sto.power_quality}</li>
              </ul>
              <h4 className="t-13 fw-600" style={{ margin: '12px 0 4px' }}>Router peak relief in Utah's rush hours</h4>
              <p className="t-12 ink-2" style={{ margin: '0 0 6px' }} data-testid="method-rush">Rush hours: validation hours with Utah net load at or above the 2022–24 top 1% ({fmt(sf.rushThr)} MW): {fmt(sf.rushN)} hours on {fmt(sf.rushDays)} days. Each site's cluster load in those hours and at the year's peak net-load hour, from the registered ledgers; MW = MWh per hour. One 2,288-GPU cluster against a Utah peak net load of about {fmt(Math.round(sf.peakNet / 100) * 100)} MW. <Ev e="observed">net load</Ev> <Ev e="simulated">cluster load</Ev></p>
              <ScrollX label="Router peak relief, table"><ReliefTable s={sto} /></ScrollX>
              <p className="t-12 ink-2" style={{ margin: '8px 0 6px' }}>The same relief at lower thresholds:</p>
              <ScrollX label="Peak relief at lower thresholds, table"><RushSensitivity s={sto} /></ScrollX>
            </Sec></div> : null}
            {data!.water ? <div className="well" style={{ padding: 12 }}><Sec title="Water footprint illustration (not the registered result)">
              <WaterPanel w={data!.water} />
            </Sec></div> : null}
            <Sec title="Evidence labels">
              <div className="flex flex-wrap gap-4"><Ev e="observed" /><Ev e="measured" /><Ev e="forecast" /><Ev e="modeled" /><Ev e="assumed" /><Ev e="simulated" /></div>
              <p className="t-12 ink-2" style={{ margin: '8px 0 0' }}>Observed: EIA-930 load and the EIA US average. Measured: job sizes from the trace, forecast errors. Modeled: EIA's hourly carbon-intensity estimates, and bounds computed from them. Assumed: parameters we chose. Simulated: schedule outcomes and their energy.</p>
            </Sec>
            <Sec title="Reproduce">
              <code className="t-12 block" style={{ padding: 8, borderRadius: 8, background: 'var(--surface-2)', boxShadow: 'inset 0 0 0 1px var(--hair-2)' }}>{man.reproduce}</code>
              {copy.validationReadings ? <code className="t-12 block" style={{ padding: 8, borderRadius: 8, background: 'var(--surface-2)', boxShadow: 'inset 0 0 0 1px var(--hair-2)', marginTop: 4 }}>make profile  # results/grid-profile.json and workload-profile.json</code> : null}
              {copy.validationReadings ? <code className="t-12 block" style={{ padding: 8, borderRadius: 8, background: 'var(--surface-2)', boxShadow: 'inset 0 0 0 1px var(--hair-2)', marginTop: 4 }}>make storage RUN_DIR=…  # results/storage.json (illustrative)</code> : null}
              {copy.validationReadings ? <code className="t-12 block" style={{ padding: 8, borderRadius: 8, background: 'var(--surface-2)', boxShadow: 'inset 0 0 0 1px var(--hair-2)', marginTop: 4 }}>make water RUN_DIR=…  # results/water.json (illustrative)</code> : null}
            </Sec>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

const VS_LIST = (e: { value: number[] }) => e.value.join(', ');

function Sec({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="t-15" style={{ margin: '0 0 8px' }}>{title}</h3>
      {children}
    </section>
  );
}
