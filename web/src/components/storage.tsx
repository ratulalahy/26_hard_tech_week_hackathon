// Stage 3 T10b (D-061; Astra F12–F15, F18, F29; fix round 1): "Move what you can, store for what
// you can't". An illustrative battery at the Utah cluster (results/storage.json), never part of the
// registered result. Dispatch outcomes are simulated, carbon inputs modeled, battery settings
// assumed. Charge and discharge are not the router's action, so they wear ink, never the route
// blue; energy held in the battery wears the teal "stored" outline (tokens.md).
import { useMemo } from 'react';
import { C } from '../lib/color';
import { pname, type Json } from '../lib/data';
import { fmt, fmtHour, pct } from '../lib/format';
import { EChart } from './EChart';

export const V = (e: Json): number => e?.value as number;
export const VS = (e: Json): number[] => (e?.value ?? []) as number[];
const ETA = '0.85';

/** The numbers the beat and the drawer quote, all from storage.json (η 0.85, headline size). */
export function storageFacts(s: Json) {
  const sizes = VS(s.assumptions.sizes_mwh);
  const E = V(s.headline.e_mwh), i = sizes.indexOf(E);
  const plateau = V(s.headline.plateau_e_mwh), ip = sizes.indexOf(plateau);
  const u = s.cases.U, mob = s.cases.mobility_le_8gpus_W;
  const A = u.strategies.A[ETA], B = u.strategies.B[ETA];
  const be = s.break_even, mt = be.marginal_threshold;
  const etaI = VS(s.assumptions.etas).indexOf(V(s.assumptions.eta_default));
  const imp = u.import_at_headline.A;
  const rel = s.peak_relief.policies;
  const hr = VS(u.charge_headroom_mw);
  const sens = s.sensitivity?.connection_plus_25;
  return {
    E, P: E * V(s.assumptions.p_over_e), hours: VS(u.load_hours)[i], i, sizes, plateau,
    cutA: VS(A.cut_frac)[i], cutB: VS(B.cut_frac)[i], cutAt: VS(A.cut_t)[i],
    cutAplateau: VS(A.cut_frac)[ip],
    terminal: VS(A.terminal_soc_mwh)[i],
    throughput: VS(A.throughput_mwh_per_day)[i], cycles: VS(A.cycles_per_day)[i],
    moveOnly: V(s.combined.move_only_cut_frac),
    moveStoreA: VS(s.combined.move_and_store_cut_frac.A)[i], moveStoreB: VS(s.combined.move_and_store_cut_frac.B)[i],
    mobCutA: VS(mob.strategies.A[ETA].cut_frac)[i],
    chargeCI: V(be.train_charge_ci_g_kwh), dischargeCI: V(be.train_discharge_ci_g_kwh), chargeOverEta: VS(be.train_charge_ci_over_eta_g_kwh)[etaI],
    eta: V(s.assumptions.eta_default), ratio: VS(mt.required_discharge_over_charge)[etaI],
    mCharge: V(mt.reference_charge_hours_g_kwh), mDischarge: V(mt.reference_discharge_hours_g_kwh), mFlat: V(mt.flat_g_kwh),
    flatAddT: -VS(A.flat_marginal_cut_t)[i], flatAddTB: -VS(B.flat_marginal_cut_t)[i],
    headroomLo: hr[0], headroomMid: hr[1],
    rushN: V(s.rush.n_hours), rushDays: V(s.rush.n_days), rushThr: V(s.rush.threshold_mw), peakNet: V(s.rush.peak_net_load_mw),
    rushBefore: V(imp.rush_before_mw), rushAfter: V(imp.rush_after_mw), rushAfterB: V(u.import_at_headline.B.rush_after_mw),
    rebound: V(imp.rebound_mw), peakBefore: V(imp.peak_before_mw), peakAfter: V(imp.peak_after_mw),
    conn: V(s.assumptions.connection_mw),
    sensConn: sens ? V(sens.connection_mw) : null, sensCutA: sens ? VS(sens.A.cut_frac)[i] : null,
    reliefW: -V(rel.W.PACE.rush_change_vs_U_mw),
    destW: ['BPAT', 'CISO', 'NEVP'].reduce((a, d) => a + V(rel.W[d].rush_change_vs_U_mw), 0),
    charge: VS(s.schedule.charge_hours), discharge: VS(s.schedule.discharge_hours),
  };
}

/** Hours whose energy sits in the battery: after the charge window until the last discharge hour, excluding both windows. */
export function storedHours(charge: number[], discharge: number[]): number[] {
  const ch = new Set(charge), dis = new Set(discharge), out: number[] = [];
  const lastCharge = Math.max(...charge);
  const walk: number[] = [];
  for (let k = 1; k < 24; k++) { const h = (lastCharge + k) % 24; if (ch.has(h)) break; walk.push(h); }
  let lastDis = -1;
  walk.forEach((h, j) => { if (dis.has(h)) lastDis = j; });
  walk.slice(0, lastDis + 1).forEach((h) => { if (!dis.has(h)) out.push(h); });
  return out;
}

const runs = (hs: number[]): [number, number][] => {
  const s = [...hs].sort((a, b) => a - b), out: [number, number][] = [];
  for (const h of s) { const r = out[out.length - 1]; if (r && h === r[1] + 1) r[1] = h; else out.push([h, h]); }
  return out;
};
export const hourSpans = (hs: number[]) => {
  const r = runs(hs);
  if (r.length > 1 && r[0][0] === 0 && r[r.length - 1][1] === 23) { const last = r.pop()!; r[0] = [last[0], r[0][1] + 24]; }
  return r.map(([a, b]) => `${fmtHour(a)}–${fmtHour(b + 1)}`);
};

/** % CO₂ cut vs battery size: A solid, B dashed ("hindsight heuristic"), and the flat-marginal threshold scenario below zero. */
export function StorageCurve({ s }: { s: Json }) {
  const f = storageFacts(s);
  const u = s.cases.U;
  const option = useMemo(() => {
    const pts = (k: string, st = 'A') => VS(u.strategies[st][ETA][k]).map((v, j) => [f.sizes[j], v * 100]);
    const A = pts('cut_frac'), B = pts('cut_frac', 'B'), M = pts('flat_marginal_cut_frac');
    const top = Math.ceil(Math.max(...B.map((p) => p[1])) + 1), bot = Math.floor(Math.min(...M.map((p) => p[1])) - 0.5);
    const lab = (t: string, color: string) => ({ show: true, formatter: t, color, fontSize: 11, fontFamily: 'Funnel Sans' });
    return {
      grid: { left: 40, right: 150, top: 16, bottom: 36 },
      xAxis: { type: 'value', min: 0, max: Math.max(...f.sizes), name: 'battery size, MWh (power = size ÷ 4)', nameLocation: 'middle', nameGap: 24, splitLine: { show: false } },
      yAxis: { type: 'value', min: bot, max: top, axisLabel: { formatter: (v: number) => `${v}%` } },
      tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${fmt(v, 1)}%` },
      series: [
        { name: 'A fixed daily schedule', type: 'line', data: A, symbol: 'circle', symbolSize: 5, lineStyle: { color: C.ink, width: 2 }, itemStyle: { color: C.ink },
          endLabel: lab('fixed schedule', C.ink),
          markLine: { symbol: 'none', silent: true, lineStyle: { color: C.ink3, width: 1 }, label: { show: false }, data: [{ yAxis: 0 }] },
          markPoint: { symbol: 'circle', symbolSize: 9, itemStyle: { color: '#fff', borderColor: C.ink, borderWidth: 2 },
            label: { show: true, position: 'top', formatter: `${fmt(f.E)} MWh: ${pct(f.cutA, 1)}%`, color: C.ink, fontSize: 11, fontWeight: 500, fontFamily: 'Funnel Sans' }, data: [{ coord: [f.E, f.cutA * 100] }] } },
        { name: 'B hindsight heuristic', type: 'line', data: B, symbol: 'none', lineStyle: { color: C.ink3, width: 1.5, type: [5, 3] }, endLabel: lab('hindsight heuristic', C.ink3) },
        { name: 'A on a flat marginal 618 g/kWh (threshold scenario)', type: 'line', data: M, symbol: 'none', lineStyle: { color: C.ink2, width: 1.5, type: [1, 3] },
          endLabel: { ...lab('flat marginal 618 g/kWh\n(threshold scenario)', C.ink2), lineHeight: 14 } },
      ],
    };
  }, [s]); // eslint-disable-line react-hooks/exhaustive-deps
  return <EChart option={option} className="h-full" testId="storage-curve" label={`CO₂ change vs battery size at the Utah cluster: the fixed daily schedule cuts ${pct(f.cutA, 1)}% at ${fmt(f.E)} MWh; on a flat marginal factor the same battery adds CO₂`} />;
}

/** The cluster's grid import by hour, before and after the fixed schedule (headline size), with the schedule's windows marked. */
export function ImportChart({ s }: { s: Json }) {
  const f = storageFacts(s);
  const imp = s.cases.U.import_at_headline.A;
  const option = useMemo(() => {
    const hrs = Array.from({ length: 24 }, (_, h) => fmtHour(h));
    const area = (hs: number[], name: string, style: Json) => runs(hs).map(([a, b]) => [
      { xAxis: hrs[a], name, itemStyle: style, label: { show: b > a } }, { xAxis: hrs[Math.min(b + 1, 23)] }]);
    const charge = area(f.charge, 'charge', { color: 'rgba(45,29,20,.05)', borderColor: C.ink, borderWidth: 1 });
    const dis = area(f.discharge, 'discharge', { color: 'rgba(45,29,20,.16)' });
    const stored = area(storedHours(f.charge, f.discharge), 'stored', { color: 'rgba(0,0,0,0)', borderColor: C.stored, borderWidth: 1.25, borderType: [3, 2] });
    return {
      grid: { left: 40, right: 96, top: 24, bottom: 24 },
      xAxis: { type: 'category', data: hrs, boundaryGap: false, axisLabel: { interval: 5 } },
      yAxis: { type: 'value', min: 0, max: 2, name: 'MW', nameGap: 8, nameTextStyle: { align: 'right' } },
      tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${fmt(v, 2)} MW` },
      series: [
        { name: 'without storage', type: 'line', data: VS(imp.before_by_hour_mw), lineStyle: { color: C.ink3, width: 1.5, type: [5, 3] }, symbol: 'none',
          endLabel: { show: true, formatter: 'without', color: C.ink3, fontSize: 11, fontFamily: 'Funnel Sans' },
          markArea: { silent: true, label: { show: true, position: 'insideTop', color: C.ink2, fontSize: 11, fontFamily: 'Funnel Sans' }, data: [...charge, ...dis, ...stored] } },
        { name: `with ${fmt(f.E)} MWh`, type: 'line', data: VS(imp.after_by_hour_mw), lineStyle: { color: C.ink, width: 2 }, symbol: 'none',
          endLabel: { show: true, formatter: `with ${fmt(f.E)} MWh`, color: C.ink, fontSize: 11, fontFamily: 'Funnel Sans' },
          markLine: { symbol: 'none', silent: true, lineStyle: { color: C.ink3, type: [2, 3], width: 1 }, label: { formatter: 'site connection', color: C.ink3, fontSize: 11, position: 'insideStartBottom' }, data: [{ yAxis: f.conn }] } },
      ],
    };
  }, [s]); // eslint-disable-line react-hooks/exhaustive-deps
  return <EChart option={option} className="h-full" testId="storage-import" label={`Utah cluster grid import by hour, typical validation day, without and with a ${fmt(f.E)} MWh battery on the fixed schedule: charge ${hourSpans(f.charge).join(', ')}, discharge ${hourSpans(f.discharge).join(', ')}`} />;
}

const SITE_NAME: Record<string, string> = { PACE: 'Utah', BPAT: 'Northwest', CISO: 'California', NEVP: 'Nevada' };
/** Router peak relief from the registered ledgers: cluster load in Utah's rush hours, U vs S and W. */
export function ReliefTable({ s }: { s: Json }) {
  const rel = s.peak_relief.policies;
  const pols = ['U', 'S', 'W'].filter((p) => rel[p]);
  return (
    <table className="tbl" data-testid="storage-relief">
      <thead><tr><th>Policy</th><th>Utah, rush hours</th><th>Utah, peak hour</th><th>Added at destinations</th></tr></thead>
      <tbody>
        {pols.map((p) => {
          const u = rel[p].PACE;
          const dest = ['BPAT', 'CISO', 'NEVP'].map((d) => [d, V(rel[p][d].rush_change_vs_U_mw)] as const).filter(([, v]) => v > 0.0005);
          return (
            <tr key={p}>
              <td>{pname(p)}</td>
              <td>{fmt(V(u.rush_mean_mw), 2)} MW{p !== 'U' ? <span className="ink-3"> ({fmt(V(u.rush_change_vs_U_mw), 2)})</span> : null}</td>
              <td>{fmt(V(u.at_peak_mw), 2)} MW{p !== 'U' ? <span className="ink-3"> ({fmt(V(u.at_peak_change_vs_U_mw), 2)})</span> : null}</td>
              <td>{dest.length ? dest.map(([d, v]) => `+${fmt(v, 2)} ${SITE_NAME[d]}`).join(', ') : '–'}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/** The rush-threshold sensitivity (95th, 98th, 99th percentile of 2022–24 net load): W's relief in Utah. */
export function RushSensitivity({ s }: { s: Json }) {
  return (
    <table className="tbl" data-testid="storage-rush-sens">
      <thead><tr><th>Threshold (2022–24)</th><th>Hours (days)</th><th>S, Utah</th><th>W, Utah</th><th>W, elsewhere</th></tr></thead>
      <tbody>
        {(s.rush.sensitivity as Json[]).map((r) => (
          <tr key={V(r.quantile)}>
            <td>top {pct(1 - V(r.quantile), 0)}%: {fmt(V(r.threshold_mw))} MW</td>
            <td>{fmt(V(r.n_hours))} ({fmt(V(r.n_days))})</td>
            <td>{fmt(V(r.relief.S.PACE), 2)} MW</td>
            <td>{fmt(V(r.relief.W.PACE), 2)} MW</td>
            <td>+{fmt(['BPAT', 'CISO', 'NEVP'].reduce((a, d) => a + V(r.relief.W[d]), 0), 2)} MW</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
