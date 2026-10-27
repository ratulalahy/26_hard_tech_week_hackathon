// Small custom SVG marks: 24-hour carbon strips, the placement-vs-timing interval chart, the policy table.
import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { C, ci2c } from '../lib/color';
import { POLICY, POLICY_ORDER, contrast, type Json } from '../lib/data';
import { fmt, fmtHour, pct, signed } from '../lib/format';

export function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number, number] {
  const ref = useRef<T>(null);
  const [s, setS] = useState({ w: 0, h: 0 });
  useLayoutEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setS({ w: Math.round(e.contentRect.width), h: Math.round(e.contentRect.height) }));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, s.w, s.h];
}

/** One 24-hour carbon strip. Cells carry their value in a tooltip; colour is never the only cue. */
export function Strip({ curve, h = 14, hour, job, label, gap = 1.5 }: { curve: (number | null)[]; h?: number; hour?: number; job?: { s: number; H: number } | null; label: string; gap?: number }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const cw = w / 24;
  return (
    <div ref={ref} style={{ height: h + (job ? 4 : 0), minWidth: 0, overflow: 'hidden' }} role="img" aria-label={label}>
      {w > 0 && (
        <svg width={w} height={h + (job ? 4 : 0)} style={{ display: 'block' }}>
          {curve.map((v, i) => (
            <rect key={i} x={i * cw + gap / 2} y={0} width={Math.max(0, cw - gap)} height={h} rx={i === 0 || i === 23 ? 3 : 1.5} fill={v == null ? '#fff' : ci2c(v)} stroke={v == null ? C.hair : 'none'}>
              <title>{`${fmtHour(i)}: ${v == null ? 'no value' : Math.round(v) + ' g/kWh'}`}</title>
            </rect>
          ))}
          {job && Array.from({ length: job.H }, (_, k) => (job.s + k) % 24).map((i) => <rect key={'j' + i} x={i * cw + gap / 2} y={h + 1} width={Math.max(0, cw - gap)} height={3} rx={1} fill={C.route} />)}
          {hour != null && <rect x={hour * cw + gap / 2 - 1} y={-0.5} width={cw - gap + 2} height={h + 1} rx={2} fill="none" stroke={C.ink} strokeWidth={1.5} />}
        </svg>
      )}
    </div>
  );
}

const SHORT: Record<string, string> = { G: 'G greedy', S: 'S static', K: 'K persistence', W: 'W weekly', L: 'L learned', H: 'H hindsight', W_time: 'W wait only', L_time: 'L wait only' };
/** The registered result on one axis: each policy's saving vs U with its 95% interval (b = 4). */
export function IntervalChart({ m, rows, height }: { m: Json; rows: string[]; height?: number }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const lx = 120, rx = 48, rh = 18, top = 4;
  const H = height ?? top + rows.length * rh + 24;
  const max = 0.3;
  const X = (v: number) => lx + (Math.max(0, Math.min(max, v)) / max) * (w - lx - rx);
  return (
    <div ref={ref} role="img" aria-label="Saving in attributed CO2 versus running local, with 95% intervals, by policy">
      {w > 0 && (
        <svg width={w} height={H} style={{ display: 'block' }}>
          {[0, 0.1, 0.2, 0.3].map((g) => (
            <g key={g}>
              <line x1={X(g)} x2={X(g)} y1={top} y2={top + rows.length * rh} stroke={g === 0 ? 'rgba(110,62,30,.3)' : C.hair2} />
              <text x={X(g)} y={top + rows.length * rh + 14} textAnchor="middle" fontSize={11} fill={C.ink3}>{g * 100}%</text>
            </g>
          ))}
          {rows.map((p, i) => {
            const c = contrast(m, p);
            const y = top + i * rh + rh / 2;
            const diag = p === 'H';
            if (!c || c.saving.value == null) return <text key={p} x={0} y={y + 4} fontSize={12} fill={C.ink3}>{POLICY[p]?.name ?? p}: {c?.saving.reason ?? 'not run'}</text>;
            const [lo, hi] = c.saving_ci95.value as [number, number];
            const place = !p.includes('time') && p !== 'G';
            return (
              <g key={p} opacity={diag ? 0.6 : 1}>
                <text x={0} y={y + 4} fontSize={12} fill={C.ink} fontWeight={place ? 600 : 400}>{SHORT[p] ?? p}</text>
                <line x1={X(lo)} x2={X(hi)} y1={y} y2={y} stroke={C.ink} strokeWidth={2} strokeLinecap="round" opacity={0.45} />
                <circle cx={X(c.saving.value)} cy={y} r={4} fill={place ? C.ink : '#fff'} stroke={C.ink} strokeWidth={1.5} />
                <text x={w} y={y + 4} textAnchor="end" fontSize={12} fill={C.ink} fontWeight={500}>{pct(c.saving.value)}%</text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}

const t1 = (kg: number) => fmt(kg / 1000, 1);
/** The policy table: feasibility and signed CO₂ (U − P, so positive = the policy emits less), b = 4 intervals. */
export function PolicyTable({ m, compact = false, testId }: { m: Json; compact?: boolean; testId?: string }) {
  const rows = compact ? ['U', 'G', 'S', 'K', 'W', 'L', 'W_time', 'L_time'] : POLICY_ORDER;
  return (
    <table className="tbl" data-testid={testId}>
      <thead>
        <tr>
          <th>Policy</th>
          <th>Feasible</th>
          {!compact && <th>Late jobs</th>}
          <th>CO₂ <span className="fw-400">t</span></th>
          <th>U − policy <span className="fw-400">t, 95%</span></th>
          {!compact && <th>Saving <span className="fw-400">95%</span></th>}
          {!compact && <th>Moved jobs</th>}
          {!compact && <th>Wait p95</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((p) => {
          const r = m.policies[p];
          if (!r) return null;
          const mt = r.metrics;
          const c = p === 'U' ? null : contrast(m, p);
          const ci = c?.diff_kg_ci95.value as [number, number] | undefined;
          const sv = c?.saving_ci95.value as [number, number] | undefined;
          const contender = ['S', 'K', 'W', 'L'].includes(p);
          return (
            <tr key={p} className={contender ? 'em' : p === 'H' ? 'diag' : ''}>
              <td title={POLICY[p]?.role}>{POLICY[p]?.name ?? p}{p === 'H' ? <span className="ink-3 fw-400"> diagnostic</span> : null}</td>
              <td>{r.feasible ? 'yes' : 'no'}</td>
              {!compact && <td>{fmt(mt.late_jobs.value)}</td>}
              <td>{t1(mt.co2_kg.value)}</td>
              <td>{c && c.diff_kg.value != null ? <>{signed(c.diff_kg.value / 1000, 1)} <span className="ink-3 fw-400">[{signed(ci![0] / 1000, 1)}, {signed(ci![1] / 1000, 1)}]</span></> : <span className="ink-3 fw-400">reference</span>}</td>
              {!compact && <td>{c && c.saving.value != null ? <>{pct(c.saving.value, 2)}% <span className="ink-3 fw-400">[{pct(sv![0], 2)}, {pct(sv![1], 2)}]</span></> : '–'}</td>}
              {!compact && <td>{pct(mt.moved_share_jobs.value, 1)}%</td>}
              {!compact && <td>{fmt(mt.wait_p95_s.value / 60, 0)} min</td>}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function Panel({ children, className, style, over }: { children: ReactNode; className?: string; style?: React.CSSProperties; over?: boolean }) {
  return <section className={`panel ${over ? 'over-map' : ''} ${className ?? ''}`} style={style}>{children}</section>;
}
