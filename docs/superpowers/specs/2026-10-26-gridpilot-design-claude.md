# GridPilot (working name): design spec, Claude's draft v2

Status: DRAFT v3. Sol's plan review is folded in (`docs/reviews/2026-10-26-plan-sol-r1-sol.md`), and so are the owner's decisions recorded in `docs/brief.md` (23:14 MT): **emissions first**, and **PACE first with a regional overview**.
- v4: the `[DATA]` items are settled from `docs/data-profile/*.md` (merged in PR #10, snapshot `05efabe781cc`), and move vs wait is in the core (owner, 00:15).

## 1. Intent

**Central question:** starting with Utah's grid (PACE), how much attributed operational emissions can a fixed amount of flexible AI work avoid at a given delay budget? How much of that needs a forecast rather than a calendar rule? And do emissions-optimal schedules move AI load into the grid's rush hours or out of them?

**Why it matters to Torus.** Torus sells fast storage for AI data centers, plus demand response to Rocky Mountain Power.
- Hourly scheduling shapes the AI load envelope; that is ours.
- Fast storage handles the shorter swings; that is theirs.
- We make no device-level claims.

**What success means.** A judge leaves with:
1. one non-obvious, defensible insight, with its number and its interval;
2. confidence the number is honest: labels, fair baselines, no lookahead, accounted work;
3. a memory of the visualization.

**Anti-goals:**
- a saving without a baseline and an interval;
- savings made by unfinished work;
- results that can't be reproduced;
- a demo that needs the network or the DGX;
- claims beyond the evidence, such as calling a stress proxy "congestion" or attributed emissions "avoided emissions".

## 2. Hypotheses and registered comparisons

Comparisons are selected on validation and registered here before the seal opens. Anything else is labeled exploratory.

- **H1, predictability.**
  - The forecast's day-ahead net-load stress beats the persistence and seasonal-naive baselines on daily top-4 precision and rush-hour F1.
  - Demand error is compared with the BA's own published day-ahead forecast at the same lead. Matching it is enough.
- **H2, value of waiting (primary).** The reduction in attributed operational tCO₂ against run-now, with identical completed work and deadlines.
  - Shown as curves over allowed wait W ∈ {0, 2, 4, 8, 12, 24} h. The 48 h point is only run if runtime allows.
  - Stress exposure and wholesale cost are reported for the same schedules. They are never traded against tCO₂ through weights.
- **H3, value of the forecast.** The same scheduler fed:
  - (a) a seasonal profile;
  - (b) our forecast;
  - (c) actuals (hindsight).

  Report the share of hindsight savings captured by (a) and by (b).
- **H4, move vs wait (core, owner 00:15).** Time only vs place only (a static best site chosen on validation) vs both, under destination capacity and migration rules. Shown on a production and a consumption basis.
- **H5, emissions vs rush hour.** Does the emissions-first schedule add AI energy to rush hours or remove it? How often do the cleanest hours coincide with high stress?
  - A stress-first schedule is run only as a labeled comparison, to show what each objective costs on the other's metric.
- **H6, PACE load-duration scenario (Should).** Headroom MW against curtailment budget: the hindsight limit vs an operational forecast rule, with and without storage (state-of-charge accounted).

Small or negative effects are results.

## 3. Data, time and availability

- **Regions** (owner: PACE first, regional overview; move vs wait in the core):
  - **PACE** gets the complete path: forecast → router → replay → offline demo.
  - **Move destinations** (core): BPAT, CISO, NEVP, plus AZPS and PSCO if runtime allows. Each has a capacity cap, and moves follow the migration rules in §6.
  - **Overview** forecasts and the clean-vs-rush analysis cover the core set: PACE, BPAT, CISO, NEVP, AZPS, PSCO, ERCO, SWPP, MISO, PJM. IPCO and NYIS are optional.
  - WACM and WAUW are excluded: both retire on 2026-04-01, inside the test window (grid §10, geo §2).
- **Timestamps:**
  - `ts_utc` is the hour start; EIA's hour-ending labels are shifted by −1 h, as confirmed in grid §2.
  - Local time comes from one IANA zone per BA. MISO publishes EST all year, so EIA's local column is never used.
  - Daylight-saving days are handled by the zone.
- **Splits:**
  - train:
    - weather-free models, 2019-01 → 2024-10;
    - models that depend on recent behaviour, from 2022;
    - the weather-augmented variant (§4) follows the weather availability;
  - validation: 2024-11-01 → 2025-10-31;
  - **test:** 2025-11-01 → the **availability cutoff**, the last complete day in snapshot `05efabe781cc`, which for EIA-930 is 2026-10-25. Every result reports its covered days.
- **Availability at issue time** (10:00 local on D−1; grid "Implications"):
  - demand through the previous hour;
  - fuel mix and interchange through the end of D−2 (published by 11:00 ET on D−1);
  - EIA CO₂ only through D−3;
  - lagged-generation features ≥ 1.5 days;
  - weather: only Open-Meteo Previous Runs `_previous_day2`, via `weather.safe_previous_day`;
  - the BA's DF is published at about 11:00 ET on day D, so it is **never a feature**, only a baseline.

  EIA-930 exists only as its current revised vintage. Its revision optimism is a stated limitation.
- **Prices** (a Should study, separately labeled "wholesale energy-cost scenario"):
  - CAISO hubs day-ahead from 2023-07-16, because of OASIS retention;
  - ERCOT hubs 2022 onward;
  - PACE uses WEIM real-time (`ELAP_PACE-APND`, 15-min FMM) for train, validation and **test throughout** (pre-registered, for consistency);
  - EDAM day-ahead (live since 2026-05-01, test window only) is a labeled sensitivity, never joined silently.

## 4. Traffic report (forecasting)

**Issue and horizon.** Daily at 10:00 local prevailing time, for the next local day's 24 hours (14–38 h ahead).

**Targets:**
- demand (observed);
- net load = demand − wind − solar (derived from observed);
- **net-load stress proxy** = the percentile of net load within the trailing 365 days. The fitting window ends at issue time; the stress is not a measure of congestion.
- **carbon intensity: the router's primary input.**
  - The primary series is **EIA's own hourly CO₂ estimate** from the per-BA workbooks, on both a production and a consumption basis, labeled modeled by EIA.
  - Our fuel-mix CI is the transparent fallback and the input to the marginal proxy. It matches EIA within ±5% for 7 of 18 BAs, and its hourly correlation is ≥ 0.97 for 16 of 18.
  - Its forecast quality, the share of the cleanest hours correctly identified, is reported next to H1.
- **Cleaning:**
  - the spike rule (isolated single-hour jumps; 0–28 hours per BA);
  - `demand_adj ≤ 0` removed;
  - **EIA-imputed hours are excluded from scoring**: 996 of 1,181 imputed demand hours equal the DF exactly.
  - Every rule reports the rows it touched.
- **DF baseline alignment**, pre-registered from validation: PJM +1 h in all years, CISO +1 h from mid-2022, the others as published.

**Rush hour.** Two definitions:
- severity: stress ≥ 0.90;
- daily window: each day's top 4 hours by stress.

**Stress check.** On validation, test how stress lines up with day-ahead prices where they exist (rank correlation) to see what the proxy tracks.

**Models:**
- persistence (latest complete day, same hour);
- seasonal naive (one week earlier);
- the BA's own forecast (demand only);
- statsforecast MSTL/ETS;
- **LightGBM quantile** (P10/P50/P90), which carries the result;
- zero-shot Chronos-2 / TimesFM 3, timeboxed to 2 h. Record the checkpoint revision and the documented pretraining coverage, and qualify any result whose independence from EIA data can't be shown.

**Calibration and fitting windows.**
- Intervals are calibrated on validation only, via conformal adjustment of the quantiles.
- Every scaler, imputer, threshold and coefficient registers its fitting window. Leakage tests check both features and fitted transforms.

**Metrics** (bootstrap over days, dependence-aware):
- MAE and scaled MAE (vs seasonal naive);
- pinball loss / WIS, plus 80 % coverage *and* width;
- stress: per-day Spearman, top-4 precision, rush-hour precision, recall and F1;
- Diebold–Mariano with HAC variance against the validation-selected best baseline.

## 5. Workload: a synthetic scenario over real grid hours

- **Traces** (`measured`):
  - **Acme Seren** is primary: LLM-era, with job types, 169 days, 450,590 GPU jobs, and 5.63 M GPU-hours on a 2,288-GPU cluster.
  - **Alibaba PAI 2020** is the robustness trace.
  - **Alibaba spot 2026** only anchors the "already flexible" share at 2.4% of GPU-hours.
- **Where the energy is:** jobs longer than 6 h are 1.1% of jobs but 88.9% of GPU-hours, and pre-training is 69.5%. The levers are start time and pause/resume of long jobs, so we report MWh moved, not jobs moved.
- **Weather choice** for the traffic report: the primary model is weather-free LightGBM on the long history. The variant is option (b): `_previous_day2` temperature from 2021-03-25, plus shortwave and 100 m wind from 2024-03. Validation decides. Option (c) is a sensitivity only.
- **Reconstruction audit** on the trace itself:
  - queue time vs execution time;
  - GPU units (e.g. Alibaba's `plan_gpu` is in percent of a GPU);
  - retries and attempts;
  - censored or incomplete records, with every exclusion and its count.
- **Mapping:**
  - Seeded and block-based: whole trace days are resampled into the test calendar, keeping within-day timing and each job's attributes together.
  - Arrival times are mapped to each job's home-region local time, keeping hour-of-day.
  - Seams between blocks are documented.
  - Trace-generation uncertainty comes from 5 mapping seeds, reported separately from grid-week uncertainty.
- **Mapping:**
  - A week-block bootstrap: whole Seren weeks are drawn with replacement, aligned by weekday and local wall-clock hour. Shanghai 10:00 becomes Utah 10:00.
  - 5 seeds; labeled `simulated`.
- **Scale:**
  - **Base:** one Seren-size tenant (~0.5–0.85 MW IT; a 2,288-GPU cap at home).
  - **Scaled scenario:** N independent seeded tenants (`assumed`), for a Utah-relevant size.
  - Relative reductions are the headline; absolute MWh and tCO₂ are conditional.
- **Energy:** 0.7 kWh per GPU-hour at the meter (0.6 kWh IT × PUE 1.2), swept 0.4–2.0. It is `modeled`, based on measured A100 power: about 400 W busy and 60 W idle. Every GPU-hour counts as load, whatever the final state.
- **Flexibility per class** (`assumed`, swept):
  - **deferrable:** batch types (Pretrain, SFT, MLLM, Eval; about 91% of GPU-hours); Debug and interactive work never wait;
  - **allowed wait:** W ∈ {0, 2, 4, 8, 12, 24} h as the primary sweep, with a run-time-proportional wait as a sensitivity (a 2-minute eval doesn't wait 6 h);
  - **interruptible:** Pretrain and Eval, with a restart cost of 10 min of lost work per pause (5–15 sensitivity); contiguous as a sensitivity;
  - **movable:** single-node jobs (≤ 8 GPUs) when submitted; multi-node jobs only before they start (data gravity).

## 6. Information rules and policies

**What a policy knows** (online):
- jobs only once they arrive;
- each job's runtime from arrival (an assumption; the sensitivity uses ±30 % noise);
- grid signals from the latest issued forecast, or from the seasonal profile beyond the forecast horizon.

It never sees future arrivals or realized future signals; those are for hindsight only. It re-plans hourly for queued jobs.

**Capacity.** Each region's capacity is identical across policies, with headroom `[assumed]` so run-now is always feasible.

| ID | Policy | Information |
|---|---|---|
| P0 | run now | none |
| P1 | calendar rule: deferrable work starts in the local 22:00–06:00 window that meets its deadline | clock |
| P2 | reactive: run when the current observed signal is below its trailing-week 30th percentile, or when the deadline forces it | current signal |
| P3s | **scheduler + seasonal profile** (trailing 4-week hour-of-week mean) | history |
| P3f | **scheduler + our forecast** | forecast |
| P4 | offline optimum with actuals and all arrivals known (certified optimal) | hindsight |

**The scheduler** (P3s, P3f, P4):
- A time-indexed LP (HiGHS) over flow per job bucket per hour, with jobs aggregated by (arrival hour, deadline hour, home region). This is exact for interruptible work.
- **Objective** (owner, E09): minimize attributed operational tCO₂, subject to deadlines and identical completed work.
  - No weighted mix with other objectives.
  - Ties are broken by lower stress exposure, as a registered secondary rule.
  - Stress and cost are reported, not optimized.
- Runtime is benchmarked before sweeps. Solver status and gap are logged per solve. The fallback is a greedy earliest-deadline-first scheduler over the same signal.

**Spatial variants (core, per the owner):** a static best site chosen on validation, plus P3f-S and P4-S.
- **Destination capacity** (`assumed`): each destination hosts a cluster of the same size as the home cluster, already 60% busy with its own steady load. Only the free GPUs take moved work. This keeps "always go to BPAT" from being free.
- **Migration** (`assumed`): a 1 h delay to move data and set up. Multi-node jobs move only before they start.
- **Accounting:** each job's energy is charged to the BA it runs in. Results are shown on both a production and a consumption basis, because BPAT is 34 vs 102 g/kWh on the two.

**Bug check.** P4 is a certified optimum on the same objective and feasible set, so it must score at least as well as every policy. Every other ordering is a result.

## 7. Accounting and statistics

- **Common cohort.** All policies share the same jobs, with a warm-up week before the scoring window and a drain period after it. Work still unfinished at drain is reported as backlog, never dropped.
- **Reported for every policy:**
  - completed GPU-hours;
  - deadline misses;
  - wait p50/p95;
  - backlog;
  - an energy reconciliation: energy scheduled = energy required.
- **Outcomes:**
  - rush-hour MWh (energy in hours with stress ≥ 0.90);
  - energy in each region's annual top-100 hours;
  - attributed operational tCO₂ (production-based average; the marginal proxy is an exploratory association fitted on development data, with its instability shown);
  - wholesale USD where priced.
- **Uncertainty.**
  - One continuous simulation per policy and seed.
  - A paired block bootstrap over **common** calendar weeks, across policies and regions.
  - Sensitivity to the block length (1 vs 2 weeks).
  - Trace seeds reported separately.
- **Share of hindsight** = (P0 − P3f) / (P0 − P4), reported with its interval.

## 8. PACE load-duration scenario (Should)

- For a constant new load of L MW, find the curtailment needed to keep demand + L at or below the reference-year peak:
  - in hindsight (the known worst hours);
  - with an operational rule (curtail when forecast stress ≥ threshold, accepting forecast misses and rebound load).
- Storage of power L and energy E (E/L ∈ {1, 2, 4} h) covers events with state-of-charge, round-trip efficiency `[assumed]` and recharge-feasibility accounting.
- Design-time numbers use pre-test years; the test year is reported once.
- Labeled modeled. Network and intertemporal limits are stated as limitations.

## 9. Results contract (what the dashboard reads)

- Pydantic models generate JSON Schema, which generates TypeScript types.
- Every field carries its **label** (observed, measured, forecast, modeled, assumed, simulated) and its **lineage**: source manifests, config and run id.

| Artifact | Content |
|---|---|
| `catalog.json` | the supported scenarios: regions × policies × W × δ × accounting, with run ids. Explore offers only these. |
| `regions.json` | regions, time zones, label points, hero flag, data-quality notes |
| `signals/<region>.parquet` | hourly observed and forecast quantiles: demand, net load, stress, rush flags, carbon intensity; the BA's own forecast; price where valid |
| `forecast_metrics.json` | per region × target × model: metrics with intervals; DM results; validation and test separated |
| `router_summary.json` | per scenario × policy: outcomes, work accounting, paired deltas with CIs, share of hindsight |
| `sweeps.json` | the curves behind H2–H5 |
| `replay/<scenario>/<week>.json` | the sampled week for the animation (jobs, hours, regions, energy) |
| `headroom_pace.json` | Should; the H6 results |
| `tomorrow.json` | the Wednesday forecast for Thursday: issue time, input freshness, frozen model id, and a fallback flag |
| `provenance.json` | sources, retrieval times, licenses, attributions, label dictionary |
| `test_reads.jsonl` | the seal log |

## 10. Story (4–5 minute core, with branches)

**Core** (time-only; complete without any Should):
1. The grid has a rush hour (the PACE grid clock).
2. It's predictable a day ahead (fan chart, hit rate vs baselines).
3. AI work can wait (trace facts, with assumptions labeled).
4. Move or wait: the replay of a week, run-now vs ours, with arcs when work moves from Utah to the Northwest, Nevada or California.
5. What it's worth (the frontier vs W, share of hindsight, calendar rule vs forecast).
6. Carbon vs stress: when they disagree.
7. Tomorrow's traffic report (Thursday, generated Wednesday).

**Branches** (each drops out cleanly if its Should is cut):
- more destinations (AZPS, PSCO) and the scaled multi-tenant scenario;
- Utah headroom and storage (the Torus link);
- prices (dollar scenarios).

## 11. Limitations to state

- The workload placement is simulated.
- Data gravity, latency and contracts are ignored.
- Wholesale prices are not tariffs.
- Production-based average emissions are attributed emissions, not avoided emissions.
- The marginal proxy is not causal.
- EIA data is revised after publication, and only the current vintage is available.
- The trace's era and mix differ from today's LLM training.
- The timing of the BA's own day-ahead forecast is assumed.
- The stress index is not a congestion measure.

## 12. Left to the builder

Features and hyperparameters (validation only), LP details within the stated formulation, replay sampling, and the visual direction (G2).
