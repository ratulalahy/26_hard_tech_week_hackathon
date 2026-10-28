// The Monitor page (T21): an operator console replaying policy S over the sealed test year's replay week,
// from the committed outputs only (results/test/job-replay.json, metrics.json, forecast-replay.json and the
// manifest's frozen ranking and assumptions). The playhead walks the week's 168 hours; the site lanes, the
// Utah CO₂ rate and the decision feed all follow it. Every feed line is a template filled from those files'
// fields (lib/monitor.ts); comparisons of outcomes are labelled retrospective, scored on realized truth.
import { useEffect, useMemo, useRef, useState, type PointerEvent as RPointerEvent } from 'react';
import { useWidth } from '../components/charts';
import { Ev, EvCI, Icon, Skel } from '../components/ui';
import { C, ci2c, setMid } from '../lib/color';
import { get } from '../lib/data';
import { fmt, fmtDate, pct } from '../lib/format';
import { MISSING, buildMonitor, hourLabel, loadMonitorFiles, siteName, stampLabel, type FeedEntry, type MonitorModel, type SiteSeries } from '../lib/monitor';

export const MONITOR_LABEL = 'simulated replay · test year (sealed, opened once)';
const SPEEDS = [2, 6, 24] as const; // replay hours per second

export function Monitor() {
  const [s, setS] = useState<{ m: MonitorModel | null; err: string | null; absent: boolean }>({ m: null, err: null, absent: false });
  useEffect(() => {
    let live = true;
    get('index.json').catch(() => ({})).then((idx) => {
      if (!idx?.test?.available) { if (live) setS({ m: null, err: null, absent: true }); return; }
      return Promise.all([loadMonitorFiles(), get('grid-profile.json', 'test').catch(() => null)]).then(([f, g]) => {
        setMid(g?.reference?.us_avg_ci?.value); // the carbon scale's midpoint, as on every other page
        if (live) setS({ m: buildMonitor(f), err: null, absent: false });
      });
    }).catch((e) => live && setS({ m: null, err: String(e), absent: false }));
    return () => { live = false; };
  }, []);
  return (
    <section aria-label="Monitor" data-testid="monitor" tabIndex={0} className="page-scroll">
      {s.err ? <div className="panel t-13" role="alert"><b className="fw-600">The test-year replay did not load.</b> <span className="ink-2">{s.err}. The Monitor reads data/results/test/ (job-replay, metrics, forecast-replay, manifest); run <code>make web</code> after the test run.</span></div>
        : s.absent ? <div className="panel t-13" data-testid="monitor-absent"><b className="fw-600">No sealed test-year run in this build.</b> <span className="ink-2">The Monitor replays only results/test/, which exists after the one opening of the test year. Nothing is shown in its place.</span></div>
          : !s.m ? <MonitorSkeleton /> : <MonitorBody m={s.m} />}
    </section>
  );
}

function MonitorSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading the replay" className="flex flex-col gap-4">
      <Skel w="60%" h={24} /><Skel w="80%" h={14} /><Skel h={56} r={16} />
      <div className="monitor-grid"><Skel h={520} r={16} /><Skel h={520} r={16} /></div>
    </div>
  );
}

function MonitorBody({ m }: { m: MonitorModel }) {
  const N = m.hours.length;
  const firstPlaced = m.feed.find((e) => e.kind === 'placed')?.h ?? 0;
  const [t, setT] = useState(firstPlaced);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(6);
  const [hover, setHover] = useState<number | null>(null);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setT((x) => { if (x >= N - 1) { setPlaying(false); return x; } return x + 1; }), 1000 / speed);
    return () => clearInterval(id);
  }, [playing, speed, N]);
  const toggle = () => { if (!playing && t >= N - 1) setT(0); setPlaying((p) => !p); };
  const hours = useMemo(() => [...new Set(m.feed.map((e) => e.h))].sort((a, b) => a - b), [m]);
  const next = hours.find((h) => h > t), prev = [...hours].reverse().find((h) => h < t);
  const at = hover ?? t;

  const moved = m.arcs.filter((a) => a.jobs > 0);
  const movedJobs = moved.reduce((s, a) => s + a.jobs, 0), movedGpuH = moved.reduce((s, a) => s + a.gpuH, 0);
  const top = moved.sort((a, b) => b.jobs - a.jobs)[0];
  const range = `${fmtDate(m.start, { month: 'short', day: 'numeric' })}–${fmtDate(new Date(Date.parse(m.end) - 1).toISOString(), { month: 'short', day: 'numeric', year: 'numeric' })}`;
  const title = top
    ? `In the replay week, S sent ${fmt(movedJobs)} of ${m.week.nJobs == null ? 'the week\'s' : fmt(m.week.nJobs)} arriving jobs to ${siteName(top.to)} (${top.to}), the top of its frozen ranking`
    : `In the replay week, S kept every arriving job in Utah`;
  return (
    <div className="flex flex-col gap-4" data-testid="monitor-body">
      <div className="monitor-head">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2"><span className="chip-neutral" data-testid="monitor-label">{MONITOR_LABEL}</span><Ev e="simulated">jobs and placements</Ev><EvCI extra="carbon" /></div>
        <h1 className="t-20" style={{ margin: 0, maxWidth: '72ch' }} data-testid="monitor-title">{title}</h1>
        <p className="t-13 ink-2" style={{ margin: 0, maxWidth: '96ch' }}>
          The router, policy S, replayed hour by hour over {range} (America/Denver), run {m.runId}. S takes the first feasible site in a ranking frozen from the training years’ mean consumed carbon ({m.rankingText}; {m.rankingWindow ? `${fmtDate(m.rankingWindow[0], { month: 'short', year: 'numeric', timeZone: 'UTC' })} to ${fmtDate(m.rankingWindow[1], { month: 'short', year: 'numeric', timeZone: 'UTC' })}` : 'training years'}); it reads no grid data while it runs. Load is the hour’s mean busy GPUs, warm-up jobs included.
        </p>
      </header>
        <Week m={m} movedJobs={movedJobs} movedGpuH={movedGpuH} />
      </div>

      <Transport t={t} setT={(x) => { setT(x); }} N={N} playing={playing} toggle={toggle} speed={speed} setSpeed={setSpeed} label={stampLabel(m.hours[t])}
        prev={prev} next={next} />

      <div className="monitor-grid">
        <div className="flex flex-col gap-4" style={{ minWidth: 0 }}>
          <div className="panel" data-testid="monitor-sites">
            <div className="flex items-baseline justify-between gap-2 flex-wrap" style={{ marginBottom: 8 }}>
              <h2 className="t-15" style={{ margin: 0 }}>GPU load by site</h2>
              <span className="t-11 ink-3">each lane scaled to its site’s GPU slots · hover to read, click to move the playhead</span>
            </div>
            <DayAxis hours={m.hours} />
            {m.sites.map((s) => <Lane key={s.site} s={s} m={m} t={t} at={at} setHover={setHover} setT={setT} />)}
            <CiStrip m={m} t={t} at={at} setHover={setHover} setT={setT} />
          </div>
          <RatePanel m={m} t={t} at={at} setHover={setHover} setT={setT} />
        </div>
        <div className="flex flex-col gap-4" style={{ minWidth: 0 }}>
          <Feed m={m} t={t} />
          <Traced m={m} />
        </div>
      </div>
    </div>
  );
}

function Transport({ t, setT, N, playing, toggle, speed, setSpeed, label, prev, next }: {
  t: number; setT: (x: number) => void; N: number; playing: boolean; toggle: () => void; speed: number; setSpeed: (s: (typeof SPEEDS)[number]) => void; label: string; prev?: number; next?: number;
}) {
  return (
    <div className="panel monitor-transport" role="group" aria-label="Replay controls" data-testid="monitor-transport">
      <button className="btn" onClick={toggle} aria-label={playing ? 'Pause replay' : 'Play replay'} data-testid="monitor-play" style={{ minWidth: 88 }}>
        <Icon name={playing ? 'pause' : 'play'} />{playing ? 'Pause' : 'Play'}
      </button>
      <div className="flex gap-1">
        <button className="iconbtn" onClick={() => prev != null && setT(prev)} disabled={prev == null} aria-label="Previous feed entry" title="Previous feed entry"><span aria-hidden="true" className="t-13 fw-600">‹</span></button>
        <button className="iconbtn" onClick={() => next != null && setT(next)} disabled={next == null} aria-label="Next feed entry" title="Next feed entry"><span aria-hidden="true" className="t-13 fw-600">›</span></button>
      </div>
      <div className="seg" role="radiogroup" aria-label="Replay speed">
        {SPEEDS.map((s) => <button key={s} role="radio" aria-checked={speed === s} onClick={() => setSpeed(s)}>{s} h/s</button>)}
      </div>
      <label className="monitor-scrub">
        <span className="sr-only">Replay hour</span>
        <input type="range" min={0} max={N - 1} step={1} value={t} onChange={(e) => setT(Number(e.target.value))} aria-valuetext={`${label}, hour ${t + 1} of ${N}`} data-testid="monitor-scrub" />
      </label>
      <div className="t-13 fw-600 num whitespace-nowrap" aria-live="off" data-testid="monitor-clock">{label}<span className="t-11 ink-3 fw-400" style={{ marginLeft: 6 }}>hour {t + 1} of {N}</span></div>
    </div>
  );
}

// ── shared x geometry for the lanes, the carbon strip and the rate chart ──
// wide: the site label sits left of its lane (148 px); narrow (phone): above it, and the lane takes the width
const NARROW = 560;
const labelW = (w: number, axis = 0) => (w < NARROW ? axis : 148);
const useX = (w: number, n: number, lw = labelW(w)) => (i: number) => lw + (i / n) * Math.max(0, w - lw);
function useScrub(w: number, n: number, setHover: (h: number | null) => void, setT: (h: number) => void, LABEL_W = labelW(w)) {
  const down = useRef(false);
  const hourAt = (e: RPointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const f = (e.clientX - r.left - LABEL_W) / Math.max(1, w - LABEL_W);
    return f < 0 || f > 1 ? null : Math.min(n - 1, Math.max(0, Math.floor(f * n)));
  };
  return {
    onPointerMove: (e: RPointerEvent<SVGSVGElement>) => { const h = hourAt(e); setHover(h); if (down.current && h != null) setT(h); },
    onPointerLeave: () => { setHover(null); down.current = false; },
    onPointerDown: (e: RPointerEvent<SVGSVGElement>) => { const h = hourAt(e); if (h != null) { down.current = true; setT(h); } },
    onPointerUp: () => { down.current = false; },
  };
}

function DayAxis({ hours }: { hours: string[] }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const X = useX(w, hours.length);
  const narrow = w < NARROW;
  const ticks = hours.map((h, i) => [h, i] as const).filter(([h]) => Number(new Intl.DateTimeFormat('en-US', { timeZone: 'America/Denver', hour: 'numeric', hourCycle: 'h23' }).format(new Date(h))) === 0);
  return (
    <div ref={ref} style={{ height: 16 }} aria-hidden="true">
      {w > 0 && <svg width={w} height={16} style={{ display: 'block' }}>
        {ticks.map(([h, i]) => <g key={i}><line x1={X(i)} x2={X(i)} y1={3} y2={15} stroke={C.hair} /><text x={X(i) + 3} y={11} fontSize={11} fill={C.ink3}>{`${fmtDate(h, { weekday: 'short' })} ${fmtDate(h, { day: 'numeric' })}`}</text></g>)}
        {!narrow && <text x={0} y={11} fontSize={11} fill={C.ink3}>MT, midnight ticks</text>}
      </svg>}
    </div>
  );
}

function Playhead({ x, h, hoverX }: { x: number; h: number; hoverX: number | null }) {
  return (<>
    {hoverX != null && <line x1={hoverX} x2={hoverX} y1={0} y2={h} stroke={C.ink3} strokeWidth={1} strokeDasharray="2 2" />}
    <line x1={x} x2={x} y1={0} y2={h} stroke={C.ink} strokeWidth={1.5} />
  </>);
}

function Lane({ s, m, t, at, setHover, setT }: { s: SiteSeries; m: MonitorModel; t: number; at: number; setHover: (h: number | null) => void; setT: (h: number) => void }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const LABEL_W = labelW(w), narrow = w < NARROW;
  const n = m.hours.length, H = 44, X = useX(w, n), cw = Math.max(0, w - LABEL_W) / n;
  const Y = (v: number) => H - 2 - (Math.min(v, s.slots) / Math.max(1, s.slots)) * (H - 6);
  const home = s.site === 'PACE';
  const area = s.s.map((v, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)},${Y(v).toFixed(1)} L${(X(i) + cw).toFixed(1)},${Y(v).toFixed(1)}`).join(' ');
  const fillPath = `${area} L${X(n).toFixed(1)},${H - 2} L${X(0).toFixed(1)},${H - 2} Z`;
  const uLine = s.u.map((v, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)},${Y(v).toFixed(1)} L${(X(i) + cw).toFixed(1)},${Y(v).toFixed(1)}`).join(' ');
  const showU = home && s.u.some((v, i) => Math.abs(v - s.s[i]) >= 0.5);
  const sc = useScrub(w, n, setHover, setT);
  const now = s.s[at];
  const arc = m.arcs.find((a) => a.to === s.site);
  const jobsLine = home
    ? (m.week.nJobs != null ? `${fmt(m.week.nJobs - m.arcs.reduce((x, a) => x + a.jobs, 0))} of the week’s arrivals stayed` : '')
    : arc ? `${fmt(arc.jobs)} job${arc.jobs === 1 ? '' : 's'} moved here this week${arc.jobs ? ` · ${fmt(arc.gpuH)} GPU-h` : ''}` : '';
  const label = `${siteName(s.site)} (${s.site}): ${fmt(Math.round(now))} of ${fmt(s.slots)} GPUs busy at ${hourLabel(m.hours[at])}`;
  const laneLabel = (
    <div className="monitor-lane-label">
      <div className="t-12 fw-600">{siteName(s.site)} <span className="ink-3 fw-500">{s.site}</span></div>
      <div className="t-12 num"><b className="fw-600">{fmt(Math.round(now))}</b><span className="ink-3"> / {fmt(s.slots)} GPUs</span></div>
    </div>
  );
  return (
    <div className="monitor-lane" data-testid={`lane-${s.site}`}>
      <div ref={ref} style={{ height: narrow ? 'auto' : H, position: 'relative' }} className={narrow ? 'monitor-narrow' : undefined}>
        {narrow ? laneLabel : null}
        {w > 0 && (
          <svg width={w} height={H} style={{ display: 'block', touchAction: 'none' }} role="img" aria-label={label} {...sc}>
            <rect x={X(0)} y={Y(s.slots)} width={Math.max(0, w - LABEL_W)} height={H - 2 - Y(s.slots)} fill={C.sky0} />
            <line x1={X(0)} x2={X(n)} y1={Y(s.slots)} y2={Y(s.slots)} stroke={C.hair} />
            <path d={fillPath} fill={home ? C.rushFill : C.routeSoft} />
            <path d={area} fill="none" stroke={home ? C.ink2 : C.route} strokeWidth={1.5} />
            {showU && <path d={uLine} fill="none" stroke={C.ink} strokeWidth={1.25} strokeDasharray="3 2" />}
            <line x1={X(0)} x2={X(n)} y1={H - 2} y2={H - 2} stroke="rgba(110,62,30,.3)" />
            <Playhead x={X(t) + cw / 2} h={H} hoverX={at !== t ? X(at) + cw / 2 : null} />
          </svg>
        )}
        {narrow ? null : laneLabel}
      </div>
      {jobsLine ? <div className="t-11 ink-3" style={{ marginLeft: LABEL_W, marginTop: 1 }}>{jobsLine}{home && showU ? ' · dashed: U, stay in Utah (retrospective)' : ''}</div> : null}
    </div>
  );
}

function CiStrip({ m, t, at, setHover, setT }: { m: MonitorModel; t: number; at: number; setHover: (h: number | null) => void; setT: (h: number) => void }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const LABEL_W = labelW(w), narrow = w < NARROW;
  const n = m.hours.length, H = 12, X = useX(w, n), cw = Math.max(0, w - LABEL_W) / n;
  const sc = useScrub(w, n, setHover, setT);
  const v = m.ciPace[at];
  const ciLabel = <div className="monitor-lane-label" style={{ top: 0 }}><div className="t-11 ink-2" style={{ lineHeight: '16px' }}>Utah carbon <b className="fw-600 num">{v == null ? '–' : fmt(v)}</b><span className="ink-3"> g/kWh</span></div></div>;
  return (
    <div style={{ marginTop: 10 }} data-testid="monitor-ci">
      <div ref={ref} style={{ height: narrow ? 'auto' : H + 4, position: 'relative' }} className={narrow ? 'monitor-narrow' : undefined}>
        {narrow ? ciLabel : null}
        {w > 0 && <svg width={w} height={H + 4} style={{ display: 'block', touchAction: 'none' }} role="img" aria-label={`Utah's grid carbon, realized: ${v == null ? 'no value' : fmt(v) + ' g/kWh'} at ${hourLabel(m.hours[at])}`} {...sc}>
          {m.ciPace.map((c, i) => <rect key={i} x={X(i)} y={2} width={Math.max(0.5, cw - 0.4)} height={H} fill={c == null ? '#fff' : ci2c(c)} />)}
          <rect x={X(t) - 0.5} y={1} width={cw + 1} height={H + 2} fill="none" stroke={C.ink} strokeWidth={1.5} />
        </svg>}
        {narrow ? null : ciLabel}
      </div>
      <div className="t-11 ink-3" style={{ marginLeft: LABEL_W, marginTop: 2 }}>PACE, realized hourly (EIA estimate). S does not read it; the replay files carry this series for PACE only.</div>
    </div>
  );
}

function RatePanel({ m, t, at, setHover, setT }: { m: MonitorModel; t: number; at: number; setHover: (h: number | null) => void; setT: (h: number) => void }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const LABEL_W = labelW(w, 44), narrow = w < NARROW;
  const n = m.hours.length, H = 150, padT = 8, padB = 18, X = useX(w, n, LABEL_W), cw = Math.max(0, w - LABEL_W) / n;
  const vals = [...m.rateS, ...m.rateU].filter((v): v is number => v != null);
  const step = 500, max = Math.max(step, Math.ceil((Math.max(...vals, 0) * 1.05) / step) * step);
  const Y = (v: number) => padT + (1 - v / max) * (H - padT - padB);
  const line = (a: (number | null)[]) => a.map((v, i) => (v == null ? '' : `${i && a[i - 1] != null ? 'L' : 'M'}${(X(i) + cw / 2).toFixed(1)},${Y(v).toFixed(1)}`)).join(' ');
  const sc = useScrub(w, n, setHover, setT, LABEL_W);
  const s = m.rateS[at], u = m.rateU[at];
  const totS = m.rateS.reduce<number>((a, v) => a + (v ?? 0), 0), totU = m.rateU.reduce<number>((a, v) => a + (v ?? 0), 0);
  const readout = (
    <div className="monitor-lane-label" style={{ top: 4, width: 100 }}>
      <div className="t-12 num"><span className="ink-3">S </span><b className="fw-600">{s == null ? '–' : fmt(s)}</b></div>
      <div className="t-12 num"><span className="ink-3">U </span>{u == null ? '–' : fmt(u)}</div>
      <div className="t-11 ink-3">kg/h, {hourLabel(m.hours[at])}</div>
    </div>
  );
  const grid = Array.from({ length: Math.floor(max / step) + 1 }, (_, i) => i * step).filter((_, i, arr) => arr.length <= 5 || i % 2 === 0);
  return (
    <div className="panel" data-testid="monitor-rate">
      <div className="flex items-baseline justify-between gap-2 flex-wrap">
        <h2 className="t-15" style={{ margin: 0 }}>Utah site’s CO₂ rate</h2>
        <span className="chip-neutral" data-testid="monitor-retro">retrospective, scored on realized truth</span>
      </div>
      <p className="t-12 ink-2" style={{ margin: '4px 0 8px' }}>
        kg CO₂ per hour = busy GPUs × {fmt(m.kwPerGpu, 1)} kW × PUE {fmt(m.pue, 1)} × Utah’s realized carbon. The moved work’s emissions at {m.arcs.filter((a) => a.jobs > 0).map((a) => a.to).join(', ') || 'the destinations'} are not in this line: the files carry no hourly carbon there. <Ev e="simulated">load</Ev> <Ev e="assumed">kW, PUE</Ev> <EvCI />
      </p>
      <div className="flex flex-wrap gap-4 t-12" style={{ marginBottom: 4 }} aria-hidden="true">
        <span className="flex items-center gap-2"><svg width="18" height="8"><line x1="0" x2="18" y1="4" y2="4" stroke={C.route} strokeWidth="2" /></svg>S, the replay</span>
        <span className="flex items-center gap-2"><svg width="18" height="8"><line x1="0" x2="18" y1="4" y2="4" stroke={C.ink} strokeWidth="1.5" strokeDasharray="3 2" /></svg>U, stay in Utah</span>
      </div>
      <div ref={ref} style={{ height: narrow ? 'auto' : H, position: 'relative' }} className={narrow ? 'monitor-narrow' : undefined}>
        {narrow ? readout : null}
        {w > 0 && (
          <svg width={w} height={H} style={{ display: 'block', touchAction: 'none' }} role="img" aria-label={`Utah site CO2 rate at ${hourLabel(m.hours[at])}: S ${s == null ? 'no value' : fmt(s) + ' kg per hour'}, U ${u == null ? 'no value' : fmt(u) + ' kg per hour'}`} {...sc}>
            {grid.map((g) => <g key={g}><line x1={X(0)} x2={X(n)} y1={Y(g)} y2={Y(g)} stroke={g === 0 ? 'rgba(110,62,30,.3)' : C.hair2} /><text x={X(0) - 6} y={Y(g) + 4} fontSize={11} fill={C.ink3} textAnchor="end">{fmt(g)}</text></g>)}
            <text x={X(0) - 6} y={H - 2} fontSize={11} fill={C.ink3} textAnchor="end">kg/h</text>
            <path d={line(m.rateU)} fill="none" stroke={C.ink} strokeWidth={1.5} strokeDasharray="3 2" />
            <path d={line(m.rateS)} fill="none" stroke={C.route} strokeWidth={2} />
            <Playhead x={X(t) + cw / 2} h={H - padB} hoverX={at !== t ? X(at) + cw / 2 : null} />
            {s != null && <circle cx={X(at) + cw / 2} cy={Y(s)} r={4} fill={C.route} stroke="#fff" strokeWidth={2} />}
          </svg>
        )}
        {narrow ? null : readout}
      </div>
      <div className="t-12 ink-2" style={{ marginTop: 4 }} data-testid="monitor-rate-total">Over the week at the Utah site: S {fmt(totS / 1000, 1)} t, U {fmt(totU / 1000, 1)} t (retrospective, scored on realized truth; Utah site only).</div>
    </div>
  );
}

function Feed({ m, t }: { m: MonitorModel; t: number }) {
  const shown = m.feed.filter((e) => e.h <= t).reverse();
  return (
    <div className="panel flex flex-col" style={{ minHeight: 0 }}>
      <div className="flex items-baseline justify-between gap-2 flex-wrap" style={{ marginBottom: 8 }}>
        <h2 className="t-15" style={{ margin: 0 }}>Decision feed</h2>
        <span className="t-11 ink-3">{fmt(shown.length)} of {fmt(m.feed.length)} entries · newest first</span>
      </div>
      <div className="monitor-feed" tabIndex={0} role="region" aria-label="Decision feed entries">
        <ol data-testid="monitor-feed" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
          {shown.map((e, i) => <FeedItem key={`${e.h}-${e.site}-${i}`} e={e} m={m} now={e.h === t} />)}
          {shown.length === 0 ? <li className="t-12 ink-3">No entries yet: S has placed nothing outside Utah before this hour.</li> : null}
        </ol>
      </div>
    </div>
  );
}

function FeedItem({ e, m, now }: { e: FeedEntry; m: MonitorModel; now: boolean }) {
  return (
    <li className={`monitor-entry ${now ? 'now' : ''}`} data-kind={e.kind}>
      <span className="monitor-dot" data-kind={e.kind} aria-hidden="true" />
      <div style={{ minWidth: 0 }}>
        <div className="t-11 ink-3 num">{stampLabel(m.hours[e.h])}</div>
        <div className="t-12">{e.text}</div>
      </div>
    </li>
  );
}

function Traced({ m }: { m: MonitorModel }) {
  if (!m.traced.length) return null;
  return (
    <div className="panel" data-testid="monitor-traced">
      <h2 className="t-15" style={{ margin: '0 0 4px' }}>Two jobs the test run traced</h2>
      <p className="t-12 ink-3" style={{ margin: '0 0 8px' }}>The run's only per-job records (job-replay.json), both outside the replay week. <Ev e="measured">size</Ev> <Ev e="simulated">placement</Ev></p>
      <ol data-testid="monitor-traced-feed" style={{ listStyle: 'none', margin: 0, padding: 0 }} className="flex flex-col gap-2">
        {m.traced.map((j) => (
          <li key={j.id} className="monitor-entry" data-kind="traced">
            <span className="monitor-dot" data-kind="placed" aria-hidden="true" />
            <div style={{ minWidth: 0 }}>
              <div className="t-11 ink-3 num">arrived {stampLabel(j.arrival)}</div>
              <div className="t-12">{j.text}</div>
              {j.outcome ? <div className="t-11 ink-2" style={{ marginTop: 2 }}>{j.outcome}</div> : null}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Week({ m, movedJobs, movedGpuH }: { m: MonitorModel; movedJobs: number; movedGpuH: number }) {
  const { uKg, sKg, nJobs } = m.week;
  return (
    <div className="panel" data-testid="monitor-week">
      <h2 className="t-15" style={{ margin: '0 0 8px' }}>The week, all sites</h2>
      <dl className="ov-dl t-12">
        <dt>Arrivals</dt><dd className="num">{nJobs == null ? '–' : fmt(nJobs)} jobs <Ev e="simulated" /></dd>
        <dt>Moved by S</dt><dd className="num">{fmt(movedJobs)} jobs, {fmt(movedGpuH)} GPU-h <Ev e="simulated" /></dd>
        {uKg != null && sKg != null ? <><dt>CO₂ of the week’s arrivals</dt><dd className="num">S {fmt(sKg / 1000, 1)} t vs U {fmt(uKg / 1000, 1)} t ({pct((uKg - sKg) / uKg, 1)}% less) <span className="chip-neutral" style={{ marginLeft: 4 }}>retrospective, scored on realized truth</span></dd></> : null}
        {m.lateS != null ? <><dt>Late jobs under S</dt><dd className="num">{fmt(m.lateS)}, over the whole test cohort <Ev e="simulated" /></dd></> : null}
      </dl>
      <details className="t-12 ink-2" style={{ marginTop: 8 }} data-testid="monitor-missing">
        <summary className="cursor-pointer fw-500">Not shown: not in the committed files</summary>
        <ul style={{ margin: '4px 0 0', paddingLeft: 16 }}>{MISSING.map((x) => <li key={x}>{x}</li>)}</ul>
      </details>
    </div>
  );
}
