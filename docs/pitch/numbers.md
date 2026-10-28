# GridPilot: numbers card

Every number said aloud in the talk or in Q&A, with its source. Keep this open during rehearsal; if a number is not on this card, don't say it.

- **Test** = the sealed test year: 358 days, 2025-11-01 to 2026-10-25 (`config/freeze.json` `test_F`), opened once (run 20261028T012253Z).
- **Validation** = Nov 2024 – Oct 2025 (run 20261027T160656Z).
- Savings are vs U (every job stays in Utah), policy S, 4-week blocks (b = 4), 95% intervals. Notation: `contrasts[S/U]` is the `contrasts` element with `candidate` S and `reference` U; values are `.blocks["4"].saving` and `.saving_ci95`.
- "derived" marks a plain ratio or difference of two copied fields; no interval is ever computed from kilograms.
- `results/overview.json` and `results/prices.json` are validation-year. `results/outlook.json` is the live outlook issued 2026-10-27 10:00 MT (for Oct 28 – Nov 3), with Utah shown at its seasonal average; its skill by horizon is measured on the validation issues.

## Said in the talk

| # | Said aloud | Test | Validation | Source |
|---|---|---|---|---|
| N1 | Headline: S cut attributed CO₂ **22.3% [17.3, 27.2]** | 22.26% [17.34, 27.20] | 22.62% [18.36, 26.82] | `results/test/metrics.json` and `results/metrics.json` `contrasts[S/U].blocks["4"].saving`, `.saving_ci95` |
| N2 | Waiting in Utah alone: **under 1%** (about 0.8%) | W_time 0.77% [0.58, 1.00]; L_time 0.79% [0.58, 1.02] | 0.72% [0.52, 0.95]; 0.75% [0.55, 0.96] | `contrasts[W_time/U]`, `contrasts[L_time/U]` |
| N3 | **358 days** of the sealed test year | 2025-11-01 → 2026-10-25 | 357 days (2024-11-01 → 2025-10-24) | derived from `results/test/manifest.json` `split.eval_start`, `split.F`; D-071, D-074 |
| N4 | **888,224** jobs replayed | 888,224 | 917,909 | `cohort.n_jobs` |
| N5 | **70%** of the work S ran outside Utah ran in the Northwest | 70.5% | 69.0% | derived: `policies.S.metrics.execution_kwh_by_site.BPAT` ÷ (BPAT + CISO + NEVP) |
| N6 | Net-load peak **about 6,200 MW at 8 PM**, July weekdays (demand peaks at 5 PM) | 6,182 MW, July 2026 (mean of weekdays) | 6,654 MW, July 2025 | `results/test/grid-profile.json`, `results/grid-profile.json` `pace_july_weekday.net_load_mw[20]`; peak of `.demand_mw` at index 17 |
| N7 | Nine of ten regions have dirtier rush hours; Bonneville's are cleaner (cut c1) | n/a | 9 of 10 `dirtier`; BPAT −8.0% [−9.5, −6.4] (90%) | `results/overview.json` `regions.*.alignment.rush_verdict`, `.rush_vs_mean_pct` |
| N8 | Cluster of **about 2,300 GPUs**, about 1.6 MW when fully busy (assumed) | 2,288 GPUs; 1.647 MW | same | derived: `results/test/manifest.json` `assumptions.home_slots` × `kw_per_gpu` × `pue` (2,288 × 0.6 × 1.2); the U load's yearly peak draw is 1.639 MW (`storage.schedule_comparison.schedules.carbon.cases.U["4"].peak_import_before_mw`) |
| N9 | Job: 72 GPUs, 104 h pre-train; **about 2,100 kg** if it stays, **about 360 kg** in the Northwest | 5930563#c5: 2,098 kg vs 362 kg (S placed it in BPAT) | 5930563#c3: 2,728 kg vs 336 kg | `results/test/job-replay.json`, `results/job-replay.json` `illustrative_job.available_actions[*].co2_kg`, `.placements` |
| N10 | Six hours of allowed delay; half an hour of transfer (assumed) | 6 h; 30 min | same | `results/test/job-replay.json` `illustrative_job.max_delay_s` (21600); `results/test/manifest.json` `assumptions.allowed_delay_s.Pretrain`, `assumptions.transfer_time_s` (1800) |
| N11 | (Q&A since fix round r1) Forecasts beat a seasonal average by **10–23%** at the destinations, not reliably in Utah | no intervals on test skill (see Q&A) | destinations 9.9–23.4% (90% intervals exclude zero, D+1…D+7); Utah 3.0–4.8%, every interval crosses zero | `results/outlook.json` `skill_by_horizon.{BPAT,CISO,NEVP,PACE}.*.skill`, `.skill_ci90`; D-072 |
| N12 | The largest 1% of jobs use **95%** of the energy | 94.5% | 94.1% | `workload.top_1pct_jobs_by_declared_gpu_h.energy_share` |
| N13 | Only jobs of ≤ 8 GPUs may move: S **22.3 → 3.2%** | 3.15% [1.89, 4.67] | 3.24% [2.07, 4.53] | test: `results/test/extras.json` `extensions.mobility_le_8gpus.vs_U.S["4"]`; val: `results/extensions.json` `sensitivities.mobility_le_8gpus.policies.S.vs_U["4"]` |
| N14 | …and the forecast policies, which can also wait, **about 3.9%** | W 3.87% [2.49, 5.51]; L 3.88% | W 3.90%; L 3.94% | same paths, `.W["4"]`, `.L["4"]` |
| N15 | Two-hour transfer: **about 20%** | 19.95% [15.77, 24.17] | 20.19% [16.59, 23.72] | `extensions.transfer_120min` (test `vs_U.S["4"]`; val `policies.S.vs_U["4"]`) |
| N16 | Twice the spare capacity: **35%** | 34.87% [32.05, 38.33] | 35.02% [32.72, 37.58] | `extensions.dest_slots_1024` |
| N17 | Battery **4 MWh / 1 MW**, **85%** round trip (assumed) | same | same | `results/test/extras.json` `storage.rule`; `results/storage.json` `headline` |
| N18 | Carbon schedule cuts the cluster's CO₂ **about 4%** | 3.95% (166.5 t) | 3.51% (164.0 t) | test `storage.schedule_comparison.schedules.carbon.cases.U["4"].cut_frac`, `.cut_t`; val `results/extras-validation.json` `storage_peak.schedules.carbon.cases.U["4"]` |
| N19 | On a flat marginal factor its losses **add about 107 t** | −107.1 t | −108.5 t | `….carbon.cases.U["4"].flat_marginal_cut_t` (negative = adds) |
| N20 | Utah's **14 tightest hours** of the test year | 14 h at ≥ 7,207 MW net load | 12 h | `results/test/extras.json` `storage.rush.n_hours`, `.threshold_mw` |
| N21 | Peak-aimed schedule: cluster's average rush-hour draw **0.88 → 0.32 MW** | 0.879 → 0.317 MW (10 of 14 h discharging) | 1.116 → 0.904 MW (4 of 12) | `….schedules.peak.cases.U["4"].rush_import_before_mw`, `.rush_import_after_mw`, `.rush_hours_discharging` |
| N22 | …but CO₂ **only about 1%** | 0.97% (40.9 t) | 0.96% | `….schedules.peak.cases.U["4"].cut_frac` |
| N23 | Neither schedule lowers the yearly peak draw: **1.64 → 1.65 MW** (the connection) | 1.639 → 1.647 MW, both schedules | same | `….cases.U["4"].peak_import_before_mw`, `.peak_import_after_mw` |
| N24 | (on screen) Carbon schedule's rush draw 0.88 → 0.55 MW, 6 of 14 h | 0.879 → 0.552 | 1.116 → 1.036 (1 of 12) | `….schedules.carbon.cases.U["4"]` |
| N25 | (on screen, optional) Move small + store: **7.7%** vs 3.9% moving only | 7.74% vs 3.87% | 7.30% vs 3.90% | `results/test/extras.json` `storage.combined.move_and_store_cut_frac.A["4"]`, `.move_only_cut_frac` |

## Q&A only

| # | Number | Test | Validation | Source |
|---|---|---|---|---|
| Q-a | Other movers vs U (K, W, L) | 22.0 / 22.2 / 22.1% | 22.4 / 22.5 / 22.5% | `contrasts[K/U]`, `[W/U]`, `[L/U]` |
| Q-b | Candidate minus S, tonnes (positive = more CO₂ than S) | K +9.9 [+0.8, +19.5]; W +3.9 [−4.7, +13.8]; L +6.6 [−2.0, +16.7] | K +10.0 [+1.5, +19.3]; W +4.9 [−3.6, +14.8]; L +5.1 [−4.2, +15.3] | `metrics.json` `framing.placement_vs_timing` (test); `contrasts[K/S]` etc. `.diff_kg`, `.diff_kg_ci95` with the sign flipped (the field is reference − candidate) |
| Q-c | Hindsight H minus S | +1.6 t [−7.1, +11.8] | +0.5 t [−8.0, +9.9] | `contrasts[H/S]`, sign flipped |
| Q-d | Frozen ranking means, PACE vs BPAT | **572.8 vs 95.5 g/kWh** (fit 2023-01-01 → 2025-10-29) | 582.5 vs 87.5 (registered); 582.3 vs 87.3 (enveloped, D-062) | `config/freeze.json` `s_ranking.mean_consumed_ci_g_kwh`; `results/manifest.json` `s_ranking.mean_consumed_ci` |
| Q-e | Robustness span (phases 49/98, 2 h transfer, 24 h delay; S, W, L) | 19.9–23.3% | 20.2–23.2% (S, incl. observed-hours-only 22.5%) | `results/test/extras.json` `extensions.{phase_49,phase_98,transfer_120min,batch_delay_24h}.vs_U.*["4"]`; `results/extensions.json` `sensitivities.*`, `common_support.by_policy.S.vs_U["4"]` |
| Q-f | Production-basis carbon, S | not run on test | 25.5% (movers 25.1–25.5%) | `results/extensions.json` `repricing.by_policy.*.production.vs_U["4"].saving` |
| Q-g | No spare destination slots | S 0.0%, W 0.77% | S 0.0%, W 0.72% | `extensions.dest_slots_0` |
| Q-h | 24 h batch delay, waiting alone | W_time 1.48% | W_time 1.38% | `extensions.batch_delay_24h` `W_time` |
| Q-i | Energy in jobs longer than 24 h | 63% | 63% | `results/test/manifest.json` `workload.energy_share_gt_24h` |
| Q-j | Flexible share of GPU-hours (assumed rule) | 45.7% | 46.1% | `cohort.flex_shares.flexible.by_gpu_h` |
| Q-k | Flexible energy whose whole window sits in forecast coverage | 29% | 29% | `coverage_stratum.share_flexible_energy_in_coverage` |
| Q-l | Removing the 10 largest source jobs raises S to | 25.6% | 25.1% | `influence.by_k["10"].saving_vs_U.S` |
| Q-m | Excluded tail arrivals (same for every policy) | 8,003 jobs, 382,074 GPU-h (3.1% of stream GPU-h) | 1,203 jobs, 460,606 GPU-h (3.9%) | `cohort.n_excluded`, `cohort.excluded_gpu_h`; share derived with `cohort.declared_gpu_h`; arrivals end `covered.arrivals[1]` 2026-10-15T23:04Z |
| Q-n | Late jobs, every policy | 0 | 0 | `policies.*.metrics.late_jobs` |
| Q-o | Relaxed lower bound | 3,184 t | 3,501 t | `relaxed_bound.primary` |
| Q-p | Transfer CO₂ of S | 38.0 t | 44.3 t | `policies.S.metrics.transfer_co2_kg` |
| Q-q | Test-year Utah forecast MAE (no interval) | K 108.1, W 91.0, L 99.6 g/kWh; W/K 0.84, L/K 0.92 | n/a | `results/test/extras.json` `forecast_skill.series.PACE.ci_consumed.models.*.mae`, `.mae_vs_climatology` |
| Q-r | Frozen 80% intervals, Utah coverage | K 0.70, W 0.77, L 0.69 | n/a | `….models.*.interval.coverage` |
| Q-s | Seasons, S vs U (b = 4) | DJF 26.1%, MAM 21.5%, JJA 28.5%, SON 13.3% | not exported by season | `results/test/extras.json` `seasonal.seasons.*.policies.S.blocks["4"].saving` |
| Q-t | Toughest days, S vs U | 2026-08-20 (7,717 MW) −6.9%; 07-23 −15.1%; 07-11 −29.2% | `results/case-days.json` | `toughest_days.days[*].policies.S.co2_change_vs_U_frac` |
| Q-u | Storage η sweep (fixed schedule, 4 MWh) | η 0.85 only | 2.0% / 3.5% / 4.2% at η 0.75 / 0.85 / 0.90 | `results/storage.json` `cases.U.strategies.A.{0.75,0.85,0.90}.cut_frac[3]` |
| Q-v | Hindsight storage heuristic (never a bound) | 5.3% | 4.4% | test `storage.cases.U.B["4"].cut_frac`; drift row "U: 4 MWh B cut fraction" |
| Q-w | Storage losses | 169 MWh | 172 MWh | test `storage.cases.U.A["4"].losses_mwh`; val `cases.U.strategies.A["0.85"].losses_mwh[3]` |
| Q-x | Residual Utah rush draw if only ≤ 8-GPU jobs move (W) | 0.83 MW | 1.04 MW | test `storage.schedule_comparison.schedules.carbon.cases.mobility_le_8gpus_W["4"].rush_import_before_mw`; val `results/storage.json` `cases.mobility_le_8gpus_W.import_at_headline.A.rush_before_mw` |
| Q-y | Router's rush-hour load shift, S | PACE −0.22 MW; BPAT +0.20, CISO +0.04, NEVP +0.001 | PACE −0.26; BPAT +0.22, CISO +0.03 | `storage.peak_relief.S.*.rush_change_vs_U_mw` (test); `results/storage.json` `peak_relief.policies.S` |
| Q-z | Water, S vs U, generation-associated | ex-hydro −18.6%; with hydro evaporation +174% | −20.5%; +145% | `results/test/extras.json` `water.policies.S.change_vs_U.ex_hydro_frac`, `.with_hydro_frac`; `results/water.json` `policies.S.change_vs_U` |
| Q-aa | Wholesale price scenario (validation only) | n/a | moving costs **$16–22k** more a year (**+7–9%**) on a $240k bill; S **about $21** per attributed tonne; waiting alone −0.8% | `results/prices.json` `california_node.range.{S,W,L}.delta_vs_U_usd`, `.delta_vs_U_frac`; `policies.S.cost_per_attributed_tonne_usd_t`; `policies.U.cost_usd`; `policies.W_time.delta_vs_U_frac` |
| Q-ab | Prices: Utah vs Bonneville mean | n/a | $28.7 vs $34.7 /MWh | `results/prices.json` `prices.mean_usd_mwh` |
| Q-ac | Ten regions: rush vs average, examples | n/a | PACE +19.7%, PSCO +18.3%, ERCO +17.2%, CISO +1.9%, BPAT −8.0% | `results/overview.json` `regions.*.alignment.rush_vs_mean_pct` |
| Q-ad | Reads in the one opening | 69 logged reads | n/a | `results/test_reads.jsonl` (`event: read`) |
| Q-ae | Opening time | 2026-10-28T01:22:53Z = **19:22 MT**, Tue Oct 27 | n/a | `results/test_reads.jsonl` (invocation event); audit packet §(a) |
| Q-af | Energy per GPU-hour at the meter (assumed) | 0.72 kWh (0.6 kW × PUE 1.2) | same | `results/test/manifest.json` `assumptions.kw_per_gpu`, `.pue` |
