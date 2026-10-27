// The ten-region overview (T18): the traffic report beyond Utah. A standalone, full-width page that reads
// results/overview.json (validation year only) and grid-profile.json (the colour scale's midpoint). It does
// not depend on the App shell; main.tsx mounts it on #regions until the shared nav (T21) takes it over.
import { useEffect, useMemo, useState } from 'react';
import { Strip, useWidth } from '../components/charts';
import { Ev, EvCI, Skel } from '../components/ui';
import { C, ci2c, setMid } from '../lib/color';
import { asNum, type Env, type Json } from '../lib/data';
import { fmt, fmtHour, signed } from '../lib/format';
import { RegionsMap } from '../map/RegionsMap';
import { Legend } from '../views/ControlRoom';

const base = import.meta.env?.BASE_URL ?? './';
const get = (f: string) => fetch(`${base}data/results/${f}`).then((r) => { if (!r.ok) throw new Error(`${f}: HTTP ${r.status}`); return r.json(); });

type SortKey = 'swing' | 'rush' | 'skill' | 'ci';
const SORTS: { id: SortKey; label: string }[] = [
  { id: 'swing', label: 'Room to shift' },
  { id: 'rush', label: 'Rush-hour carbon' },
  { id: 'skill', label: 'Forecast skill' },
  { id: 'ci', label: 'Cleanest' },
];
const MODEL: Record<string, string> = { W: 'W weekly profile', K: 'K climatology', L: 'L learned model', P: 'P persistence' };
const v = (e: Env | undefined | null) => (e ? asNum(e) : null);
const fmtUtc = (iso: string) => new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }).format(new Date(iso));
const pctS = (x: number | null, d = 0) => (x == null ? '–' : `${signed(x * 100, d)}%`);

/** The 4 highest (or lowest) hours of a 24-value profile. */
function topHours(a: (number | null)[], k = 4, low = false): number[] {
  return a.map((x, i) => [x, i] as const).filter(([x]) => x != null).sort((p, q) => (low ? p[0]! - q[0]! : q[0]! - p[0]!)).slice(0, k).map(([, i]) => i).sort((p, q) => p - q);
}
const hoursLabel = (hs: number[]) => {
  // contiguous runs of hour starts, e.g. "5 PM–9 PM"
  const runs: [number, number][] = [];
  for (const h of hs) { const r = runs[runs.length - 1]; if (r && r[1] === h - 1) r[1] = h; else runs.push([h, h]); }
  return runs.map(([a, b]) => `${fmtHour(a)}–${fmtHour(b + 1)}`).join(', ');
};

export function Regions() {
  const [ov, setOv] = useState<Json | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>('swing');
  const [sel, setSel] = useState<string | null>('PACE');
  useEffect(() => {
    document.title = 'GridPilot · Ten regions';
    Promise.all([get('overview.json'), get('grid-profile.json').catch(() => null)])
      .then(([o, g]) => { setMid(asNum(g?.reference?.us_avg_ci)); setOv(o); })
      .catch((e) => setErr(String(e)));
  }, []);

  const rows = useMemo(() => {
    if (!ov) return [];
    const list = (ov.order as string[]).map((b) => ov.regions[b]);
    const key = (r: Json): number => {
      if (sort === 'swing') return -(v(r.swing.median_g) ?? -Infinity);
      if (sort === 'rush') return -(v(r.alignment.rush_vs_mean_pct) ?? -Infinity);
      if (sort === 'skill') return -(v(r.forecast.ci.skill.vs_persistence) ?? -Infinity);
      return v(r.alignment.mean_ci) ?? Infinity;
    };
    return [...list].sort((a, b) => key(a) - key(b) || a.ba.localeCompare(b.ba));
  }, [ov, sort]);

  return (
    <div className="regions-page" data-testid="regions-page">
      <header className="flex items-center gap-3" style={{ marginBottom: 16 }}>
        <a href="#control" className="btn" aria-label="Back to the Utah dashboard">← Utah dashboard</a>
        <span className="t-15" style={{ fontFamily: 'var(--font-display)', fontWeight: 600 }}>GridPilot</span>
        <span className="t-12 ink-3">Ten-region overview of the traffic report</span>
      </header>
      <main>
        {err ? <div className="panel t-13" role="alert"><b className="fw-600">The overview did not load.</b> <span className="ink-2">{err}. Run <code>make overview</code>, then <code>make web</code>.</span></div>
          : !ov ? <Loading />
            : rows.length === 0 ? <div className="panel t-13">No region has enough validation data for the overview.</div>
              : <Content ov={ov} rows={rows} sort={sort} setSort={setSort} sel={sel} setSel={setSel} />}
      </main>
    </div>
  );
}

function Loading() {
  return (
    <div aria-busy="true" aria-label="Loading the overview">
      <Skel w="60%" h={24} /><div style={{ height: 8 }} /><Skel w="80%" h={14} />
      <div className="grid" style={{ gridTemplateColumns: '1.3fr 1fr', gap: 16, marginTop: 16 }}><Skel h={380} r={16} /><Skel h={380} r={16} /></div>
      <div style={{ height: 16 }} /><Skel h={420} r={16} />
    </div>
  );
}

function Content({ ov, rows, sort, setSort, sel, setSel }: { ov: Json; rows: Json[]; sort: SortKey; setSort: (s: SortKey) => void; sel: string | null; setSel: (s: string) => void }) {
  const all = (ov.order as string[]).map((b) => ov.regions[b]);
  const dirtier = all.filter((r) => (v(r.alignment.rush_vs_mean_pct) ?? 0) > 0);
  const cleaner = all.filter((r) => (v(r.alignment.rush_vs_mean_pct) ?? 0) < 0);
  const maxSwing = all.reduce((m, r) => (v(r.swing.median_g) ?? 0) > (v(m.swing.median_g) ?? 0) ? r : m, all[0]);
  const beat = all.filter((r) => (v(r.forecast.ci.skill.vs_persistence) ?? 0) > 0).length;
  const title = cleaner.length && dirtier.length
    ? `In ${dirtier.length} of ${all.length} regions the rush hours are dirtier than the average hour; in ${cleaner.map((r) => `${r.name.replace(/ \(.*\)$/, '')} (${r.ba})`).join(', ')} they are cleaner`
    : dirtier.length === all.length ? `In all ${all.length} regions the rush hours are dirtier than the average hour` : `In ${cleaner.length} of ${all.length} regions the rush hours are cleaner than the average hour`;
  const ci = Object.fromEntries(all.map((r) => [r.ba, v(r.alignment.mean_ci)]));
  const names = Object.fromEntries(all.map((r) => [r.ba, r.name]));
  const s = ov.window;
  return (
    <>
      <section aria-labelledby="ov-title" style={{ marginBottom: 16 }}>
        <h1 id="ov-title" className="t-20" style={{ margin: 0 }} data-testid="regions-title">{title}</h1>
        <p className="t-13 ink-2" style={{ margin: '4px 0 8px', maxWidth: '96ch' }}>
          Rush hours are each day's four highest net-load hours (demand minus wind and solar). The widest daily carbon swing, the room a time shift has, is {maxSwing.name}'s: a typical day runs {fmt(v(maxSwing.swing.median_g) ?? 0)} g/kWh from its cleanest to its dirtiest hour.
          Day-ahead, our forecasts beat same-hour persistence on carbon in {beat} of {all.length} regions.
        </p>
        <div className="flex flex-wrap items-center gap-3" data-testid="regions-sources">
          <span className="chip-neutral">Validation year · {fmtUtc(s.start)} – {fmtUtc(new Date(new Date(s.end).getTime() - 3600e3).toISOString())} (UTC) · test year sealed</span>
          <EvCI extra="EIA-930 BA workbooks" />
          <Ev e="observed">net load: EIA-930 balance</Ev>
          <Ev e="forecast" title="Issued daily at 10 AM Mountain for the next day, from published data only">day-ahead forecasts, issued 10 AM MT</Ev>
          <Ev e="measured" title="Forecast errors measured against the published values">forecast errors</Ev>
          <span className="t-11 ink-3">Hours are Mountain Time, one clock for every region.</span>
        </div>
      </section>

      <div className="grid ov-top" style={{ gap: 16, marginBottom: 16 }}>
        <section className="panel" style={{ padding: 0, overflow: 'hidden', position: 'relative', minHeight: 360 }} aria-label="Map">
          <RegionsMap ci={ci} names={names} selected={sel} onPick={setSel} />
          <div className="panel over-map" style={{ position: 'absolute', left: 12, bottom: 12, padding: '8px 12px', width: 300 }}><Legend width={276} short /><div className="t-11 ink-3">Validation-year mean, g CO₂/kWh <Ev e="modeled" /></div></div>
        </section>
        <Detail r={ov.regions[sel ?? all[0].ba] ?? all[0]} />
      </div>

      <section className="panel" style={{ marginBottom: 16 }} aria-labelledby="ov-table">
        <div className="flex flex-wrap items-center justify-between gap-3" style={{ marginBottom: 8 }}>
          <h2 id="ov-table" className="t-15" style={{ margin: 0 }}>Ranked: where a flexible job can gain, and how well tomorrow is forecast</h2>
          <div className="seg" role="group" aria-label="Rank regions by">
            {SORTS.map((o) => <button key={o.id} aria-pressed={sort === o.id} onClick={() => setSort(o.id)}>{o.label}</button>)}
          </div>
        </div>
        <RankTable rows={rows} sel={sel} setSel={setSel} />
      </section>

      <section className="panel" aria-labelledby="ov-mult">
        <h2 id="ov-mult" className="t-15" style={{ margin: '0 0 4px' }}>A typical day in each region</h2>
        <p className="t-12 ink-2" style={{ margin: '0 0 12px' }}>The line is net-load stress (its percentile against the region's 2022–Oct 2024 training hours; above 95 is a stress hour); the hatch marks the four most stressed hours. The strip below is carbon intensity by hour on the shared scale. Same order as the table. <Ev e="modeled" /></p>
        <div className="ov-mult" data-testid="regions-multiples">
          {rows.map((r) => <Multiple key={r.ba} r={r} sel={sel === r.ba} onPick={() => setSel(r.ba)} />)}
        </div>
      </section>
      {ov.dropped?.length > 0 && <p className="t-12 ink-2" data-testid="regions-dropped">Not shown: {ov.dropped.map((d: Json) => `${d.ba} (${d.reason})`).join('; ')}.</p>}
      <footer className="t-11 ink-3" style={{ margin: '16px 0 8px', maxWidth: '120ch' }}>
        {(ov.limitations as string[]).join(' ')} Skill = 1 − MAE(model) ÷ MAE(baseline) on the same issued hours; the region's model is the best of W, K and L by validation MAE, so its skill is development evidence. Source: results/overview.json ({ov.run_id ?? 'no run id'}).
      </footer>
    </>
  );
}

function Detail({ r }: { r: Json }) {
  const al = r.alignment, sw = r.swing, f = r.forecast;
  const ciDay: (number | null)[] = r.profile.ci.value;
  const stDay: (number | null)[] = r.profile.stress_pct.value;
  const rush = topHours(stDay), clean = topHours(ciDay, 4, true);
  const gap = v(al.rush_vs_mean_pct);
  return (
    <section className="panel flex flex-col gap-3" aria-labelledby="ov-detail" data-testid="regions-detail">
      <div>
        <h2 id="ov-detail" className="t-15" style={{ margin: 0 }}>{r.name} · {r.ba}</h2>
        <div className="t-12 ink-3">{r.interconnection} Interconnection{r.core_site ? ' · a core site of the router experiment' : ' · overview only'}</div>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="t-hero">{gap == null ? '–' : `${signed(gap, 0)}%`}</span>
        <span className="t-12 ink-2">carbon in rush hours vs the average hour <Ev e="modeled" /></span>
      </div>
      <div className="t-13 ink-2">
        Cleanest on a typical day: <b className="fw-600" style={{ color: C.ink }}>{hoursLabel(clean)}</b>. Most stressed: <b className="fw-600" style={{ color: C.ink }}>{hoursLabel(rush)}</b>.
        A typical day swings <b className="fw-600" style={{ color: C.ink }}>{fmt(v(sw.median_g) ?? 0)} g/kWh</b> (middle half of days {fmt(v(sw.p25_g) ?? 0)}–{fmt(v(sw.p75_g) ?? 0)}), {fmt(v(sw.median_pct) ?? 0)}% of its mean.
      </div>
      <div><Strip curve={ciDay} h={16} label={`${r.ba} typical-day carbon intensity by Mountain hour`} /><HourAxis /></div>
      <dl className="ov-dl t-12">
        <dt>Stress hours in the dirtiest quarter</dt><dd>{v(al.stress_top_quartile_share) == null ? '–' : `${fmt(v(al.stress_top_quartile_share)!)}%`} <span className="ink-3">of {fmt(v(al.n_stress_hours) ?? 0)} h</span></dd>
        <dt>Carbon vs net load, rank correlation</dt><dd>{v(al.spearman_ci_net_load) == null ? '–' : fmt(v(al.spearman_ci_net_load)!, 2).replace('-', '−')}</dd>
        <dt>Cleanest 4 hours that are also rush hours</dt><dd>{fmt(v(al.clean_rush_overlap_pct) ?? 0)}% <span className="ink-3">(chance 17%)</span></dd>
        <dt>Carbon forecast, {MODEL[f.ci.model]}</dt><dd>MAE {fmt(v(f.ci.mae) ?? 0)} g/kWh · {pctS(v(f.ci.skill.vs_persistence))} vs persistence · {pctS(v(f.ci.skill.vs_climatology))} vs climatology</dd>
        <dt>Net-load forecast, {MODEL[f.net_load.model]}</dt><dd>MAE {fmt(v(f.net_load.mae) ?? 0)} MW · {pctS(v(f.net_load.skill.vs_persistence))} vs persistence · top-4 hours hit {fmt((v(f.stress.top4_precision[f.stress.model].precision) ?? 0) * 100)}%</dd>
      </dl>
      <div className="flex flex-wrap gap-3"><Ev e="measured">forecast errors, {fmt(v(f.ci.models.P.n_hours) ?? 0)} issued hours</Ev><Ev e="modeled">profiles and alignment</Ev></div>
    </section>
  );
}

function HourAxis() {
  return (
    <div className="flex justify-between t-11 ink-3" style={{ marginTop: 2 }} aria-hidden="true">
      {[0, 6, 12, 18].map((h) => <span key={h}>{fmtHour(h)}</span>)}<span>MT</span>
    </div>
  );
}

function Bar({ x, max, signedBar = false }: { x: number | null; max: number; signedBar?: boolean }) {
  if (x == null) return null;
  const w = Math.min(1, Math.abs(x) / max) * 100;
  if (!signedBar) return <span className="ov-bar" aria-hidden="true"><i style={{ width: `${w}%`, background: C.ink3 }} /></span>;
  return (
    <span className="ov-bar ov-bar-s" aria-hidden="true">
      <i style={{ width: `${w / 2}%`, left: x >= 0 ? '50%' : `${50 - w / 2}%`, background: x >= 0 ? '#c6481c' : '#298954' }} />
    </span>
  );
}

function RankTable({ rows, sel, setSel }: { rows: Json[]; sel: string | null; setSel: (s: string) => void }) {
  const maxSw = Math.max(...rows.map((r) => v(r.swing.median_g) ?? 0), 1);
  const maxGap = Math.max(...rows.map((r) => Math.abs(v(r.alignment.rush_vs_mean_pct) ?? 0)), 1);
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="tbl ov-tbl" data-testid="regions-table">
        <caption className="sr-only">Ten regions ranked; validation year; select a row to show it on the map and in the detail panel</caption>
        <thead>
          <tr>
            <th scope="col">Region</th>
            <th scope="col">Mean carbon <span className="fw-400">g/kWh</span></th>
            <th scope="col">Daily swing <span className="fw-400">g/kWh, median</span></th>
            <th scope="col">Rush hours vs average <span className="fw-400">carbon</span></th>
            <th scope="col">Stress hours in dirtiest ¼</th>
            <th scope="col">ρ carbon, net load</th>
            <th scope="col">Carbon forecast <span className="fw-400">skill vs persistence · climatology</span></th>
            <th scope="col">Net-load forecast <span className="fw-400">skill vs persistence · top-4 hit</span></th>
          </tr>
          <tr className="ov-ev">
            <th /><th><Ev e="modeled" /></th><th><Ev e="modeled" /></th><th><Ev e="modeled" /></th><th><Ev e="modeled" /></th><th><Ev e="modeled" /></th><th><Ev e="measured" /></th><th><Ev e="measured" /></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const al = r.alignment, f = r.forecast;
            const mci = v(al.mean_ci), gap = v(al.rush_vs_mean_pct), sw = v(r.swing.median_g);
            return (
              <tr key={r.ba} className={sel === r.ba ? 'sel' : ''}>
                <td>
                  <button className="ov-row" aria-pressed={sel === r.ba} onClick={() => setSel(r.ba)}>
                    <span className="ink-3 num" style={{ width: 16, display: 'inline-block' }}>{i + 1}</span>
                    <span className="fw-600">{r.ba}</span> <span className="ink-2">{r.name}</span>
                  </button>
                </td>
                <td><span className="ov-sw" style={{ background: mci == null ? '#fff' : ci2c(mci) }} aria-hidden="true" />{mci == null ? '–' : fmt(mci)}</td>
                <td><Bar x={sw} max={maxSw} /> {sw == null ? '–' : fmt(sw)}</td>
                <td><Bar x={gap} max={maxGap} signedBar /> {gap == null ? '–' : `${signed(gap, 0)}%`}</td>
                <td>{v(al.stress_top_quartile_share) == null ? <span className="ink-3" title={al.stress_top_quartile_share.reason}>–</span> : `${fmt(v(al.stress_top_quartile_share)!)}%`}</td>
                <td>{v(al.spearman_ci_net_load) == null ? '–' : fmt(v(al.spearman_ci_net_load)!, 2).replace('-', '−')}</td>
                <td title={`${MODEL[f.ci.model]}; MAE ${fmt(v(f.ci.mae) ?? 0)} g/kWh`}>{pctS(v(f.ci.skill.vs_persistence))} · {pctS(v(f.ci.skill.vs_climatology))}</td>
                <td title={`${MODEL[f.net_load.model]}; MAE ${fmt(v(f.net_load.mae) ?? 0)} MW`}>{pctS(v(f.net_load.skill.vs_persistence))} · {fmt((v(f.stress.top4_precision[f.stress.model].precision) ?? 0) * 100)}%</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Multiple({ r, sel, onPick }: { r: Json; sel: boolean; onPick: () => void }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const st: (number | null)[] = r.profile.stress_pct.value;
  const rush = topHours(st);
  const H = 56, cw = w / 24;
  const y = (p: number) => 2 + (1 - p / 100) * (H - 4);
  const path = st.map((p, i) => (p == null ? '' : `${i === 0 || st[i - 1] == null ? 'M' : 'L'}${(i + 0.5) * cw},${y(p)}`)).join('');
  const gap = v(r.alignment.rush_vs_mean_pct);
  return (
    <button className="ov-card" aria-pressed={sel} onClick={onPick} aria-label={`${r.name}: rush hours ${gap == null ? 'not available' : `${signed(gap, 0)}% carbon vs the average hour`}, daily swing ${fmt(v(r.swing.median_g) ?? 0)} grams per kilowatt-hour`}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="t-12 fw-600">{r.ba} <span className="fw-400 ink-2">{r.name}</span></span>
        <span className="t-12 num">{gap == null ? '–' : `${signed(gap, 0)}%`}</span>
      </div>
      <div ref={ref} style={{ height: H, marginTop: 4 }}>
        {w > 0 && (
          <svg width={w} height={H} style={{ display: 'block' }} aria-hidden="true">
            <defs><pattern id={`h-${r.ba}`} width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="4" height="4" fill={C.rushFill} /><line x1="0" y1="0" x2="0" y2="4" stroke={C.rush} strokeOpacity={0.35} strokeWidth={1.2} /></pattern></defs>
            {rush.map((h) => <rect key={h} x={h * cw} y={0} width={cw} height={H} fill={`url(#h-${r.ba})`} />)}
            <line x1={0} x2={w} y1={y(95)} y2={y(95)} stroke={C.ink3} strokeDasharray="2 2" strokeOpacity={0.6} />
            <text x={2} y={y(95) + 10} fontSize={10} fill={C.ink3}>95th pct</text>
            <line x1={0} x2={w} y1={H - 1} y2={H - 1} stroke={C.hair} />
            <path d={path} fill="none" stroke={C.ink} strokeWidth={1.75} strokeLinejoin="round" />
          </svg>
        )}
      </div>
      <Strip curve={r.profile.ci.value} h={12} label={`${r.ba} carbon by hour`} />
      <div className="flex justify-between t-11 ink-3" style={{ marginTop: 2 }}><span>{fmtHour(0)}</span><span>{fmtHour(12)}</span><span>swing {fmt(v(r.swing.median_g) ?? 0)} g/kWh</span></div>
    </button>
  );
}
