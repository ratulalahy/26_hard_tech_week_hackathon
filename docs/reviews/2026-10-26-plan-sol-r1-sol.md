The direction matches the brief, but the plan needs revision before approval. The largest problems are an unavailable portion of the test year, excessive mandatory scope, and experimental rules that could reward leakage or suppress negative results.

Reviewed commit `88ab93a6ff6e36dfa792844ab58f3e71ef6482d0` read-only. No files changed and no experimental data values were inspected.

Locations below use **P** for the [plan](/home/nvidia/workspace/personal/projects/htw-review/plan-sol/docs/plan/2026-10-26-hackathon-plan.md), **B** for the [brief](/home/nvidia/workspace/personal/projects/htw-review/plan-sol/docs/brief.md), and **A** for [AGENTS.md](/home/nvidia/workspace/personal/projects/htw-review/plan-sol/AGENTS.md). Each finding gives severity, confidence, location, failure scenario and correction. Details deliberately deferred to the spec are treated as approval conditions, rather than as missing implementation.

1. **Feasibility.** There are **36 hours 5 minutes until experiment freeze**, before allowing for sleep, integration and review. A focused version is feasible; the mandatory surface described here is not reliably deliverable.

- **F01 — critical; high confidence — P34, P105, P141; B58; A37. The test year extends beyond judging.** Failure: the project claims a full-year backtest even though October 29–31 have not happened; publication delays further shorten usable coverage. **Correction:** retain the prescribed sealed boundaries, declare an immutable availability cutoff, and report the available portion honestly. A different complete-year holdout requires an explicit owner decision and corresponding rule changes.

- **F02 — critical; high confidence — P87–132, P261–279. The Must list exceeds the available integration time.** Failure: ten BAs, several forecast targets, probabilistic evaluation, a constrained router, robustness studies and numerous custom interactive views converge late with no working presentation. **Correction:** make one PACE forecast-to-router-to-replay path the first deliverable. Obtain approval for a smaller mandatory presentation surface and thinner coverage elsewhere before overnight work.

- **F03 — important; high confidence — P19 versus P130–132. The deadline is contradictory.** Failure: agents interpret “experiments mostly done by Wed 2 PM” as permission to keep changing results after the 11 AM freeze. **Correction:** make Wednesday 11 AM the sole experiment deadline; reserve 11 AM–2 PM for packaging already frozen results.

- **F04 — important; high confidence — P37, P45–46, P193, P199 versus P269–279. Optional features remain dependencies of the promised story.** Failure: cutting cross-region routing or headroom leaves missing story beats, unsupported insight claims and unfinished map interactions. **Correction:** define the complete time-only story and its acceptance criteria, then specify exactly which claims, controls and scenes disappear when each optional feature is omitted.

- **F05 — important; medium confidence — P128–130, P157, P229. Optimization and sweep runtime are unbounded.** Failure: a job-level, multi-region scheduling formulation consumes Tuesday night or returns an uncertified “hindsight bound.” **Correction:** benchmark a representative workload early; specify aggregation, rolling horizon, scenario count, solve limits and feasible fallbacks. Record solver status and optimality gaps.

The critical path is **usable cached data → profile → approved spec and results contract → causal evaluation harness and simulator → validation and model/policy freeze → sealed evaluation → audit → dashboard artifacts → laptop rehearsal**. Fixtures let UI work overlap this path, but cannot remove it. Robustness studies will slip first; unresolved result semantics will then consume visualization polish and rehearsal time.

2. **Experimental soundness.** The plan contains good intentions—paired comparisons, weekly blocks, explicit hindsight and provenance—but several proposed checks do not yet establish validity.

- **E01 — critical; high confidence — P105, P136–137, P130; A38–39. The seal-opening condition is weaker than the repository rule.** Failure: agents read test results after spec approval while models, thresholds or policies are still being chosen; Wednesday “fixes” become test-driven tuning. **Correction:** require an approved spec **and frozen model/policy configurations** before opening the seal. Log input hashes, code/configuration hashes, read purpose and every rerun. Explicitly identify G2/G3 development numbers as validation results.

- **E02 — important; high confidence — P98, P143–146. Publication lag does not solve historical revisions.** Failure: lagged features still use corrected values unavailable at the historical issue time. EIA publishes demand, fuel mix, interchange and emissions on different schedules and revises historical records. **Correction:** distinguish event time, availability time and data vintage; use defensible vintages or conservative lag assumptions and disclose the remaining limitation. [EIA methodology](https://www.eia.gov/electricity/930-content/about.html).

- **E03 — important; high confidence — P113–114, P138–159. Leakage checks cover features but omit fitted transformations.** Failure: annual stress percentiles, normalization, imputations, calibration residuals or marginal-carbon coefficients incorporate validation/test outcomes. **Correction:** register the fitting window for every learned transformation, threshold and coefficient; test those boundaries alongside feature availability.

- **E04 — important; medium confidence — P152, P160–165. Zero-shot models have no contamination check.** Failure: a pretrained model has seen overlapping public energy series or evaluation periods, making “zero-shot” performance look more independent than it is. **Correction:** record checkpoint revisions and documented training coverage; investigate overlap and qualify models whose independence cannot be established.

- **E05 — important; high confidence — P34–37, P143, P157. Grid causality leaves workload clairvoyance unresolved.** Failure: the optimizer sees future arrivals, exact completed-job durations or signals beyond its forecast horizon. A 48-hour wait can also require a horizon longer than 48 hours once runtime is included. **Correction:** define what is known at arrival, distinguish assumed known runtimes from estimated runtimes, and specify causal replanning and horizon-end behavior. Reserve future arrivals and realized future signals for hindsight.

- **E06 — important; high confidence — P36, P147–155. Baseline fairness is underspecified.** Failure: run-now receives less capacity, different placement or stricter deadlines; “greedy current” sees unavailable signals; the BA forecast is compared at a different lead time. **Correction:** hold jobs, capacities, constraints, issue times and scoring hours fixed. Include an availability-safe seasonal-signal scheduler and, for spatial routing, a static best-site baseline selected on validation.

- **E07 — critical; high confidence — P323–325. The verification rule assumes the desired scientific result.** Failure: valid optimizer losses or forecasts worse than persistence are treated as bugs and repeatedly “fixed” against the holdout. **Correction:** accept negative results. Only a correctly established hindsight optimum bounds feasible policies on the identical objective and feasible set; forecast-driven optimization need not beat any baseline on realized outcomes.

- **E08 — important; high confidence — P44, P154–158, P319. Savings can be manufactured by unfinished work.** Failure: jobs miss deadlines, disappear at the year boundary or are deferred beyond scoring, reducing recorded energy and carbon. **Correction:** report completed work, deadline misses, rejected work, backlog, wait percentiles and energy reconciliation. Define warm-up and drain periods and a common accounting cohort across policies.

- **E09 — important; high confidence — P31, P44, P114, P159, P324. The optimization objective and denominators remain ambiguous.** Failure: arbitrary weights make the optimizer appear to improve “the objective” while worsening dollars, emissions or service; percentage savings use inconsistent work totals. **Correction:** register one primary objective and explicit guardrails, training/validation-derived scaling, units and common denominators. Report component outcomes separately.

- **E10 — important; high confidence — P32, P153. The probabilistic metrics require a forecast representation the plan does not specify.** Failure: CRPS is claimed from a point forecast plus one interval; broad intervals achieve coverage without useful precision; MAPE becomes unstable at zero or negative targets. **Correction:** specify samples or quantiles, validation-only calibration, coverage and width by lead/region, and suitable scores such as WIS or pinball loss. Use target-appropriate MAE/scaled errors rather than blanket MAPE.

- **E11 — important; high confidence — P155–156, P285. Weekly bootstrap details can produce false precision.** Failure: regions, policies or seeds are resampled independently, destroying pairing; repeated trace fragments are counted as independent observations; queues are restarted at artificial block boundaries. **Correction:** use common time blocks across all compared outcomes and regions, preserve continuous simulation state, and distinguish grid-week uncertainty from trace-generation uncertainty. Check sensitivity to block length.

- **E12 — important; high confidence — P140, P153, P157–158. Selection and dependence are not addressed by naming a statistical test.** Failure: the “best baseline,” headline BA or favorable wait window is chosen on test results; an ordinary Diebold–Mariano calculation ignores overlapping horizons. The “prior year” is already the validation year. **Correction:** select primary comparisons on validation, use dependence-aware inference, identify exploratory comparisons, and label the prior year as development evidence unless a separate rolling-origin holdout is constructed.

- **E13 — important; high confidence — P44, P159. Average-carbon accounting can be presented as avoided emissions.** Failure: production-mix intensity ignores imported electricity, and lower attributed emissions become a causal “CO₂ saved” claim. **Correction:** distinguish production from consumption accounting and label the result as an operational emissions estimate under the chosen accounting method. EIA itself distinguishes production and consumption intensity. [EIA methodology](https://www.eia.gov/electricity/930-content/about.html).

- **E14 — important; high confidence — P159. The proposed marginal regression is not a causal marginal-emissions estimate.** Failure: Δdemand correlates with weather, renewable output, imports and operating schedules; noisy coefficients reverse the apparent carbon benefit. **Correction:** call it an exploratory association proxy, fit it only on allowed development data, report instability and confounding, and avoid presenting agreement with it as validation of causal avoided emissions.

- **E15 — important; high confidence — P34, P157–158, P285. Annual trace mapping is too vague to support annual claims.** Failure: independent arrival resampling destroys bursts and job-size correlations, timezone alignment creates artificial solar coincidence, or repetition creates fictitious sample size. **Correction:** register a seeded, block-based mapping preserving within-block timing and job attributes; specify timezone, offsets, seams and workload scale. Describe the result as a synthetic workload scenario over real grid hours.

- **E16 — important; high confidence — P35, P44, P157. GPU-hours alone do not establish facility energy savings.** Failure: fixed energy-per-GPU-hour ignores idle power, utilization, cooling, heterogeneous hardware and transfer/checkpoint overhead; the router merely reallocates accounting. **Correction:** define the energy boundary and power assumptions, include material overheads, and show sensitivity. Keep absolute MW, MWh and carbon estimates visibly conditional.

- **E17 — important; high confidence — P166, P211, P220; A41. Input labels alone do not establish output provenance.** Failure: measured trace attributes survive into resampled arrivals or simulated savings with a misleading “measured” badge. **Correction:** require provenance on every output field plus source/assumption lineage. Distinguish observations, predictions, reconstructed workloads and simulated policy outcomes in both the contract and presentation.

3. **Insight quality.** The planned comparisons can produce useful evidence, but the current framing risks yielding “flexible jobs can move to better hours,” which the judges already know.

- **I01 — important; high confidence — P31, P39, P43–46, P188–194. Grid stress is being conflated with physical congestion.** Failure: a high-load percentile is described as congestion or reliability risk without transmission limits, reserve margins or outages. **Correction:** name the metric as a load/ramp stress proxy and state what it measures. Validate its relationship to another observable where feasible; keep congestion claims narrower than the available evidence.

- **I02 — important; high confidence — P42–46, P147–158. The design does not isolate the value of forecasting.** Failure: most savings come from generic flexibility or permanently choosing a cleaner region, while the forecast model receives the credit. This is especially relevant because cited prior work finds simple scheduling policies can capture much of the benefit. **Correction:** run the same scheduler with seasonal signals, learned forecasts and hindsight; separate time-only, location-only and combined routing. [Sukprasert et al.](https://arxiv.org/abs/2306.06502).

- **I03 — important; high confidence — P39–40, P46. “Utah headroom” can overstate both geography and feasibility.** Failure: skipping the ex-post worst N hours produces an apparent interconnection capacity number, without forecast errors, rebound load, network constraints or feasible storage charging. **Correction:** call it a PACE aggregate load-duration scenario; show the hindsight limit separately from an operational rule. Require rebound, power/energy limits, efficiency and state-of-charge accounting if storage remains. Duke’s own presentation lists network and intertemporal constraints as limitations. [Duke presentation](https://nicholasinstitute.duke.edu/sites/default/files/documents/rethinking-load-growth-webinar-presentation.pdf).

- **I04 — minor; high confidence — P10, P39–40, P193; B42. The sponsor connection crosses unsupported timescales.** Failure: hourly job scheduling is implied to demonstrate buffering of fast AI load swings or a specific Torus device’s value. **Correction:** explain the complementary roles: hourly scheduling changes the load envelope; fast storage addresses shorter fluctuations. Keep device-level claims outside the experiment.

A sharper central question is: **How much rush-hour exposure can a fixed amount of AI work avoid at a given delay budget, how much better is forecasting than a calendar rule, and when do carbon and grid-stress objectives disagree?** That supports a defensible result even when the optimizer adds little value.

4. **Visualization and demo.** An excellent offline demonstration is achievable, but the plan spends too much effort on rendering variety before securing the shortest complete story.

- **V01 — important; high confidence — P187–195, P333; B10–11. An eight-minute story does not fit an eight-minute demo-plus-Q&A slot.** Failure: the presenter reaches the result as judging ends. **Correction:** rehearse a four-to-five-minute core demonstration, with optional branches for longer slots and direct navigation to methodological evidence during questions.

- **V02 — important; high confidence — P16, P94, P197, P210, P221, P288. “Static build” is not a complete offline packaging strategy.** Failure: map glyphs, sprites, workers or assets still require a network; PMTiles serving fails; the transferred laptop cannot launch the chosen server. **Correction:** bundle all dependencies and a tested launcher, cap map extent/zoom, and cold-start with network disabled and caches cleared on the actual laptop. PMTiles normally requires a local server supporting range requests. [Protomaps documentation](https://docs.protomaps.com/pmtiles/).

- **V03 — important; high confidence — P195, P220, P301. Explore mode promises more combinations than frozen artifacts may contain.** Failure: a judge chooses an unsupported region/day/policy/wait combination and sees fixtures, stale results or unjustified interpolation. **Correction:** include an explicit scenario-availability manifest in the results contract and expose only supported combinations. Display run identity and scenario assumptions.

- **V04 — important; high confidence — P196–219, P127. The visualization toolchain multiplies integration work.** Failure: MapLibre, deck.gl, D3/visx, ECharts and GSAP compete for state, layout and animation time while three prototypes and two themes consume the first night. **Correction:** select one charting approach, one desktop theme and one visual direction early. Spend the saved time on the map/replay synchronization and the savings comparison.

- **V05 — minor; high confidence — P198–211, P216–221. Visual craft checks do not establish quantitative readability.** Failure: 3D regions obscure comparisons, normalized stress looks like comparable physical risk, or canvas content passes axe while remaining unreadable or inaccessible. **Correction:** provide a clear 2D comparison, visible units and scale definitions, keyboard-accessible controls and a static fallback. Inspect the actual laptop at presentation scale.

- **V06 — important; high confidence — P131, P194; A39. The prospective forecast is introduced after freeze without a release contract.** Failure: missing fresh inputs trigger model changes, late test-window reads bypass the evaluation logger, or the app silently presents an older snapshot as “tomorrow.” **Correction:** rehearse this production path Tuesday; permit only inference with frozen code/model, log applicable reads, show issue time and input freshness, and retain a labeled fallback snapshot.

5. **Data.** None of the named source families inherently prevents the project, but several distinctions could invalidate the proposed experiment or consume the remaining build time.

- **D01 — critical; high confidence — P91, P139, P144, P177, P283. The selected weather endpoint does not establish day-ahead availability.** Failure: Open-Meteo historical-forecast values are treated as forecasts available at a fixed earlier issue time, although that endpoint stitches the first hours of successive runs. Single-run archives have different coverage and initialization is earlier than publication. **Correction:** verify model, run, lead time and release lag before using weather. Choose a conservative reconstructable archive or a weather-free primary model; do not assume “starts around 2022” solves this. [Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api), [Single Runs API](https://open-meteo.com/en/docs/single-runs-api).

- **D02 — important; high confidence — P90, P97–101, P176. EIA ingestion needs more than completeness counts.** Failure: hour-ending timestamps, daylight-saving transitions, signed interchange, missing fuel categories or schema changes distort peaks and carbon. **Correction:** establish a UTC source contract, preserve quality flags, reconcile fuel totals and explicitly handle missing/negative values. Perform value-based profiling only before the sealed window. [EIA methodology](https://www.eia.gov/electricity/930-content/about.html).

- **D03 — important; high confidence — P92, P139–141, P179. PACE day-ahead pricing lacks the assumed historical continuity.** Failure: WEIM real-time and EDAM day-ahead prices are silently combined into a year-long comparable signal. EDAM launched on May 1, 2026, including PACE and PACW. **Correction:** identify exact products and nodes, preserve the market-regime boundary, and use a shorter separately labeled price study if needed. [CAISO market update](https://www.caiso.com/documents/market-update-jun-2026.pdf).

- **D04 — important; high confidence — P87–95, P179. Public price access is not a verified download path.** Failure: ERCOT authentication, historical-product retrieval or CAISO archive tooling blocks overnight acquisition. **Correction:** prove a small download and an older-period download for each retained price source, then cache bounded requests. ERCOT’s public historical API has registration/authentication requirements; CAISO directs older data to a historical downloader. [ERCOT portal](https://www.ercot.com/services/mdt/data-portal), [CAISO OASIS](https://oasis.caiso.com/mrioasis/logon.do).

- **D05 — important; high confidence — P31, P44, P92, P179. Wholesale price savings are not necessarily customer savings.** Failure: hub prices become a Utah facility bill estimate despite different settlement locations, demand charges or tariffs; published day-ahead prices are treated as forecasts of the wrong product. **Correction:** define market, node, settlement interval, publication time and price exposure. Label dollar results as wholesale energy-cost scenarios unless a defensible tariff is modeled.

- **D06 — important; high confidence — P95, P103, P180, P285. Trace fields require workload reconstruction.** Failure: submission-to-completion is mistaken for execution time; Alibaba GPU percentages become GPU counts; retries, missing attempts or censored jobs bias work estimates. **Correction:** audit job/task joins, queue time, attempts, resource units and exclusions on development data. Alibaba mixes training and inference; Philly includes incomplete records and spans August–December 2017, so the blanket “2–3 months” statement is inaccurate. [Alibaba schema](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-gpu-v2020/README.md), [Philly schema](https://raw.githubusercontent.com/msr-fiddle/philly-traces/master/README.md).

- **D07 — important; high confidence — P93–95, P168, P181, P303; A25, A48. Public availability is substituted for the required license/provenance record.** Failure: sources are downloaded without established reuse terms or attribution, and the proposed single manifest conflicts with the per-source convention. **Correction:** use `data/manifests/<source>.json` with URL, retrieval time, hash and license, including map assets. Preserve required attribution: Philly is CC BY 4.0 and the Protomaps basemap requires OpenStreetMap attribution. [Philly license](https://raw.githubusercontent.com/msr-fiddle/philly-traces/master/LICENSE), [Protomaps downloads](https://docs.protomaps.com/basemaps/downloads).

- **D08 — minor; medium confidence — P91, P104. A BA weather point may poorly represent its load or renewable fleet.** Failure: a convenient Utah coordinate is used as PACE-wide weather, and model error is interpreted as a forecasting-method failure. **Correction:** document the spatial approximation; use a small justified aggregation where feasible and compare it with the weather-free model.

6. **Workflow.** Worktrees and pinned reviews are appropriate. The main risks are unenforced assumptions at the handoffs and a lead responsible for too many serial decisions.

- **W01 — important; high confidence — P70–80, P244; A52, A86. Required local workflow controls are absent at the reviewed commit.** Failure: overnight agents follow references to experiment-protocol, codex-gates or viz-critique files that do not exist, leaving gates and data handling inconsistent. **Correction:** complete and smoke-test the small local skills and reviewer instructions before unattended experiments. Their absence is a setup dependency, not something to discover during the results audit.

- **W02 — important; high confidence — P71, P252–257. The permission plan does not establish unattended execution.** Failure: read-only git permissions block worktree/commit operations, while broad `make`, `npm` or `uv` permissions provide less protection than their names suggest. **Correction:** test the actual safe branch→worktree→checks→PR path and a background-job completion path before the owner sleeps; define how blocked permissions are surfaced.

- **W03 — important; high confidence — P56, P127–128, P239–240; A43–45. Shared data introduces shared mutable state.** Failure: parallel agents overwrite processed outputs or manifests, consume different preprocessing versions, or use worktree-local caches because the environment override is missing. **Correction:** verify the shared path in every worker, assign cache ownership, use versioned/atomic derived outputs, and give runs isolated destinations. Keep raw files immutable.

- **W04 — important; high confidence — P56, P118, P130, P327. A successful Codex command is not a passing gate.** Failure: automation merges after a review that executed successfully but returned `not_ready`; the shared wrapper explicitly returns zero when a valid review ran regardless of findings. **Correction:** gate on the verdict and disposition table, record the reviewed SHA, and re-review relevant fixes on the final candidate.

- **W05 — important; medium confidence — P83, P228–232. Wheel availability is overstated as environment verification.** Failure: installation succeeds but model loading, GPU execution or solver operation fails on GB10; separate dependency groups still leave incompatible runtime combinations. **Correction:** retain short install/load/infer/solve evidence for the exact pins on this machine, with a strict time limit for optional foundation models. LightGBM and a CPU-capable core should carry the presentation.

- **W06 — minor; high confidence — P168–170, P219, P321. Reproduction promises byte-identical artifacts without defining stable content.** Failure: timestamps, serialization metadata or GPU numerical variation break hashes despite equivalent results; model or frontend dependencies drift. **Correction:** pin checkpoints and frontend dependencies, preserve run-to-artifact lineage, and define deterministic canonical hashes or documented numerical tolerances where exact equality is inappropriate.

- **W07 — minor; high confidence — P310. Asking the owner to paste a key creates avoidable transcript exposure.** Failure: the EIA key enters chat or review logs instead of only the ignored environment file. **Correction:** instruct the owner to set it locally and verify presence without printing its value.

- **W08 — minor; high confidence — P20–23, P50–56. Setup instructions describe an empty repository rather than the reviewed state.** Failure: agents initialize or scaffold a second location, duplicate existing foundations or start from the wrong checkout. **Correction:** identify the current starting commit and remaining setup work, preserving the historical start-state description as dated context.

7. **Cut or add.** Findings F02, F04 and V04 mean the present cut order will not protect completion: it preserves nearly all integration-heavy work.

I would propose these cuts, with owner approval wherever a Must changes:

| Cut or defer | Preserve or add |
|---|---|
| Foundation-model comparison, Qwen captions, bidding and throttling | One dependable forecast model and strong seasonal baselines |
| Storage/headroom study until the core result works | PACE delay-versus-benefit frontier with service constraints |
| Cross-region animation until static spatial baselines are sound | Explicit time-only versus location-only comparison |
| Three prototypes, dual themes, mobile polish and overlapping chart libraries | One polished laptop layout, synchronized replay and readable uncertainty |
| Unrestricted Explore combinations | A frozen, fully supported scenario catalog |
| Full complexity across all ten BAs | A complete PACE path; a thinner regional overview if approved |

The highest-value additions are an availability/vintage table, explicit seal-opening record, runtime budget, completed-work accounting, forecast-value ablation and a four-to-five-minute demo script.

I would structure the revised plan around deliverable gates:

1. **Data viability:** available evaluation extent, source timing, licenses and one reconstructed workload; no sealed-value exploration.
2. **Spec approval:** one primary question, fair baselines, causal information rules, accounting boundaries and the results contract.
3. **First complete slice:** PACE validation result exported into the actual offline map and replay.
4. **Validation freeze:** select models/policies and scenarios; prove runtime and laptop operation.
5. **Sealed evaluation and audit:** registered comparisons, paired uncertainty, all findings dispositioned; experiments stop Wednesday 11 AM.
6. **Presentation release:** frozen artifacts, timestamped prospective forecast, video/deck fallback, short and extended rehearsals.

Verdict: not_ready
---

## Dispositions (Claude, 2026-10-26 23:30 MT)

Reviewed: `main @ 88ab93a`, run `20261027T045628Z-9e4972`, Sol 6.1 (review profile), verdict `not_ready`. Each finding was checked against the plan text.

**Legend.** *spec* means the item is closed in the experiment spec (Phase 2), which is gated by Astra. *owner* means it needs the owner's decision because it changes a Must or the headline.

### Feasibility

| ID | Disposition |
|---|---|
| F01 | **Fixed, spec.** The sealed boundaries stay. The test window ends at an immutable availability cutoff: the last complete day in tonight's frozen snapshot. Every result states the covered days. |
| F02 | **Owner.** Proposed: the first deliverable is one complete PACE slice (forecast → router → replay → offline dashboard). The other regions get a thinner overview unless time allows more. |
| F03 | **Fixed** (plan amendment). Wed 11:00 is the only experiment deadline; 11:00–14:00 is packaging of frozen results. |
| F04 | **Fixed, spec.** The core time-only story is complete on its own. For each optional feature, the spec lists the claims and scenes that disappear without it. |
| F05 | **Fixed, spec.** Runtime is benchmarked on a representative workload before sweeps, with a rolling horizon, solve limits and fallbacks. Solver status and gaps are recorded. |

### Experimental soundness

| ID | Disposition |
|---|---|
| E01 | **Fixed** (AGENTS.md, hackathon-evidence). The seal opens only after spec approval *and* frozen model and policy configs at a recorded commit. Each read logs input, code and config hashes plus the purpose. Results shown at G2 and G3 are validation results. |
| E02 | **Fixed, spec.** Event time, availability time and vintage are distinguished. Only the current EIA vintage exists, so conservative lags are used and the revision limitation is disclosed. |
| E03 | **Fixed, spec.** Every fitted transform, threshold and coefficient has a registered fitting window, and the tests check those windows. |
| E04 | **Fixed, spec.** Foundation models: checkpoint revision and documented training coverage are recorded, and the results are qualified where independence can't be shown. |
| E05 | **Fixed, spec.** Online information rules: future arrivals are never visible; runtime is known as an assumption, with a noisy-estimate sensitivity; the rule at the forecast horizon's end is defined. Future arrivals are hindsight-only. |
| E06 | **Fixed, spec.** All policies get identical jobs, capacity, constraints, issue times and scoring hours. Added: a seasonal-profile scheduler and a static best-site spatial baseline chosen on validation. |
| E07 | **Fixed** (hackathon-evidence, plan verification). Only a solver-certified hindsight optimum on the same objective and feasible set is a bug check. Every other ordering is a result, and negative results are accepted. |
| E08 | **Fixed, spec.** A common accounting cohort, with warm-up and drain periods. Completed work, misses, backlog, wait percentiles and an energy reconciliation are reported. |
| E09 | **Spec + owner.** One registered primary objective with guardrails, scaling from train and validation, and common denominators, with every component reported. Which objective is primary is the owner's call. |
| E10 | **Fixed, spec.** Quantile forecasts with validation-only calibration; pinball loss / WIS, plus coverage and width by lead and region; scaled errors instead of MAPE near zero. |
| E11 | **Fixed, spec.** Common time blocks across regions and policies, one continuous simulation, and trace-generation seeds reported separately from grid-week uncertainty. The sensitivity to block length is checked. |
| E12 | **Fixed, spec.** Primary comparisons are selected on validation, with dependence-aware inference. The "prior year" is development evidence. Exploratory comparisons are labeled as such. |
| E13 | **Fixed, spec/UI.** The wording is "attributed operational emissions (production-based average)". Production vs consumption accounting is distinguished. |
| E14 | **Fixed, spec.** The marginal regression is an exploratory association proxy fitted on development data, with its instability reported. |
| E15 | **Fixed, spec.** A seeded, block-based trace mapping with defined time-zone alignment, seams and scale, described as a "synthetic workload scenario over real grid hours". |
| E16 | **Fixed, spec.** The energy boundary, power assumptions and overheads are defined, with sensitivity. Absolute MWh and tCO₂ figures are shown as conditional. |
| E17 | **Fixed, spec.** Every output field in the results contract carries its label and lineage. |

### Insight

| ID | Disposition |
|---|---|
| I01 | **Fixed, spec.** Renamed "net-load stress proxy", checked against prices where they exist, and never called congestion. |
| I02 | **Fixed, spec.** Ablation: seasonal profile vs forecast vs hindsight, and time-only vs place-only vs both. |
| I03 | **Fixed, spec.** Reframed as a "PACE load-duration scenario". The hindsight limit is shown separately from an operational rule. Storage needs state-of-charge accounting, or it is deferred. |
| I04 | **Fixed** (narrative). Hourly scheduling shapes the load envelope; fast storage handles shorter swings. No device claims. |

### Visualization and demo

| ID | Disposition |
|---|---|
| V01 | **Fixed** (plan). A 4–5 minute core demo, with optional branches for longer slots. |
| V02 | **Fixed** (plan). A bundled launcher plus a single-file fallback, cold-started on the MacBook with the network off. The PMTiles path was already dropped in favor of Natural Earth. |
| V03 | **Fixed, spec.** A scenario-availability catalog in the contract; Explore offers only the combinations in it. |
| V04 | **Partly accepted.** One charting library (ECharts) plus deck.gl/MapLibre; GSAP dropped; one theme; desktop only. The owner's practice of 2–3 named directions is kept, but as *single-screen static mockups*, not prototypes. |
| V05 | **Fixed** (UI). 2D comparisons carry the analysis; 3D is decorative only. |
| V06 | **Fixed** (plan). The prospective forecast is rehearsed Tuesday: frozen code and model, inference only, freshness shown, a labeled fallback snapshot. |

### Data

| ID | Disposition |
|---|---|
| D01 | **Pending recon.** The grid agent is comparing Open-Meteo's Historical Forecast, Previous Runs and Single Runs APIs. If none is reconstructable, the primary model is weather-free. |
| D02 | **Fixed** (pipeline task). UTC source contract, quality flags kept, fuel totals reconciled, negative and missing values handled. |
| D03 | **Fixed, spec.** PACE prices: the EDAM day-ahead regime since 2026-05-01 is kept separate from earlier WEIM real-time prices, as a separately labeled price study. |
| D04 | **Pending recon.** Each price source must show a small download and an older-period download before it is relied on. |
| D05 | **Fixed** (labels). Dollar figures are "wholesale energy-cost scenarios". |
| D06 | **Pending recon + spec.** Trace reconstruction audit: queue vs execution time, GPU units, retries, censored records. The plan's "2–3 months" wording is corrected per trace. |
| D07 | **Fixed.** Per-source manifests with licenses. Attributions go into `provenance.json` and the UI credits. |
| D08 | **Fixed, spec.** 2–3 weighted points per BA, documented, plus a weather-free comparison. |

### Workflow

| ID | Disposition |
|---|---|
| W01 | **Fixed** in `a85e957`: the skills exist and are validated, and the plan is amended. |
| W02 | **To do tonight.** The data-profile commit goes through a real worktree → PR → merge path as a smoke test, and a background-job completion is checked. |
| W03 | **Fixed** (AGENTS.md). Derived outputs are written atomically and versioned; each run writes only to its own directory. |
| W04 | **Fixed** (codex-gates). A gate passes only on a `ready` or `ready_with_minor_fixes` verdict with every finding dispositioned. The SHA is recorded, and fixes are re-reviewed on the final candidate. |
| W05 | **Fixed** (plan). Install, load, infer and solve evidence is kept for the exact pins. Foundation models are timeboxed to 2 h; LightGBM and the CPU core carry the result. |
| W06 | **Fixed** (hackathon-evidence). Canonical hashes or numeric tolerances; checkpoints and frontend dependencies pinned. |
| W07 | **Fixed.** The owner was told to set `.env` locally, never in chat. |
| W08 | **Fixed** (plan amendment). The start state is dated context; current state lives in `docs/HANDOFF.md`. |

**Re-check:** this is folded into the Astra spec gate. The plan items above are amendments, and the experimental items are closed in the spec that Astra reviews.
