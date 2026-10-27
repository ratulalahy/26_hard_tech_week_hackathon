import { useMemo, useRef } from 'react';
import { EChart } from '../components/EChart';
import { Panel, Strip, useWidth } from '../components/charts';
import { Ev, Icon } from '../components/ui';
import { C, CI_MAX, ci2c } from '../lib/color';
import { DESTS, REGION, asNum, dayCurve, headline, type Core, type Dest } from '../lib/data';
import { fmt, fmtHour, fmtSpan, monthLabel, pct, pctRange, sig2 } from '../lib/format';
import { makePlan } from '../lib/plan';
import { useApp, type Mode } from '../lib/store';
import { WestMap, type ArcSpec } from '../map/WestMap';

const SCRUB = {
  gpus: { min: 8, max: 512, step: 8, fmt: (v: number) => fmt(v), label: 'GPUs' },
  hours: { min: 1, max: 16, step: 1, fmt: (v: number) => String(v), label: 'Run length in hours' },
  hour: { min: 0, max: 23, step: 1, fmt: (v: number) => fmtHour(v), label: 'Arrival hour' },
  maxWait: { min: 0, max: 24, step: 1, fmt: (v: number) => String(v), label: 'Longest allowed wait in hours' },
} as const;
type ScrubKey = keyof typeof SCRUB;

function Scrub({ k }: { k: ScrubKey }) {
  const v = useApp((s) => s[k]);
  const set = useApp((s) => s.set);
  const c = SCRUB[k];
  const st = useRef<{ x: number; v: number } | null>(null);
  const put = (n: number) => set({ [k]: k === 'hour' ? ((n % 24) + 24) % 24 : Math.max(c.min, Math.min(c.max, n)) } as never);
  return (
    <button className="scrub" role="spinbutton" aria-label={c.label} aria-valuenow={v} aria-valuemin={c.min} aria-valuemax={c.max} aria-valuetext={c.fmt(v)}
      onPointerDown={(e) => { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); st.current = { x: e.clientX, v }; }}
      onPointerMove={(e) => { if (!st.current) return; put(st.current.v + Math.round((e.clientX - st.current.x) / 12) * c.step); }}
      onPointerUp={() => (st.current = null)}
      onKeyDown={(e) => { const d = ({ ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 } as Record<string, number>)[e.key]; if (d) { e.preventDefault(); put(v + d * c.step); } }}>
      {c.fmt(v)}
    </button>
  );
}

export function ModeSeg() {
  const { mode, set } = useApp();
  const M: { m: Mode; l: string; i: string }[] = [{ m: 'now', l: 'Run now', i: 'bolt' }, { m: 'wait', l: 'Wait', i: 'moon' }, { m: 'move', l: 'Move', i: 'route' }];
  return (
    <div className="seg" role="group" aria-label="Router action">
      {M.map((x) => <button key={x.m} aria-pressed={mode === x.m} onClick={() => set({ mode: x.m })}><Icon name={x.i} size={14} />{x.l}</button>)}
    </div>
  );
}

export function Cockpit() {
  const s = useApp();
  const { data, mode, dest, month } = s;
  const p = useMemo(() => makePlan(data!, { month, hour: s.hour, hours: s.hours, gpus: s.gpus, maxWait: s.maxWait }), [data, month, s.hour, s.hours, s.gpus, s.maxWait]);
  const h = headline(data!.metrics);
  const best = ([['now', p.now], ['wait', p.wait.v], ['move', p.moves[dest]]] as [Mode, number][]).sort((a, b) => a[1] - b[1])[0][0];
  const V = mode === 'move' ? p.moves[dest] : mode === 'wait' ? p.wait.v : p.now;
  const verdict = mode === 'move' ? `Move it to ${REGION[dest].name}` : mode === 'wait' ? (p.wait.d ? `Hold it until ${fmtHour(p.wait.s)}` : `Waiting up to ${s.maxWait} h does not help`) : 'Run it now in Utah';
  const ci = useMemo(() => Object.fromEntries((['PACE', 'BPAT', 'CISO', 'NEVP'] as Core[]).map((c) => [c, dayCurve(data!.grid, c, month)[s.hour]])), [data, month, s.hour]);
  const arcs = useMemo<ArcSpec[]>(() => (mode === 'move' ? DESTS.map((d) => ({ to: d, weight: d === dest ? 0.5 : 0.05, label: '', selected: d === dest })) : []), [mode, dest]);
  const context = useMemo(() => Object.fromEntries(Object.entries(data!.grid.context_year_mean_ci.by_ba).map(([k, e]) => [k, asNum(e as never)])), [data]);
  const kw = asNum(data!.manifest.assumptions.kw_per_gpu), pue = asNum(data!.manifest.assumptions.pue);

  return (
    <section aria-label="Decision cockpit" className="fixed z-10 grid" style={{ top: 72, left: 16, right: 16, bottom: 32, gridTemplateColumns: 'minmax(0,1fr) clamp(400px, 30vw, 520px)', gap: 16 }}>
      <div className="grid min-h-0" style={{ gridTemplateRows: 'auto minmax(0,1fr) auto', gap: 16 }}>
        <Panel>
          <div className="flex items-start justify-between gap-4">
            <h1 className="t-20" style={{ margin: 0, maxWidth: '46ch', lineHeight: 1.5 }}>
              Run <Scrub k="gpus" /> GPUs for <Scrub k="hours" /> hours, arriving in Utah at <Scrub k="hour" />. It can wait up to <Scrub k="maxWait" /> hours.
            </h1>
            <span className="ev" data-ev="modeled" style={{ padding: '2px 8px', borderRadius: 8, boxShadow: 'inset 0 0 0 1px var(--hair)', color: 'var(--ink-2)' }}>illustrative · modeled</span>
          </div>
          <div className="flex flex-wrap items-center gap-4 t-12 ink-3" style={{ marginTop: 8 }}>
            <span>Drag a number sideways, or focus it and use the arrow keys.</span>
            <Ev e="observed">carbon: typical {monthLabel(month, true)} day, America/Denver hours</Ev>
            <Ev e="assumed">{fmt(kw ?? 0, 1)} kW per GPU × PUE {fmt(pue ?? 0, 1)}</Ev>
          </div>
        </Panel>

        <Panel className="flex flex-col min-h-0" style={{ padding: 0 }}>
          <div className="flex items-start justify-between gap-4" style={{ padding: 16 }}>
            <div>
              <h2 className="t-15" style={{ margin: 0 }}>{verdict}{best === mode ? ': the cleanest of the three' : ''}</h2>
              <div className="flex items-baseline gap-2" style={{ marginTop: 4 }}>
                <span className="t-hero">{mode === 'now' ? fmt(V) : `${pct(Math.max(0, p.cut(V)), 0)}%`}<span className="unit">{mode === 'now' ? 'g/kWh average' : 'less CO₂ than running now'}</span></span>
              </div>
              <div className="t-12 ink-2" style={{ marginTop: 4 }}>
                {fmt(p.kwh)} kWh for the run, about {sig2(p.kg(V))} kg CO₂ at {fmt(V)} g/kWh{best !== mode ? `. The cleanest option here is to ${best === 'move' ? 'move' : best === 'wait' ? 'wait' : 'run now'}.` : '.'} <Ev e="modeled" />
              </div>
            </div>
            <ModeSeg />
          </div>
          <Lanes p={p} />
          <div style={{ padding: '0 16px 8px', flex: 1, minHeight: 140 }}><Patience p={p} /></div>
        </Panel>

        <Panel style={{ padding: '12px 16px' }}>
          <div data-testid="cockpit-registered" className="flex flex-wrap items-baseline gap-x-4 gap-y-1 t-13">
            <span className="t-15">The registered result is the whole year, not this one job</span>
            <span>Moving: <b className="fw-600">{pctRange(h.placement.lo, h.placement.hi)}%</b> less CO₂ <span className="t-12 ink-3">(95% {pct(h.placement.ciLo)}–{pct(h.placement.ciHi)}%)</span></span>
            <span>Waiting only: <b className="fw-600">{pctRange(h.timing.lo, h.timing.hi)}%</b> <span className="t-12 ink-3">(95% {pct(h.timing.ciLo)}–{pct(h.timing.ciHi)}%)</span></span>
            <span className="t-12 ink-3">{fmt(data!.metrics.cohort.n_jobs.value)} jobs, same work, deadlines met. <Ev e="simulated" /></span>
          </div>
        </Panel>
      </div>

      <div className="grid min-h-0" style={{ gridTemplateRows: 'minmax(0,1fr) auto', gap: 16 }}>
        <Panel className="relative overflow-hidden" style={{ padding: 0 }}>
          <WestMap id="map-inset" variant="inset" interactive={false} ci={ci} context={context} hourLabel={fmtHour(s.hour)} arcs={arcs} ring={mode === 'wait'}
            bounds={[[-124.6, 32.2], [-105.5, 48.6]]} padding={{ top: 64, bottom: 16, left: 16, right: 16 }} />
          <div className="absolute flex items-baseline justify-between gap-2" style={{ left: 16, right: 16, top: 16 }}>
            <span className="t-15">{mode === 'move' ? `Utah to ${REGION[dest].name}` : mode === 'wait' ? `Held in Utah until ${fmtHour(p.wait.s)}` : 'Runs in Utah now'}</span>
            <Ev e="observed">carbon at {fmtHour(s.hour)}</Ev>
          </div>
        </Panel>
        <Panel>
          <div className="flex items-baseline justify-between"><span className="t-15">Where the job's hours land</span><Ev e="observed">typical day</Ev></div>
          <HoursLand p={p} />
        </Panel>
      </div>
    </section>
  );
}

function Lanes({ p }: { p: ReturnType<typeof makePlan> }) {
  const { mode, dest, maxWait, set } = useApp();
  const [ref, w] = useWidth<HTMLDivElement>();
  const lanes: { m: Mode; d?: Dest; t: string; s: string; v: number }[] = [
    { m: 'now', t: 'Run now in Utah', s: fmtSpan(p.a, p.H), v: p.now },
    { m: 'wait', t: 'Wait in Utah', s: p.wait.d ? `${fmtSpan(p.wait.s, p.H)}, starts ${p.wait.d} h later` : `no cleaner start within ${maxWait} h`, v: p.wait.v },
    ...DESTS.map((d) => ({ m: 'move' as Mode, d, t: `Move to ${REGION[d].name}`, s: `${fmtSpan(p.a, p.H)} · ${d}`, v: p.moves[d] })),
  ];
  const lx = 200, rx = 150, aw = Math.max(40, w - lx - rx), X = (v: number) => (Math.min(v, CI_MAX) / CI_MAX) * aw;
  return (
    <div ref={ref} style={{ padding: '0 8px' }} role="group" aria-label="Options for this run">
      <div className="flex t-11 ink-3" style={{ padding: '0 8px 4px', paddingLeft: lx + 8 }}>Average carbon intensity of the run, g CO₂/kWh</div>
      {lanes.map((L) => {
        const sel = L.m === mode && (L.m !== 'move' || L.d === dest);
        const cut = p.cut(L.v);
        return (
          <button key={L.t} className="rowbtn grid items-center" aria-pressed={sel} style={{ gridTemplateColumns: `${lx - 8}px minmax(0,1fr) ${rx - 16}px`, gap: 8, padding: '6px 8px' }}
            onClick={() => set({ mode: L.m, ...(L.d ? { dest: L.d } : {}) })}>
            <span className="flex items-center gap-2 min-w-0">
              <span className="grid place-items-center flex-none" style={{ width: 24, height: 24, borderRadius: 8, background: sel ? C.route : '#fff', color: sel ? '#fff' : C.ink2, boxShadow: sel ? 'none' : 'inset 0 0 0 1px var(--hair)' }}>
                <Icon name={L.m === 'now' ? 'bolt' : L.m === 'wait' ? 'moon' : 'route'} size={14} />
              </span>
              <span className="min-w-0"><span className="t-13 fw-600 block truncate">{L.t}</span><span className="t-11 ink-3 block truncate">{L.s}</span></span>
            </span>
            <span className="flex items-center gap-2" style={{ height: 20 }}>
              <span style={{ width: Math.max(4, X(L.v)), height: 14, borderRadius: '0 4px 4px 0', background: ci2c(L.v), boxShadow: 'inset 0 0 0 1px rgba(110,62,30,.10)' }} />
              <span className="t-13 fw-500 num">{fmt(L.v)}</span>
            </span>
            <span className="text-right"><span className="t-13 fw-600 num block">{L.m === 'now' ? 'baseline' : Math.round(cut * 100) === 0 ? 'no gain' : `${cut >= 0 ? '−' : '+'}${pct(Math.abs(cut), 0)}%`}</span><span className="t-11 ink-3 num block">≈ {sig2(p.kg(L.v))} kg CO₂</span></span>
          </button>
        );
      })}
    </div>
  );
}

function Patience({ p }: { p: ReturnType<typeof makePlan> }) {
  const { maxWait, dest } = useApp();
  const ends = useMemo(() => {
    const items = [{ k: 'wait', v: p.patience[24] * 100 }, ...DESTS.map((d) => ({ k: d as string, v: Math.max(0, p.cut(p.moves[d])) * 100 }))].sort((a, b) => b.v - a.v);
    const off: Record<string, number> = {};
    let last = Infinity, shift = 0;
    for (const it of items) { shift = last - it.v < 7 ? shift + 12 : 0; off[it.k] = shift; last = it.v; }
    return off;
  }, [p]);
  const option = useMemo(() => ({
    grid: { left: 188, right: 150, top: 28, bottom: 28 },
    xAxis: { type: 'value', min: 0, max: 24, interval: 6, name: 'allowed wait, h', nameLocation: 'end', nameGap: 8, axisLabel: { formatter: (v: number) => `${v} h` } },
    yAxis: { type: 'value', min: 0, max: 100, interval: 50, axisLabel: { formatter: (v: number) => `${v}%` } },
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${Math.round(v)}%` },
    graphic: [],
    series: [
      { name: 'Wait in Utah', type: 'line', step: 'end', data: p.patience.map((v, d) => [d, v * 100]), lineStyle: { color: C.ink, width: 2 }, symbol: 'none',
        markLine: { silent: true, symbol: 'none', label: { show: true, position: 'insideEndTop', color: C.ink, fontSize: 11, formatter: 'your limit' }, lineStyle: { color: C.route, width: 1.5, type: 'solid' }, data: [{ xAxis: maxWait }] },
        endLabel: { show: true, formatter: () => `Wait in Utah · up to ${Math.round(p.patience[24] * 100)}%`, color: C.ink, fontSize: 11, fontWeight: 500, offset: [8, ends.wait] } },
      ...DESTS.map((d) => ({ name: `Move to ${REGION[d].name}`, type: 'line', data: [[0, Math.max(0, p.cut(p.moves[d])) * 100], [24, Math.max(0, p.cut(p.moves[d])) * 100]], symbol: 'none',
        lineStyle: { color: d === dest ? C.route : C.ink3, width: d === dest ? 2 : 1, type: d === dest ? 'solid' : [4, 4] },
        endLabel: { show: true, formatter: () => `${REGION[d].name} · ${Math.round(Math.max(0, p.cut(p.moves[d])) * 100)}%`, color: C.ink, fontSize: 11, fontWeight: d === dest ? 600 : 400, offset: [8, ends[d]] } })),
    ],
  }), [p, maxWait, dest, ends]);
  return (
    <div className="flex h-full" style={{ gap: 0 }}>
      <div style={{ width: 0, position: 'relative' }}>
        <div className="absolute t-13" style={{ left: 8, top: 24, width: 170 }}>
          <div className="fw-600">What patience buys</div>
          <div className="t-12 ink-3" style={{ marginTop: 2 }}>Best cut from waiting, by the longest wait allowed; moving needs no wait.</div>
          <div style={{ marginTop: 4 }}><Ev e="modeled" /></div>
        </div>
      </div>
      <EChart option={option} className="flex-1" label="Best carbon cut from waiting in Utah by allowed wait, compared with moving" />
    </div>
  );
}

function HoursLand({ p }: { p: ReturnType<typeof makePlan> }) {
  const { data, mode, dest, month } = useApp();
  const rows: [Core, string][] = [['PACE', 'Utah'], [dest, REGION[dest].name]];
  const js = mode === 'wait' ? p.wait.s : p.a;
  return (
    <div className="flex flex-col" style={{ gap: 8, marginTop: 8 }}>
      {rows.map(([c, nm], i) => {
        const on = (mode === 'move') === (i === 1);
        return (
          <div key={c} className="grid items-center" style={{ gridTemplateColumns: '112px minmax(0,1fr)', gap: 8 }}>
            <span className="t-13 fw-500">{nm} <span className="t-11 ink-3 fw-400">{c}</span></span>
            <Strip curve={dayCurve(data!.grid, c, month)} h={24} job={on ? { s: js, H: p.H } : null} label={`${nm}, typical day carbon; the job's hours marked`} />
          </div>
        );
      })}
      <div className="grid t-11 ink-3" style={{ gridTemplateColumns: '112px repeat(4, 1fr)', gap: 8 }}>
        <span />{[0, 6, 12, 18].map((h) => <span key={h}>{fmtHour(h)}</span>)}
      </div>
    </div>
  );
}
