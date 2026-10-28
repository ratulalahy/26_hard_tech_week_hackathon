// The grid outlook (Stage 3 T19): the next seven Utah days of consumed CO2 intensity for Utah and its
// three move destinations, forecast with p10–p90 bands, and what the deployed router (policy S) would
// recommend each day. A standalone, full-width page: it loads data/results/outlook.json itself and needs
// nothing from the rest of the app, so a top-level nav can mount <Outlook /> on its own route.
// Every number keeps its evidence envelope. A validation-dated demo is labelled as such on the page.
import { useEffect, useMemo, useState } from 'react';
import { EChart } from '../components/EChart';
import { Ev, Num } from '../components/ui';
import { C, ci2c } from '../lib/color';
import { REGION, type Core, type Env, type Json } from '../lib/data';
import { fmt, fmtDate, pct } from '../lib/format';

const SITES: Core[] = ['PACE', 'BPAT', 'CISO', 'NEVP'];
const DEN = 'America/Denver';
const base = import.meta.env?.BASE_URL ?? './';

export async function loadOutlook(): Promise<Json> {
  const r = await fetch(`${base}data/results/outlook.json`);
  if (!r.ok) throw new Error(`outlook.json: HTTP ${r.status}`);
  const o = await r.json();
  if (o.kind !== 'outlook') throw new Error('outlook.json is not an outlook artifact');
  return o;
}

export function useOutlook() {
  const [s, setS] = useState<{ o: Json | null; err: string | null }>({ o: null, err: null });
  useEffect(() => {
    let live = true;
    loadOutlook().then((o) => live && setS({ o, err: null })).catch((e) => live && setS({ o: null, err: String(e) }));
    return () => { live = false; };
  }, []);
  return s;
}

const hourOf = (iso: string) => Number(new Intl.DateTimeFormat('en-US', { timeZone: DEN, hour: 'numeric', hourCycle: 'h23' }).format(new Date(iso)));
const timeLabel = (iso: string) => new Intl.DateTimeFormat('en-US', { timeZone: DEN, hour: 'numeric' }).format(new Date(iso));
const dayLabel = (d: string, o: Intl.DateTimeFormatOptions = { weekday: 'short', month: 'short', day: 'numeric' }) =>
  new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', ...o }).format(new Date(`${d}T12:00:00Z`));
const v = (e: Env | undefined) => (e && e.status === 'ok' ? (e.value as number) : null);

/** The page. */
export function Outlook() {
  const { o, err } = useOutlook();
  return (
    <section aria-label="Grid outlook" data-testid="outlook" tabIndex={0} className="fixed z-10 overflow-y-auto" style={{ top: 72, left: 16, right: 16, bottom: 32 }}>
      {err ? <OutlookError msg={err} /> : !o ? <OutlookSkeleton /> : <OutlookBody o={o} />}
    </section>
  );
}

function OutlookBody({ o }: { o: Json }) {
  const days: Json[] = o.days;
  const pick: Core = o.router.s_ranking[0];
  const agree = days.every((d) => d.s_agrees_with_forecast);
  const sk = skillSummary(o);
  // the most common start of Utah's cleanest 4 hours across the days shown (ties: the earlier hour)
  const starts = days.map((d) => d.home_cleanest_block.start_utc as string);
  const count = (iso: string) => starts.filter((x) => hourOf(x) === hourOf(iso)).length;
  const mode = [...starts].sort((a, b) => count(b) - count(a) || hourOf(a) - hourOf(b))[0];
  const span = `${timeLabel(mode)}–${timeLabel(new Date(Date.parse(mode) + 4 * 3600e3).toISOString())}`;
  // merge-time fix (T19 re-review): hours read off the seasonal average are "typical", not forecast
  const typical = days.some((d) => hourOf(d.home_cleanest_block.start_utc) === hourOf(mode) && d.regions.PACE.status !== 'forecast');
  const issued = fmtDate(o.issue_utc, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' });
  const first = days[0].date_local, last = days[days.length - 1].date_local;
  return (
    <div className="flex flex-col" style={{ gap: 16, padding: '0 8px 16px' }}>
      {o.demo && (
        <div role="note" data-testid="outlook-demo" className="panel flex items-center gap-3" style={{ padding: '8px 12px', boxShadow: 'inset 0 0 0 1.5px var(--rush), var(--e-1)' }}>
          <span className="chip-neutral" style={{ fontWeight: 600, color: 'var(--ink)' }}>DEMO · validation date</span>
          <span className="t-12 ink-2">Issued as if it were {issued}, a past validation date, not today. The live run replaces this page after the sealed test year is opened.</span>
        </div>
      )}
      <header className="flex items-end justify-between gap-6 flex-wrap">
        <div>
          <h1 className="t-20" style={{ margin: 0 }} data-testid="outlook-title">
            {agree ? `Next ${days.length} days: ${REGION[pick].name} stays the cleanest place to run; in Utah, the ${typical ? 'typical ' : ''}cleanest hours are ${span}${count(mode) * 2 >= days.length ? ' on most days' : ''}`
              : `Next ${days.length} days: the forecast and the router's fixed ranking disagree on some days`}
          </h1>
          <p className="t-13 fw-500" style={{ margin: '6px 0 0', maxWidth: '100ch' }} data-testid="outlook-skill-line">{sk.line}</p>
          <p className="t-13 ink-2" style={{ margin: '4px 0 0', maxWidth: '100ch' }}>
            Consumed CO₂ intensity for {dayLabel(first)} to {dayLabel(last)}, issued {issued}. The deployed router (policy S) sends a movable job to the first region in a fixed ranking learned from training years; it does not read this forecast. The forecast adds the time-shift view: which hours of each day are cleanest.
          </p>
        </div>
        <div className="flex gap-3 items-center"><Ev e="forecast">forecast · p10–p90 band</Ev><Ev e="measured">skill: validation year</Ev></div>
      </header>

      <DayStrip o={o} />
      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 2.2fr) minmax(320px, 1fr)', gap: 16 }}>
        <div className="panel" style={{ padding: '12px 8px 8px' }}>
          <div className="flex items-baseline justify-between" style={{ padding: '0 8px' }}>
            <span className="t-15 whitespace-nowrap">Hourly CO₂ by region, g/kWh</span>
            <span className="t-11 ink-3">Hours are America/Denver · line: median · band: p10–p90 from validation errors · shaded days: seasonal average only · Utah has its own y scale; the destinations share one</span>
          </div>
          {SITES.map((ba) => <RegionChart key={ba} o={o} ba={ba} big={ba === 'PACE'} />)}
        </div>
        <SkillTable o={o} />
      </div>
      <p className="t-11 ink-3" style={{ margin: 0, maxWidth: '120ch' }}>
        {o.limitations.join(' ')} Data: U.S. EIA Form EIA-930 hourly CO₂ estimates (consumption basis), published about {fmt(v(o.envelope_h) ?? 96)} h after the hour (assumed). Run {o.run_id}.
      </p>
    </div>
  );
}

/** One card per day: the router's pick, Utah's cleanest 4 hours, and whether the day has skill. */
function DayStrip({ o }: { o: Json }) {
  return (
    <ol className="grid" data-testid="outlook-days" aria-label="Router recommendation by day" style={{ gridTemplateColumns: `repeat(${o.days.length}, minmax(0, 1fr))`, gap: 8, listStyle: 'none', margin: 0, padding: 0 }}>
      {o.days.map((d: Json) => {
        const b = d.home_cleanest_block, clim = d.regions.PACE.status !== 'forecast';
        const mean = v(b.mean);
        return (
          <li key={d.day} className="panel flex flex-col" style={{ padding: 12, gap: 6, ...(clim ? hatch : {}) }} data-status={d.status}>
            <div className="flex items-baseline justify-between">
              <span className="t-13 fw-600">{dayLabel(d.date_local)}</span>
              <span className="t-11 ink-3">{d.day}</span>
            </div>
            <div className="t-12"><span className="ink-3">Router S → </span><span className="fw-600" style={{ color: C.route }}>{REGION[d.router_s_pick as Core].name}</span></div>
            <div className="flex items-center gap-2">
              <span aria-hidden="true" style={{ width: 14, height: 14, borderRadius: 4, flex: 'none', background: ci2c(mean), boxShadow: 'inset 0 0 0 1px rgba(110,62,30,.18)' }} />
              <span className="t-13 fw-600 whitespace-nowrap">{timeLabel(b.start_utc)}–{timeLabel(new Date(Date.parse(b.start_utc) + 4 * 3600e3).toISOString())}</span>
            </div>
            <div className="t-11 ink-3">Utah's cleanest 4 h · <Num v={mean} unit="g/kWh" /></div>
            {clim ? <Ev e="modeled">seasonal average</Ev> : <><span className="t-11 ink-3">{cardStatus(d.regions.PACE)}</span><Ev e="forecast" /></>}
          </li>
        );
      })}
    </ol>
  );
}

/** The skill sentence, from the data: which regions' forecasts clear the 90% block-bootstrap rule. */
function skillSummary(o: Json) {
  const ds = ['1', '2', '3', '4', '5', '6', '7'];
  const pass = (ba: Core) => ds.filter((d) => o.skill_by_horizon[ba][d].status === 'forecast');
  const utah = pass('PACE');
  const dest = (['BPAT', 'CISO', 'NEVP'] as Core[]);
  const dSk = dest.flatMap((b) => pass(b).map((d) => v(o.skill_by_horizon[b][d].skill) ?? 0));
  const allDest = dest.every((b) => pass(b).length === ds.length);
  const destTxt = dSk.length
    ? `the destinations' forecasts are ${pct(Math.min(...dSk), 0)}–${pct(Math.max(...dSk), 0)}% better${allDest ? ' on every day through D+7' : ' on the days marked'}`
    : "neither are the destinations'";
  if (!utah.length) {
    return { utahNone: true, line: `Utah's forecast is not reliably better than its seasonal average (on every day the 90% interval includes zero), so Utah's days show the seasonal average; ${destTxt}.` };
  }
  const uSk = utah.map((d) => v(o.skill_by_horizon.PACE[d].skill) ?? 0);
  return { utahNone: false, line: `Utah's forecast beats its seasonal average by ${pct(Math.min(...uSk), 0)}–${pct(Math.max(...uSk), 0)}% on D+${utah.join(', D+')}; its other days show the average. ${destTxt[0].toUpperCase()}${destTxt.slice(1)}.` };
}

/** A day card's Utah status, only for a cell that passes the skill rule. A cell that fails it shows
 *  "seasonal average" alone; its point estimate lives in the skill table (merge-time fix, T19 re-review). */
function cardStatus(r: Json) {
  return `forecast · ${pct(v(r.skill_vs_climatology) ?? 0, 0)}% better than avg`;
}

const hatch = { backgroundImage: 'repeating-linear-gradient(135deg, rgba(74,58,48,.07) 0 2px, transparent 2px 7px)' } as const;

/** Small multiples on one shared y scale: no categorical colour is needed, the panel names the region. */
function RegionChart({ o, ba, big }: { o: Json; ba: Core; big: boolean }) {
  const r = o.regions[ba];
  const option = useMemo(() => {
    const hours: string[] = o.hours_utc;
    const p10: number[] = r.p10.value, p50: number[] = r.p50.value, p90: number[] = r.p90.value;
    // two y scales (m10): Utah on its own, the three destinations on one shared scale
    const group = ba === 'PACE' ? ['PACE'] : SITES.filter((x) => x !== 'PACE');
    const top = Math.max(...group.flatMap((x) => o.regions[x].p90.value as number[]));
    const step = top > 600 ? 300 : top > 300 ? 150 : 100;
    const ymax = Math.ceil(top / step) * step;
    const dayIdx = hours.map((h) => o.days.findIndex((d: Json) => h >= d.first_hour_utc && (o.days[o.days.indexOf(d) + 1] ? h < o.days[o.days.indexOf(d) + 1].first_hour_utc : true)));
    const climAreas = o.days.map((d: Json, k: number) => ({ d, k })).filter(({ d }: Json) => d.regions[ba].status !== 'forecast')
      .map(({ k }: Json) => [{ xAxis: dayIdx.indexOf(k) }, { xAxis: Math.min(dayIdx.lastIndexOf(k) + 1, hours.length - 1) }]);
    const midnights = hours.map((h, i) => (hourOf(h) === 0 ? i : -1)).filter((i) => i > 0);
    return {
      grid: { left: 152, right: 16, top: 10, bottom: big ? 24 : 8 },
      xAxis: { type: 'category', data: hours.map((_, i) => i), boundaryGap: false, axisLabel: { show: big, interval: (i: number) => hourOf(hours[i]) === 12, formatter: (i: string) => fmtDate(hours[Number(i)], { weekday: 'short', day: 'numeric' }) + ' noon' }, axisLine: { show: big }, splitLine: { show: false } },
      yAxis: { type: 'value', min: 0, max: ymax, interval: big ? step : ymax / 2, axisLabel: { formatter: (x: number) => fmt(x) } },
      tooltip: {
        trigger: 'axis',
        formatter: (ps: { dataIndex: number }[]) => {
          const i = ps[0].dataIndex;
          const st = o.days[dayIdx[i]]?.regions[ba].status;
          return `${fmtDate(hours[i], { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric' })} MT<br/><b>${REGION[ba].name}</b> ${fmt(p50[i])} g/kWh<br/>p10–p90 ${fmt(p10[i])}–${fmt(p90[i])}<br/><span style="color:${C.ink3}">${st === 'forecast' ? 'forecast' : 'seasonal average only'}</span>`;
        },
      },
      series: [
        { name: 'p10', type: 'line', data: p10, stack: 'band', lineStyle: { width: 0 }, symbol: 'none', silent: true, tooltip: { show: false } },
        { name: 'band', type: 'line', data: p90.map((x, i) => x - p10[i]), stack: 'band', lineStyle: { width: 0 }, symbol: 'none', areaStyle: { color: 'rgba(45,29,20,.12)' }, silent: true,
          markArea: { silent: true, itemStyle: { color: 'rgba(234,223,211,.55)' }, data: climAreas } },
        { name: REGION[ba].name, type: 'line', data: p50, lineStyle: { color: C.ink, width: 1.75 }, symbol: 'none', z: 3,
          markLine: { silent: true, symbol: 'none', label: { show: false }, lineStyle: { color: C.hair, type: 'solid', width: 1 }, data: midnights.map((i) => ({ xAxis: i })) } },
      ],
    };
  }, [o, r, ba, big]);
  return (
    <div className="relative" style={{ borderTop: big ? 0 : '1px solid var(--hair-2)' }}>
      <div className="absolute t-12" style={{ left: 8, top: 8, width: 104, lineHeight: 1.25 }}>
        <div className="fw-600">{REGION[ba].name}</div>
        <div className="ink-3 t-11">{ba}</div>
      </div>
      <EChart option={option} testId={`outlook-chart-${ba}`} label={`${REGION[ba].name}: hourly consumed CO2 intensity forecast with p10 to p90 band, g per kWh`} className="w-full" />
      <style>{`[data-testid="outlook-chart-${ba}"]{height:${big ? 168 : 104}px}`}</style>
    </div>
  );
}

/** Skill by horizon: 1 − MAE / MAE(seasonal average), measured on the validation year, per region and day. */
function SkillTable({ o }: { o: Json }) {
  const ds = ['1', '2', '3', '4', '5', '6', '7'];
  return (
    <div className="panel" data-testid="outlook-skill">
      <div className="t-15">How far ahead it is worth forecasting</div>
      <p className="t-12 ink-2" style={{ margin: '4px 0 12px' }}>
        Skill over the seasonal average, 1 − MAE ÷ MAE(average), on {fmt(v(o.skill_by_horizon.PACE['1'].n_issues) ?? 0)} validation-year issues. A cell is a forecast only where its 90% interval, from a block bootstrap over runs of 7 consecutive days (forecast errors are correlated day to day), stays above zero. Otherwise the outlook shows the average, and the cell shows the best model's point estimate in grey: not distinguishable from the average.
      </p>
      <table className="tbl">
        <caption className="sr-only">Forecast skill over the seasonal average by region and days ahead, validation year</caption>
        <thead><tr><th scope="col">Region</th>{ds.map((d) => <th key={d} scope="col">D+{d}</th>)}</tr></thead>
        <tbody>
          {SITES.map((ba) => (
            <tr key={ba} className={ba === 'PACE' ? 'em' : ''}>
              <th scope="row" className="t-12" style={{ textAlign: 'left', padding: '6px 0', fontWeight: ba === 'PACE' ? 600 : 500, color: 'var(--ink)', fontSize: 12 }}>{REGION[ba].name}</th>
              {ds.map((d) => {
                const c = o.skill_by_horizon[ba][d];
                const s = v(c.skill) ?? 0, ci = c.skill_ci90.value as number[], ci14 = c.skill_ci90_b14.value as number[];
                const ok = c.status === 'forecast';
                return (
                  <td key={d} title={`${REGION[ba].name} D+${d}: skill ${pct(s, 1)}%; 90% interval ${pct(ci[0], 1)} to ${pct(ci[1], 1)}% (7-day blocks), ${pct(ci14[0], 1)} to ${pct(ci14[1], 1)}% (14-day blocks); best model ${c.best_model}${ok ? '' : '; not distinguishable from the seasonal average'}`}
                    style={ok ? undefined : { ...hatch, color: C.ink3 }}>
                    {ok ? `${pct(s, 0)}%` : <><span aria-hidden="true">({pct(s, 0)}%)</span><span className="sr-only">{pct(s, 0)}%, not distinguishable from the average</span></>}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <hr className="rule" style={{ margin: '16px 0 12px' }} />
      <div className="t-15">The router's fixed ranking</div>
      <p className="t-12 ink-2" style={{ margin: '4px 0 8px' }}>Policy S tries regions in this order every day, cleanest training-year average first: the forecast does not change it.</p>
      <ol data-testid="outlook-ranking" style={{ margin: 0, padding: 0, listStyle: 'none' }} className="flex flex-col gap-1">
        {o.router.s_ranking.map((ba: Core, i: number) => {
          const m = v(o.router.s_ranking_mean_ci[ba]);
          return (
            <li key={ba} className="flex items-center gap-2 t-12">
              <span className="ink-3" style={{ width: 14 }}>{i + 1}</span>
              <span aria-hidden="true" style={{ width: 14, height: 14, borderRadius: 4, background: ci2c(m), boxShadow: 'inset 0 0 0 1px rgba(110,62,30,.18)' }} />
              <span className={i === 0 ? 'fw-600' : ''} style={{ color: i === 0 ? C.route : undefined }}>{REGION[ba].name}</span>
              <span className="ml-auto"><Num v={m} unit="g/kWh" /></span>
            </li>
          );
        })}
      </ol>
      <div className="t-11 ink-3" style={{ marginTop: 6 }}>{o.router.note}. <Ev e="modeled" /></div>
      <p className="t-11 ink-3" style={{ margin: '12px 0 0' }}>
        Grey, in brackets: not distinguishable from the seasonal average, which the outlook uses. The best model per cell is chosen on the same validation issues it is scored on (development evidence). Out-of-fold coverage of the p10–p90 band: {pct(Math.min(...SITES.flatMap((b) => ds.map((d) => v(o.skill_by_horizon[b][d].band_coverage_out_of_fold) ?? 1))), 0)}–{pct(Math.max(...SITES.flatMap((b) => ds.map((d) => v(o.skill_by_horizon[b][d].band_coverage_out_of_fold) ?? 0))), 0)}% (target 80%). <Ev e="measured" />
      </p>
    </div>
  );
}

function OutlookSkeleton() {
  return (
    <div className="flex flex-col" style={{ gap: 16, padding: '0 8px' }} aria-busy="true" aria-label="Loading the outlook">
      <span className="skel" style={{ width: '60%', height: 24 }} />
      <div className="grid" style={{ gridTemplateColumns: 'repeat(7, 1fr)', gap: 8 }}>{Array.from({ length: 7 }, (_, i) => <span key={i} className="skel" style={{ height: 120, borderRadius: 16 }} />)}</div>
      <span className="skel" style={{ height: 480, borderRadius: 16 }} />
    </div>
  );
}

function OutlookError({ msg }: { msg: string }) {
  return (
    <div className="panel" style={{ maxWidth: 520, margin: '48px auto' }} role="alert">
      <div className="t-15">The outlook did not load</div>
      <p className="t-13 ink-2" style={{ margin: '8px 0 0' }}>{msg}. The page reads <code>data/results/outlook.json</code>; run <code>make outlook</code>, then <code>make web</code>. No forecast is shown until it loads.</p>
    </div>
  );
}
