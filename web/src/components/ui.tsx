import type { ReactNode } from 'react';
import type { Env, Evidence } from '../lib/data';

/* One authored icon set: 16 px grid, 1.5 px stroke, round caps. */
const P: Record<string, ReactNode> = {
  sun: (<><circle cx="8" cy="8" r="2.75" /><path d="M8 1.75v1.5M8 12.75v1.5M1.75 8h1.5M12.75 8h1.5M3.6 3.6l1.05 1.05M11.35 11.35l1.05 1.05M3.6 12.4l1.05-1.05M11.35 4.65l1.05-1.05" /></>),
  rush: (<><path d="M1.75 12.25 5.25 8l2.75 2.25 5.5-6" /><path d="M10.25 4.25h3.25V7.5" /></>),
  route: (<><path d="M2.75 13.25c0-4.75 2.75-5.75 5.75-5.75h4.75" /><path d="M10.5 4.75 13.25 7.5 10.5 10.25" /></>),
  drop: <path d="M8 2s-4.25 4.75-4.25 7.5a4.25 4.25 0 0 0 8.5 0C12.25 6.75 8 2 8 2Z" />,
  bolt: <path d="M8.75 1.75 3.75 9h4l-.75 5.25L12.25 7h-4l.5-5.25Z" />,
  moon: <path d="M12.75 10.25A5.25 5.25 0 1 1 5.75 3.25a4.25 4.25 0 0 0 7 7Z" />,
  plus: <path d="M8 3.5v9M3.5 8h9" />,
  minus: <path d="M3.5 8h9" />,
  reset: (<><path d="M2.75 8a5.25 5.25 0 1 0 1.6-3.8" /><path d="M2.5 2.25v2.5H5" /></>),
  play: <path d="M5 3.25v9.5L12.5 8 5 3.25Z" />,
  pause: <path d="M5.25 3.5v9M10.75 3.5v9" />,
  doc: (<><path d="M4 1.75h5.25l2.75 2.75v9.75H4z" /><path d="M9 1.75V4.75h3M6 8h4M6 10.5h4" /></>),
  close: <path d="M4 4l8 8M12 4l-8 8" />,
  arrowDown: <path d="M8 3v10M4.25 9.25 8 13l3.75-3.75" />,
};
export function Icon({ name, size = 16, className, strokeWidth = 1.5 }: { name: keyof typeof P | string; size?: number; className?: string; strokeWidth?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      {P[name]}
    </svg>
  );
}

const EV_TEXT: Record<Evidence, string> = {
  observed: 'observed', measured: 'measured', forecast: 'forecast', modeled: 'modeled', assumed: 'assumed', simulated: 'simulated',
};
/** Evidence chip: the label is spelled out and carried by a shape, never by colour alone. */
export function Ev({ e, children, title }: { e: Evidence; children?: ReactNode; title?: string }) {
  return (
    <span className="ev" data-ev={e} title={title ?? `Evidence: ${e}`}>
      {children ?? EV_TEXT[e]}
    </span>
  );
}

/** A number with its unit in smaller muted type. A null value shows its reason, never zero. */
export function Num({ v, unit, d = 0, className, fmt }: { v: number | null | undefined; unit?: string; d?: number; className?: string; fmt?: (v: number) => string }) {
  if (v == null || !Number.isFinite(v)) return <span className={className} title="not available">–</span>;
  const s = fmt ? fmt(v) : new Intl.NumberFormat('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }).format(v).replace('-', '−');
  return (
    <span className={`num ${className ?? ''}`}>
      {s}
      {unit && <span className="unit">{unit}</span>}
    </span>
  );
}

export function Unavailable({ env }: { env: Env<unknown> }) {
  return <span className="t-12 ink-3">{env.reason ?? 'not available'}</span>;
}

export function Skel({ w = '100%', h = 12, r = 8, className }: { w?: number | string; h?: number | string; r?: number; className?: string }) {
  return <span className={`skel block ${className ?? ''}`} style={{ width: w, height: h, borderRadius: r }} aria-hidden="true" />;
}

export const SEALED = 'Validation year (Nov 2024 – Oct 2025) · test year sealed';
