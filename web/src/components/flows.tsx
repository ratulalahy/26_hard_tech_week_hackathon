// Stage 3 T15 (D-064): the "Which jobs can move?" toggle over the already-computed validation
// scenarios (results/scenario-flows.json) and the flexibility budget (results/flexibility-budget.json).
// Every number keeps its envelope; savings are copied from metrics.json / extensions.json by the export.
import { useId } from 'react';
import { C, CARBON } from '../lib/color';
import { DESTS, REGION, pname, type Dest, type Json } from '../lib/data';
import { fmt, pct } from '../lib/format';
import { useApp, type ScenarioId } from '../lib/store';
import { useViewport } from '../lib/useViewport';
import { useWidth } from './charts';
import { Ev } from './ui';

export const SCENARIOS: { id: ScenarioId; label: string; short: string }[] = [
  { id: 'registered', label: 'All flexible jobs (registered)', short: 'All flexible' },
  { id: 'mobility_le_8gpus', label: 'Only jobs ≤ 8 GPUs', short: '≤ 8 GPUs' },
  { id: 'dest_slots_0', label: 'No remote capacity (wait only)', short: 'Wait only' },
  { id: 'dest_slots_1024', label: 'Double remote capacity', short: '2× remote room' },
];

/** One scenario's block from scenario-flows.json (null if the file or the scenario is missing). */
export const scenarioOf = (flows: Json | null, id: ScenarioId): Json | null => flows?.scenarios?.find((s: Json) => s.id === id) ?? null;
/** One policy's flows in a scenario. */
export const flowOf = (flows: Json | null, id: ScenarioId, p: string): Json | null => scenarioOf(flows, id)?.policies?.[p] ?? null;
/** "registered result" or "scenario estimate (validation)", from the export. */
export const kindOf = (s: Json | null) => (s?.registered ? 'registered result' : 'scenario estimate (validation)');

/** A policy's saving vs U in a scenario: point and 95% interval (copied envelopes). */
export function savingOf(f: Json | null): { v: number; lo: number; hi: number } | null {
  const s = f?.saving_vs_U;
  if (!s || s.saving?.value == null) return null;
  const [lo, hi] = s.saving_ci95.value as [number, number];
  return { v: s.saving.value, lo, hi };
}

/** The segmented control, "Which jobs can move?". Shared by the control room and story 4. */
export function ScenarioToggle({ compact = false }: { compact?: boolean }) {
  const { data, scenario, set } = useApp();
  const vp = useViewport();
  const short = compact || vp.w < 1600;
  const lid = 'toggle-' + useId().replace(/[^a-zA-Z0-9]/g, '');
  const s = scenarioOf(data!.flows, scenario);
  // validation scenarios only: with no scenario-flows.json for this window, there is nothing to switch
  if (!data!.flows) return <div className="t-11 ink-3" data-testid="scenario-toggle-off"><span data-valok="">The mobility/capacity toggle: validation year · no test counterpart.</span> The map shows the test year's own replay week; the test year's mobility check is in the text and the method drawer.</div>;
  return (
    <div className={short ? 'flex items-center' : 'flex flex-col items-center'} style={{ gap: short ? 8 : 4 }} data-testid="scenario-toggle">
      <div className="flex items-center gap-2 justify-center">
        <span className="t-12 fw-600 whitespace-nowrap" id={lid}>Which jobs can move?</span>
        <div className="seg" role="group" aria-labelledby={lid}>
          {SCENARIOS.map((x) => (
            <button key={x.id} aria-pressed={scenario === x.id} disabled={!scenarioOf(data!.flows, x.id)} onClick={() => set({ scenario: x.id })} title={`${x.label}: ${scenarioOf(data!.flows, x.id)?.note ?? ''}`}>
              {short ? x.short : x.label}
            </button>
          ))}
        </div>
      </div>
      {short ? (
        <div className="t-11 ink-2 whitespace-nowrap" aria-live="polite" data-testid="scenario-kind" title={s && !s.registered ? `${s.note}; a one-axis sensitivity, never pooled with the registered result` : undefined}>
          <span className="fw-600" style={{ color: C.ink }}>{s?.registered ? 'Registered result' : 'Scenario estimate'}</span>
        </div>
      ) : (
        <div className="t-11 ink-2 text-center" aria-live="polite" data-testid="scenario-kind">
          <span className="fw-600" style={{ color: C.ink }}>{s?.registered ? 'Registered result' : 'Scenario estimate (validation)'}</span>
          {s && !s.registered ? <span title="A one-axis sensitivity, never pooled with the registered result"> · {s.note} <Ev e="assumed">setting</Ev></span> : <> · validation year <Ev e="simulated" /></>}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ flexibility budget

export const BUCKET: Record<string, { name: string; fill: string; hatch?: boolean; ink: string }> = {
  moved_remote: { name: 'Ran elsewhere', fill: CARBON[0], ink: '#fff' },
  retimed_home: { name: 'Retimed in Utah', fill: C.route, ink: '#fff' },
  stayed_booking: { name: 'Could move, stayed', fill: '#e6d9ca', ink: C.ink },
  must_stay: { name: 'Must stay in Utah', fill: C.ink2, ink: '#fff' },
  capacity_blocked: { name: 'Capacity-blocked', fill: C.rushFill, hatch: true, ink: C.ink },
};

/** The budget's headline numbers for one policy (null if the file or the policy is missing). */
export function budgetFacts(budget: Json | null, p: string) {
  const b = budget?.policies?.[p] ?? budget?.policies?.[budget?.default_policy ?? 'S'];
  if (!b) return null;
  const by = Object.fromEntries((b.buckets as Json[]).map((k) => [k.id, k]));
  const total = b.total_mwh.value as number;
  const big = by.stayed_booking?.larger_than_destination_mwh?.value ?? 0;
  return { b, by, total, flex: b.flexible_mobile_share.value as number, fits: (b.fits_remote_share?.value ?? null) as number | null, must: b.must_stay_share.value as number, bigShare: total ? big / total : 0,
    slots: b.dest_slots.value as number, policy: budget.policies[p] ? p : budget.default_policy };
}

const pctSmall = (x: number | null | undefined) => (x == null ? '–' : x === 0 ? '0' : Math.abs(x) < 0.0005 ? '≈0' : pct(x, Math.abs(x) < 0.1 ? 1 : 0));
const mwh = (v: number) => (v > 0 && v < 0.1 ? '<0.1' : fmt(v, v > 0 && v < 10 ? 1 : 0));

/** One sentence: "{x}% of the energy sits in jobs that can move; {y}% must stay in Utah." */
export function BudgetHeadline({ p }: { p: string }) {
  const { data } = useApp();
  const f = budgetFacts(data!.budget, p);
  if (!f) return null;
  return (
    <span data-testid="budget-headline">
      {pct(f.flex, 0)}% of the energy sits in jobs flagged movable{f.fits != null ? ` (${pct(f.fits, 0)}% fit a remote site)` : ''}; {pct(f.must, 0)}% must stay in Utah.
    </span>
  );
}

/** A horizontal stacked bar sized by execution energy, buckets (a)–(e), with direct labels. */
export function BudgetBar({ p, rows = true, testId = 'budget' }: { p: string; rows?: boolean; testId?: string }) {
  const { data } = useApp();
  const [ref, w] = useWidth<HTMLDivElement>();
  const hid = 'hatch-' + useId().replace(/[^a-zA-Z0-9]/g, '');
  const f = budgetFacts(data!.budget, p);
  if (!f) return <div className="t-12 ink-3" data-valok="">The flexibility budget was computed on the validation year only (no test counterpart).</div>;
  const ks: Json[] = f.b.buckets;
  let x = 0;
  const H = 22;
  const label = `Flexibility budget for ${pname(f.policy)}: ` + ks.map((k) => `${BUCKET[k.id].name} ${k.share.value == null ? 'not run' : pctSmall(k.share.value) + '%'}`).join(', ');
  return (
    <div data-testid={testId}>
      <div ref={ref} role="img" aria-label={label}>
        {w > 0 && (
          <svg width={w} height={H} style={{ display: 'block' }}>
            <defs>
              <pattern id={hid} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill={C.rushFill} /><line x1="0" y1="0" x2="0" y2="6" stroke={C.rush} strokeWidth="1.4" /></pattern>
            </defs>
            <rect x={0} y={0} width={w} height={H} rx={4} fill="#fff" stroke={C.hair} />
            {ks.map((k) => {
              const s = (k.share.value as number | null) ?? 0, sw = s * w, x0 = x;
              x += sw;
              const st = BUCKET[k.id];
              return (
                <g key={k.id}>
                  <rect x={x0} y={0} width={Math.max(0, sw)} height={H} fill={st.hatch ? `url(#${hid})` : st.fill} stroke="#fff" strokeWidth={sw > 2 ? 1 : 0}>
                    <title>{`${st.name}: ${k.mwh.value == null ? 'not run' : `${fmt(k.mwh.value)} MWh, ${pctSmall(s)}% of energy`}`}</title>
                  </rect>
                  {sw >= 44 && <text x={x0 + sw / 2} y={H / 2 + 4} textAnchor="middle" fontSize={11} fontWeight={600} fill={st.ink}>{pct(s, 0)}%</text>}
                </g>
              );
            })}
          </svg>
        )}
      </div>
      {!rows && (
        <div className="flex flex-wrap t-11 ink-2" style={{ gap: '2px 12px', marginTop: 6 }} aria-hidden="true">
          {ks.map((k) => (
            <span key={k.id} className="inline-flex items-center gap-1 whitespace-nowrap">
              <svg width="10" height="10"><rect x="0.5" y="0.5" width="9" height="9" rx="2" fill={BUCKET[k.id].hatch ? `url(#${hid})` : BUCKET[k.id].fill} stroke={BUCKET[k.id].hatch ? C.rush : 'none'} /></svg>
              <span className="fw-500" style={{ color: C.ink }}>{BUCKET[k.id].name}</span> {k.status !== 'ok' ? 'not run' : `${pctSmall(k.share.value)}%`.replace('≈0%', '≈0%')}
            </span>
          ))}
        </div>
      )}
      {rows && (
        <ul className="t-12" style={{ listStyle: 'none', margin: '6px 0 0', padding: 0, display: 'grid', gap: 2 }}>
          {ks.map((k) => {
            const st = BUCKET[k.id];
            const nr = k.status !== 'ok';
            return (
              <li key={k.id} className="grid items-baseline" style={{ gridTemplateColumns: '12px minmax(0,1fr) auto', gap: '0 6px' }} title={k.text}>
                <svg width="10" height="10" aria-hidden="true" style={{ alignSelf: 'center' }}><rect x="0.5" y="0.5" width="9" height="9" rx="2" fill={st.hatch ? `url(#${hid})` : st.fill} stroke={st.hatch ? C.rush : 'none'} /></svg>
                <span className="fw-500 whitespace-nowrap" style={{ color: C.ink }}>{st.name}</span>
                <span className="num whitespace-nowrap">{nr ? <span className="ink-3">not run</span> : <><b className="fw-600">{pctSmall(k.share.value)}%</b><span className="ink-3"> · {mwh(k.mwh.value)} MWh · {pctSmall(k.saving_share.value)}% of saving</span></>}</span>
                {k.id === 'stayed_booking' && f.bigShare > 0 ? <span className="t-11 ink-3" style={{ gridColumn: '2 / 4' }}>{pct(f.bigShare / (k.share.value || 1), 0)}% of it is in jobs larger than a {fmt(f.slots)}-slot destination</span> : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ where the work went

/** The replay-week arcs of one policy in the toggled scenario, for the map (GPU-hours; < 1% not drawn). */
export function arcsOf(f: Json | null, dest: Dest) {
  const arcs: Json[] = f?.week_arcs ?? [];
  const gh = (a: Json) => (a.gpu_h.value as number) ?? 0;
  const max = Math.max(...arcs.map(gh), 1), tot = arcs.map(gh).reduce((x, y) => x + y, 0) || 1;
  return DESTS.flatMap((d) => {
    const a = arcs.find((x) => x.to === d);
    const g = a ? gh(a) : 0;
    if (g / tot < 0.01 || g === 0) return [];
    return [{ to: d, weight: Math.sqrt(g / max), label: `${Math.round(g).toLocaleString('en-US')} GPU-h`, selected: d === dest }];
  });
}

/** "ran 32% of its energy outside Utah (BPAT 1,757 MWh, …); 'moved' incl. retiming in Utah: 31%" (F08). */
export function RemoteLine({ f, p, over = 'Over the year' }: { f: Json | null; p: string; over?: string }) {
  if (!f) return null;
  const rem = DESTS.map((d) => [d, f.remote_execution_mwh[d].value as number] as const).filter(([, v]) => v > 0);
  return (
    <span data-testid="remote-line">
      {over}, by execution energy, {pname(p)} ran <b className="fw-600">{pct(f.remote_execution_share.value)}%</b> outside Utah
      {rem.length ? <> ({rem.map(([d, v]) => `${REGION[d].name} ${fmt(v)} MWh`).join(', ')})</> : null}
      {' '}and retimed {pct(f.retimed_home_execution_share.value)}% (flexible jobs) in Utah; rigid jobs' queue slips add {pct(f.rigid_slip_execution_share.value)}%, for the ledger's “moved” {pct(f.moved_share_energy.value)}%. {fmt(f.late_jobs.value)} late jobs.
    </span>
  );
}

/** S only ranks sites, so with no remote room it keeps every booking (shown in the hero and story 4). */
export function NoChangeNote({ f, p, testId = 'hero-nochange' }: { f: Json | null; p: string; testId?: string }) {
  if (!f || f.remote_execution_share.value !== 0 || f.retimed_home_execution_share.value !== 0) return null;
  return <div className="t-12 ink-2" style={{ marginTop: 4 }} data-testid={testId}>{pname(p)} only ranks sites, so with no remote room it keeps every booking; pick W or L under “Where the work went” to see waiting.</div>;
}
