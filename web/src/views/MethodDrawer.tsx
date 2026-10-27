import * as Dialog from '@radix-ui/react-dialog';
import { PolicyTable } from '../components/charts';
import { Ev, Icon, SEALED } from '../components/ui';
import { asNum } from '../lib/data';
import { fmt, fmtDate, pct, signed } from '../lib/format';
import { useApp } from '../lib/store';

const iso = (s: string) => fmtDate(s, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' });

/** Method & evidence: reachable from every view. The claim frame is shown verbatim from manifest.json. */
export function MethodDrawer() {
  const { data, drawer, set } = useApp();
  const m = data!.metrics, man = data!.manifest, fr = data!.forecast;
  const a = man.assumptions;
  const h2 = m.h2;
  const h2b4 = h2.intervals['4'];
  const rb = m.relaxed_bound;
  return (
    <Dialog.Root open={drawer} onOpenChange={(o) => set({ drawer: o })}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40" style={{ background: 'rgba(45,29,20,.18)' }} />
        <Dialog.Content className="panel fixed z-50 flex flex-col" style={{ top: 12, right: 12, bottom: 12, width: 'min(760px, calc(100vw - 24px))', padding: 0, overflow: 'hidden' }} aria-describedby="method-desc">
          <div className="flex items-start justify-between gap-4" style={{ padding: 16, borderBottom: '1px solid var(--hair-2)' }}>
            <div>
              <Dialog.Title className="t-20" style={{ margin: 0 }}>Method and evidence</Dialog.Title>
              <Dialog.Description id="method-desc" className="t-12 ink-2" style={{ margin: '4px 0 0' }}>
                {SEALED}. Run {man.run_id}, commit {String(man.git_sha).slice(0, 7)}{man.git_clean ? ' (clean)' : ' (dirty tree)'}, snapshot {man.snapshot_id}.
              </Dialog.Description>
            </div>
            <Dialog.Close className="iconbtn" aria-label="Close method and evidence"><Icon name="close" /></Dialog.Close>
          </div>
          <div className="flex flex-col gap-4" style={{ padding: 16, overflow: 'auto' }}>
            <Sec title="What this result is">
              <p className="t-13" style={{ margin: 0 }}><span className="ink-3">Claim frame, verbatim:</span> “{man.claim_frame}”.</p>
              <p className="t-13 ink-2" style={{ margin: '8px 0 0' }}>
                Every job runs either at its Utah booking (U) or where a policy places it; every policy completes the same declared work, and a deadline is the job's run-now finish plus its allowed delay
                ({fmt((asNum(a.allowed_delay_s.SFT) ?? 0) / 3600)} h for flexible jobs; <Ev e="assumed" />). Emissions are EIA's consumption-basis intensity times energy; differences are attributed, not “avoided”.
              </p>
            </Sec>
            <Sec title="Every policy, the validation cohort">
              <div className="t-12 ink-2" style={{ marginBottom: 8 }}>
                Arrivals {iso(m.covered.arrivals[0])} to {iso(m.covered.arrivals[1])}; drain to {iso(m.covered.drain[1])}. U − policy is reference minus candidate, so positive means the policy emits less.
                Intervals: conditional temporal block resampling, 4-week blocks, {fmt(m.cohort.n_weeks.value)} weeks. <Ev e="simulated" />
              </div>
              <div style={{ overflowX: 'auto' }}><PolicyTable m={m} testId="policy-table" /></div>
            </Sec>
            <Sec title="Forecast choice barely matters here; placement dominates">
              <p className="t-13" style={{ margin: 0 }}>
                The pre-registered forecast test (H2: does the learned forecast L beat the weekly profile W?) is <b className="fw-600">inconclusive</b>: W − L = {signed(h2b4.diff_kg.value / 1000, 1)} t CO₂, 95% interval [{signed(h2b4.diff_kg_ci95.value[0] / 1000, 1)}, {signed(h2b4.diff_kg_ci95.value[1] / 1000, 1)}] t
                ({h2.reason}). <Ev e="simulated" />
              </p>
              <p className="t-12 ink-2" style={{ margin: '8px 0 0' }}>{m.framing.placement_vs_timing}</p>
            </Sec>
            <Sec title="A bound, not a target">
              <p className="t-13" style={{ margin: 0 }}>
                Relaxed hindsight bound (no capacity coupling): {fmt(rb.primary.value / 1000, 0)} t with placement, {fmt(rb.time_only.value / 1000, 0)} t with waiting only. Every feasible policy sits above it{rb.all_feasible_policies_ok ? ' (checked)' : ''}. <Ev e="modeled" />
              </p>
            </Sec>
            <Sec title="Forecasts in the replay week">
              <p className="t-13" style={{ margin: 0 }}>
                {fr.issue_rule}. Week MAE: {(['K', 'W', 'L'] as const).map((k, i) => <span key={k}>{i ? ', ' : ''}{k} {fmt(fr.week_errors[k].mae.value)} g/kWh</span>)}; selection-period MAE {(['K', 'W', 'L'] as const).map((k, i) => <span key={k}>{i ? ', ' : ''}{k} {fmt(fr.selection_mae[k].value)}</span>)}. <Ev e="measured" />
              </p>
            </Sec>
            <Sec title="Assumptions">
              <ul className="t-13" style={{ margin: 0, paddingLeft: 16 }}>
                <li>GPU slots: Utah {fmt(asNum(a.home_slots) ?? 0)}; each destination {fmt(asNum(a.destination_slots.BPAT) ?? 0)}. <Ev e="assumed" /></li>
                <li>{fmt(asNum(a.kw_per_gpu) ?? 0, 1)} kW per GPU, PUE {fmt(asNum(a.pue) ?? 0, 1)}, transfer energy {pct(asNum(a.transfer_energy_fraction) ?? 0, 0)}% and {fmt((asNum(a.transfer_time_s) ?? 0) / 60)} min per move. <Ev e="assumed" /></li>
                <li>Flexible (and mobile) share: {pct(m.cohort.flex_shares.flexible.by_jobs.value)}% of jobs, {pct(m.cohort.flex_shares.flexible.by_gpu_h.value)}% of GPU-hours. <Ev e="assumed" /></li>
              </ul>
            </Sec>
            <Sec title="Limitations">
              <ul className="t-13" style={{ margin: 0, paddingLeft: 16 }}>
                {man.limitations.map((l: string) => <li key={l} style={{ marginBottom: 4 }}>{l}</li>)}
                <li>Runtime uncertainty is untested: realised runtimes equal declared runtimes.</li>
                <li>Not yet run (scheduled after the Tuesday checkpoint): {man.not_before_18.join('; ')}.</li>
              </ul>
            </Sec>
            <Sec title="Evidence labels">
              <div className="flex flex-wrap gap-4"><Ev e="observed" /><Ev e="measured" /><Ev e="forecast" /><Ev e="modeled" /><Ev e="assumed" /><Ev e="simulated" /></div>
              <p className="t-12 ink-2" style={{ margin: '8px 0 0' }}>Observed: EIA-930 load and EIA's published hourly CO₂ intensity. Measured: job sizes from the trace, forecast errors. Modeled: energy and bounds computed from those. Assumed: parameters we chose. Simulated: schedule outcomes.</p>
            </Sec>
            <Sec title="Reproduce">
              <code className="t-12 block" style={{ padding: 8, borderRadius: 8, background: 'var(--surface-2)', boxShadow: 'inset 0 0 0 1px var(--hair-2)' }}>{man.reproduce}</code>
              <code className="t-12 block" style={{ padding: 8, borderRadius: 8, background: 'var(--surface-2)', boxShadow: 'inset 0 0 0 1px var(--hair-2)', marginTop: 4 }}>make profile  # results/grid-profile.json</code>
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
