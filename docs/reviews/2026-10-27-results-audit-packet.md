# Results audit packet: GridPilot sealed test-year run

Prepared 2026-10-27 (about 21:45 MT) for the independent Codex (Astra) results audit. Assembled read-only from committed files at origin/main 605e845. Every value below was copied from the named JSON field; no new statistic was computed, except where a row says "derived" (a plain ratio of two copied fields, shown so the auditor can check it). **This packet is a map, not evidence: verify every row against the files.**

Notation: `S/U` means policy S against reference U. "Block 4" is the 4-week temporal block-bootstrap interval, the registered primary (`contrasts[i].blocks["4"]`). Savings are `saving` (ratio of totals) with `saving_ci95`. Contrasts live in `contrasts[]`, a list with `candidate` and `reference` keys.

## (a) What was frozen and what ran

| Item | Value |
|---|---|
| Freeze record | `config/freeze.json`, schema `gridpilot.freeze.v1`, sha256 `5941c49de736416d8f92f8836a7b5ca05b94f8c52e8744d31a0946864e735987` (witness `config_sha256`) |
| Freeze commit (`freeze_commit` field) | `8afed0c65b5e80142843bf74aa8e2a061452607a` (T20 integration, PR #91) |
| Freeze-record commit | `881fce65c4bcb35bc5a6b88b3a2e0777da70da28` = `code_commit` of the run; the annotated tag `config-freeze` points to it (tag object `3d6ea29315884ecd7c237575a4bc38c2eb9653b7`) |
| `frozen_at` | 2026-10-28T01:22:06Z (19:22 MT) |
| Deployed policy | S (rule trace in `deployed_policy.rule_trace`): lowest validation CO2 of six feasible candidates, 3,613,423 kg vs W 3,618,363 kg (D-074) |
| S ranking (frozen) | BPAT 95.5 < CISO 194.2 < NEVP 312.6 < PACE 572.8 g/kWh; fit window 2023-01-01 to 2025-10-29 (`s_ranking`) |
| Test cutoff F | 2026-10-25T00:00Z (`test_F`), basis day 2026-10-24, value completeness; 358 days from 2025-11-01 |
| Test fit / history | `test_fit_at` 2025-10-29T00Z, `test_history_start` 2023-01-01T00Z; L max leaf nodes 15 (31 for PACE demand) |
| Snapshot | `snapshot_id` 8a1b36b24b91; 8 raw inputs + derived tables hashed in `input_sha256` |
| Validation run behind the freeze | `20261027T160656Z`, canonical metrics sha256 `e6ad2635699099775e414ddd073b5a7d9a81a57293d2ea3693ec309d9baeae35` (independent rebuild reproduced it exactly: D-074, `docs/evidence/rebuild-20261027.json`, sha256 3d5d454f0712b5687f0df698ef8d05e4870457e139ee6d8c621c88396b1f33a2). Note: D-056 and the run directory name the earlier registered run `20261027T122317Z`; `results/metrics.json` carries `20261027T160656Z`. |
| Test opening | 2026-10-28T01:22:53Z (19:22:53 MT; the run was started at 19:23 MT), run `20261028T012253Z`, session `2f5e1d16cef84ec1`, argv `scripts/run_slice.py --window test`, no rerun reason, `prior_openings: []`, closed `outcome: ok, rc 0` at 02:39:55Z |
| Results commit | `605e845` "T13: sealed test-year run (one opening, run 20261028T012253Z) and the read log". Diff 881fce6..605e845 touches only `results/test/*` (7 files) and `results/test_reads.jsonl`; `git diff 8afed0c..605e845 -- lab config` shows only the added `config/freeze.json`. |
| Primary export | `results/test/metrics.json`, `manifest.json`, `job-replay.json`, `forecast-replay.json`, `grid-profile.json`, `workload-profile.json`; extras in `results/test/extras.json` (extras run `20261028T023856Z`, 3,504 s) |
| Coverage | arrivals 2025-11-01T00Z to 2026-10-15T23:03:57Z, drain to 2026-10-25T00Z (`covered`); 51 weeks; 888,224 cohort jobs, 11,805,978 declared GPU-h; 8,003 excluded jobs / 382,074 GPU-h (validation: 917,909 jobs; 1,203 excluded) |
| Policies | U, G, S, K, W, L, H (hindsight diagnostic, not a contender), W_time, L_time; all feasible, 0 late jobs, 0 capacity violations (`policies.*.metrics`) |
| Extras (D-071) | the seven D-058 scenarios on the test year, storage with the D-073 peak-aimed schedule, toughest days, water, seasonal split, forecast skill + L permutation importance, drift table (197 rows) |
| Failure rule (D-074) | no extra failed; none reported `not_run`; no second opening |

## (b) Headline-claim table

Sources: pitch drafts `docs/pitch/one-pager.md` (OP), `deck-outline.md` (DK), `narrative.md` (NR), `qa.md` (QA). "Val" = `results/…` validation file; "Test" = `results/test/…`. Paths are JSON paths; `[S,U]` means the `contrasts` element with those candidate/reference keys, then `.blocks["4"]`.

| # | Claim (where) | Source field | Validation | Test |
|---|---|---|---|---|
| 1 | S saving vs U, with interval (OP table, DK5, NR3, QA5) | `metrics.json` `contrasts[S,U].blocks["4"].saving` / `.saving_ci95` | 22.62% [18.36, 26.82] | 22.26% [17.34, 27.20] |
| 2 | S minus U, kg CO2 (not in pitch; for checking) | same, `.diff_kg` / `.diff_kg_ci95` | 1,056,263 [910,438; 1,195,250] | 937,774 [755,608; 1,103,474] |
| 3 | "about 22.5%" for moving (OP, DK5, QA5) | `contrasts[W,U]` and `[L,U]` `.saving` | W 22.51%; L 22.51%; K 22.41% | W 22.17%; L 22.11%; K 22.03% |
| 4 | Waiting alone "0.7% / under 1%" (OP, DK5, QA1, QA5) | `contrasts[W_time,U]`, `[L_time,U]` `.saving` | W_time 0.72% [0.52, 0.95]; L_time 0.75% [0.55, 0.96] | W_time 0.77% [0.58, 1.00]; L_time 0.79% [0.58, 1.02] |
| 5 | K, W, L minus S (OP "no demonstrated aggregate benefit"; DK5, NR3) | `contrasts[K,S]`, `[W,S]`, `[L,S]` `.diff_kg`, `.diff_kg_ci95` (positive = candidate emits less; negative means candidate emits MORE than S) | K -10,007 [-19,330; -1,522]; W -4,940 [-14,832; 3,642]; L -5,104 [-15,294; 4,152] | K -9,922 [-19,497; -843]; W -3,926 [-13,781; 4,712]; L -6,632 [-16,660; 2,040] |
| 6 | H2 verdict (QA9; NR3 last sentence) | `h2.direction`, `h2.decided`, `h2.intervals["4"].diff_kg_ci95` (W − L) | inconclusive, decided false; -164 [-8,770; 7,161] | inconclusive, decided false; -2,706 [-12,583; 6,096] |
| 7 | H3 (dynamic search beats S) | `framing.placement_vs_timing` (text: "H3 not supported"; K emits more than S, interval excludes zero) | same wording, K − S = +10.0 t [+1.5, +19.3] | K − S = +9.9 t [+0.8, +19.5]; W − S +3.9 t [-4.7, +13.8]; L − S +6.6 t [-2.0, +16.7] |
| 8 | Cohort size (OP, NR3 placeholder) | `cohort.n_jobs.value` | 917,909 | 888,224 |
| 9 | Top 1% of jobs = 94% of energy (OP, DK6, QA3) | `workload.top_1pct_jobs_by_declared_gpu_h.energy_share.value` | 0.9409 | 0.9452 (rounds to 95%, not 94%) |
| 10 | Share of S's remote energy in BPAT (OP: 69% validation; NR3, DK placeholder) | `policies.S.metrics.execution_kwh_by_site.{PACE,CISO,BPAT,NEVP}.value` (derived ratio BPAT / (CISO+BPAT+NEVP)) | BPAT 1,757,153; CISO 679,775; NEVP 108,595 kWh → 69.0% | BPAT 1,735,162; CISO 623,965; NEVP 103,479 kWh → 70.5% (`framing`: "67% of L's remote execution energy") |
| 11 | Remote energy share of S | `policies.S.metrics.remote_energy_share.value` | 0.3197 | 0.2998 |
| 12 | Mobility caveat: S 22.6% → 3.2% [2.1–4.5] if only jobs of ≤8 GPUs move (OP, DK5/6, NR4, QA3) | Val: `extensions.json` `sensitivities.mobility_le_8gpus.policies.S.vs_U["4"].saving`; Test: `test/extras.json` `extensions.mobility_le_8gpus.vs_U.S["4"].saving` | S 3.24% [2.07, 4.53]; W 3.90% [2.60, 5.35]; remote energy share 4.3% | S 3.15% [1.89, 4.67]; W 3.87% [2.49, 5.51] (console log: remote energy 4.0%) |
| 13 | "not rerun on the test year" (OP table row; NR4 note "none was rerun on the test year") | `test/extras.json` `extensions.mobility_le_8gpus.status` = ok, run `20261028T022912Z` | n/a | **Contradicted: it was run (row 12).** |
| 14 | Two-hour transfer "about 20%" (DK6, NR4, QA6) | `…transfer_120min.policies.S.vs_U["4"].saving` | 20.19% [16.59, 23.72] | 19.95% [15.77, 24.17] |
| 15 | Double spare capacity "35%" (DK6, NR4, QA1) | `…dest_slots_1024…S` | 35.02% [32.72, 37.58] | 34.87% [32.05, 38.33] |
| 16 | No spare capacity: only waiting is left, 0.7% (QA1) | `…dest_slots_0…` S and W | S 0.0%; W 0.72% [0.52, 0.95] | S 0.0%; W 0.77% [0.58, 1.00] |
| 17 | Workload phase / 24 h delay robustness, "20.2–23.2%" (QA6) | `…phase_49`, `phase_98`, `batch_delay_24h`, `transfer_120min` S | S 23.16 / 21.97 / 22.79 / 20.19% | S 23.08 / 23.29 / 22.34 / 19.95% |
| 18 | Production-basis repricing "25.2–25.5%", S 25.5% (QA6, QA12) | `extensions.json` `repricing.by_policy.S.production.vs_U["4"].saving` | S 25.49% [20.81, 30.13]; W 25.25% | not run on test (`metrics.json` `common_support.status_rerun` = not_run; no repricing block in test extras) |
| 19 | Only 29% of flexible energy had its whole window inside forecast coverage (QA9) | `coverage_stratum.share_flexible_energy_in_coverage.value` | 0.2902 | 0.2901 |
| 20 | Deadlines met by construction, no late jobs (OP, DK5, QA4) | `policies.*.metrics.late_jobs.value` | 0 for all nine | 0 for all nine |
| 21 | Hindsight H "diagnostic, not optimum" (QA7) | `policies.H.contender` = false; `framing.greedy_search`; `contrasts[H,S]` | H − S -486 kg [-9,948; 8,035] | H − S -1,631 kg [-11,803; 7,051] |
| 22 | Utah net-load peak 8 PM, 6,654 MW, July 2025 weekdays (OP, DK2, NR1, QA14) | `results/grid-profile.json` `pace_july_weekday` (value 6654.3042 at line 2879) | validation only | n/a (labelled validation; `test/grid-profile.json` is the test counterpart) |
| 23 | Job 5930563#c3: 2,728 kg stay vs 336 kg in the Northwest (DK4, NR2) | `results/job-replay.json` `illustrative_job…execution_co2_kg` 2728.25; BPAT option `co2_kg` 336.12 | validation only | `test/job-replay.json` holds the test illustrative job (check whether the deck re-shoots it) |
| 24 | PACE ~580 vs BPAT ~90 g/kWh training mean (QA14) | Frozen test S ranking, `config/freeze.json` `s_ranking.mean_consumed_ci_g_kwh` | n/a | PACE 572.8, BPAT 95.5 (test ranking fit, 2023-01-01 to 2025-10-29); the 580/90 figures use a different window |
| 25 | Storage (OP, DK7, NR5, QA16-18; placeholders `{{STORAGE: …}}`) | Val: `results/storage.json`; Test: `test/extras.json` `storage.*` | 4 MWh / 1 MW, η 0.85, U load: fixed schedule `cases.U.strategies.A["0.85"]` cut 3.51% (164.0 t), flat-marginal cut -108.5 t; hindsight B cut 4.41%; rush import (carbon schedule) 1.12 → 1.04 MW per D-073 | Carbon schedule, U load, 4 MWh: `schedule_comparison.schedules.carbon.cases.U["4"]` cut 3.95% (166.5 t), flat-marginal cut -107.1 t, rush import 0.879 → 0.552 MW, 6 of 14 rush hours discharging. Peak-aimed schedule (`…schedules.peak`): cut 0.97% (40.9 t), flat-marginal -77.0 t, rush import 0.879 → 0.317 MW, 10 of 14 rush hours discharging. Move-and-store `combined.move_and_store_cut_frac.A["4"]` 7.74% vs move-only 3.87% |
| 26 | Peak relief from moving: PACE rush load change, destination increase (QA18, DK7) | `test/extras.json` `storage.peak_relief.S.{PACE,CISO,BPAT,NEVP}.rush_change_vs_U_mw` | val `storage.json` `peak_relief.policies.S`: PACE -0.263, CISO +0.033, BPAT +0.224, NEVP 0.0 MW | PACE -0.222, CISO +0.040, BPAT +0.204, NEVP +0.001 MW |
| 27 | Water, illustrative (DK A2, QA20) | `test/extras.json` `water.policies.S.change_vs_U`; `water.claim` = "none" | `results/water.json` | S vs U: ex-hydro -18.6% (less), with hydro-evaporation +174.1% (more); no water-saving claim |
| 28 | Forecast skill: "forecasts follow Utah's daily swing" (NR3); Utah not reliably better than seasonal average (D-072) | `test/extras.json` `forecast_skill.series.PACE.ci_consumed.models.{K,W,L}` (MAE 108.1 / 91.0 / 99.6 g/kWh; `mae_vs_climatology` W 0.842, L 0.921; interval coverage 0.70 / 0.77 / 0.69 vs nominal 0.80) | `results/extras-validation.json` `forecast_skill` | see left; the "follow the daily swing" wording needs the auditor's check |
| 29 | Relaxed bound ("never a ceiling") | `relaxed_bound.primary.value` | 3,501,312 kg | 3,184,387 kg |
| 30 | Totals (context) | `policies.U.metrics.co2_kg`, `policies.S.metrics.co2_kg` | U 4,669,686; S 3,613,423 kg | U 4,212,140; S 3,274,366 kg |
| 31 | Share of kWh priced on truth tiers 2–4 (spec F14.6) | `policies.*.metrics.kwh_share_tier_ge2.value` | U 0; S 0.00056; W 0.00066; K 0.00130 | U 0.00014; S 0.00122; W 0.00126; K 0.00127; H 0.00128 |
| 32 | "Cost was not evaluated" (OP limits) | no test cost field; price lens (T22) is `results/prices.json`, validation only, wholesale scenario | | |
| 33 | Placeholders still open: `{{WATER: …}}`, `{{STORAGE: …}}` | see rows 25–27 | | |

### Claims in the pitch drafts the JSON does not support, or supports differently

1. **Mobility "not rerun on the test year"** (OP table; NR4 note "none was rerun on the test year"). False after D-071: the ≤8-GPU scenario ran in the opening (rows 12–13). The deck's "22.6% → about 3%" caveat is the validation figure and should be paired with the test figure 3.15% [1.89, 4.67].
2. **"Top 1% of jobs use 94% of the energy"** is the validation number. The test value is 94.5%, which rounds to 95%.
3. **QA10 "Did you peek at the test year? No."** is absolute. D-072 records a T22 metadata touch, D-060 records a blocked early attempt, and the extras and the T19 outlook add logged reads (section d). The answer needs the disclosures.
4. **QA14 "about 580 vs about 90 g/kWh"** does not match the frozen test ranking (572.8 vs 95.5).
5. **"Dynamic search has no demonstrated aggregate benefit"** is supported, but K is reliably worse than S on both years (the interval excludes zero); the pitch could say so, and must not say K, W, L "match" S.
6. **NR3 "our day-ahead forecasts follow Utah's daily swing"**: D-072 says Utah is not reliably better than its seasonal average on any day D+1 to D+7 under block-bootstrap intervals; test-year PACE carbon MAE is 108 (K), 91 (W), 100 (L) g/kWh, and the frozen 80% intervals cover 69–77%. The wording is not backed by a field.
7. **Storage "helps during Utah's evening rush"**: the carbon schedule discharges in 6 of 14 test rush hours and the flat-marginal basis is negative (-107 t) in every case; the peak-aimed schedule cuts rush import to 0.317 MW but cuts attributed CO2 only 0.97%. QA17/18 placeholders must carry both.
8. **"Sealed test year"** covers 358 days (arrivals to 2026-10-15, drain to 2026-10-25), not a calendar year.
9. **Cohort drift**: test excludes 8,003 jobs (validation 1,203) with no pitch disclosure; the cause is not stated in the pitch (check `cohort` and the spec's arrival-exclusion rule, spec line 708).
10. Everything labelled "validation" in the drafts (6,654 MW, job 5930563#c3, 69% BPAT share, storage numbers) is correctly labelled in the text I read; the audit should check the final deck re-shoots do not mix windows.

## (c) Disclosures and known limits

- **D-072 (validation extras).**
  - Live outlook reads (T19) occur after the single opening, outside `data/raw`, logged to `results/outlook_reads.jsonl` (the file does not exist on main; the outlook has not run on main). Registering `live_read` in the F8 guard is deferred; it is a deployment read, not an evaluation.
  - Forecast skill uses week-block intervals because iid intervals overstated Utah's skill: Utah is not reliably better than its seasonal average for D+1 to D+7; destinations are (10–23%).
  - The California price node (PG&E `DLAP_PGAE-APND`) is an unregistered choice; SCE shown as sensitivity (W adds +$16.4k at SCE vs +$21.6k at PG&E); the block-bootstrap whiskers do not cover node choice.
  - Seal metadata touch (T22): column names and node list of one raw price file dated after 2025-11-01 were printed; no values; prices are not a test input; shipped code now refuses files that start or straddle the seal.
- **D-074.** The T12r reviewer-found value-completeness correction (F 10-27 → 10-25); the T20r reviewer created and deleted an empty `data/.wtest` (directory mtime only); item 3 net-load reads are logged under item 2's label; seasons are assigned by the Monday of each arrival week (SON mixes Nov 2025 with Sep–Oct 2026); frozen p10/p90 intervals are validation-fit residuals "transferred from the validation-fit model"; extension scenarios run sequentially; failure rule never permits a second opening.
- **D-060.** Entry-point check accepts HEAD differing from `freeze_commit` only by `config/freeze.json` and test outputs; check (b) pins the record via the annotated tag; test forecast issues start at the test fit date 2025-10-29; freeze uses snapshot 8a1b36b24b91.
- **D-058 cuts (`extensions.json` `not_run`, 13 items).** No-advance-reservation (shadow-U), missingness-blind scheduling, batch delay 0 h, transfer 0 min, transfer energy 0%/20%, active IT power 0.40/0.80 kW, remote PUE 1.10/1.56, idle power, no flexible jobs, all candidates flexible, home capacity 1.25x, DST alignment, +25% runtime overrun. The test year ran only the seven D-058 scenarios; common-support, production-basis repricing and the scenarios above were not rerun on test.
- **Data and preprocessing limits.**
  - **Revised snapshot, not vintages.** Publication delays are enforced as assumed envelopes (demand +2 h; fuel mix and total interchange +48 h; consumed/generated carbon and bilateral interchange +96 h), not archived receipt times; revisions and retroactively updated emission factors cannot be reconstructed (spec §5, lines 133–142). EIA 2025–26 factors may be provisional (spec line 558).
  - **Carbon basis.** EIA consumption-basis intensity is a modeled average, not marginal; results are attributed, not avoided emissions (spec lines 101, 448; D-055). Production-basis repricing gives 25.5% for S on validation only.
  - **Net load.** Missing wind/solar are treated as 0 in net load (grid-profile and rush definitions); flagged for audit.
  - **Demand spike rule.** Isolated demand spikes (>15% from both neighbours' mean while they agree within 10%) and values ≤ 0 are removed, thresholds chosen by judgment (D-021-era, `docs/decisions.md` line 199); imputed hours are not scored.
  - **Four-tier truth fill (F14.6).** Missing consumption-basis hours use, in order: EIA consumption CI; EIA production CI; EIA-930 fuel-mix CI; mean of the preceding 7 days at the same UTC hour. Forecasts are never fill. Test-year tier ≥2 energy share is 0.12–0.13% for the five contender policies; common-support sensitivity was not run on test.
  - **Energy.** 0.7 kWh per GPU-hour at the meter (0.6 kWh IT × PUE 1.2), assumed (D-035); the 0.4–2.0 sweep was cut (D-058). Site: 2,288 GPUs at PACE; 512 spare slots per destination; 30 min transfer; 6 h batch delay: all assumed.
  - **Mobility and deadlines.** Mobility is assumed; deadlines are met by construction (baseline bookings, F11), runtimes are exact declared; runtime uncertainty untested.
  - **Intervals** are conditional on this one replay (4-week temporal block resampling, 2,000 replicates; blocks 2 and 8 also exported).
  - **Rest.** Hindsight H is a diagnostic; the relaxed bound is a lower bound, not a ceiling; storage is an hourly illustration (fast buffering out of scope); water is consumption, not withdrawal, with production-side weighting.

## (d) Seal-integrity evidence

| Check | Evidence |
|---|---|
| Witness lines | `$(git rev-parse --git-common-dir)/gridpilot/test_openings.jsonl` (`.git/gridpilot/test_openings.jsonl`): **2 lines**, both session `2f5e1d16cef84ec1`: line 1 `event: invocation` (utc 2026-10-28T01:22:53Z, `prior_openings: []`, `rerun_reason: null`, `exceptions: []`, `synthetic: false`, `remote_tag` 3d6ea29…, config sha 5941c49d…, inputs and manifests hashed), line 2 `event: close` (`outcome: ok`, `rc: 0`, `exported: true`, `n_reads: 69`, nine run directories) |
| Lock released | `.git/gridpilot/` holds only `test_openings.jsonl`; no `test_mode.lock` |
| One opening | one `invocation` event in the witness and one in `results/test_reads.jsonl`; `results/test/` was empty before 605e845; origin/main has no later commit touching results/test |
| Read log | `results/test_reads.jsonl`: **89 lines**, one session. Events: 69 `read`, 8 `run_start`, 7 `extension_end`, 2 `export`, 1 each `invocation`, `extras_start`, `close` (69 matches the close event's `n_reads`). Read purposes: truth-table builds for the primary and for each of the seven scenarios (4 reads each); F14.6 tiers 1–2/4 EIA carbon and tier 3 fuel-mix CI (primary and each scenario); forecast series ci_consumed/demand/solar/wind for the test fit and issues; grid profile (test) 2 reads; D-071 item 3 Salt Lake City temperature archive 2 reads; D-071 item 2 storage forecast series; item 4 water fuel mix; item 6 EIA day-ahead demand forecast and forecast series. All purposes are in the file; none is empty on a `read` event. |
| Frozen inputs | witness `inputs_sha256` and `manifests_sha256` against `config/freeze.json` `input_sha256`; code tree identical to the freeze commit apart from `config/freeze.json` (`git diff 8afed0c..605e845 -- lab config`) |
| No change to F, policy or catalog | `test_F` 2026-10-25T00Z in freeze, witness, metrics; deployed policy S; `scenario_catalog` in freeze; extras `freeze.rerun_reason: null` |
| T11 blocked early attempt (D-060) | During T11 the implementer ran `make slice WINDOW=test` on real data against its brief; the permission classifier blocked it and it would have refused anyway (no freeze record). The lead verified that no `test_reads.jsonl`, `results/test/` or test carbon parquet existed anywhere. |
| T22 metadata touch (D-072) | Column names and the node list of one raw price file after 2025-11-01 were printed, no values; prices are not a test input; fix: shipped code refuses files that start or straddle the seal (`.superpowers/sdd/2026-10-27-stage3-freeze-test/t22-review.md`, `t22-rereview-r1.md`) |
| Other disclosures | T20r reviewer's empty `data/.wtest` file (D-074); T19 outlook reads happen after the opening (`results/outlook_reads.jsonl` absent) |
| Console log | `/tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/t13-console.log` ends `exit=0` after all seven scenarios and the extras (3,504 s) |

Open points the lead should resolve or the auditor should weigh: the validation run id (`20261027T160656Z` vs D-056's `20261027T122317Z`); the 8,003-job exclusion; the contradicted "not rerun" statements; the absolute "No" in QA10.
