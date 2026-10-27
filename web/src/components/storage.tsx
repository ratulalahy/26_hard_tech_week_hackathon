// Stage 3 T10b (D-061; Astra F12–F15, F18, F29): "Move what you can, store for what you can't".
// An illustrative battery at the Utah cluster (results/storage.json), never part of the registered
// result. Dispatch outcomes are simulated, carbon inputs modeled, battery settings assumed.
// Charge and discharge are not the router's action, so they wear ink, never the route blue; energy
// held in the battery wears the teal "stored" outline (tokens.md).
import { useMemo } from 'react';
import { C, ci2c, onFill } from '../lib/color';
import { pname, type Json } from '../lib/data';
import { fmt, fmtHour, pct } from '../lib/format';
import { EChart } from './EChart';
import { useWidth } from './charts';

export const V = (e: Json): number => e?.value as number;
export const VS = (e: Json): number[] => (e?.value ?? []) as number[];
const ETA = '0.85';

/** The numbers the beat and the drawer quote, all from storage.json (η 0.85, headline size). */
export function storageFacts(s: Json) {
  const sizes = VS(s.assumptions.sizes_mwh);
  const E = V(s.headline.e_mwh), i = sizes.indexOf(E);
  const u = s.cases.U, mob = s.cases.mobility_le_8gpus_W;
  const A = u.strategies.A[ETA], B = u.strategies.B[ETA];
  const be = s.break_even, mt = be.marginal_threshold;
  const etaI = VS(s.assumptions.etas).indexOf(V(s.assumptions.eta_default));
  const imp = u.import_at_headline.A;
  const rel = s.peak_relief.policies;
  return {
    E, P: E * V(s.assumptions.p_over_e), hours: VS(u.load_hours)[i], i, sizes,
    cutA: VS(A.cut_frac)[i], cutB: VS(B.cut_frac)[i], cutAt: VS(A.cut_t)[i], cutBt: VS(B.cut_t)[i],
    maxA: Math.max(...VS(A.cut_frac)), maxB: Math.max(...VS(B.cut_frac)),
    terminal: VS(A.terminal_soc_mwh)[i],
    moveOnly: V(s.combined.move_only_cut_frac),
    moveStoreA: VS(s.combined.move_and_store_cut_frac.A)[i], moveStoreB: VS(s.combined.move_and_store_cut_frac.B)[i],
    mobCutA: VS(mob.strategies.A[ETA].cut_frac)[i],
    chargeCI: V(be.train_charge_ci_g_kwh), dischargeCI: V(be.train_discharge_ci_g_kwh), chargeOverEta: VS(be.train_charge_ci_over_eta_g_kwh)[etaI],
    eta: V(s.assumptions.eta_default), ratio: VS(mt.required_discharge_over_charge)[etaI],
    mCharge: V(mt.reference_charge_hours_g_kwh), mDischarge: V(mt.reference_discharge_hours_g_kwh), mFlat: V(mt.flat_g_kwh),
    flatAddT: -VS(mt.flat_scenario_cut_t_A.U)[i],
    rushN: V(s.rush.n_hours), rushThr: V(s.rush.threshold_mw), rushByHour: VS(s.rush.by_local_hour),
    rushBefore: V(imp.rush_before_mw), rushAfter: V(imp.rush_after_mw), rushAfterB: V(u.import_at_headline.B.rush_after_mw),
    rebound: V(imp.rebound_mw), peakBefore: V(imp.peak_before_mw), peakAfter: V(imp.peak_after_mw),
    conn: V(s.assumptions.connection_mw),
    reliefW: -V(rel.W.PACE.rush_change_vs_U_mw), reliefS: -V(rel.S.PACE.rush_change_vs_U_mw),
    reliefWpeak: -V(rel.W.PACE.at_peak_change_vs_U_mw),
    destW: ['BPAT', 'CISO', 'NEVP'].reduce((a, d) => a + V(rel.W[d].rush_change_vs_U_mw), 0),
    charge: VS(s.schedule.charge_hours), discharge: VS(s.schedule.discharge_hours),
  };
}

/** Hours whose energy sits in the battery: after the charge window until the last discharge hour, excluding both windows. */
export function storedHours(charge: number[], discharge: number[]): number[] {
  const ch = new Set(charge), dis = new Set(discharge), out: number[] = [];
  const lastCharge = Math.max(...charge);
  // walk from the end of the charge window until the next charge window starts
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
  // join a run that wraps midnight (… 23 and 0 …)
  if (r.length > 1 && r[0][0] === 0 && r[r.length - 1][1] === 23) { const last = r.pop()!; r[0] = [last[0], r[0][1] + 24]; }
  return r.map(([a, b]) => `${fmtHour(a)}–${fmtHour(b + 1)}`);
};

/** % CO₂ cut vs battery size: A solid, B dashed ("hindsight heuristic"). */
export function StorageCurve({ s }: { s: Json }) {
  const f = storageFacts(s);
  const u = s.cases.U;
  const option = useMemo(() => {
    const A = VS(u.strategies.A[ETA].cut_frac).map((v, k) => [f.sizes[k], v * 100]);
    const B = VS(u.strategies.B[ETA].cut_frac).map((v, k) => [f.sizes[k], v * 100]);
    const top = Math.ceil(Math.max(...B.map((p) => p[1])) + 1);
    return {
      grid: { left: 40, right: 128, top: 16, bottom: 36 },
      xAxis: { type: 'value', min: 0, max: Math.max(...f.sizes), name: 'battery size, MWh (power = size ÷ 4)', nameLocation: 'middle', nameGap: 24, splitLine: { show: false } },
      yAxis: { type: 'value', min: 0, max: top, axisLabel: { formatter: (v: number) => `${v}%` } },
      tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${fmt(v, 1)}%` },
      series: [
        { name: 'A fixed daily schedule', type: 'line', data: A, symbol: 'circle', symbolSize: 5, lineStyle: { color: C.ink, width: 2 }, itemStyle: { color: C.ink },
          endLabel: { show: true, formatter: 'fixed schedule', color: C.ink, fontSize: 11, fontFamily: 'Funnel Sans' },
          markPoint: { symbol: 'circle', symbolSize: 9, itemStyle: { color: '#fff', borderColor: C.ink, borderWidth: 2 }, label: { show: true, position: 'top', formatter: `${fmt(f.E)} MWh: ${pct(f.cutA, 1)}%`, color: C.ink, fontSize: 11, fontWeight: 500, fontFamily: 'Funnel Sans' }, data: [{ coord: [f.E, f.cutA * 100] }] } },
        { name: 'B hindsight heuristic', type: 'line', data: B, symbol: 'none', lineStyle: { color: C.ink3, width: 1.5, type: [5, 3] },
          endLabel: { show: true, formatter: 'hindsight heuristic', color: C.ink3, fontSize: 11, fontFamily: 'Funnel Sans' } },
      ],
    };
  }, [s]); // eslint-disable-line react-hooks/exhaustive-deps
  return <EChart option={option} className="h-full" testId="storage-curve" label={`CO₂ cut vs battery size at the Utah cluster: a fixed daily schedule reaches ${pct(f.maxA, 1)}%, the hindsight heuristic ${pct(f.maxB, 1)}%`} />;
}

const LX = 64;
/** Utah's validation-year day (modeled CI by local hour) with the fixed schedule's windows and the rush hours. */
export function StorageDayStrip({ s }: { s: Json }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const prof = VS(s.validation_profile_g_kwh);
  const f = storageFacts(s);
  const stored = new Set(storedHours(f.charge, f.discharge));
  const ch = new Set(f.charge), dis = new Set(f.discharge);
  const cw = (w - LX - 8) / 24;
  const H = 104;
  return (
    <div ref={ref} style={{ height: H }} data-testid="storage-strip">
      {w > 0 && (
        <svg width={w} height={H} role="img" aria-label={`Utah carbon by hour, validation year, with the fixed schedule: charge ${hourSpans(f.charge).join(', ')}, discharge ${hourSpans(f.discharge).join(', ')}`}>
          <text x={LX - 8} y={30} textAnchor="end" fontSize={12} fontWeight={500} fill={C.ink}>Carbon</text>
          <text x={LX - 8} y={44} textAnchor="end" fontSize={11} fill={C.ink3}>g/kWh</text>
          <text x={LX - 8} y={68} textAnchor="end" fontSize={11} fill={C.ink3}>battery</text>
          <text x={LX - 8} y={88} textAnchor="end" fontSize={11} fill={C.ink3}>rush</text>
          {prof.map((v, h) => {
            const x = LX + h * cw, fill = ci2c(v);
            return (
              <g key={h}>
                <rect x={x + 1} y={18} width={cw - 2} height={32} rx={4} fill={fill}><title>{`${fmtHour(h)}: ${Math.round(v)} g/kWh (modeled, EIA estimate, validation-year mean)`}</title></rect>
                {h % 3 === 0 && <text x={x + cw / 2} y={38} textAnchor="middle" fontSize={11} fontWeight={500} fill={onFill(fill)}>{Math.round(v)}</text>}
                {h % 3 === 0 && <text x={x + cw / 2} y={12} textAnchor="middle" fontSize={11} fill={C.ink3}>{fmtHour(h)}</text>}
                {ch.has(h) && <rect x={x + 1.5} y={58} width={cw - 3} height={14} rx={3} fill="#fff" stroke={C.ink} strokeWidth={1.5}><title>{`${fmtHour(h)}: charge (fixed schedule)`}</title></rect>}
                {dis.has(h) && <rect x={x + 1} y={58} width={cw - 2} height={14} rx={3} fill={C.ink}><title>{`${fmtHour(h)}: discharge into the cluster (fixed schedule)`}</title></rect>}
                {stored.has(h) && <rect x={x + 1.5} y={58} width={cw - 3} height={14} rx={3} fill="none" stroke={C.stored} strokeWidth={1.5} strokeDasharray="3 2"><title>{`${fmtHour(h)}: energy held in the battery`}</title></rect>}
                {f.rushByHour[h] > 0 && <rect x={x + 1} y={80} width={cw - 2} height={12} rx={3} fill={C.rushFill} stroke={C.rush} strokeWidth={1}><title>{`${fmtHour(h)}: ${f.rushByHour[h]} of the ${f.rushN} rush hours`}</title></rect>}
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}

/** The cluster's grid import by hour, before and after the fixed schedule (headline size). */
export function ImportChart({ s }: { s: Json }) {
  const f = storageFacts(s);
  const imp = s.cases.U.import_at_headline.A;
  const option = useMemo(() => {
    const hrs = Array.from({ length: 24 }, (_, h) => fmtHour(h));
    return {
      grid: { left: 40, right: 112, top: 12, bottom: 24 },
      xAxis: { type: 'category', data: hrs, boundaryGap: false, axisLabel: { interval: 5 } },
      yAxis: { type: 'value', min: 0, max: 2, axisLabel: { formatter: (v: number) => `${v}` }, name: 'MW', nameGap: 8, nameTextStyle: { align: 'right' } },
      tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${fmt(v, 2)} MW` },
      series: [
        { name: 'without storage', type: 'line', data: VS(imp.before_by_hour_mw), lineStyle: { color: C.ink3, width: 1.5, type: [5, 3] }, symbol: 'none',
          endLabel: { show: true, formatter: 'without', color: C.ink3, fontSize: 11, fontFamily: 'Funnel Sans' } },
        { name: `with ${fmt(f.E)} MWh`, type: 'line', data: VS(imp.after_by_hour_mw), lineStyle: { color: C.ink, width: 2 }, symbol: 'none',
          endLabel: { show: true, formatter: `with ${fmt(f.E)} MWh`, color: C.ink, fontSize: 11, fontFamily: 'Funnel Sans' },
          markLine: { symbol: 'none', silent: true, lineStyle: { color: C.ink3, type: [2, 3], width: 1 }, label: { formatter: 'site connection', color: C.ink3, fontSize: 11, position: 'insideEndTop' }, data: [{ yAxis: f.conn }] } },
      ],
    };
  }, [s]); // eslint-disable-line react-hooks/exhaustive-deps
  return <EChart option={option} className="h-full" testId="storage-import" label={`Utah cluster grid import by hour, typical validation day, without and with a ${fmt(f.E)} MWh battery on the fixed schedule`} />;
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
              <td title={pname(p)}>{pname(p)}</td>
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
