// The price lens (Stage 3 T22): what moving and waiting cost or save in dollars, as a WHOLESALE
// SCENARIO on the validation year. A standalone, full-width page: it loads data/results/prices.json
// itself, so a top-level nav can mount <Prices /> on its own route, and <PriceCard /> anywhere.
// Every number keeps its evidence envelope. Wholesale real-time prices are not what a data center
// pays; the page says so before any number, and says plainly when moving costs more.
import { BarChart, CustomChart } from 'echarts/charts';
import * as echarts from 'echarts/core';
import { useEffect, useMemo, useState } from 'react';
import { EChart } from '../components/EChart';
import { Ev } from '../components/ui';
import { C } from '../lib/color';
import { REGION, pname, type Core, type Env, type Json } from '../lib/data';
import { MINUS, fmt, fmtDate, fmtHour, pct, signed } from '../lib/format';
import { useViewport } from '../lib/useViewport';

echarts.use([BarChart, CustomChart]);

const SITES: Core[] = ['PACE', 'BPAT', 'CISO', 'NEVP'];
const MOB = 'mobility_le_8gpus:W';
const ORDER = ['S', 'W', 'L', MOB, 'W_time'];
const MOVES = new Set(['S', 'W', 'L', MOB]);
const base = import.meta.env?.BASE_URL ?? './';
const v = (e: Env | undefined) => (e && e.status === 'ok' ? (e.value as number) : null);
const name = (p: string) => (p === MOB ? 'W, only jobs of ≤ 8 GPUs move' : pname(p));
const SHORT: Record<string, string> = { S: 'S static ranking', W: 'W weekly profile', L: 'L learned model', [MOB]: 'W, ≤ 8 GPUs move', W_time: 'W wait-only' };
const usd = (x: number, d = 0) => `${x < 0 ? MINUS : ''}$${fmt(Math.abs(x), d)}`;
const usdSigned = (x: number) => (Math.abs(x) < 0.5 ? '$0' : `${x > 0 ? '+' : MINUS}$${fmt(Math.abs(x))}`);
const utcDay: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' };
const usdK = (x: number) => (x === 0 ? '$0' : `${x > 0 ? '+' : MINUS}$${fmt(Math.abs(x) / 1000, Math.abs(x) % 1000 ? 1 : 0)}k`);

export async function loadPrices(): Promise<Json> {
  const r = await fetch(`${base}data/results/prices.json`);
  if (!r.ok) throw new Error(`prices.json: HTTP ${r.status}`);
  const o = await r.json();
  if (o.scenario !== 'wholesale scenario') throw new Error('prices.json is not a wholesale-scenario price artifact');
  return o;
}

export function usePrices() {
  const [s, setS] = useState<{ o: Json | null; err: string | null }>({ o: null, err: null });
  useEffect(() => {
    let live = true;
    loadPrices().then((o) => live && setS({ o, err: null })).catch((e) => live && setS({ o: null, err: String(e) }));
    return () => { live = false; };
  }, []);
  return s;
}

/** The numbers the headline, the card and the charts quote. */
export function priceFacts(o: Json) {
  const P = o.policies;
  const pol = ORDER.filter((p) => P[p]);
  const d = (p: string) => v(P[p]?.delta_vs_U_usd) ?? 0;
  const f = (p: string) => v(P[p]?.delta_vs_U_frac) ?? 0;
  const ci = (p: string) => (P[p]?.interval?.blocks?.['4']?.saving_usd_ci95?.value ?? null) as [number, number] | null;
  return { P, pol, d, f, ci, perT: (p: string) => v(P[p]?.cost_per_attributed_tonne_usd_t), u: v(P.U.cost_usd) ?? 0 };
}

const Caveat = ({ compact }: { compact?: boolean }) => (
  <div role="note" data-testid="prices-caveat" className={compact ? 'flex items-start gap-2' : 'panel flex items-center gap-3'}
    style={compact ? undefined : { padding: '8px 12px', boxShadow: 'inset 0 0 0 1.5px var(--rush), var(--e-1)' }}>
    <span className="chip-neutral" style={{ fontWeight: 600, color: 'var(--ink)' }}>Wholesale scenario</span>
    <span className={compact ? 't-11 ink-2' : 't-12 ink-2'}>
      {compact ? 'Real-time wholesale prices, not what a data center pays.'
        : 'Simulated energy priced at real-time wholesale market prices (CAISO and the Western Energy Imbalance Market). A data center pays a retail tariff or a contract, with demand charges, transmission and fees, not these prices. Read the direction and the rough size, not a bill.'}
    </span>
  </div>
);

/** The page. */
export function Prices() {
  const { o, err } = usePrices();
  return (
    <section aria-label="Price lens" data-testid="prices" tabIndex={0} className="fixed z-10 overflow-y-auto" style={{ top: 72, left: 16, right: 16, bottom: 32 }}>
      {err ? <PricesError msg={err} /> : !o ? <PricesSkeleton /> : <PricesBody o={o} />}
    </section>
  );
}

function headline(o: Json) {
  const { d, f, P } = priceFacts(o);
  const w = d('W'), t = P.W_time ? d('W_time') : null;
  const move = w > 0 ? `moving jobs out of Utah costs more: W adds ${usd(w)} (+${pct(f('W'), 1)}%) over the year`
    : `moving jobs out of Utah saves money: W saves ${usd(-w)} (${pct(f('W'), 1)}%) over the year`;
  const wait = t == null ? '' : t < 0 ? `; waiting in Utah for cheaper, cleaner hours saves ${usd(-t)} (${MINUS}${pct(-f('W_time'), 1)}%)`
    : `; waiting in Utah also costs more (+${usd(t)})`;
  return `At wholesale prices, ${move}${wait}`;
}

function PricesBody({ o }: { o: Json }) {
  const { perT, pol } = priceFacts(o);
  const cov = o.coverage;
  const mp = o.prices.mean_usd_mwh;
  const pw = perT('W');
  const dearer = SITES.filter((s) => s !== 'PACE' && (v(mp[s]) ?? 0) > (v(mp.PACE) ?? 0)).map((s) => REGION[s].name);
  return (
    <div className="flex flex-col" style={{ gap: 16, padding: '0 8px 16px' }}>
      <Caveat />
      <header className="flex items-end justify-between gap-6 flex-wrap">
        <div>
          <h1 className="t-20" style={{ margin: 0, maxWidth: '64ch' }} data-testid="prices-title">{headline(o)}</h1>
          <p className="t-13 ink-2" style={{ margin: '4px 0 0', maxWidth: '92ch' }}>
            Each policy's simulated hourly energy, priced at each site's real-time market price, {fmtDate(o.window.start, utcDay)} to {fmtDate(o.window.end, utcDay)} (UTC).
            Utah's wholesale power averaged {usd(v(mp.PACE) ?? 0, 2)}/MWh{dearer.length ? `, less than ${dearer.join(' and ')}` : ''}, so most of what moving costs is location, not timing.
            {pw != null ? ` W pays about ${usd(pw)} for each tonne of attributed CO₂ it cuts.` : ''} The router never saw a price; this lens is applied after the fact.
          </p>
        </div>
        <div className="flex gap-3 items-center"><Ev e="observed">prices: observed</Ev><Ev e="simulated">costs: simulated</Ev></div>
      </header>

      <div className="grid prices-grid" style={{ gap: 16 }}>
        <div className="panel" style={{ padding: '12px 8px 8px' }}>
          <div className="flex items-baseline justify-between flex-wrap gap-2" style={{ padding: '0 8px' }}>
            <h2 className="t-15" style={{ margin: 0 }}>Cost change vs keeping every job in Utah (U)</h2>
            <span className="t-11 ink-3">right: costs more · left: saves · whisker: 95% block-bootstrap interval, 4-week blocks</span>
          </div>
          <DeltaChart o={o} />
        </div>
        <PriceCard o={o} />
      </div>

      <div className="grid prices-grid prices-grid-2" style={{ gap: 16 }}>
        <div className="panel" style={{ padding: '12px 8px 8px' }}>
          <div className="flex items-baseline justify-between flex-wrap gap-2" style={{ padding: '0 8px' }}>
            <h2 className="t-15" style={{ margin: 0 }}>Real-time price by hour of day, $/MWh</h2>
            <span className="t-11 ink-3">mean over the priced hours · hours are America/Denver</span>
          </div>
          <ProfileChart o={o} />
        </div>
        <div className="panel">
          <h2 className="t-15" style={{ margin: '0 0 8px' }}>Where the difference comes from</h2>
          <SplitTable o={o} pol={pol} />
          <p className="t-11 ink-3" style={{ margin: '8px 0 0' }}>
            Location: energy placed at a site whose average price differs from Utah's. Extra energy: the 5% transfer overhead of a moved job, at Utah's average. Timing: when in the year the energy is drawn, against each site's average. The three add up to the change.
          </p>
        </div>
      </div>

      <p className="t-11 ink-3" style={{ margin: 0, maxWidth: '120ch' }} data-testid="prices-method">
        Prices: CAISO OASIS fifteen-minute real-time LMPs, hourly means, at {SITES.map((s) => `${REGION[s].name} ${o.prices.nodes.map[s]}`).join(', ')} (node choice assumed).
        Real-time marks everywhere, because Utah had no day-ahead price before EDAM. Coverage: {fmt(v(cov.priced_hours) ?? 0)} of {fmt(v(cov.window_hours) ?? 0)} hours priced at every site
        ({pct(v(cov.priced_share) ?? 0, 1)}%); an hour missing any site's price would be left out for every policy.
        Cost per attributed tonne uses attributed (average-intensity) CO₂, not marginal emissions. Pricing California at SCE's load point instead changes W's difference to {usdSigned(v(o.sensitivity?.ciso_node?.delta_vs_U_usd?.W) ?? 0)}.
        Validation year only; registered run {o.registered_run_id}.
      </p>
    </div>
  );
}

/** Δ$ vs U per policy, bars from zero with the b = 4 interval. Moving policies wear the route blue (the router's action). */
function DeltaChart({ o }: { o: Json }) {
  const { pol, d, ci, f } = priceFacts(o);
  const narrow = useViewport().w < 700; // phone: shorter names column, no % in the bar labels
  const option = useMemo(() => {
    const ys = [...pol].reverse();
    const rows = ys.map((p) => ({ p, d: d(p), lo: ci(p) ? -ci(p)![1] : null, hi: ci(p) ? -ci(p)![0] : null }));
    const raw = Math.max(...rows.flatMap((r) => [Math.abs(r.d), Math.abs(r.lo ?? 0), Math.abs(r.hi ?? 0)])) * (narrow ? 2.2 : 1.45);
    const step = raw > 20000 ? 10000 : raw > 4000 ? 2000 : 500;
    const ext = Math.ceil(raw / step) * step;
    return {
      grid: { left: narrow ? 112 : 190, right: 24, top: 8, bottom: 32 },
      xAxis: { type: 'value', min: -ext, max: ext, interval: step, axisLabel: { formatter: (x: number) => usdK(x) } },
      yAxis: { type: 'category', data: ys.map(name), axisLabel: { color: C.ink2, fontSize: narrow ? 11 : 12, width: narrow ? 104 : 180, overflow: 'break' }, splitLine: { show: false }, axisLine: { show: false } },
      tooltip: {
        trigger: 'item',
        formatter: (q: Json) => {
          const r = rows[q.dataIndex];
          const iv = r.lo == null ? '' : `<br/>95% interval ${usdSigned(r.lo)} to ${usdSigned(r.hi!)}`;
          return `<b>${name(r.p)}</b><br/>${usdSigned(r.d)} vs U (${signed(f(r.p) * 100, 2)}%)${iv}`;
        },
      },
      series: [
        {
          type: 'bar', barWidth: 14, data: rows.map((r) => ({
            value: r.d,
            itemStyle: { color: MOVES.has(r.p) ? C.route : C.ink2, borderRadius: r.d >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4] },
          })),
          markLine: { symbol: 'none', silent: true, lineStyle: { color: C.ink3, width: 1 }, label: { show: false }, data: [{ xAxis: 0 }] },
        },
        {
          // the interval whisker, and the value label just past whichever reaches further (bar or whisker)
          type: 'custom', silent: true, z: 5,
          data: rows.map((r, i) => [r.lo ?? r.d, r.hi ?? r.d, i, r.d]),
          renderItem: (_: Json, api: Json) => {
            const i = api.value(2), r = rows[i];
            const a = api.coord([api.value(0), i]), b = api.coord([api.value(1), i]), z = api.coord([r.d, i]);
            const st = { stroke: C.ink, lineWidth: 1.25 };
            const neg = r.d < 0;
            const x = neg ? Math.min(a[0], z[0]) - 8 : Math.max(b[0], z[0]) + 8;
            const kids: Json[] = [{ type: 'text', x, y: z[1], style: {
              text: narrow ? usdSigned(r.d) : `${usdSigned(r.d)}  ${signed(f(r.p) * 100, 1)}%`, fill: C.ink, font: '500 12px Funnel Sans', align: neg ? 'right' : 'left', verticalAlign: 'middle' } }];
            if (r.lo != null) kids.push(
              { type: 'line', shape: { x1: a[0], y1: a[1], x2: b[0], y2: b[1] }, style: st },
              { type: 'line', shape: { x1: a[0], y1: a[1] - 5, x2: a[0], y2: a[1] + 5 }, style: st },
              { type: 'line', shape: { x1: b[0], y1: b[1] - 5, x2: b[0], y2: b[1] + 5 }, style: st });
            return { type: 'group', children: kids };
          },
        },
      ],
    };
  }, [o, narrow]); // eslint-disable-line react-hooks/exhaustive-deps
  const desc = pol.map((p) => `${name(p)} ${usdSigned(d(p))}`).join('; ');
  return (
    <>
      <EChart option={option} className="prices-delta" testId="prices-delta" label={`Wholesale-scenario cost change vs U over the validation year: ${desc}`} />
      <table className="sr-only" data-testid="prices-delta-table">
        <caption>Cost change vs U, wholesale scenario</caption>
        <thead><tr><th>Policy</th><th>Change, $</th><th>Change, %</th><th>95% interval, $</th></tr></thead>
        <tbody>{pol.map((p) => { const c = ci(p); return (
          <tr key={p}><td>{name(p)}</td><td>{usdSigned(d(p))}</td><td>{signed(f(p) * 100, 2)}%</td><td>{c ? `${usdSigned(-c[1])} to ${usdSigned(-c[0])}` : 'none'}</td></tr>); })}</tbody>
      </table>
    </>
  );
}

const DASH: Record<Core, number[] | 'solid'> = { PACE: 'solid', BPAT: [6, 3], CISO: [2, 3], NEVP: [8, 3, 2, 3] };
/** Mean real-time price by Denver hour, one line per site: Utah solid and dark, the destinations lighter with distinct dashes, named in a legend with each site's average. */
function ProfileChart({ o }: { o: Json }) {
  const prof = o.prices.by_local_hour_usd_mwh;
  const option = useMemo(() => ({
    grid: { left: 44, right: 24, top: 16, bottom: 28 },
    xAxis: { type: 'category', data: Array.from({ length: 24 }, (_, h) => fmtHour(h)), boundaryGap: false, axisLabel: { interval: 5 } },
    yAxis: { type: 'value', axisLabel: { formatter: (x: number) => `$${x}` } },
    tooltip: { trigger: 'axis', valueFormatter: (x: number) => `$${fmt(x, 2)}/MWh` },
    series: SITES.map((s) => ({
      name: REGION[s].name, type: 'line', symbol: 'none', data: prof[s].value,
      lineStyle: { color: s === 'PACE' ? C.ink : C.ink3, width: s === 'PACE' ? 2.25 : 1.5, type: DASH[s] },
      itemStyle: { color: s === 'PACE' ? C.ink : C.ink3 },
      emphasis: { focus: 'series' },
    })),
  }), [o]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      <ul className="flex flex-wrap t-12 ink-2" style={{ gap: '4px 16px', listStyle: 'none', margin: '6px 0 0', padding: '0 8px' }} data-testid="prices-profile-legend">
        {SITES.map((s) => (
          <li key={s} className="flex items-center gap-2">
            <svg width="28" height="8" aria-hidden="true"><line x1="0" y1="4" x2="28" y2="4" stroke={s === 'PACE' ? C.ink : C.ink3} strokeWidth={s === 'PACE' ? 2.25 : 1.5}
              strokeDasharray={DASH[s] === 'solid' ? undefined : (DASH[s] as number[]).join(' ')} /></svg>
            <span className={s === 'PACE' ? 'fw-600' : undefined} style={{ color: s === 'PACE' ? C.ink : undefined }}>{REGION[s].name}</span>
            <span className="num">avg ${fmt(v(o.prices.mean_usd_mwh[s]) ?? 0, 2)}</span>
          </li>
        ))}
      </ul>
      <EChart option={option} className="prices-profile" testId="prices-profile" label={`Mean real-time wholesale price by hour of day for ${SITES.map((s) => `${REGION[s].name} (average $${fmt(v(o.prices.mean_usd_mwh[s]) ?? 0, 2)}/MWh)`).join(', ')}`} />
      <table className="sr-only">
        <caption>Mean real-time price by hour, $/MWh, America/Denver</caption>
        <thead><tr><th>Hour</th>{SITES.map((s) => <th key={s}>{REGION[s].name}</th>)}</tr></thead>
        <tbody>{Array.from({ length: 24 }, (_, h) => (
          <tr key={h}><td>{fmtHour(h)}</td>{SITES.map((s) => <td key={s}>{fmt(prof[s].value[h], 2)}</td>)}</tr>))}</tbody>
      </table>
    </>
  );
}

function SplitTable({ o, pol }: { o: Json; pol: string[] }) {
  const P = o.policies;
  const cell = (p: string, k: string) => usdSigned(v(P[p].decomposition_vs_U_usd[k]) ?? 0);
  return (
    <div style={{ overflowX: "auto" }}><table className="tbl" data-testid="prices-split">
      <thead><tr><th>Policy</th><th>Location</th><th>Extra energy</th><th>Timing</th><th>Total</th><th style={{ paddingRight: 0 }}>Per attributed<br />tonne CO₂</th></tr></thead>
      <tbody>
        {pol.map((p) => {
          const t = v(P[p].cost_per_attributed_tonne_usd_t);
          return (
            <tr key={p}>
              <td title={name(p)}>{SHORT[p] ?? name(p)}</td>
              <td>{cell(p, 'location_usd')}</td><td>{cell(p, 'extra_energy_usd')}</td><td>{cell(p, 'timing_usd')}</td>
              <td className="fw-600">{usdSigned(v(P[p].delta_vs_U_usd) ?? 0)}</td>
              <td style={{ paddingRight: 0 }} title={t == null ? P[p].cost_per_attributed_tonne_usd_t.reason : t < 0 ? 'negative: cheaper and lower-carbon' : 'positive: pays this much per tonne of attributed CO₂ cut'}>
                {t == null ? '–' : `${usdSigned(t)}/t`}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table></div>
  );
}

/** A compact card for any view: the year's wholesale-scenario difference for moving (W) and waiting (W_time). */
export function PriceCard({ o }: { o: Json }) {
  const { d, f, perT, ci, u, P } = priceFacts(o);
  const w = d('W'), ciW = ci('W');
  return (
    <aside className="panel flex flex-col" style={{ gap: 10 }} data-testid="prices-card" aria-label="Price lens summary">
      <div className="flex items-baseline justify-between gap-2"><h2 className="t-15" style={{ margin: 0 }}>Moving, in dollars</h2><Ev e="simulated" /></div>
      <div>
        <div className="t-hero num" data-testid="prices-card-hero">{usdSigned(w)}<span className="unit">a year vs U</span></div>
        <div className="t-12 ink-2">{w > 0 ? 'W costs more than keeping every job in Utah' : 'W costs less than keeping every job in Utah'} ({signed(f('W') * 100, 1)}% of U's {usd(u)}).
          {ciW ? ` 95% interval ${usdSigned(-ciW[1])} to ${usdSigned(-ciW[0])}.` : ''}</div>
      </div>
      <dl className="t-12" style={{ margin: 0, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px' }}>
        {P.W_time && (<><dt className="ink-3">Wait only</dt><dd style={{ margin: 0 }} className="num">{usdSigned(d('W_time'))} ({signed(f('W_time') * 100, 1)}%)</dd></>)}
        {P[MOB] && (<><dt className="ink-3">Only ≤ 8-GPU jobs move</dt><dd style={{ margin: 0 }} className="num">{usdSigned(d(MOB))} ({signed(f(MOB) * 100, 1)}%)</dd></>)}
        {perT('W') != null && (<><dt className="ink-3">W per attributed tonne</dt><dd style={{ margin: 0 }} className="num">{usdSigned(perT('W')!)}/t CO₂</dd></>)}
      </dl>
      <Caveat compact />
    </aside>
  );
}

function PricesSkeleton() {
  return (
    <div className="flex flex-col" style={{ gap: 16, padding: '0 8px' }} aria-busy="true" aria-label="Loading the price lens">
      <span className="skel" style={{ width: '60%', height: 24 }} />
      <span className="skel" style={{ width: '100%', height: 280, borderRadius: 16 }} />
    </div>
  );
}

function PricesError({ msg }: { msg: string }) {
  return (
    <div className="panel" style={{ maxWidth: 520, margin: '40px auto' }}>
      <h1 className="t-15" style={{ margin: 0 }}>The price lens did not load</h1>
      <p className="t-13 ink-2" style={{ margin: '8px 0 0' }}>{msg}. It reads <code>data/results/prices.json</code>. Run <code>make prices RUN_DIR=…</code>, then <code>npm run data</code> and rebuild.</p>
    </div>
  );
}
