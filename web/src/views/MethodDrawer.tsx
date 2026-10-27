import * as Dialog from '@radix-ui/react-dialog';
import { PolicyTable } from '../components/charts';
import { Ev, Icon, SEALED } from '../components/ui';
import { DEADLINE_RULE, VALIDATION_LINE, asNum, headline, plainLimitations, pname, stripCodes } from '../lib/data';
import { fmt, fmtDate, pct, pctRange, signed } from '../lib/format';
import { useApp } from '../lib/store';

const iso = (s: string) => fmtDate(s, { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }) + ' UTC';

/** Method & evidence: reachable from every view. The claim frame is shown verbatim from manifest.json. */
export function MethodDrawer() {
  const { data, drawer, set } = useApp();
  const m = data!.metrics, man = data!.manifest, fr = data!.forecast, g = data!.grid;
  const hd = headline(m);
  const a = man.assumptions;
  const h2 = m.h2;
  const h2b4 = h2.intervals['4'];
  const rb = m.relaxed_bound;
  return (
    <Dialog.Root open={drawer} onOpenChange={(o) => set({ drawer: o })}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40" style={{ background: 'rgba(45,29,20,.18)' }} />
        <Dialog.Content className="panel fixed z-50 flex flex-col" style={{ top: 12, right: 12, bottom: 12, width: 'min(760px, calc(100vw - 24px))', padding: 0, overflow: 'hidden', background: 'var(--surface)' }} aria-describedby="method-desc">
          <div className="flex items-start justify-between gap-4" style={{ padding: 16, borderBottom: '1px solid var(--hair-2)' }}>
            <div>
              <Dialog.Title className="t-20" style={{ margin: 0 }}>Method and evidence</Dialog.Title>
              <Dialog.Description id="method-desc" className="t-12 ink-2" style={{ margin: '4px 0 0' }}>
                {SEALED}. Run {man.run_id}, commit {String(man.git_sha).slice(0, 7)}{man.git_clean ? ' (clean)' : ' (dirty tree)'}, snapshot {man.snapshot_id}.
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
              <p className="t-13" style={{ margin: '8px 0 0' }} data-testid="validation-line"><b className="fw-600">{VALIDATION_LINE}</b></p>
            </Sec>
            <Sec title="Every policy, the validation cohort">
              <div className="t-12 ink-2" style={{ marginBottom: 8 }}>
                Arrivals {iso(m.covered.arrivals[0])} to {iso(m.covered.arrivals[1])}; jobs then finish by {iso(m.covered.drain[1])}. U − policy is the U total minus the policy's, so positive means the policy emits less.
                Intervals: 95%, resampling 4-week blocks of the {fmt(m.cohort.n_weeks.value)} weeks. Hover a name for its rule. <Ev e="simulated" />
              </div>
              <div style={{ overflowX: 'auto' }}><PolicyTable m={m} testId="policy-table" /></div>
            </Sec>
            <Sec title="Forecast choice barely matters here; placement dominates">
              <p className="t-13" style={{ margin: 0 }}>
                The pre-registered forecast test, whether {pname('L')} beats {pname('W')}, is <b className="fw-600">{h2.direction === 'inconclusive' || h2.decided === false || h2.direction == null ? 'inconclusive' : h2.direction}</b>:
                W − L = {signed(h2b4.diff_kg.value / 1000, 1)} t CO₂, 95% interval [{signed(h2b4.diff_kg_ci95.value[0] / 1000, 1)}, {signed(h2b4.diff_kg_ci95.value[1] / 1000, 1)}] t; {stripCodes(h2.reason ?? '')}. <Ev e="simulated" />
              </p>
              <p className="t-13 ink-2" style={{ margin: '8px 0 0' }}>
                Waiting in Utah alone saves {pctRange(hd.timing.lo, hd.timing.hi)}%; nearly all of the saving comes from moving work, mostly to the Northwest. A per-job search, even with hindsight, is not a best plan for the whole year: holding scarce Northwest slots for cleaner hours can push later jobs to dirtier sites.
              </p>
            </Sec>
            <Sec title="A bound, not a target">
              <p className="t-13" style={{ margin: 0 }}>
                A relaxed hindsight bound that ignores competition between jobs for capacity (each job's own limits still apply): {fmt(rb.primary.value / 1000, 0)} t when work may move, {fmt(rb.time_only.value / 1000, 0)} t when it may only wait. Every feasible policy sits above it{rb.all_feasible_policies_ok ? ' (checked)' : ''}. <Ev e="modeled" />
              </p>
            </Sec>
            <Sec title="Forecasts in the replay week">
              <p className="t-13" style={{ margin: 0 }}>
                Forecasts are issued daily at 10 AM Denver time for the next day, from data at least four days old. Mean absolute error in the replay week: {(['K', 'W', 'L'] as const).map((k, i) => <span key={k}>{i ? '; ' : ''}{pname(k)} {fmt(fr.week_errors[k].mae.value)} g/kWh</span>)}. Over the selection period: {(['K', 'W', 'L'] as const).map((k, i) => <span key={k}>{i ? '; ' : ''}{pname(k)} {fmt(fr.selection_mae[k].value)}</span>)}. <Ev e="measured" />
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
            <Sec title="Evidence labels">
              <div className="flex flex-wrap gap-4"><Ev e="observed" /><Ev e="measured" /><Ev e="forecast" /><Ev e="modeled" /><Ev e="assumed" /><Ev e="simulated" /></div>
              <p className="t-12 ink-2" style={{ margin: '8px 0 0' }}>Observed: EIA-930 load and the EIA US average. Measured: job sizes from the trace, forecast errors. Modeled: EIA's hourly carbon-intensity estimates, and bounds computed from them. Assumed: parameters we chose. Simulated: schedule outcomes and their energy.</p>
            </Sec>
            <Sec title="Reproduce">
              <code className="t-12 block" style={{ padding: 8, borderRadius: 8, background: 'var(--surface-2)', boxShadow: 'inset 0 0 0 1px var(--hair-2)' }}>{man.reproduce}</code>
              <code className="t-12 block" style={{ padding: 8, borderRadius: 8, background: 'var(--surface-2)', boxShadow: 'inset 0 0 0 1px var(--hair-2)', marginTop: 4 }}>make profile  # results/grid-profile.json and workload-profile.json</code>
            </Sec>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function Sec({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="t-15" style={{ margin: '0 0 8px' }}>{title}</h3>
      {children}
    </section>
  );
}
