// Stage 3 T10: the D-058 robustness and sensitivity checks (results/extensions.json), validation only.
// One compact table: each check's S, W and L saving vs U (b = 4) with its 95% interval, next to the
// registered result. Rows that did not run show their reason. Every number keeps its envelope.
import { contrast, pname, type Json } from '../lib/data';
import { fmt, pct } from '../lib/format';
import { Ev, EvCI } from './ui';

const POLS = ['S', 'W', 'L'] as const;

/** Plain-language row names, in display order. */
const SENS: [string, string][] = [
  ['phase_49', 'Workload shifted 49 days later'],
  ['phase_98', 'Workload shifted 98 days later'],
  ['dest_slots_0', 'No room at the destinations (wait only)'],
  ['dest_slots_1024', 'Twice the room at the destinations (1,024 GPU slots each)'],
  ['transfer_120min', 'A move takes 2 hours instead of 30 minutes'],
  ['batch_delay_24h', 'Batch jobs may wait 24 hours instead of 6'],
  ['mobility_le_8gpus', 'Only jobs of 8 GPUs or fewer may move'],
];

interface Cell { v: number | null; lo?: number; hi?: number; reason?: string | null }
export interface ExtRow { id: string; label: string; cells: Record<string, Cell>; late: number | null; status: string; reason?: string | null; group: 'registered' | 'basis' | 'scenario' }

const cell = (blocks: Json | undefined): Cell => {
  const b = blocks?.['4'];
  if (!b || b.saving?.value == null) return { v: null, reason: b?.saving?.reason ?? 'not run' };
  const ci = b.saving_ci95?.value as [number, number] | null;
  return { v: b.saving.value, lo: ci?.[0], hi: ci?.[1] };
};

/** The table's rows, from metrics.json (registered) and extensions.json. */
export function extRows(m: Json, ext: Json): ExtRow[] {
  const reg: Record<string, Cell> = {};
  for (const p of POLS) {
    const c = contrast(m, p);
    reg[p] = c ? { v: c.saving.value, lo: (c.saving_ci95.value as [number, number])[0], hi: (c.saving_ci95.value as [number, number])[1] } : { v: null };
  }
  const late = Object.values(m.policies as Record<string, Json>).reduce((a: number, r: Json) => a + (r.metrics.late_jobs?.value ?? 0), 0);
  const rows: ExtRow[] = [{ id: 'registered', label: 'As registered (phase 0, consumption basis)', cells: reg, late, status: 'ok', group: 'registered' }];
  if (!ext) return rows;
  const rp = ext.repricing, cs = ext.common_support;
  if (rp?.status === 'ok') {
    rows.push({ id: 'production', label: 'Production-basis carbon, same schedules', group: 'basis', status: 'ok', late: null,
      cells: Object.fromEntries(POLS.map((p) => [p, cell(rp.by_policy[p]?.production?.vs_U)])) });
  }
  if (cs?.status === 'ok') {
    rows.push({ id: 'common_support', group: 'basis', status: 'ok', late: null,
      label: `Only jobs priced on published hourly values (${pct(cs.cohort.share_jobs.value, 1)}% of jobs, ${pct(cs.cohort.energy_share_U.value, 1)}% of energy)`,
      cells: Object.fromEntries(POLS.map((p) => [p, cell(cs.by_policy[p]?.vs_U)])) });
  }
  for (const [id, label] of SENS) {
    const b = ext.phases?.[id] ?? ext.sensitivities?.[id];
    if (!b) continue;
    if (b.status !== 'ok') { rows.push({ id, label, cells: {}, late: null, status: b.status, reason: b.reason, group: 'scenario' }); continue; }
    const late = Object.values(b.policies as Record<string, Json>).reduce((a: number, r: Json) => a + (r.late_jobs?.value ?? 0), 0);
    rows.push({ id, label, group: 'scenario', status: 'ok', late,
      cells: Object.fromEntries(POLS.map((p) => [p, cell(b.policies[p]?.vs_U)])) });
  }
  return rows;
}

/** How each check reads inside a sentence ("We re-ran it ..."). */
export const PHRASE: Record<string, string> = {
  production: 'on production-basis carbon',
  common_support: 'on only the jobs priced on published hourly values',
  phase_49: 'with the workload shifted 49 days',
  phase_98: 'with the workload shifted 98 days',
  dest_slots_0: 'with no room at the destinations',
  dest_slots_1024: 'with twice the room there',
  transfer_120min: 'with 2-hour transfers',
  batch_delay_24h: 'with a 24-hour batch delay',
  mobility_le_8gpus: 'with only jobs of 8 GPUs or fewer allowed to move',
};
export const listJoin = (xs: string[]) => (xs.length <= 1 ? xs.join('') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`);

/** Consumption-basis checks that keep the registered fleet and mobility (only the cohort, the
 * workload alignment, the transfer time or the allowed delay change). The production basis is
 * reported on its own: it is a different carbon accounting, not a robustness check (fix r1 I-2). */
export const CONSUMPTION_CHECKS = ['common_support', 'phase_49', 'phase_98', 'transfer_120min', 'batch_delay_24h'];

/** The S–L range of one check row, rounded to whole percent: "4" or "3–4" (null if it did not run). */
export function roundedSpan(rows: ExtRow[], id: string): string | null {
  const s = placementSpan(rows, [id]);
  if (!s) return null;
  const [a, b] = s.map((x) => Math.round(x * 100));
  return a === b ? `${a}` : `${a}–${b}`;
}

/** Lowest and highest S/W/L point saving over the given rows (null if none ran). */
export function placementSpan(rows: ExtRow[], ids?: string[]): [number, number] | null {
  const xs = rows.filter((r) => r.status === 'ok' && r.group !== 'registered' && (ids ? ids.includes(r.id) : r.id !== 'dest_slots_0'))
    .flatMap((r) => POLS.map((p) => r.cells[p]?.v)).filter((v): v is number => typeof v === 'number');
  return xs.length ? [Math.min(...xs), Math.max(...xs)] : null;
}

const show = (c: Cell | undefined) => c && c.v != null
  ? <>{pct(c.v, 1)}% <span className="ink-3 fw-400">[{c.lo != null ? pct(c.lo, 1) : '–'}, {c.hi != null ? pct(c.hi, 1) : '–'}]</span></>
  : <span className="ink-3">{c?.reason ?? '–'}</span>;

export function ExtensionsTable({ m, ext, testId }: { m: Json; ext: Json; testId?: string }) {
  const rows = extRows(m, ext);
  return (
    <div>
      <div style={{ overflowX: 'auto' }}>
        <table className="tbl" data-testid={testId}>
          <thead>
            <tr>
              <th>Check <span className="fw-400">(validation year)</span></th>
              {POLS.map((p) => <th key={p} title={pname(p)}>{p} saving vs U <span className="fw-400">[95%]</span></th>)}
              <th>Late jobs</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className={r.group === 'registered' ? 'em' : ''}>
                <td style={{ whiteSpace: 'normal', maxWidth: 280 }}>{r.label}</td>
                {r.status === 'ok'
                  ? POLS.map((p) => <td key={p}>{show(r.cells[p])}</td>)
                  : <td colSpan={POLS.length} className="ink-3" style={{ textAlign: 'left' }}>not run: {r.reason}</td>}
                <td>{r.status !== 'ok' ? <span className="ink-3">–</span> : r.late == null ? <span className="ink-3">same schedules</span> : fmt(r.late)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap gap-3 items-center t-12 ink-3" style={{ marginTop: 6 }}>
        <span>{pname('S')}, {pname('W')} and {pname('L')}; ratio of totals, 4-week blocks.</span>
        <Ev e="simulated">savings, 95% intervals</Ev><Ev e="assumed">scenario settings</Ev><EvCI extra="both bases" />
      </div>
    </div>
  );
}
