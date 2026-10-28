// The sealed test year's pre-registered extras (D-071), read from results/test/extras.json, and the
// validation → test drift table. Every number comes from that file (or results/test/metrics.json);
// nothing here computes a saving from kilograms. Where the test year has no counterpart, the view says so.
import { useState } from 'react';
import { Ev, ScrollX } from './ui';
import { asNum, pname, type Env, type Json } from '../lib/data';
import { fmt, pct, pctRange, signed } from '../lib/format';

export const TEST_TAG = 'test year (sealed, opened once)';
export const VAL_ONLY = 'validation year · no test counterpart';

/** The label every test-year number carries. */
export const TestTag = ({ children }: { children?: React.ReactNode }) => (
  <span className="chip-neutral" data-testid="test-tag" style={{ fontWeight: 600, color: 'var(--ink)' }}>{children ?? TEST_TAG}</span>
);
/** The label a validation number carries when it is shown in test mode because the test has no counterpart. */
export const ValOnlyTag = ({ what }: { what?: string }) => (
  <span className="chip-neutral" data-testid="val-only" data-valok="">{what ? `${what}: ` : ''}{VAL_ONLY}</span>
);

const b4 = (cell: Json) => cell?.['4'];
const v = (e: Env | undefined | null) => asNum(e ?? null);

/** Facts the story, hero and drawer quote in test mode, all read from extras.json / test metrics. */
export function testFacts(x: Json | null, m: Json) {
  if (!x) return null;
  const mobX = x.extensions?.mobility_le_8gpus;
  const mobVals = mobX?.status === 'ok' ? (['S', 'W', 'L'] as const).map((p) => v(b4(mobX.vs_U[p])?.saving)).filter((n): n is number => n != null) : [];
  const mobS = mobX?.status === 'ok' ? b4(mobX.vs_U.S) : null;
  const sc = x.storage?.status === 'ok' ? x.storage.schedule_comparison.schedules : null;
  const carbonU = sc?.carbon.cases.U['4'], peakU = sc?.peak.cases.U['4'];
  // H3: does dynamic search (K, W, L) beat the fixed ranking S? diff_kg = S − candidate (positive = candidate emits less)
  const vsS = (['K', 'W', 'L'] as const).map((p) => {
    const c = m.contrasts.find((y: Json) => y.candidate === p && y.reference === 'S');
    const k = c?.blocks['4'];
    if (!k) return null;
    const d = v(k.diff_kg), ci = k.diff_kg_ci95.value as [number, number];
    // candidate − S in tonnes: the sign of "more CO₂ than S"
    return { p, t: -(d as number) / 1000, lo: -ci[1] / 1000, hi: -ci[0] / 1000, beats: ci[0] > 0 };
  }).filter(Boolean) as { p: string; t: number; lo: number; hi: number; beats: boolean }[];
  const checks = ['phase_49', 'phase_98', 'transfer_120min', 'batch_delay_24h'].map((id) => x.extensions?.[id]).filter((r: Json) => r?.status === 'ok');
  const checkVals = checks.flatMap((r: Json) => (['S', 'W', 'L'] as const).map((p) => v(b4(r.vs_U[p])?.saving))).filter((n: number | null): n is number => n != null);
  return {
    mob: mobVals.length ? { lo: Math.min(...mobVals), hi: Math.max(...mobVals), s: v(mobS?.saving), sLo: mobS?.saving_ci95?.value?.[0] as number | undefined, sHi: mobS?.saving_ci95?.value?.[1] as number | undefined } : null,
    storage: carbonU && peakU ? {
      carbonCut: v(carbonU.cut_frac)!, peakCut: v(peakU.cut_frac)!,
      rushBefore: v(peakU.rush_import_before_mw)!, carbonRushAfter: v(carbonU.rush_import_after_mw)!, peakRushAfter: v(peakU.rush_import_after_mw)!,
      carbonRushH: v(carbonU.rush_hours_discharging)!, peakRushH: v(peakU.rush_hours_discharging)!, rushN: v(x.storage.rush.n_hours)!,
      moveOnly: v(x.storage.combined.move_only_cut_frac)!, moveStore: v(x.storage.combined.move_and_store_cut_frac.A['4'])!,
    } : null,
    h3: vsS.length ? { rows: vsS, supported: vsS.some((r) => r.beats) } : null,
    checks: checkVals.length ? { n: checks.length, lo: Math.min(...checkVals), hi: Math.max(...checkVals) } : null,
    ranPhases: ['phase_49', 'phase_98'].filter((id) => x.extensions?.[id]?.status === 'ok'),
  };
}

/** "K +9.9 t [0.8, 19.5]" */
export const tonnes = (r: { p: string; t: number; lo: number; hi: number }) => `${r.p} − S ${signed(r.t, 1)} t [${fmt(r.lo, 1)}, ${fmt(r.hi, 1)}]`;

/** The H3 sentence: whether any forecast-driven policy beat the fixed ranking on the test year. */
export function h3Sentence(h3: NonNullable<ReturnType<typeof testFacts>>['h3']) {
  if (!h3) return '';
  const worse = h3.rows.filter((r) => r.lo > 0), tied = h3.rows.filter((r) => r.lo <= 0 && !r.beats);
  if (h3.supported) return `Dynamic search beat the fixed ranking on the test year: ${h3.rows.filter((r) => r.beats).map(tonnes).join('; ')}.`;
  return `Dynamic search did not beat the fixed ranking (H3 not supported): ${[...worse, ...tied].map(tonnes).join('; ')}${tied.length ? `; ${tied.map((r) => r.p).join(' and ')} ${tied.length > 1 ? 'are' : 'is'} not distinguishable from S` : ''}.`;
}

// ---------------------------------------------------------------- the drift table
function cell(e: Env<unknown> | null | undefined): string {
  if (!e || e.status !== 'ok' || e.value == null) return e?.reason ?? 'unavailable';
  const one = (x: number) => {
    switch (e.unit) {
      case 'fraction': return `${pct(x, 1)}%`;
      case 'kg_CO2': return `${fmt(x / 1000, 1)} t`;
      case 't_CO2': return `${fmt(x, 1)} t`;
      case 'MW': return `${fmt(x, 2)} MW`;
      case 'g/kWh': return `${fmt(x, 1)}`;
      case 'ratio': return fmt(x, 2);
      case 'hours': return fmt(x, 0);
      default: return fmt(x, 2);
    }
  };
  const val = e.value as number | number[];
  return Array.isArray(val) ? `[${val.map(one).join(', ')}]` : one(val);
}
function diffCell(e: Env<unknown> | null | undefined): string {
  if (!e || e.status !== 'ok' || e.value == null || Array.isArray(e.value)) return '';
  const x = e.value as number;
  switch (e.unit) {
    case 'fraction': return `${signed(x * 100, 1)} pt`;
    case 'kg_CO2': return `${signed(x / 1000, 1)} t`;
    case 't_CO2': return `${signed(x, 1)} t`;
    case 'MW': return `${signed(x, 2)} MW`;
    case 'g/kWh': return signed(x, 1);
    case 'ratio': return signed(x, 2);
    default: return signed(x, 0);
  }
}

/** The row's name, with kilograms restated as the tonnes the cells show. */
const metricLabel = (r: Json, strip?: RegExp) => {
  const m: string = strip ? r.metric.replace(strip, '') : r.metric;
  return r.test?.unit === 'kg_CO2' || r.validation?.unit === 'kg_CO2' ? m.replace(/\(kg\b/, '(t') : m;
};

/** Drift rows of one D-071 item, in the file's order. */
export const driftRows = (x: Json | null, item: string | ((s: string) => boolean)) =>
  ((x?.drift?.rows ?? []) as Json[]).filter((r) => (typeof item === 'string' ? r.item === item : item(r.item)));

export function DriftTable({ rows, testId, label, strip }: { rows: Json[]; testId: string; label: string; strip?: RegExp }) {
  if (!rows.length) return <p className="t-12 ink-3" style={{ margin: 0 }}>Not in the test run's drift table.</p>;
  return (
    <ScrollX label={label}>
      <table className="tbl" data-testid={testId} data-valok="">
        <caption className="sr-only">{label}: validation year, test year (sealed, opened once), and test − validation</caption>
        <thead><tr><th scope="col" style={{ textAlign: 'left' }}>Quantity</th><th scope="col">Validation</th><th scope="col">Test (sealed)</th><th scope="col">Test − validation</th></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td style={{ textAlign: 'left', whiteSpace: 'normal' }}>{metricLabel(r, strip)}</td>
              <td className="ink-2">{cell(r.validation)}</td>
              <td className="fw-600">{cell(r.test)}</td>
              <td className="ink-2">{diffCell(r.difference)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollX>
  );
}

const ITEMS: [string, string][] = [
  ['headline', 'Headline'], ['1 extensions', 'Checks (extensions)'], ['2 storage', 'Storage'], ['2b storage schedules', 'Storage: carbon vs peak schedule'],
  ['3 toughest days', 'Toughest days'], ['4 water', 'Water'], ['5 seasonal', 'Seasons'], ['6 forecast skill', 'Forecast skill'], ['6 permutation importance', 'Permutation importance'],
];

/** The compact validation → test drift view: every headline number and every D-071 item, one item at a time. */
export function DriftView({ x }: { x: Json }) {
  const [item, setItem] = useState('headline');
  const rows = driftRows(x, item);
  return (
    <div data-testid="drift-view" className="flex flex-col" style={{ gap: 8 }}>
      <div className="flex flex-wrap items-center gap-3">
        <label className="t-12 ink-2 flex items-center gap-2">Show
          <select className="btn" value={item} onChange={(e) => setItem(e.target.value)} data-testid="drift-item" aria-label="Drift table item">
            {ITEMS.map(([k, l]) => <option key={k} value={k}>{l} ({driftRows(x, k).length})</option>)}
          </select>
        </label>
        <TestTag />
        <span className="t-11 ink-3" data-valok="">{fmt(v(x.drift.n_rows) ?? 0)} rows in all; {x.drift.rule}. <Ev e="simulated" /><Ev e="measured">skill</Ev></span>
      </div>
      <DriftTable rows={rows} testId="drift-table" label={`Validation to test drift, ${ITEMS.find(([k]) => k === item)?.[1]}`} />
    </div>
  );
}

// ---------------------------------------------------------------- item panels
/** D-073: the carbon schedule (the headline) beside the peak-aimed schedule, 4 MWh, every job in Utah. */
export function TestStorage({ x, testId = 'test-storage' }: { x: Json; testId?: string }) {
  const s = x.storage;
  if (s?.status !== 'ok') return <p className="t-12 ink-3">Storage did not run on the test year.</p>;
  const sc = s.schedule_comparison.schedules;
  const n = v(s.rush.n_hours)!;
  const row = (k: 'carbon' | 'peak', name: string) => {
    const c = sc[k].cases.U['4'];
    return (
      <tr key={k}>
        <th scope="row" style={{ textAlign: 'left', fontWeight: 500 }}>{name}</th>
        <td>{pct(v(c.cut_frac)!, 1)}%</td>
        <td>{fmt(v(c.rush_import_before_mw)!, 2)} → <b className="fw-600">{fmt(v(c.rush_import_after_mw)!, 2)}</b> MW</td>
        <td>{fmt(v(c.rush_hours_discharging)!)} of {fmt(n)}</td>
      </tr>
    );
  };
  return (
    <div className="flex flex-col" style={{ gap: 6 }}>
      <ScrollX label="Storage schedules on the test year, table">
        <table className="tbl" data-testid={testId}>
          <caption className="sr-only">Battery 4 MWh at the Utah cluster, test year: carbon schedule vs peak-aimed schedule</caption>
          <thead><tr><th scope="col" style={{ textAlign: 'left' }}>4 MWh battery, every job in Utah</th><th scope="col">CO₂ cut</th><th scope="col">Rush-hour grid import</th><th scope="col">Rush hours discharging</th></tr></thead>
          <tbody>{row('carbon', 'Carbon schedule (the headline)')}{row('peak', 'Peak-aimed schedule (D-073)')}</tbody>
        </table>
      </ScrollX>
      <div className="t-11 ink-3" data-valok="">Rush hours: test-year hours with Utah net load at or above the training years' top 1% ({fmt(v(s.rush.threshold_mw)!)} MW), {fmt(n)} hours. {String(s.schedule_comparison.label_note).replace(/^./, (c) => c.toUpperCase())}. Move small and store for big: {pct(v(s.combined.move_only_cut_frac)!, 1)}% moving only, {pct(v(s.combined.move_and_store_cut_frac.A['4'])!, 1)}% with the 4 MWh battery. <TestTag /> <Ev e="simulated">dispatch</Ev> <Ev e="assumed">battery, schedules</Ev></div>
    </div>
  );
}

/** D-066 on the test window: the top 3 days by PACE daily maximum net load, CO₂ per policy by day. */
export function TestToughDays({ x }: { x: Json }) {
  const t = x.toughest_days;
  if (t?.status !== 'ok') return null;
  return (
    <div className="panel flex flex-col min-h-0 flex-1" style={{ padding: '12px 14px 10px', gap: 8 }} data-testid="test-tough-days">
      <div className="flex items-center justify-between gap-2 flex-wrap"><span className="t-15">Utah's toughest grid days</span><TestTag /></div>
      <div className="t-11 ink-3">Top 3 test-year days by Utah's peak net load, the rule fixed in advance (D-066), of {fmt(v(t.days_considered)!)} days. <Ev e="observed">load</Ev> <Ev e="simulated">CO₂ by day</Ev></div>
      <ScrollX label="Toughest test-year days, table">
        <table className="tbl">
          <caption className="sr-only">Utah's toughest grid days in the test year: peak net load and each policy's CO2 that day</caption>
          <thead><tr><th scope="col" style={{ textAlign: 'left' }}>Day</th><th scope="col">Peak net load</th><th scope="col">{pname('U')}</th><th scope="col">S vs U</th><th scope="col">W vs U</th></tr></thead>
          <tbody>
            {t.days.map((d: Json) => (
              <tr key={d.date}>
                <th scope="row" style={{ textAlign: 'left', fontWeight: 500 }}>{new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(`${d.date}T12:00:00Z`))}</th>
                <td>{fmt(v(d.peak.net_load_mw)!)} MW</td>
                <td>{fmt(v(d.policies.U.co2_t)!, 1)} t</td>
                <td>{pct(v(d.policies.S.co2_change_vs_U_frac)!, 1)}%</td>
                <td>{pct(v(d.policies.W.co2_change_vs_U_frac)!, 1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollX>
      <div className="t-11 ink-3" data-valok="">The validation days' chart, temperatures and public context are not recomputed for the test year. Validation → test for these rows is in the drift table (method drawer).</div>
    </div>
  );
}

/** One D-071 item as validation beside test, for the method drawer. */
export function ItemSection({ x, item, strip, note }: { x: Json; item: string; strip?: RegExp; note?: React.ReactNode }) {
  const label = ITEMS.find(([k]) => k === item)?.[1] ?? item;
  return (
    <div className="flex flex-col" style={{ gap: 6 }}>
      {note ? <p className="t-12 ink-2" style={{ margin: 0 }} data-valok="">{note}</p> : null}
      <DriftTable rows={driftRows(x, item)} testId={`test-item-${item.replace(/\W+/g, '-')}`} label={`${label}, validation and test year`} strip={strip} />
    </div>
  );
}

/** Pre-registered checks on the test year: S, W and L vs U at b = 4, from the extension runs. */
export const checkLine = (f: ReturnType<typeof testFacts>) =>
  f?.checks ? `On the test year, ${f.checks.n} one-axis checks (the workload shifted 49 and 98 days, 2-hour transfers, a 24-hour batch delay) keep S, W and L at ${pctRange(f.checks.lo, f.checks.hi)}%: scenario estimates, not a confidence interval.` : '';

