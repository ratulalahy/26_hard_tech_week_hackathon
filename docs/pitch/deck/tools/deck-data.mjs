#!/usr/bin/env node
// Builds docs/pitch/deck/data.js from the committed results JSON, so the deck never carries a number
// that is not in results/. Every slide number tagged data-n="<key>" must equal N[key] (checked by
// web/tests/deck.spec.ts); the chart series come from the same files.
//   node docs/pitch/deck/tools/deck-data.mjs           write data.js
//   node docs/pitch/deck/tools/deck-data.mjs --check   fail if data.js is stale
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '../../../..');
const out = resolve(here, '../data.js');
const J = (p) => JSON.parse(readFileSync(resolve(repo, p), 'utf8'));
const v = (f) => {
  if (f == null || typeof f !== 'object' || !('value' in f)) throw new Error(`not an evidence field: ${JSON.stringify(f)?.slice(0, 120)}`);
  return f.value;
};

const tm = J('results/test/metrics.json');
const vm = J('results/metrics.json');
const tx = J('results/test/extras.json');
const vx = J('results/extensions.json');
const tman = J('results/test/manifest.json');
const tg = J('results/test/grid-profile.json');
const tj = J('results/test/job-replay.json');
const ov = J('results/overview.json');
const pr = J('results/prices.json');
const vw = J('results/water.json');
const reads = readFileSync(resolve(repo, 'results/test_reads.jsonl'), 'utf8').trim().split('\n').map((l) => JSON.parse(l));

const contrast = (m, c, r = 'U') => {
  const x = m.contrasts.find((k) => k.candidate === c && k.reference === r);
  if (!x) throw new Error(`no contrast ${c}/${r}`);
  return x.blocks['4'];
};
const pct1 = (x) => (x * 100).toFixed(1);
const pct0 = (x) => (x * 100).toFixed(0);
const int = (x) => Math.round(x).toLocaleString('en-US');
const mw2 = (x) => x.toFixed(2);
const hour12 = (h) => `${h % 12 === 0 ? 12 : h % 12} ${h < 12 ? 'AM' : 'PM'}`;
const minus = (s) => s.replace(/^-/, '−');

// headline
const S = contrast(tm, 'S'), Sv = contrast(vm, 'S');
const pol = ['S', 'K', 'W', 'L', 'W_time', 'L_time'].map((p) => {
  const b = contrast(tm, p);
  return { p, saving: v(b.saving), ci: v(b.saving_ci95) };
});
const mob = tx.extensions.mobility_le_8gpus.vs_U;
const mobV = vx.sensitivities.mobility_le_8gpus.policies.S.vs_U['4'];
const exec = tm.policies.S.metrics.execution_kwh_by_site;
const nwShare = v(exec.BPAT) / (v(exec.BPAT) + v(exec.CISO) + v(exec.NEVP));
const days = Math.round((Date.parse(tman.split.F) - Date.parse(tman.split.eval_start)) / 86_400_000);

// Utah's July weekday (test year), and the rush band the dashboard draws (web/src/lib/derive.ts rushHours)
const pj = tg.pace_july_weekday;
const net = v(pj.net_load_mw), dem = v(pj.demand_mw);
const netPeakH = net.indexOf(Math.max(...net)), demPeakH = dem.indexOf(Math.max(...dem));
const counts = v(tg.pace_top100_net_load.counts_month_hour), k = v(tg.pace_top100_net_load.k);
const byHour = Array.from({ length: 24 }, (_, h) => counts.reduce((s, row) => s + row[h], 0));
const hot = byHour.map((n) => n >= 0.1 * k);
const rush = hot.indexOf(true) < 0 ? [19, 22] : [hot.indexOf(true), hot.lastIndexOf(true) + 1];
const regions = Object.values(ov.regions);
const dirtier = regions.filter((r) => r.alignment.rush_verdict === 'dirtier').length;

// one job
const job = tj.illustrative_job;
const act = (site) => job.available_actions.find((a) => a.site === site);
const coKg = (a) => v(a.co2_kg ?? { value: v(a.execution_co2_kg) + v(a.transfer_co2_kg) });

// storage (test year)
const sc = tx.storage.schedule_comparison.schedules;
const cu = (s) => sc[s].cases.U['4'];
const relief = tx.storage.peak_relief.S;

// drift (S vs U, b = 4), test beside validation, from the test run's own drift table
const driftRow = (metric) => {
  const r = tx.drift.rows.find((x) => x.metric === metric);
  if (!r) throw new Error(`no drift row ${metric}`);
  return [pct1(v(r.validation)), pct1(v(r.test))];
};
const scen = [
  ['Registered primary', 'S vs U saving (b = 4)'],
  ['Workload phase 49', 'phase_49: S vs U saving (b = 4)'],
  ['Workload phase 98', 'phase_98: S vs U saving (b = 4)'],
  ['Two-hour transfer', 'transfer_120min: S vs U saving (b = 4)'],
  ['24-hour batch delay', 'batch_delay_24h: S vs U saving (b = 4)'],
  ['No spare destination slots', 'dest_slots_0: S vs U saving (b = 4)'],
  ['Twice the spare capacity (1,024)', 'dest_slots_1024: S vs U saving (b = 4)'],
  ['Only jobs of ≤ 8 GPUs may move', 'mobility_le_8gpus: S vs U saving (b = 4)'],
].map(([label, metric]) => [label, ...driftRow(metric)]);

const N = {
  days: String(days),
  jobs: int(v(tm.cohort.n_jobs)),
  reads: String(reads.filter((r) => r.event === 'read').length),
  s: pct1(v(S.saving)), s_lo: pct1(v(S.saving_ci95)[0]), s_hi: pct1(v(S.saving_ci95)[1]),
  s_val: pct1(v(Sv.saving)),
  wait: pct1(v(contrast(tm, 'W_time').saving)),
  nw_share: pct0(nwShare),
  net_peak: int(net[netPeakH]), net_peak_h: hour12(netPeakH), dem_peak_h: hour12(demPeakH),
  rush: `${hour12(rush[0]).replace(' PM', '')}–${hour12(rush[1] % 24)}`,
  regions_dirtier: String(dirtier), regions_n: String(regions.length),
  bpat_rush: minus(v(ov.regions.BPAT.alignment.rush_vs_mean_pct).toFixed(1)),
  gpus_cluster: int(v(tman.assumptions.home_slots)),
  job_gpus: String(job.gpus?.value ?? job.gpus),
  job_h: (v(job.declared_duration_s) / 3600).toFixed(0),
  job_delay_h: (v(job.max_delay_s) / 3600).toFixed(0),
  transfer_min: (v(tman.assumptions.transfer_time_s) / 60).toFixed(0),
  job_stay: int(coKg(act('PACE'))), job_nw: int(coKg(act('BPAT'))),
  top1: pct0(v(tm.workload.top_1pct_jobs_by_declared_gpu_h.energy_share)),
  mob_s: pct1(v(mob.S['4'].saving)), mob_lo: pct1(v(mob.S['4'].saving_ci95)[0]), mob_hi: pct1(v(mob.S['4'].saving_ci95)[1]),
  mob_w: pct1(v(mob.W['4'].saving)), mob_val: pct1(v(mobV.saving)),
  tr120: pct0(v(tx.extensions.transfer_120min.vs_U.S['4'].saving)),
  cap1024: pct0(v(tx.extensions.dest_slots_1024.vs_U.S['4'].saving)),
  st_c_cut: pct1(v(cu('carbon').cut_frac)), st_p_cut: pct1(v(cu('peak').cut_frac)),
  st_c_flat: int(-v(cu('carbon').flat_marginal_cut_t)), st_p_flat: int(-v(cu('peak').flat_marginal_cut_t)),
  st_rush_before: mw2(v(cu('carbon').rush_import_before_mw)),
  st_c_rush_after: mw2(v(cu('carbon').rush_import_after_mw)), st_p_rush_after: mw2(v(cu('peak').rush_import_after_mw)),
  st_c_hours: String(v(cu('carbon').rush_hours_discharging)), st_p_hours: String(v(cu('peak').rush_hours_discharging)),
  st_rush_n: String(v(tx.storage.rush.n_hours)),
  st_peak_before: mw2(v(cu('carbon').peak_import_before_mw)), st_peak_after: mw2(v(cu('carbon').peak_import_after_mw)),
  relief_bpat: mw2(v(relief.BPAT.rush_change_vs_U_mw)), relief_ciso: mw2(v(relief.CISO.rush_change_vs_U_mw)),
  residual_rush: mw2(v(sc.carbon.cases.mobility_le_8gpus_W['4'].rush_import_before_mw)),
  price_lo: pct0(Math.min(...['S', 'W', 'L'].map((p) => v(pr.california_node.range[p].delta_vs_U_frac)[0]))),
  price_hi: pct0(Math.max(...['S', 'W', 'L'].map((p) => v(pr.california_node.range[p].delta_vs_U_frac)[1]))),
  price_t: v(pr.policies.S.cost_per_attributed_tonne_usd_t).toFixed(0),
  water_ex: minus(pct1(v(tx.water.policies.S.change_vs_U.ex_hydro_frac))),
  water_with: pct0(v(tx.water.policies.S.change_vs_U.with_hydro_frac)),
  water_ex_val: minus(pct1(v(vw.policies.S.change_vs_U.ex_hydro_frac))),
  water_with_val: pct0(v(vw.policies.S.change_vs_U.with_hydro_frac)),
  excl_jobs: int(v(tm.cohort.n_excluded)),
};

const data = {
  generated_from: ['results/test/metrics.json', 'results/metrics.json', 'results/test/extras.json', 'results/extensions.json', 'results/test/manifest.json', 'results/test/grid-profile.json', 'results/test/job-replay.json', 'results/overview.json', 'results/prices.json', 'results/water.json', 'results/test_reads.jsonl'],
  N,
  july: { month: pj.month, net: net.map((x) => Math.round(x)), demand: dem.map((x) => Math.round(x)), solar: v(pj.solar_mw).map((x) => Math.round(x)), rush, netPeakH, demPeakH },
  policies: pol,
  mobility: { S: v(mob.S['4'].saving), S_ci: v(mob.S['4'].saving_ci95), S_val: v(mobV.saving), S_val_ci: v(mobV.saving_ci95), all: v(S.saving), all_ci: v(S.saving_ci95), all_val: v(Sv.saving), all_val_ci: v(Sv.saving_ci95) },
  top1: v(tm.workload.top_1pct_jobs_by_declared_gpu_h.energy_share),
  drift: scen,
  claim_frame: tman.claim_frame,
};

const text = `// Generated by docs/pitch/deck/tools/deck-data.mjs from committed results JSON. Do not edit.\nwindow.DECK_DATA = ${JSON.stringify(data, null, 1)};\n`;
if (process.argv.includes('--check')) {
  let cur = '';
  try { cur = readFileSync(out, 'utf8'); } catch {}
  if (cur !== text) { console.error('deck data.js is stale: run node docs/pitch/deck/tools/deck-data.mjs'); process.exit(1); }
  console.log('deck data.js matches results/');
} else {
  writeFileSync(out, text);
  console.log(`wrote ${out}`);
  console.log(N);
}
