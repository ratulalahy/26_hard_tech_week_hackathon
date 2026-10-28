// The Monitor page's model (T21): a replay of policy S on the sealed test year, built only from fields the
// committed outputs already hold (results/test/job-replay.json, metrics.json, forecast-replay.json and the
// test manifest's frozen ranking and assumptions). Nothing is generated: every feed line is a template whose
// slots are filled from those fields, and anything the files do not carry is left out (see `missing`).
import { CORE, REGION, asNum, contrast, get, type Core, type Json } from './data';
import { fmt, fmtDate } from './format';

export interface MonitorFiles { job: Json; metrics: Json; forecast: Json; manifest: Json }

/** The four committed test-year files the Monitor reads; refuses anything that is not the test window. */
export async function loadMonitorFiles(): Promise<MonitorFiles> {
  const [job, metrics, forecast, manifest] = await Promise.all(['job-replay.json', 'metrics.json', 'forecast-replay.json', 'manifest.json'].map((f) => get(f, 'test')));
  for (const [n, x] of [['job-replay', job], ['metrics', metrics], ['forecast-replay', forecast], ['manifest', manifest]] as const) {
    if (x.window !== 'test') throw new Error(`results/test/${n}.json is not a test-window artifact`);
  }
  if (job.run_id !== metrics.run_id || job.run_id !== manifest.run_id) throw new Error('results/test/ files come from different runs');
  return { job, metrics, forecast, manifest };
}

export interface SiteSeries {
  site: Core;
  slots: number;
  /** S's mean busy GPUs per hour of the replay week (includes warm-up occupancy) */
  s: number[];
  /** U's (stay in Utah), for the retrospective comparison */
  u: number[];
}

export interface FeedEntry {
  /** index of the replay hour the entry belongs to (a ramp's first hour) */
  h: number;
  /** a ramp's last hour (same as h for a one-hour change) */
  h1: number;
  kind: 'rise' | 'fall' | 'week';
  site?: Core;
  text: string;
}

export interface TracedJob {
  id: string;
  type: string;
  gpus: number;
  gpuH: number;
  arrival: string;
  site: string;
  start: string;
  end: string;
  deadline: string;
  waitS: number;
  met: boolean;
  stayKg: number | null;
  sKg: number | null;
  text: string;
  outcome: string;
}

export interface MonitorModel {
  runId: string;
  hours: string[];
  start: string;
  end: string;
  sites: SiteSeries[];
  /** PACE's realized consumption-basis intensity per replay hour (EIA estimate; S never reads it) */
  ciPace: (number | null)[];
  /** Utah-site CO₂ rate, kg/h, under S and U: busy GPUs × kW per GPU × PUE × PACE intensity */
  rateS: (number | null)[];
  rateU: (number | null)[];
  kwPerGpu: number;
  pue: number;
  transferMin: number;
  ranking: { site: string; ci: number }[];
  rankingWindow: [string, string] | null;
  rankingText: string;
  arcs: { to: string; jobs: number; gpuH: number }[];
  week: { nJobs: number | null; uKg: number | null; sKg: number | null };
  lateS: number | null;
  feed: FeedEntry[];
  traced: TracedJob[];
  /** the whole test year's S saving vs U (b = 4) and the top 1% of jobs' share of energy, from metrics.json */
  yearSaving: number | null;
  top1: { nJobs: number; share: number } | null;
}

const num = (e: Json): number | null => asNum(e);
const DEN = 'America/Denver';
export const hourLabel = (iso: string) => new Intl.DateTimeFormat('en-US', { timeZone: DEN, weekday: 'short', hour: 'numeric' }).format(new Date(iso));
export const stampLabel = (iso: string) => new Intl.DateTimeFormat('en-US', { timeZone: DEN, weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(new Date(iso)) + ' MT';
const dayStamp = (iso: string) => fmtDate(iso, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' MT';
const gpuTxt = (v: number) => fmt(Math.round(v));

/** "BPAT 96 < CISO 194 < NEVP 313 < PACE 573 g/kWh" from the frozen ranking. */
export function rankingSentence(r: { site: string; ci: number }[]) {
  return r.map((x) => `${x.site} ${fmt(x.ci)}`).join(' < ') + ' g/kWh';
}

/** The S rule, as a template on the frozen ranking. Never "forecast", never "lowest actual emissions". */
export const sRule = (rankingText: string) => `S rule: first feasible site in the frozen ranking (${rankingText})`;

/** A change smaller than this, in hour-mean busy GPUs per hour (one 8-GPU node), is not an entry. */
export const MIN_CHANGE_GPUS = 8;

/** Entries from S's hour-mean busy GPUs at each move destination. These are site load changes, not jobs:
 * consecutive hours that change the same way merge into one ramp, and hourly changes under
 * MIN_CHANGE_GPUS are left out. */
export function feedFrom(sites: SiteSeries[], hours: string[], nJobs: number | null): FeedEntry[] {
  const out: FeedEntry[] = [];
  out.push({ h: 0, h1: 0, kind: 'week', text: `Replay week opens · ${nJobs == null ? 'the cohort\'s' : fmt(nJobs)} jobs arrive this week · every job holds its Utah booking as a fallback` });
  for (const s of sites) {
    if (s.site === 'PACE') continue;
    let run: { dir: 1 | -1; h: number; h1: number; from: number; to: number } | null = null;
    const flush = () => {
      if (!run) return;
      const span = run.h1 > run.h ? ` over ${run.h1 - run.h + 1} h` : '';
      out.push({
        h: run.h, h1: run.h1, kind: run.dir > 0 ? 'rise' : 'fall', site: s.site,
        text: run.dir > 0 ? `${s.site} ${gpuTxt(run.from)} → ${gpuTxt(run.to)} GPUs${span} · moved work running` : `${s.site} ${gpuTxt(run.from)} → ${gpuTxt(run.to)} GPUs${span} · moved work finishing`,
      });
      run = null;
    };
    for (let h = 0; h < hours.length; h++) {
      const a = h ? s.s[h - 1] : 0, b = s.s[h], d = b - a;
      const dir = Math.abs(d) < MIN_CHANGE_GPUS ? 0 : d > 0 ? 1 : -1;
      if (dir === 0) { flush(); continue; }
      if (run && run.dir === dir && run.h1 === h - 1) { run.h1 = h; run.to = b; continue; }
      flush();
      run = { dir, h, h1: h, from: a, to: b };
    }
    flush();
  }
  return out.sort((p, q) => p.h - q.h || (p.kind === 'week' ? -1 : 0));
}

/** A job the test run traced (job-replay's illustrative jobs), as a feed line from its own fields. */
export function tracedJob(j: Json, transferMin: number): TracedJob | null {
  const pS = j?.placements?.S, pU = j?.placements?.U;
  if (!pS || !j.deadline) return null;
  const waitS = (Date.parse(pS.start) - Date.parse(j.arrival)) / 1000;
  const met = Date.parse(pS.end) <= Date.parse(j.deadline);
  const gpus = num(j.gpus) ?? 0, gpuH = num(j.declared_gpu_h) ?? 0;
  const moved = pS.site !== 'PACE';
  const where = moved ? `→ ${pS.site}` : 'stays at PACE';
  const parts = [
    `Job ${j.job_uid} (${j.job_type}, ${fmt(gpus)} GPUs, ${fmt(gpuH, gpuH < 10 ? 3 : 0)} GPU-h) ${where}`,
    moved ? 'first feasible site in the frozen ranking' : 'no feasible site ahead of PACE in the frozen ranking',
    moved ? `transfer ${fmt(transferMin)} min (starts ${fmt(waitS / 60)} min after arrival)` : `starts ${fmt(waitS / 60)} min after arrival`,
    met ? `deadline met (ends ${dayStamp(pS.end)}, deadline ${dayStamp(j.deadline)})` : `deadline missed (ends ${dayStamp(pS.end)}, deadline ${dayStamp(j.deadline)})`,
  ];
  const stayKg = num(pU?.co2_kg), sKg = num(pS.co2_kg);
  const kg = (v: number) => (v < 1 ? v.toFixed(4) : fmt(v));
  const outcome = stayKg != null && sKg != null ? `Retrospective, scored on realized truth: staying ${kg(stayKg)} kg CO₂ vs ${moved ? 'moved' : 'S'} ${kg(sKg)} kg CO₂` : '';
  return { id: j.job_uid, type: j.job_type, gpus, gpuH, arrival: j.arrival, site: pS.site, start: pS.start, end: pS.end, deadline: j.deadline, waitS, met, stayKg, sKg, text: parts.join(' · '), outcome };
}

export function buildMonitor({ job, metrics, forecast, manifest }: MonitorFiles): MonitorModel {
  const wk = job.week, hours: string[] = wk.hours;
  const a = manifest.assumptions;
  const kwPerGpu = num(a.kw_per_gpu) ?? 0, pue = num(a.pue) ?? 0, transferMin = (num(a.transfer_time_s) ?? 0) / 60;
  const slots = (s: Core) => (s === 'PACE' ? num(a.home_slots) : num(a.destination_slots?.[s])) ?? 0;
  const pol = (p: string) => wk.policies[p]?.mean_busy_gpus_by_hour ?? {};
  const series = (p: string, s: Core): number[] => (pol(p)[s]?.value as number[] | undefined) ?? hours.map(() => 0);
  const sites: SiteSeries[] = CORE.map((site) => ({ site, slots: slots(site), s: series('S', site), u: series('U', site) }));
  // PACE's intensity is aligned by timestamp, never by position alone
  const frIdx = new Map<string, number>((forecast.hours as string[]).map((t, i) => [t, i]));
  const truth: (number | null)[] = forecast.truth?.value ?? [];
  const ciPace = hours.map((t) => { const i = frIdx.get(t); return i == null ? null : truth[i] ?? null; });
  const pace = sites[0];
  const rate = (g: number[]) => ciPace.map((ci, i) => (ci == null ? null : (g[i] * kwPerGpu * pue * ci) / 1000));
  const r = manifest.s_ranking;
  const ranking = ((r?.order ?? []) as string[]).map((s) => ({ site: s, ci: num(r.mean_consumed_ci?.[s]) ?? NaN })).filter((x) => Number.isFinite(x.ci));
  const rankingText = rankingSentence(ranking);
  const arcs = ((wk.policies.S?.arcs ?? []) as Json[]).map((x) => ({ to: x.to, jobs: num(x.jobs) ?? 0, gpuH: num(x.gpu_h) ?? 0 }));
  // the replay week's row of metrics.weekly (weeks by arrival, Monday 00:00 America/Denver)
  const wl = metrics.weekly;
  const wi = wl ? (wl.week_start_local as string[]).findIndex((t) => Date.parse(t) === Date.parse(wk.start)) : -1;
  const at = (p: string): number | null => (wi < 0 ? null : (wl.co2_kg?.[p]?.value?.[wi] ?? null));
  const nJobs = wi < 0 ? (num(wk.policies.S?.n_arrivals) ?? null) : (wl.n_jobs?.value?.[wi] ?? null);
  const traced = [job.illustrative_job, job.illustrative_job_literal].map((j) => tracedJob(j, transferMin)).filter((x): x is TracedJob => !!x);
  return {
    runId: job.run_id, hours, start: wk.start, end: wk.end, sites, ciPace,
    rateS: rate(pace.s), rateU: rate(pace.u), kwPerGpu, pue, transferMin,
    ranking, rankingWindow: r?.window ?? null, rankingText, arcs,
    week: { nJobs, uKg: at('U'), sKg: at('S') },
    lateS: num(metrics.policies?.S?.metrics?.late_jobs),
    feed: feedFrom(sites, hours, nJobs),
    traced,
    yearSaving: num(contrast(metrics, 'S')?.saving),
    top1: (() => { const t = metrics.workload?.top_1pct_jobs_by_declared_gpu_h; const n = num(t?.n_jobs), sh = num(t?.energy_share); return n != null && sh != null ? { nJobs: n, share: sh } : null; })(),
  };
}

/** What the committed outputs do not carry, so the Monitor does not show it (stated on the page). */
export const MISSING = [
  'per-job decisions inside the replay week (the files give hourly GPU load per site and the week\'s move totals, not job ids or times)',
  'hourly carbon at BPAT, CISO and NEVP for the replay week (only PACE\'s is in forecast-replay.json), so the CO₂ rate is the Utah site\'s alone',
  'job counts per site per hour, and why a job that stayed could not move',
];

export const siteName = (s: string) => (REGION as Record<string, { name: string }>)[s]?.name ?? s;
