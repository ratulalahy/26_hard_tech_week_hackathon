# GridPilot: when should a Utah AI job stay, wait, or travel?

**Reconciled spec, 2026-10-27.** It combines two independent proposals:
- the base text is Codex's proposal (`2026-10-26-gridpilot-design-codex.md`);
- Claude's proposal (`2026-10-26-gridpilot-design-claude.md`) contributed the amendments tagged [R1]–[R6], listed in §14.

Status: candidate for the fresh Astra soundness gate, then owner approval (G1). No experimental result is claimed, and the test seal stays closed.

## 1. The entry and the claim

Build one product: a day-ahead grid report connected to an AI batch-job scheduler. Start in PacifiCorp East (PACE), then visibly place eligible jobs in California (CISO), Bonneville (BPAT) or Nevada (NEVP) [R1], subject to finite compute capacity, deadlines, and transfer overhead. A national overview supplies context; these four core sites receive the full experiment.

The question is: **How much does knowing tomorrow's grid help an operator who already knows which regions are usually cleaner?**

The strongest demonstration is a job that has a credible reason to stay, wait, or travel, accompanied by a complete accounting of the work. The aggregate result must distinguish:
- the value of access to another location;
- the value of allowing a delay;
- the additional value of forecasting;
- the conditions under which the apparent benefit disappears.

A large saving relative to running everything in Utah does not establish forecasting skill. A forecast can lose to a fixed-region rule. Either outcome is acceptable evidence.

Owner requirements remain fixed: emissions first; Utah/PACE first; **regional placement in the core**, as expressly required by the current owner instruction; offline MacBook Pro/Chrome delivery; experiments freeze Wednesday 2026-10-28 at **13:00 MT**, final displayed numbers by **14:00 MT**. A tagged, checkable build with real validation results is due Tuesday at **18:00 MT**. This proposal supersedes my earlier suggestion to leave regional placement until later. The test seal remains unchanged.

The intended final wording is conditional on the actual result:

> In simulation, using a public AI workload and historical grid data over [covered dates], this policy changed attributed operational CO2 by [signed result] while executing the same GPU-hours within [declared deadlines]. Its additional benefit over [strong simple policy] was [signed result]. Capacity, power, and transfer assumptions are visible.

Do not substitute “useful training completed,” model quality, physically avoided CO2, a cloud-bill saving, or relieved transmission congestion for the quantities actually evaluated.

## 2. What the profiles change

The design uses the three committed profiles, rather than another author's design:
- [Grid and weather](../../data-profile/grid.md)
- [Workloads and prices](../../data-profile/workloads-prices.md)
- [Offline geography](../../data-profile/geo.md)
- [Owner decisions](../../brief.md) and [agent/evidence rules](../../../AGENTS.md)

The following are **profile findings, not new measurements or held-out results**:

| Finding and evidence class | Consequence |
|---|---|
| BPAT was cleaner than PACE in every profiled validation hour on the profile's production basis; its consumption estimate was substantially higher than its production estimate (**modeled**, grid §8). | Consumption-based intensity is primary. A capacity-constrained fixed clean-region baseline is mandatory. |
| PACE's demand and carbon intensity had a negative validation correlation (**modeled statistic from observed/modeled inputs**, grid §8). | Carbon and grid-stress outcomes must remain separate; a low-carbon decision can increase stress exposure. |
| Seren's jobs longer than a day carried 64.0% of its GPU-hours (**measured**, workload §1.2). | Preserve full durations and gang size. No hourly restart or free checkpointing in the main experiment. |
| Cancelled Seren attempts carried 67.2% of GPU-hours (**measured**, workload §1.4). | Include their consumed budgets. Completed status is not a proxy for all energy, and consumed GPU-hours are not a quality-adjusted work metric. |
| The BA demand forecast reaches EIA too late for our prior-day issue (**observed publication metadata**, grid §7). | It is a later-information diagnostic, not an input or an equal-information baseline. |
| PACE has no pre-seal day-ahead price training history (**observed source availability**, workload §2). | Use consistent real-time wholesale marks for secondary accounting; do not train on the sealed EDAM regime. |
| Weather is still being downloaded and fixed-lead archives require an issue-time audit (**observed source metadata**, grid §9). | The core model works without weather. Weather must earn inclusion before configuration freeze. |
| Local vector/raster map assets already exist (**observed artifact inventory**, geo profile). | Spend visual effort on decisions and replay, rather than tile infrastructure. |

I challenge two interpretations in the profiles. A high R-squared for a CO2/net-load regression does **not** identify causal marginal emissions. Also, repeating or resampling a short workload does **not** create independent evidence from additional real clusters.

## 3. Pre-registered questions and success conditions

**H1 — placement under limits.** A forecast-guided placement-and-delay policy reduces attributed CO2 relative to immediate execution at PACE, under the same fleet and workload. This establishes conditional operational opportunity, not forecast value.

**H2 — forecast value.** With the same scheduler, feasible actions, power model, and jobs, learned forecasts improve realized attributed CO2 relative to seasonal forecasts. Compare the paired difference; do not conflate it with H1.

**H3 — beyond a fixed clean destination.** Dynamic placement-and-delay improves on a capacity-constrained, training-ranked destination rule. This is the skeptical judge's main challenge.

**H4 — limits.** The gain changes with destination capacity, acceptable waiting, transfer overhead, mobility, and the carbon-accounting basis. Find the boundary where a move ceases to help, rather than optimizing assumptions until the percentage looks large.

A result qualifies as a deadline-preserving saving only if all policies in the stated comparison:
1. receive exactly the same attempted-work cohort and declared budgets;
2. execute every cohort GPU-second, including failed/cancelled attempts' declared budgets;
3. have zero deadline misses, no discarded or rejected cohort jobs, no unfinished cohort work, and no capacity violations;
4. reconcile energy and CO2 from the schedule ledger.

These are hard eligibility conditions, not penalty weights in the objective. An infeasible policy is shown as infeasible. Its partial-execution carbon reduction is never shown as a saving. A feasible simple baseline can become the recommended policy if the learned policy fails. Do not shrink the primary cohort or relax deadlines after seeing test results.

A forecast-improvement claim requires the paired uncertainty interval for the pre-registered H2 contrast to exclude zero in the favorable direction. Otherwise report the estimate and uncertainty as inconclusive or adverse. No minimum positive saving is assumed.

## 4. Regions, data, and accounting boundary

### Four core sites and ten overview regions

Core placement set: **PACE, CISO, BPAT, NEVP** [R1]. This is a deliberately difficult test: the hero has substantial fossil generation, California has a changing daily mix, and the hydro destination provides a strong static alternative.

Overview set: **PACE, CISO, BPAT, NEVP, AZPS, PSCO, ERCO, SWPP, MISO, PJM**. Overview regions have real historical demand/net load and clearly identified forecast channels. Only the core placement set has a routing-capacity assumption; the map must not imply GPUs are available in every overview region.

Use EIA code CISO, with “CAISO” as the human-facing name. A job arc represents movement of a computation request, not electricity, a physical transmission path, or an existing data center. Site points are illustrative regional endpoints, labeled modeled. Do not infer a facility location from a BA polygon.

### Frozen inputs

Use source snapshot 05efabe781cc in [snapshot.json](../../../data/manifests/snapshot.json) as the starting inventory. It is not a blanket authorization to use a growing source. Record the exact manifest hashes and output-table hashes in each run. In particular, the weather manifest must be frozen separately before weather is used.

Shared cache: /home/nvidia/workspace/personal/projects/26_hard_tech_week_hackathon/data, read-only from this checkout. No downloads or cleaning writes are authorized for this planning task.

### Primary carbon signal

Primary truth and forecast target: **EIA's modeled consumption-based hourly CO2 intensity**, from the BA workbooks, converted to g CO2/kWh. This includes EIA's treatment of imports. It is an accounting estimate, with reporting and flow-model limitations, not a measured response to adding our load.

Retain the workbook's original units, conversion, column identity, interval boundaries, and lineage. A conversion test must distinguish pounds from grams and kWh from MWh. Store production-based intensity alongside consumption-based intensity.

The core simulation treats the workload as small enough not to change the historical grid mix or prices. No dispatch response, renewable additionality, contractual renewable matching, embodied emissions, or facility construction is modeled.

Secondary carbon views:
- Reprice the **same schedules** on EIA production-based intensity. This isolates accounting sensitivity.
- A fuel-mix reconstruction is a separately named modeled diagnostic, with fixed factors and an explicit storage denominator. It never silently replaces missing consumption values.
- Marginal analysis is a diagnostic described in §10. It cannot turn the primary number into “CO2 avoided.”

Reject negative/nonfinite intensity values as invalid; zero can be valid. Record all rejection reasons. Do not cap high realized intensities or fill evaluation truth with a forecast.

### Price and stress

Use PACE ELAP_PACE-APND FMM/RTPD real-time prices, averaged only from complete constituent intervals, consistently across validation and test. California's NP15 price is a **hub proxy**, not a BA-average electricity rate. BPAT real-time ELAP accounting is optional only if its frozen source metadata and coverage are verified before opening test.

Missing price is null with an explicit reason, never zero. Report a complete-fleet wholesale energy-cost scenario only when all destinations have comparable, verified marks. Otherwise show PACE-only time-shift cost and individually priced energy shares; do not label the partial total a fleet saving. No synthetic PACE day-ahead history, pre-EDAM DAM interpretation, cloud rental costs, or egress bill is required.

Net load is demand minus wind and solar, using the harmonized parent fuel categories exactly once. It is a **grid-stress proxy**, not transmission congestion or available interconnection capacity.

For each BA, fit an empirical net-load CDF and its 95th-percentile threshold on the training window. Freeze them before the period they score. The report shows forecast net load, its training-relative percentile, and whether it exceeds that threshold. Test values can exceed the training range; do not rescale using the test maximum.

Secondary stress outcomes are execution energy in above-threshold hours, energy-weighted net-load percentile, and the change in those quantities. A positive stress change is a real tradeoff, not a reason to redefine the carbon objective.

## 5. Time, splits, and what the scheduler is allowed to know

### Seal and coverage

Training/development values must be strictly before 2025-11-01T00:00Z. Validation reporting uses [2024-11-01T00:00Z, 2025-11-01T00:00Z). The sealed bounds remain **[2025-11-01T00:00Z, 2026-11-01T00:00Z)**.

The common evaluation cutoff F is the earlier of the sealed end and the last complete UTC day supported by the frozen core carbon/demand snapshot. Choose it from completeness metadata, not favorable outcomes. The profile's currently established grid cutoff is 2026-10-25T00:00Z; verify consumption-intensity completeness before locking F. An earlier legitimate cutoff must be documented. Do not claim a full twelve months.

Only the approved evaluation entry point may open sealed values, after the reconciled spec is approved and code/configuration hashes are frozen. Append an entry for each invocation to results/test_reads.jsonl, including purpose, time, code/config/input hashes and covered fields. This proposal does not open the seal.

### Issue time and horizon

Issue once daily at **10:00 America/Denver**, for the next Utah civil day. That day contains 23, 24, or 25 hours. The same UTC target intervals apply to every BA, with local clocks available for inspection.

At an arrival time, the scheduler uses only forecast records whose issue time is at or before the arrival. Use the newest eligible record for each target hour. For long jobs extending beyond issued forecast coverage, use the frozen training calendar climatology for the entire uncovered tail and tag it as a modeled forecast component. Never ignore tail energy, truncate the job to a day, or use realized future intensity.

Main forecast inputs obey these deliberately conservative availability envelopes (**assumed availability rules**, not archived receipt timestamps):
- Demand: hour end plus 2 hours.
- Fuel mix and total interchange: hour end plus 48 hours.
- Consumed and generated carbon estimates, and bilateral interchange: hour end plus 96 hours.
- Later-published BA demand forecasts: excluded from the operational input set.
- Prices: not needed by the carbon scheduler. Any later price-forecast extension needs its own availability rule.

These envelopes simplify the differing source schedules. The EIA documentation separately identifies slower bilateral-flow and imported/exported-carbon publication. Do not use the faster generation schedule for consumption intensity.

The data is a **publication-lagged replay of a revised historical snapshot**. Publication delays are enforced, but historical revisions and retrospectively updated emission factors cannot be reconstructed from this bulk cache. State this limitation beside the forecast evaluation. Do not call it an exact reconstruction of information available to a historical operator.

### Model fitting and selection

Validation models are fitted at 2024-10-29T00:00Z, using target history from 2022-01-01 through the last label available under the target's envelope at that fit time. Test models are fitted once at 2025-10-29T00:00Z using the analogous history from 2023-01-01. The earlier fit dates permit forecasts covering the UTC/local-day boundary at the start of each evaluation period.

All model weights, fit windows, scalers, thresholds, calibration residuals, lookup tables, and configuration choices are frozen for the corresponding evaluation. No model refitting on sealed outcomes. Lagged test observations may become inputs to later test forecasts under the pre-registered publication envelopes; this is authorized only through the logged evaluation entry point.

Reconstruct features at each historical issue time, not by shifting a completed table indiscriminately. For example, a weekly target lag can be available while yesterday's value for a late target hour is not.

Selection uses validation only, with a selection/calibration cutoff of 2025-10-24T00:00Z so those labels are available before the final fit and the first test forecast. Later pre-seal validation hours may be reported descriptively but cannot select the deployed policy, parameters, or calibration. Because the profiles already exposed the validation year, validation comparisons are development evidence, not an untouched confirmation set. Report this explicitly.

## 6. Forecast experiment: make the decision signal earn its complexity

Forecast four targets per core BA: demand MW, wind MW, solar MW, and consumed intensity g/kWh. Derive forecast net load by subtraction. Do not predict five inconsistent versions of the same quantity.

Required candidates:
1. **Last available value:** persistence using the publication envelopes.
2. **Weekly seasonal:** median of the available target-hour lags at 168, 336, 504, and 672 hours. If none exists, use training calendar climatology.
3. **Calendar climatology:** training median by BA, local month, local hour, and weekday/weekend; progressively back off to month/hour, hour, then BA median.
4. **Histogram gradient boosting:** per BA and target, using scikit-learn HistGradientBoostingRegressor already in the project dependency family.

The learned model uses target calendar features, forecast lead, available weekly target lags, latest available observations, trailing available means/ranges, and missingness indicators. Demand models can use recently published demand; carbon/generation models respect their slower envelopes. Use one explicit IANA zone per BA: PACE America/Denver, CISO and BPAT America/Los_Angeles, NEVP America/Los_Angeles [R1]. The overview zones are registered explicitly, rather than inferred from EIA's published local timestamp.

Bound the search to two parameter sets (**assumed modeling choices**): max_leaf_nodes in {15, 31}, max_iter=200, learning_rate=0.05, min_samples_leaf=48, l2_regularization=1.0, squared-error loss, early_stopping=False, random_state=42. Do not let an internal random validation split select boosting iterations. Training medians for missing inputs and any scaling are fitted only on the stated training data; keeping native target units per BA avoids a pooled size imbalance.

Clip physically nonnegative predictions at zero. Preserve unbounded high predictions and log clipping counts. Solar's zero-at-night rule must use a documented astronomical/calendar method or be omitted; do not infer the test year's night mask from realized solar output.

Within the two boosting configurations, choose the learned candidate by validation-selection MAE. For the traffic report, also choose the best forecast family by that same MAE, breaking ties in favor of seasonal, climatology, persistence, then boosting. Keep all candidates' scores and identify exactly which forecasts each routing policy consumes. H2 compares the fixed learned candidate with the seasonal candidate in the **same scheduler**, even if the deployed choice is seasonal. Do not claim ML value when the selected system is using a simple forecast.

Report:
- MAE and signed bias in native units, normalized MAE using the training mean for demand/generation;
- daily error distributions, peak-hour timing error for demand/net load, stress-event precision and recall;
- carbon error weighted both uniformly and by an independently fixed reference execution profile;
- decision regret using realized carbon for candidate actions under a common reservation state, identified as a diagnostic rather than the policy's achieved yearly result.

Do not use MAPE for zero/near-zero wind, solar, or carbon. Prediction intervals may use 10th/90th percentiles of daily-forecast residuals before the validation-selection cutoff, frozen for test, with actual coverage and width reported. Such intervals are empirical and have no guaranteed conditional coverage. Do not call their score CRPS.

The BA's published demand forecast appears only in a later-information comparison, with a visible publication caveat. PACE is scored as published; CISO/PJM reported and profile-suggested shifted diagnostics are separate. No headline “beat the utility forecast” based on a mismatched information set.

**Weather experiment, optional:** only frozen Previous Runs archives, no observed/reanalysis or unsuffixed stitched nowcasts. Keep the weather-free candidate as the core. Use fixed-lead fields only after verifying, for every feature, that its latest possible initialization plus a conservative publication latency precedes the issue. Account for the source label versus stored hour-start offset. For far targets a field named previous_day2 is not automatically safe; use a larger available lead or omit the feature. A single Salt Lake City forecast is not evidence of BA-wide wind/solar conditions. Compare weather/no-weather on identical dates starting no earlier than the common honest archive coverage. Admit weather only by Tuesday 10:00 MT if its lineage audit and validation comparison finish; otherwise record its deferral. No new downloads are necessary for the core.

## 7. Workload: preserve the expensive jobs and expose the assumptions

### Primary trace and work definition

Use **Acme Seren**. Keep every GPU attempt with finite, positive GPU count and finite, positive measured execution duration, regardless of final status. Do not deduplicate retries without a documented attempt identifier; do not invent checkpoint chains from cancelled records. Audit GPU request/count semantics and remove only explicitly logged malformed records.

Each retained attempt becomes a **run-to-budget request**: its measured GPU count and duration define a declared service budget. The simulator knows this budget at arrival (**assumed**); it is not predicting a future failure or successful completion. Trace duration remains measured; its availability as a declared budget is assumed. The outcome is attempted GPU-work delivered, not equal model quality.

Primary jobs are non-preemptive gang jobs: all requested GPUs run together at one site for the full measured duration. No cross-region execution after starting, no intra-job splitting, and no checkpointing in the main experiment.

### Replay calendar

Avoid week-block resampling in the primary replay because the energy-heavy multi-day attempts cross block boundaries. Use the continuous Seren arrival sequence as one cycle:
- Source cycle starts at 2023-03-06T00:00:00+08:00 and lasts 161 days, an integer number of weeks wholly inside the profiled source span.
- Select attempts by submission within that cycle, retaining their complete durations even when execution extends past the source-cycle boundary. If the actual source schema contradicts this support, fail the input audit and correct the source-only boundary before configuration freeze.
- Remove the UTC+8 wall-clock offset and anchor the first cycle to Monday 2024-01-01 00:00 **fixed UTC−07:00** for the primary calendar. Repeat the whole 161-day cycle in order; duplicate IDs include the cycle number. This preserves within-cycle elapsed timing, weekday, burst structure and long durations.
- Fixed UTC−07 is a stated synthetic business clock. In summer, replayed arrivals appear one hour later on Utah's civil clock. A civil-time alignment is a separate sensitivity, with DST gap/fold handling logged.
- Pre-register phase offsets of 0, 49, and 98 days, all whole weeks. Phase zero is primary; the other phases are workload-alignment sensitivities, not additional independent clusters or independent grid years.

Use mapped **submission** times as arrivals, not measured historical start times. Historical queue time is descriptive only; it is not secretly supplied as a future start reservation. The simulator creates its own queue and schedule.

No load multiplier in the primary result. The whole-cycle repetition and US-clock mapping are **simulated**. State the number of unique source attempts, repeated instances, GPU-hours, and fraction of energy in long and large attempts.

### Flexibility and hardware assumptions

Assumption registry, frozen before test:

| Parameter | Primary choice, labeled assumed | Required sensitivity |
|---|---|---|
| Flexible request eligibility | Pretrain, SFT, MLLM, Eval are candidates; SHA-256 of source attempt ID and seed 42 selects half of candidate requests. The same flag persists across repeated instances. | No flexible jobs; all candidates flexible. Report realized job and GPU-hour shares, not “50% of energy.” |
| Allowed start delay | Eligible Pretrain/SFT/MLLM: 6 h; eligible Eval: 1 h; other requests: 0 h. | Batch delay 0 h and 24 h; Eval remains bounded at 1 h. |
| Mobility | Flexible jobs may be placed before execution at any core site with enough GPUs. Software/data compatibility and site-equivalent A100-class throughput are assumed. | Restrict mobility to jobs requesting at most 8 GPUs; this exposes the energy cost of multi-node data gravity. |
| Home GPU capacity | 2,288 GPU slots, from the profiled Seren cluster, treated as an assumed replay capacity. | 1.25× home capacity, rounded to an 8-GPU node. |
| Destination spare capacity | 512 slots each in CISO, BPAT and NEVP [R1]. These are spare compute reservations, not inferred grid headroom. | 0 and 1,024 each. The zero case is time-only. |
| Remote transfer time | 30 min before execution; no delay for staying home. | 0 and 120 min. Transfer time consumes the same deadline slack as waiting. |
| Remote transfer energy | 5% of the job's modeled full active IT energy, half attributed at the source and half at the destination. Book this energy at arrival, when staging begins, under an assumed instantaneous accounting convention. | 0% and 20%. No actual dataset sizes or network power were measured. |
| Active IT power | 0.60 kW per allocated GPU slot, including its host allocation. | 0.40 and 0.80 kW; changing GPU generation does not imply faster work. |
| PUE | 1.20 at each site. | Remote PUE 1.10 and 1.56 with home fixed. |
| Idle IT power | 0.20 kW per provisioned slot, as a meter-accounting sensitivity. | 0 and 0.30 kW; no claim of automatically powering servers down. |

A request's deadline is arrival plus declared execution duration plus allowed start delay. Transfer plus queueing must fit in the latter. An inflexible job has no discretionary delay; capacity overload is therefore visible as a deadline failure, not silently absorbed.

The primary workload is not guaranteed to fit the recorded cluster when replayed at submission times. **That is an input feasibility question to answer on validation**, rather than a reason to use historical future starts. If the recorded capacity makes the primary cohort infeasible, report that case. The pre-registered 1.25× capacity case may provide a separate feasible planning result, but must be called a larger-capacity scenario; it cannot replace the primary result unnoticed.

Declared runtime is a consequential assumption. Add a stress replay in which actual service is 25% longer than declared, with fixed original deadlines and no rescheduling of running jobs. Update reservations as overruns become known; report capacity/deadline failures and completed GPU-hours. This case measures fragility; it is not an excuse to retune.

## 8. Scheduler and fair comparators

### Core policy: deterministic reservation search

Maintain an event-time reservation ledger. At each arrival, expose only that request, earlier requests/reservations, and forecasts already issued. Future arrivals and realized future grid values are unavailable to operational policies.

Process simultaneous arrivals by deadline, then stable attempt ID. Already running jobs and committed reservations are immutable. For a flexible job:
1. Enumerate its immediate start, every UTC-hour boundary up to its latest allowed start, and reservation-release instants within that window, at each allowed site.
2. A remote start must follow transfer time. Require enough simultaneous GPUs throughout the full execution interval and finish by the deadline.
3. Integrate forecast intensity over the complete job interval, using exact overlap with hourly intensity and the registered tail climatology. Include the transfer-energy attribution.
4. Choose the minimum predicted total CO2 action. Break numeric ties within 1e-9 kg by earlier completion, staying at PACE, then lexical BA code and start time. Reserve it immediately.
5. If no feasible action exists, retain the job in a late-work queue, schedule it at its earliest available legal site, finish its full budget, and mark the policy infeasible. Never drop it or call a late schedule feasible.

For inflexible jobs, use the immediate PACE action if feasible; otherwise finish the budget late and record failure. The chosen policy is an implementable heuristic, not a globally optimal scheduler. Reserving a flexible job can disadvantage a later unknown arrival: the zero-miss eligibility test is essential, and a production admission guarantee is outside this prototype.

Capacity is checked against exact overlapping execution intervals, not hourly mean GPU use. Energy uses exact measured durations, not durations rounded up to an hour. Several minute-long jobs may share an hour but may not overlap above the slot cap.

### Required comparison table

All policies have the same fleet, transfer overhead, job flags, power assumptions, deadlines, and input visibility unless explicitly marked hindsight. Unused destination slots are still part of the fixed fleet in the idle sensitivity.

| ID | Policy | Purpose |
|---|---|---|
| U | Earliest feasible execution at PACE, stable FIFO with the specified simultaneous-arrival tie break; no intentional carbon delay. | Local operational reference. “Run immediately” is descriptive only where capacity permits it. |
| G | Earliest feasible execution across the core sites, ordered by earliest finish then home then BA code; no carbon input. | Separates extra capacity access from carbon-aware placement. |
| S | Fixed clean-region priority: rank by training mean consumed intensity, try earliest feasible completion at each ranked site with the same remote overhead and deadlines, then home/late handling. | Strong “just use the usually clean region” baseline. |
| K | Exact same carbon reservation search as the learned policy, driven only by frozen calendar climatology. | Cost of sophisticated prediction versus a calendar rule. |
| W | Same search, driven by available weekly seasonal forecasts. | Main equal-information forecast baseline. |
| L | Same search, driven by the fixed learned forecasts. | H2 candidate; failure or underperformance is publishable. |
| H | Same search with realized carbon substituted for predicted carbon, with future arrivals still hidden. | Hindsight heuristic diagnostic, **not** a certified optimum or upper-bound ordering check. |

Run a PACE-only restriction of W and L (time-only), and a zero-discretionary-delay restriction of W and L (place-only). For place-only, remote staging is pre-completed with zero transfer latency **in every compared policy in that specific sensitivity**, while its energy charge remains; label that additional assumption. Otherwise a zero-wait request could never travel under the main transfer model. Do not compare differently defined feasible sets as if they isolate forecast skill.

The deployed product policy is chosen from U/G/S/K/W/L by validation: first require the hard feasibility conditions, then minimize aggregate attributed CO2; tie-break on lower mean wait, then simpler policy order U, G, S, K, W, L. Preserve L as a separate experimental candidate even if deployment selects S or W. Freeze that choice before unsealing.

### Relaxed hindsight bound and certification

For every job, find its minimum realized CO2 over every continuous start time within its legal window and allowed sites, including transfer overhead, **while ignoring competition for slots**. This start set contains the operational policy's candidates. With piecewise-constant hourly intensity and transfer energy booked at arrival, the execution integral is piecewise linear in start time: evaluate both window endpoints, each hourly boundary, and each hourly boundary minus the job duration within the window. The minimum over this finite set is exact for the stated relaxation. Sum the independent minima to obtain C_relaxed, a lower bound on full-cohort CO2. Therefore C_U − C_relaxed is an **optimistic upper bound on possible reduction**, not an achievable schedule.

Verify every feasible policy's realized CO2 is at least this lower bound within numeric tolerance. Do not assert that H beats L: greedy choices can interact with capacity.

On deterministic small benchmark cohorts, additionally formulate binary job/action assignments with one action per job and interval-capacity constraints, and solve with scipy.optimize.milp/HiGHS. Enumerate all allowed hourly actions and their exact capacity breakpoints. Use a 30-second time limit; save status, feasible objective if any, dual bound and gap. Only a certified optimum at the declared tolerance is called an optimum. A time-limited incumbent is a feasible hindsight schedule, not a bound on every other policy.

The exact small benchmark is a verification instrument, not evidence of year-long global optimality. If its action set differs from the operational search, display that difference; compare ordering only on the intersecting or explicitly matched feasible set.

## 9. Continuous evaluation, uncertainty, and runtime limits

Let R_max be the longest retained source attempt duration, computed from trace data alone. Let W_max include the largest allowed delay in the registered scenario family. Use a warm-up of at least R_max + W_max before the evaluation start. Execute this warm-up once with carbon-blind policy U, without any later-fitted forecast or grid-dependent choice, then clone its entire running/queued/reservation state for every policy at evaluation start. This common initial state avoids leaking later-fitted model information into warm-up decisions. From that point each policy maintains its own continuous state on the same arrival stream.

For primary scoring, stop new arrivals at A = F − R_max − W_max. Score cohort requests arriving in [test_start, A), and execute them to completion no later than F for a feasible policy. Stop the entire arrival stream at A, not just the favorable job classes. Report the actual arrival window and the later execution/drain window. Long-job drain can shorten the scored arrival window materially.

Warm-up requests remain in the capacity ledger until they finish; their energy and work are reported separately from the scored cohort. No daily or weekly queue reset. If an infeasible policy needs execution after F to finish, its completion ledger can record that remaining work structurally, but no unavailable realized carbon may be invented; its carbon claim is ineligible.

Before evaluation, form one common hourly truth-availability mask across the core carbon signals. Do not remove different hours for different policies. For a missing truth hour, fail the primary total and report the coverage gap; optionally publish a separately labeled complete-coverage cohort using a common, policy-independent exclusion of every job whose **possible** execution window touches any such hour. Never fill truth with a forecast. Register this exclusion rule before test; disclose excluded jobs, GPU-hours and calendar coverage. It cannot become the headline if it omits substantial energy without a clear qualification.

Primary phase-zero metrics for every policy/scenario:
- total completed GPU-seconds versus requested; retained original-status mix;
- deadline misses by jobs and GPU-hours; wait p50/p95/max; unfinished/backlogged GPU-hours; rejection and capacity-violation counts;
- execution energy and transfer energy, home/remote energy share;
- attributed CO2 in kg and kg per 1,000 completed GPU-hours;
- absolute and percentage CO2 change versus U, and incremental change versus S and W;
- production-basis repricing, stress exposure, and supported wholesale cost separately;
- forecast error, scheduler runtime, and fallback/infeasibility counts.

Use total differences and ratio-of-total savings, not means of daily percentages. When a reference total is zero, the percentage is null, not infinity. Positive reduction is C_reference − C_policy; also retain the signed raw difference.

For router uncertainty, assign each completed job's **full** energy/emissions/wait to its arrival UTC week, preserving cross-week execution in the ledger. Bootstrap paired contiguous blocks of 4 arrival weeks, 2,000 replicates, seed 20261027; compute percentile 95% intervals for ratio-of-totals savings and paired absolute differences. Repeat block lengths 2 and 8 as an uncertainty sensitivity. The schedule is simulated once continuously; resampling never resets queues or pretends the resampled schedule is physically executable.

These intervals describe variation across calendar/workload alignment conditional on the replay and modeling assumptions. They do not cover emissions-factor error or represent a population of independent clusters. Report the number of weeks and the number of unique source cycles; flag intervals unstable under block length or dominated by a single long campaign. Phase offsets are a separate sensitivity and must not be pooled as independent years. Forecast uncertainty uses paired daily errors, with temporal dependence acknowledged.

Keep the primary test scenario and contrasts above fixed. Secondary stress, cost, production basis and sensitivity views are exploratory; do not mine their best subgroup for a new headline.

Runtime discipline (**assumed engineering budgets**, not measured performance):
- Benchmark a fixed two-week validation arrival slice before full sweeps, including long-job tail integration.
- Core phase-zero validation policies plus a short replay must finish early enough to put real artifacts in the Tuesday 18:00 build.
- Build only one-axis endpoint sensitivities around the primary scenario; no factorial grid. Reuse forecast arrays and prefix integrals of hourly intensity. Use a reservation interval structure rather than rescanning the entire schedule per candidate.
- Log wall time and memory for feature building, each fit, forecasting, each replay and serialization. Forecast every target hour once per issued scenario, rather than per job.
- If full execution threatens the deadline, prioritize primary phase-zero core policies, their time/place restrictions, and the capacity/overhead limits. Mark unrun sensitivity cases explicitly. Regional movement, the fixed-clean-region comparator, and work accounting remain core.

## 10. Sensitivity that can change the interpretation

The most useful dashboard view is a **stay / wait / travel boundary**, backed only by computed scenarios. Precompute the primary case and the individual endpoint changes in §7. A control selects a registered run; it does not fabricate intermediate solver results.

For a candidate move, display:
- expected source and destination carbon attribution;
- extra transfer energy and staging delay;
- the GPU capacity needed for the entire run;
- the latest completion time and remaining slack;
- realized outcome and forecast error when replaying history.

Compute the transfer-energy break-even point from the complete execution-carbon difference and the source/destination transfer-intensity mix booked at arrival. If staying already has lower modeled CO2, show “no positive transfer allowance.” Label this boundary **modeled**, identify the power/PUE/carbon basis, and avoid treating an uncertain threshold as a measured network property.

Required interpretation checks:
1. **Static-region challenge:** S versus L, including remote occupancy/saturation. A large U-to-L difference with a negligible S-to-L difference means location access explains the gain.
2. **Long-job challenge:** report results by duration and GPU-size bands with each band's energy share. Do not headline counts of tiny jobs moved.
3. **Mobility challenge:** the single-node restriction tests whether the result depends on moving large pre-training jobs with assumed pre-staged data.
4. **Idle-power challenge:** main job attribution uses full active-slot energy. Recompute policy differences with active-minus-idle power, retaining transfer energy, to represent an always-on identical fleet whose fixed idle baseline cancels. Do not add the full idle baseline on top of full active-slot energy for occupied GPUs. Absolute whole-facility emissions require a separate, common-window ledger including all background work.
5. **Deadline/runtime challenge:** show the overrun stress case and any infeasibility prominently. Do not promise a production SLO from declared-runtime simulation.
6. **Carbon-basis challenge:** same schedules, consumption and production basis side by side. Hydro's low production intensity is not the same as delivered consumption intensity.

For a marginal diagnostic, fit first-difference production-emissions/net-load regressions on **training only**, with predefined local 6-hour blocks, an intercept, sample count, coefficient interval, R-squared, and residual diagnostics. Require both consecutive observations and no imputed/spike inputs. Freeze coefficients before validation/test.

Call the result an **associational emissions-response proxy**. Neither a high R-squared nor a positive coefficient makes it a causal marginal factor. Imports, storage and dispatch confounding remain. Do not sum an invented fleet-wide “avoided emissions” figure where destination response is unidentified. A PACE-only temporal repricing is a labeled sensitivity; unknown destination response stays unknown. An optional assumed-factor break-even chart may show what destination marginal factor would be required, but its factors are labeled assumed and it is not a test result.

PAI 2020 is a useful second-trace extension only after the core is complete: audit attempt/task multiplicity, fractional GPUs, missing end times, and supported work units first. Its incomplete durations prevent silently treating it as an equivalent full-load replication. No second trace or 2026 spot-share assumption is needed for the primary claim; the latter's additional terms are unnecessary for this build.

## 11. The visible product and offline evidence contract

### Story mode

Default to a legible 2D map with a synchronized carbon chart, capacity bars, and job execution lanes. A mild camera tilt can introduce the region, but quantitative comparisons use flat geometry and readable scales. Avoid encoding carbon and stress in the same color or height.

A 4–5 minute path:
1. **Utah now / tomorrow:** show observed history ending at the issue cutoff, then a visibly different forecast segment. Toggle carbon versus net-load stress to reveal that they answer different questions.
2. **One request:** open its declared budget, gang size, deadline, allowed sites and assumptions. Compare stay, wait and travel as concrete feasible actions.
3. **Place the work:** replay local and chosen-policy schedules side by side. Arcs move job requests; slot bars show where capacity prevents the tempting move. Long jobs remain visible across midnight.
4. **Count the result:** show equal completed GPU-hours and deadline status beside signed carbon differences. Compare U, S, W and L, with uncertainty and the data period.
5. **Challenge it:** choose the capacity, overhead or mobility sensitivity. Show the precomputed result, including loss of benefit or infeasibility. Open the evidence drawer to trace the headline to its run.

Choose the illustrative job from validation, not by searching held-out successes. Use this deterministic rule: among validation flexible jobs with a feasible remote action in the primary replay, select the job nearest the median GPU-hours of that set, breaking ties by stable ID. If it has no visually distinct action choices, use the smallest stable-ID job with two feasible site choices and disclose that illustration criterion. The test aggregate is not replaced by that example.

A held-out replay day, if supplied, is the first complete Monday after test start with the required assets, chosen from completeness only. Do not search for the best-looking test day.

### Results contract

Small, versioned JSON artifacts in results/ feed the static UI. Full prediction and schedule ledgers remain Parquet in versioned run directories, with inspectable excerpts exported for the demo.

Required artifacts:
- manifest.json: schema version, run IDs, source/config/code hashes, split and coverage, model fit/issue rules, reproducibility command, assumptions, artifact hashes and provenance registry.
- metrics.json: one record per scenario/policy/contrast, work/feasibility/energy/carbon metrics, uncertainty method and interval, covered dates, evaluation status.
- forecast-replay.json: issue time, target interval, BA, observed history/forecast/realized channels and quality flags.
- job-replay.json: stable source/mapped IDs, request attributes, declared/realized-budget distinction, available actions, reservations, transfers and decision explanation.
- scenarios.json: the exact computed scenario catalog, parameters and unavailable-case reasons.
- claims.json: each user-facing claim's text template, referenced metric IDs, comparison and limitations.
- test_reads.jsonl: append-only sealed evaluation audit.

Every numeric data field exported to results, UI or slides resolves to exactly one evidence class through a mandatory field registry or a scalar envelope. A compact scalar envelope is:

~~~json
{
  "value": null,
  "unit": "kg_CO2",
  "evidence": "simulated",
  "provenance_id": "registered_run_and_metric",
  "status": "not_evaluated",
  "reason": "No experiment has been run for this proposal."
}
~~~

The registry covers series, intervals, counts, uncertainty endpoints, map geometry/positions and scenario parameters as well as headline scalars. Dates, IDs, schema versions and display constants are metadata, not quantitative evidence; they still have type/schema definitions. A derived field's top-level label reflects its meaning and links to input labels. Examples:
- EIA demand: observed.
- EIA's estimated historical consumption intensity: modeled.
- Source-trace duration: measured; its remapped request budget: assumed with measured lineage.
- Predicted intensity, including a climatology tail: forecast, with model provenance.
- Chosen power/PUE/capacity: assumed.
- Energy calculated from a request budget and assumed power: modeled.
- CO2 and completion outcomes from a schedule: simulated.
- A deterministic break-even calculation from modeled inputs: modeled.

Use null plus reason for unavailable values. A missing field must not be inferred to be zero. No placeholder number may resemble a finished result. Formatting a g/kWh value as kg/MWh preserves both its numeric conversion and label.

### Laptop delivery

Use Vite/React/TypeScript, ECharts for quantitative plots, and deck.gl/MapLibre for local map assets. Use a single theme and system/self-hosted fonts. These choices are proposed technology, not evidence that the packages are installed or tested.

Bundle JS, styles, fonts, licensed map layers, raster relief and result JSON locally. Preserve asset attributions and the geometry source license materials. The existing processed geography is enough; no new map-data search is necessary.

Deliver a release archive with the built static directory and a documented localhost static-server launcher. The laptop must not require Node dependencies, a Python analysis environment, a GPU, SSH, remote APIs, or an experiment backend. A launcher may use a runtime already verified on the owner's Mac; identify and rehearse that prerequisite. Do not promise double-click file-URL support for a fetch-based app.

Use a relative deployment base and resolve asset paths against it, rather than relying on the profile examples' root-absolute paths. Provide a screenshot/video fallback and an inspectable metrics table for WebGL failure. A recording is a fallback, never presented as a live calculation.

Offline acceptance means the exact release loads in Chrome on the actual MacBook, with browser cache cleared and external network disconnected, and every story beat and registered scenario works. Collect a network log showing only local requests. Localhost serving is compatible with an offline demo. A Linux browser check cannot substitute for that laptop rehearsal.

## 12. Execution gates and verification

These are implementation targets; commands for new entry points become required only when their code lands. None below is claimed to exist merely because it appears here.

| Gate and deadline (MT) | Required evidence |
|---|---|
| Reconciled spec and frozen inputs, Tuesday morning | Owner-approved reconciled decisions; fresh soundness review; input hashes; no sealed values read. Separate weather status. |
| Forecast/router validation, Tuesday daytime | Exact as-of feature audit; capacity and complete-work ledgers; all U/G/S/K/W/L comparisons; declared-runtime caveat; common input cohorts. |
| Checkable version, Tuesday 18:00 | Tagged clean commit, real validation metrics in an offline-capable dashboard, PACE-to-destination routing visible, reproducible run reference. |
| Configuration freeze, Tuesday evening | Selected models/policy, fitted transforms, scenario catalog, replay mapping, claims, source and config hashes fixed before test entry point runs. |
| Sealed evaluation and audit, overnight to Wednesday morning | Logged test reads; no test-directed selection; all signed outcomes and failures retained; independent results audit against actual ledgers. |
| Experiment freeze, Wednesday 13:00 | Final clean run hashes and artifact checksums. Later runs only for documented bugs, with old/new results retained and logged. |
| Presentation lock, Wednesday 14:00 | Numbers trace to frozen artifacts; actual-Mac offline rehearsal; short story plus question-ready evidence drawer. |

No elaborate serving architecture, foundation-model installation, live LLM explanation, battery simulation, RL training, or hardware measurement is a dependency. An optional model must improve a registered validation comparison and pass the same availability/reproducibility rules; model size is not a success metric.

Implementation verification must include:
- Boundary and DST tests for hour-ending to hour-start conversion, civil-day horizons, and half-open splits.
- A sentinel future feature that provokes the availability guard; delayed consumed-carbon and bilateral-flow fields tested separately.
- Target/imputation tests preventing the BA forecast from reappearing as demand truth; source spike rules use neighboring hours only when both are already available.
- Synthetic jobs crossing midnight, DST, a forecast horizon, an arrival-cycle seam, and the evaluation/drain boundary.
- A long gang job whose hourly-average occupancy would hide a capacity violation; exact interval checking must reject it.
- Missing carbon truth, missing price, unavailable forecast tails, no legal action, and runtime overrun.
- Work and energy conservation, unit conversion, full versus incremental idle accounting, and transfer charges. A same-site transfer has no remote overhead.
- Exhaustive tiny scheduling examples versus the MILP and relaxed lower bound; mutate a constraint to demonstrate the test detects an illegal schedule.
- Paired comparison invariants and a known negative saving that remains negative in export and UI.
- Export validation for every numeric field's evidence/provenance, null handling, finite values, and metric-to-headline links.
- A clean rebuild with canonical hashes of sorted, rounded ledgers and stated numeric tolerances, not Parquet byte equality.
- Browser checks for every story beat, disabled unavailable scenarios, wrong asset base paths, network failures, and the actual laptop rehearsal.

The existing repository test command is:

~~~sh
cd lab
uv run pytest
~~~

New implementation entry points must document the exact command, environment lock, clean commit and output run directory for: source audit; validation forecasts; validation replay; configuration freeze; sealed evaluation; export; web build; release packaging; and offline verification. Do not place guessed future CLI commands in AGENTS.md.

When code is implemented, tests for new correctness behavior must demonstrate failure under a relevant mutation. This document itself needs link, consistency, and whitespace checks rather than tests that merely restate its prose. No production deployment, database migration, or public-hosting gate is required for a private offline hackathon artifact.

## 13. Judge-facing answers and remaining limits

**“Why not always use Bonneville?”** That is baseline S. If it wins, say so. The map shows finite spare GPUs and the jobs too large to fit. Forecast value is the incremental comparison, not the entire location difference.

**“Did you actually save CO2?”** We changed an attributed estimate in simulation. The historical mix is held fixed. Causal avoided emissions need a validated dispatch-response model or an intervention; this entry has neither.

**“Did you just finish less work?”** Open the common-cohort budget, completion, deadline and energy reconciliation. Any failure disqualifies that savings claim.

**“You knew how long a failed job would run?”** The experiment replays measured attempts as declared run-to-budget requests. That is an assumption, exposed with an overrun stress test. It does not predict failures or guarantee equal model quality.

**“Did you add a free data center?”** Every policy gets the same stated fleet and spare-capacity assumptions. G isolates capacity access. Transfers, destination saturation, PUE and idle-power sensitivity remain visible.

**“Did you use tomorrow's weather or revised history?”** Core forecasts need no weather and enforce publication envelopes. The bulk history is revised, so the replay is not an archived-vintage reconstruction. Optional weather has a separate initialization/publication audit.

**“What does this have to do with Torus?”** Flexible-work placement addresses hour-scale demand shaping and regional energy differences. Storage can address other timescales, but this study does not model Torus devices, dispatch a battery, or prove additional physical grid capacity.

No numerical benefit has been estimated in this proposal. The principal remaining risks are workload infeasibility at submission-time replay, assumed runtime/mobility, revised-data availability, consumption-intensity quality, and too little incremental value over a fixed clean-region policy. Each has a comparison or explicit qualification above. A negative result narrows the product's honest use case; it does not authorize changing the test.

## Sources checked for this proposal

The data profiles and frozen manifests are the quantitative source of record. External references checked 2026-10-27 support method choices, not experimental outcomes:

- [EIA: About the EIA-930 data](https://www.eia.gov/electricity/930-content/about.html): source timing, modeled carbon methods and revision limitations. This design deliberately uses conservative availability envelopes rather than claiming archived receipt times.
- [Sukprasert et al., On the Limitations of Carbon-Aware Temporal and Spatial Workload Shifting in the Cloud, EuroSys 2024](https://arxiv.org/abs/2306.06502): motivates testing strong simple policies and practical constraints.
- [SciPy mixed-integer linear programming reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html): solver status, time limits and objective bounds must accompany certification claims.
- [scikit-learn histogram gradient boosting reference](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html): the proposed bounded forecast family; installed versions and runtime remain implementation checks.
- [Open-Meteo Previous Runs reference](https://open-meteo.com/en/docs/previous-runs-api): lead-relative archives need explicit issue-time and publication checks.

## 14. Reconciliation with Claude's proposal (amendments R1–R6)

These amendments were added when the two independent proposals were reconciled. Apart from the [R1] tags and the gate fixes in §15, the other sections keep Codex's text.

- **[R1] NEVP is a third destination.**
  - The owner asked for Utah plus 3–5 neighbours (D-029).
  - Nevada is the realistic non-hydro neighbour, where placement and waiting are expected to be close calls. That makes it the most informative destination for H3/H4.
  - NEVP uses the same rules as the other destinations.
  - No runtime fallback drops it: cutting it would need the owner's approval (gate finding L6-2).
- **[R2] Secondary insight: clean hours ≠ rush hours.** This is registered as secondary and descriptive, so it cannot become a selection target.
  - **Across the 10 overview BAs, on validation:** the hourly correlation between consumed intensity and the training-fitted net-load percentile, plus the share of each BA's above-threshold stress hours that fall in its top carbon quartile.
  - **In the replay:** the §4 stress outcomes of L and S versus U show whether emissions-first scheduling adds or removes energy in high-stress hours.
  - **Expected:** the profile suggests PACE behaves differently from the eastern BAs. The result is reported whatever it shows.
- **[R3] Skeptic view.** The UI's skeptic mode is the §10 carbon-basis challenge (production vs consumption) plus the marginal associational proxy. It stays inside §10's limits and never shows "avoided" emissions.
- **[R4] Optional extensions,** only after the core and the 18:00 build. Each follows the same availability, freezing and labeling rules:
  - **(a)** one zero-shot time-series foundation model as an extra forecast candidate, timeboxed to 2 h, with checkpoint and pre-training coverage recorded;
  - **(b)** a PACE load-duration "headroom" illustration with a simple storage overlay. It is labeled modeled, makes no claims about Torus devices, and has no dispatch model;
  - **(c)** the PAI 2020 robustness replay, as in §10.
- **[R5] UI direction.**
  - The visual system and layout are chosen by the owner from `docs/design/concepts/`; round 3 is in progress.
  - Recommended backbone: the Day ribbon (insights on one 24-hour axis) and the Control room (the where-map). Story mode steps through them.
  - §11's honesty rules bind every concept. The mockup numbers (production basis, typical day, illustrative job) are replaced by registered results before any judge sees them.
- **[R6] Where Codex's choice replaced Claude's,** recorded for the decision log:
  - consumption-based intensity is primary (Claude had production primary, consumption alongside);
  - jobs are non-preemptive gang jobs (Claude had hourly-interruptible as primary);
  - the job log is replayed as a continuous 161-day cycle (Claude had a week-block bootstrap);
  - HistGradientBoosting replaces LightGBM, with no new dependency;
  - the bound is a relaxed per-job lower bound, not a "certified optimum" (Claude's draft had used the stronger "certified optimum" wording);
  - the stress threshold is a training-fitted 95th-percentile CDF (Claude had a trailing 365-day percentile).

  In each case Codex's version is stricter or more honest, so it was adopted.

## 15. Gate fixes (binding; they override earlier sections where they differ)

These come from the fresh-context soundness review of 2026-10-27, at about 02:45 MT (`docs/reviews/2026-10-27-spec-gate-r1-claude.md`, verdict `not_ready`). They were decided before any validation result was seen.

### F1. Deadlines relative to run-now (fixes L3-1, critical; also L2-5, L8-1)
- The submit-time replay of Seren overloads 2,288 slots: a peak of 3,082 GPUs and 31 episodes per cycle. It still overloads at 1.25×.
- So each job's deadline is `max(arrival + duration + allowed delay, its finish time under U)`. That finish time is computed once, from U, and does not depend on any other policy.
- This makes U feasible by construction. Flexibility means extra slack beyond what the cluster already gives the job.
- The overload is reported as a workload fact: "on-arrival replay needs queueing; the recorded cluster absorbed it with queues".
- **Deployed-policy fallback, if no policy meets the hard conditions:** the fewest deadline-miss GPU-hours, then the lowest CO₂.

### F2. Validation window and drain (fixes L1-1, L3-4)
- R_max = 336 h.
- **Validation selection cohort:** F_val = 2025-10-24T00Z, so the arrivals scored are [2024-11-01, A_val = F_val − R_max − W_max).
- **Warm-up:** at least 15 days, under U.
- **Test:** F = the frozen cutoff (expected 2026-10-25), giving A ≈ 2026-10-10.
- **Guard test:** the validation ledger never requests truth at or after TEST_START.

### F3. Missing carbon truth (fixes L3-2)
- Instead of failing the total or dropping jobs, use a site-availability mask that is the same for every policy.
- A destination is closed to any start whose execution would touch a missing-truth hour there. The missing hours before the seal:
  - CISO: 120 hours in the validation year, in three gaps;
  - NEVP: 4 hours;
  - BPAT: 93 hours in training;
  - PACE: none.
- The mask applies equally to H and to C_relaxed. The closed hours are disclosed.

### F4. Forecast value in coverage (fixes L2-1, L2-2, L4-2, L4-3)
- **H2's primary decision statistic:** the absolute paired difference in kg CO₂ (W − L) at phase 0, with a 4-week block percentile CI. A claim also needs the same sign at block lengths 2 and 8.
- **Pre-registered H2 stratum:** jobs whose whole latest-start-plus-duration window is inside issued forecast coverage. Report the share of decision-relevant energy inside coverage.
- H2 is named "system-level forecast value". Decision regret under a common reservation state is its forecast-skill companion.
- Only H2's primary contrast carries a decision rule. Everything else is an estimate.

### F5. Fair comparisons (fixes L2-3, L2-4, L1-4)
- H3 compares dynamic placement-and-delay with static placement and no delay.
- **S-wait** (S's ranking plus K's start choice) is a deferred extra comparator.
- **Place-only set:** U, G, S, W and L, all with zero latency and the energy charge kept.
- The relaxed bound relaxes only contention between jobs. The per-job limits on site size, mobility and delay still apply.

### F6. Statistics and concentration (fixes L4-1, L4-4, L3-5, L3-7, L8-4)
- Report:
  - leave-top-k-jobs-out results for k = 1, 5 and 10;
  - the number of distinct source weeks per block;
  - the immovable mass ceiling: jobs over 512 GPUs carry 30.3% of GPU-hours;
  - the cycle-seam censoring deficit;
  - Chinese holidays inside the cycle.
- Forecast errors use a 7-day block bootstrap.

### F7. Wording and definitions (fixes L5-1 to L5-5, L6-3, L8-2, L8-3, L3-8, L1-3)
- **Headline:** "attributed operational CO₂ (EIA consumption basis, modeled), including X MWh of modeled transfer energy".
- **Skeptic view:**
  - the marginal proxy is shown for PACE temporal shifts only;
  - it is not identifiable for CISO, NEVP or BPAT.
- **Destination ranking:** S ranks destinations by the unweighted hourly mean, which is never shown as an attributed factor.
- **Emission factors:** the possible provisional vintage of EIA's 2025–26 factors is disclosed.
- **R2:** "top carbon quartile" means a training-fitted quartile for each BA.
- **The relaxed bound:** it is called a bound, never a ceiling. Its "possible reduction" appears only in the evidence drawer.
- **Power and energy:**
  - idle power is sensitivity-only;
  - transfer energy is IT energy, with PUE applied at both ends.
- **Prediction intervals** are labeled "transferred from the validation-fit model".

### F8. Leakage guards (fixes L1-2, L1-5, L1-6)
- **Grid loaders** default to `drop_sealed`. Only the evaluation entry point holds the unseal path, and it logs every read; a test checks this.
- **Foundation models (R4a):** admitted only if the checkpoint's documented training cutoff is before 2025-11-01, or its corpus excludes EIA-930.
- **Weather** is deferred now: its manifest is still growing, so it can't be gated by Tue 10:00.

### F9. Minimal honest core by Tue 18:00 (fixes L7-1, critical; L6-6)
**Core, validation only:**
1. Consumed and produced carbon truth for PACE, CISO, BPAT and NEVP, with a unit test and the F3 mask.
2. Forecasts:
   - K, W and L for consumed intensity at the 4 BAs;
   - PACE demand, wind and solar;
   - an as-of guard with a sentinel test.
3. The Seren 161-day cycle at phase 0, with the flexibility hash, the 6 h / 1 h delays and the F1 deadlines.
4. The simulator:
   - exact-interval gang capacity;
   - the immutable ledger and the late queue;
   - policies U, G, S, K, W, L and H;
   - the primary scenario plus time-only;
   - warm-up and drain per F13.2 and F14.4.
5. Accounting:
   - conservation checks;
   - the feasibility table;
   - the vectorized relaxed bound;
   - the "feasible ≥ bound" check.
6. The 4-week paired block bootstrap.
7. `manifest.json`, `metrics.json`, and excerpts of `job-replay.json` and `forecast-replay.json`, with evidence envelopes on the exported fields.
8. One offline page in the chosen direction:
   - the PACE observed-vs-forecast chart;
   - the map with arcs to the three destinations;
   - the policy table with feasibility and signed CO₂;
   - evidence labels.
9. A Linux offline smoke check and a tagged commit.

**After 18:00, before the configuration freeze** (hard stop for every extension: validation selection done by Tue 21:00):
- the one-axis sensitivities (§7);
- place-only;
- phases 49 and 98, and block lengths 2 and 8;
- the production-basis repricing (first in line);
- the PACE marginal skeptic view;
- the R2 cross-BA statistics;
- forecasts for the other BAs (the overview shows observed data at 18:00);
- stress precision/recall, empirical intervals, the DF comparison;
- the break-even view;
- S-wait.

**Deferred past the freeze, or cut:**
- MILP certification (tiny brute-force cases stay in the unit tests);
- the overrun stress, redefined as excess misses vs U with mutable downstream reservations (L3-3);
- weather, prices, the fuel-mix diagnostic;
- R4 (a)–(c);
- the complete-coverage cohort (superseded by F3);
- the full field registry, the canonical-hash rebuild.

The Mac offline rehearsal moves to Wed morning.

### F10. Runtime (fixes L3-6)
- Candidate starts are hourly boundaries plus the earliest feasible start at each site.
- Capacity uses an interval or segment-tree structure.
- Benchmark on a 2-week slice first.

### F11. Baseline bookings: every job holds its U slot as a fallback (lead ruling during Stage 2, Task 4; revised after the task review)
- **Simulated** on a synthetic Poisson slice: under F1 deadlines without bookings, G and S missed deadlines on capacity-legal ledgers.
- **Cause:** a zero-slack job's deadline equals its U finish, and greedy list scheduling is not monotone. Moving or advancing some jobs lets others backfill, which pushes a later job past its U finish. Small-slack flexible jobs are exposed the same way.
- **Rule (bookings):**
  - Every job in the run holds a booking: its U site and interval, computed once per scenario from the U run (F1).
  - Every policy run starts with all bookings reserved.
  - When job *j* arrives, the policy may choose any on-time action that fits the capacity left after releasing *j*'s own booking, while still respecting every other booking and every earlier move. *j*'s booking is then released.
  - If no such action fits, or the policy returns none, *j* runs on its booking.
  - Releasing only ever adds capacity, so no other booking can become infeasible. **Every policy is on time by construction.**
- **Assumption (label: assumed, disclosed on the method page):** the baseline booking calendar is known in advance, as day-ahead reservations of the cluster's normal schedule. This is the one exception to §8's "future arrivals are unavailable". It is the same for every policy, and it carries no grid information, so the H1–H4 contrasts stay paired and fair.
- **Consequence:** routing can use only capacity that the baseline schedule leaves free, plus capacity freed by earlier moves. The effect on realized savings is not signed (F12.7).
- **The F1 fallback rule stays** as a guard. With bookings it should never fire; a fired fallback is a bug.
- **Search window for flexible jobs:** starts lie in `[arrival, deadline − duration]`, capped by R_max.
- **Arithmetic:** time in the engine and in capacity is integer microseconds, so bookings and tolerances are exact.
- **F3 mask:** it is enforced inside the engine, for every policy and fallback. Bookings sit at PACE, which has no missing truth in validation.

### F12. Astra gate r1 fixes (2026-10-27 ~02:45 MT; review: `docs/reviews/2026-10-27-spec-astra-r1-astra.md`)

These override earlier sections where they differ. F11's motivating counts came from a **simulated** synthetic slice (`lab/scripts/bench_sim_core.py`, Poisson arrivals, PR #19); they are not validation grid or workload outcomes. F11 and F12 were written during Stage 2, after F1–F10. The motivating benchmark is `origin/s2/task-4` at 8f438aa, `lab/scripts/bench_sim_core.py` (synthetic Poisson slice, no bookings). When F11–F14 were written, the only validation outcomes that existed were forecast error metrics (Task 2) and workload-only U statistics; no policy CO₂ result had been computed.

**F12.1 Truth support (A1, A2).**
- F3's mask is an **assumed, advance-known closure calendar**. It is the same for every policy and disclosed beside the result, like F11.
- A move is legal only if truth exists for every component it charges: execution hours at the site, and both arrival-hour transfer charges (home and destination) for a remote move. This rule applies identically to policies, H and C_relaxed.
- **Deferred causal sensitivity:** scheduling ignores missingness; scoring uses common support, where every policy drops any job whose charged hours touch missing truth under any policy.

**F12.2 Definitions (B1–B3).**
- **Baseline queue window:** [arrival, U start].
- **Deadline:** `max(U finish, arrival + duration + allowed delay)`.
- **Discretionary slack:** deadline − U finish, which can be 0. F1's phrase "extra slack beyond U" means discretionary slack.
- Carbon-driven choice inside the baseline queue window is allowed for every job, and its energy is reported separately.
- **Place-only:** the earliest feasible start at each candidate site, with the site chosen by the policy and no choice among start times. It is deferred from the 18:00 core.
- **S:** for each ranked destination in order (home is included in the ranking at its rank), take its earliest on-time feasible start. Use the first destination that has one; otherwise use the booking.
- **Capacity scenarios** are complete scenarios. Report each one's U waiting, deadline distribution and U emissions.

**F12.3 Cohort, legality and estimand (C1–C3).**
- The scored cohort is every arrival in [eval_start, A) whose deadline is ≤ F. Set A to the largest arrival at which all permitted completions are ≤ F. These are workload-only quantities from U bookings, frozen before any grid outcome is computed.
- Excluded arrivals are counted and disclosed.
- The R_max cap on starts is removed. One legal-action set — [arrival, deadline − duration] at each legal site, plus the exact booking, under capacity, mobility, transfer and the F12.1 support rules — is shared by policies, the validator and C_relaxed.
- Before any comparison, check every U booking against F and against PACE truth support. A failure is an **accounting-support failure**, not a scheduler bug.
- **Estimand:** a finite replay initialised empty at a fixed timestamp, with a ≥ 15 d warm-up under U. One cloned initial state is used for every policy.

**F12.4 Statistics (D1–D4).**
- Intervals are called **conditional temporal block-resampling intervals**. They are conditional on this replay, alignment and model, assume weekly totals are dependent only within blocks, and do not cover alternative alignments (the cycle recurs every 23 weeks).
- An interval that excludes zero is described as such, never as "confirmation".
- **Frozen algorithm:**
  - Weekly totals are taken by arrival week (Monday 00:00 America/Denver). Partial edge weeks are kept as they are.
  - Circular block bootstrap with non-overlapping draw positions sampled uniformly from all n start indices (wrapping), concatenated, and trimmed to n weeks.
  - The same sampled indices are used for every policy in a replicate. 2,000 replicates, seed 20261027, percentile 95%.
- **H2 decision rule:** the W − L kg interval lies wholly on one side of zero at block lengths 2, 4 and 8.
- **Influence diagnostic:** rank unique source attempts by declared GPU-hours, independent of policy, and remove every instance of the top k from both totals, on fixed schedules.

**F12.5 Wording (E1–E3).**
- Every headline carries "baseline-relative deadlines, exact declared runtimes; runtime uncertainty untested". Zero misses is never presented as production reliability.
- R2 coefficient intervals are omitted.
- The consumption-basis drawer states that EIA assigns Canadian and Mexican imports the average US emissions rate.

**F12.6 Delivery (G1, G2).**
- The Task 4 benchmark uses the real replay with every booking pre-reserved.
- **18:00 fallback:** if the full validation year cannot finish by 15:00, the checkpoint uses the 13 full weeks ending at F_val, labelled with their actual coverage.
- One independent clean rebuild of the selected core run, comparing canonical metrics and ledger invariants, is required **before freeze**.

**F12.7 Bookings (H1–H3).**
- F11 is an **advance-reservation scheduling scenario**. The booking calendar is synthesized from the complete replay, and its advance-knowledge horizon is the whole run. The result is not a historical online-router claim.
- Bookings restrict rescheduling opportunity, and **their effect on realized policy savings is not signed**. Report reservation-blocked preferred actions, by count and energy.
- Every carbon-search policy includes the exact booking as an explicit candidate.
- **Deferred causal sensitivity: shadow U.** Real PACE occupancy must stay at or below the shadow-U occupancy of arrived jobs. Report it as "what is possible without advance reservations".

**F12.8 Not changed.** The envelopes, the seal protocol, the H2 framing ("system-level forecast value"), and R1–R6, which Astra found sound.

**F12.9 R4a (A3),** if ever revived, needs independence from the validation period used for selection, and an audit of republished target sources.

### F13. Sol re-check r2 fixes (2026-10-27 ~03:10 MT; review: `docs/reviews/2026-10-27-spec-sol-r2-sol.md`)

These override §1–§14 and F1–F12 where they differ. Within §15, a later F-item overrides an earlier one.

**F13.1 Three action sets (R1).**
- **Envelope (per job):** release at arrival (+ transfer when remote), deadline, mobility, transfer, truth support (F12.1), and gang size ≤ site capacity.
- **Operational candidates:** the F10 candidates plus the exact booking, filtered against the evolving reservation ledger. H uses the same candidates and reservations; only its scoring signal differs.
- **C_relaxed:** minimises over the continuous envelope and drops all other jobs' occupancy, bookings and warm-up occupancy.

**F13.2 Cohort prefix rule (R2).**
1. Compute workload-only U bookings through the declared horizon.
2. A = the first arrival timestamp at which any request's deadline exceeds F, taking the minimum across registered scenarios that need a common cohort. Exclude that whole simultaneous-arrival group and every later arrival. If none fails, A is the horizon end.
3. Stop the arrival stream at A, and install no suffix bookings. U is causal, so the prefix's bookings are unchanged.
4. Warm-up running and queued work is kept exactly once, with no double booking, reported separately, and support-checked through its actual completion.
5. Before grid scoring, record the initialisation time, A, the cohort IDs, the booking hash and the drain coverage.

**F13.3 U tie-break and booking support (R3).**
- U's pass orders simultaneous arrivals by `(arrival, declared deadline = arrival + duration + allowed delay, job_uid)`. None of these depends on U. Final deadlines come afterwards.
- Bookings are **not** exempt from truth support. Every U booking is pre-checked against F and PACE truth (F12.3); a failure is an accounting-support failure.

**F13.4 Bootstrap and diagnostics (R4, R5, R9).**
- **Weeks:** every Monday-based America/Denver week that intersects the arrival interval, zero-job weeks included, with partial edges unchanged.
- **Draws:** for each b ∈ {2, 4, 8}, reset `numpy.random.Generator(PCG64(20261027))`. For each of 2,000 replicates, draw `ceil(n/b)` starts with replacement from `[0, n)`, expand each start to `(start+j) % n`, concatenate, and keep the first n indices. Source blocks may overlap.
- **Shared indices:** the same indices go to every policy. Differences and ratios are computed from resampled totals.
- **Quantiles:** 0.025 and 0.975, `method="linear"`.
- **Degenerate cases:** empty input returns null intervals; a zero reference total gives a null ratio.
- **H2 direction:** favourable only if all three lower endpoints of W − L are > 0; adverse only if all three upper endpoints are < 0. Anything else is inconclusive.
- **Influence ties** go to the stable `source_job_id`.

**F13.5 Fallback and benchmark (R6).**
- The 18:00 fallback is a **91-day truth window** [2025-07-25T00Z, 2025-10-24T00Z), with its own recorded initialisation and a workload-derived A under F13.2. Its actual, shorter arrival window is reported.
- The fallback never replaces the registered full validation selection before freeze.
- The benchmark times forecast construction, carbon-search replay and export, with full booking density.

**F13.6 Wording (R7, R11).**
- Coefficient confidence intervals for §10's first-difference marginal regressions are omitted unless a dependence-aware estimator and its settings are frozen before evaluation. R2's descriptive correlations are separate.
- F12.1's deferred variant is a **missingness-blind scheduling sensitivity**: carbon signals are kept and whole-run bookings remain. An arrival-causal reading is reserved for a replay that also removes booking knowledge.

**F13.7 Blocked diagnostic (R9).**
- For each job, compare its preferred action under the real view with its preferred action under a view without other jobs' pending (not-yet-arrived) U bookings. Earlier committed moves are kept in both views.
- The job is blocked if these differ. Count it once, and sum its modeled execution energy once.

### F14. Fresh Claude re-check fixes (2026-10-27 ~03:30 MT; the re-check returned `ready_with_minor_fixes`; review: `docs/reviews/2026-10-27-spec-claude-r3.md`)

These override §1–§14 and F1–F13 where they differ.

**F14.1 Common cohort (N1).**
- For each evaluation window (validation, fallback, test) and each phase, A is the minimum of the F13.2 first-failure arrival over these scenarios:
  - primary;
  - batch delay 0 h and 24 h;
  - no flexible jobs, and all candidates flexible;
  - 1.25× home capacity.
  These are the §7 sensitivities that change U or deadlines.
- A is computed from workload-only U before any grid scoring. Every scenario in that window and phase uses that A.
- Phases 49 and 98 have their own arrival streams and their own A.

**F14.2 U (N2, N5).**
- U processes arrivals in the F13.3 order. It reserves each job at the earliest start at or after arrival at which its whole gang fits for its full duration, given all existing reservations. Later jobs may fill earlier gaps, and existing reservations never move. This makes U causal.
- Every policy, the validator and the U pass process simultaneous arrivals by `(arrival, arrival + duration + allowed delay, job_uid)`, where `job_uid` is the cycle-qualified mapped ID.

**F14.3 H2 population (N3).** The H2 decision rule (F13.4) applies to the full scored phase-0 cohort. The coverage stratum (F4) is a pre-registered secondary estimate with its own intervals and no decision rule.

**F14.4 Windows (N4, N9).**
- Initialisation = eval_start − 15 d exactly:
  - validation: 2024-10-17T00Z → eval_start 2024-11-01T00Z, F = 2025-10-24T00Z;
  - fallback: 2025-07-10T00Z → 2025-07-25T00Z, F = 2025-10-24T00Z;
  - test: 2025-10-17T00Z → 2025-11-01T00Z, F = the frozen cutoff.
- The U horizon is arrivals in [initialisation, F).
- Warm-up arrivals keep their U reservations immutable in every policy. Policies decide only arrivals at or after eval_start.
- The fallback reports n weeks and makes no H2 decision statement. Its b = 8 interval is labelled low-n.

**F14.5 Interval semantics (N10).**
- Execution intervals and closures are half-open, [s, s + d). "Touch" means positive overlap.
- The transfer-charge hour is the UTC hour containing the arrival.
- The bound's breakpoint set (window endpoints, hour boundaries, hour boundaries − d) is exact under hour-aligned closures.
- Envelope parameters (latency, capacity, mobility) are the scenario's own.
- The bound check uses a 1e-6 kg tolerance on the scored cohort, excluding warm-up.

**F14.6 Scoring truth fill (N6; pre-registered, replaces the "accounting-support failure" outcome).**
- **Why:** a completeness-only check (counts only, 2026-10-27 03:25 MT) found missing consumed-basis hours in the sealed window:
  - PACE 51 (one 50 h gap and 1 h; 24 h also missing production basis and EIA-930 fuel mix);
  - CISO 138;
  - BPAT 51;
  - NEVP 51.
  A shared roughly 50 h gap hits every site. Closing PACE or every site for those hours would make long jobs unplaceable. Missing truth needs a rule set now, before the freeze.
- **Fill rule.** For every BA, in validation and test alike, the scoring truth for hour h is the first available of:
  1. EIA consumption-basis CI (observed);
  2. EIA production-basis CI for the same hour (modeled substitute);
  3. our EIA-930 fuel-mix CI for the same hour (the grid-profile formula over adjusted generation; modeled);
  4. the mean over the 7 preceding days of tier-1 values at the same UTC hour (modeled).
- **Recording and reporting.**
  - Each scored hour records its tier.
  - Report, per policy, the share of kWh priced on tiers 2–4.
  - Sensitivity: common support, dropping every job whose charged hours touch tier ≥ 2 under any policy.
- **Interaction with other rules.**
  - The F3/F12.1 closure calendar now closes only hours with no value after tier 4. None is expected; any that occur are reported.
  - The F13.3 booking pre-check uses filled truth.
  - H uses filled truth.
  - Forecasts are never used as fill.

**F14.7 Blocked diagnostic (N7, N15).**
- The counterfactual candidates are the union of both views' candidates, filtered against the counterfactual ledger.
- A job is blocked only if the counterfactual choice differs **and** improves the policy's own score by more than 1e-9 kg (for G and S: an earlier finish, or a higher-ranked site).
- It is a diagnostic only; state evolves under the real view. "Pending" means not yet processed in the F14.2 order.
- Report it for G, S, K, W, L and H. It lands after 18:00 and before the freeze.

**F14.8 Bootstrap details (N11).**
- Starts = `rng.integers(0, n, size=ceil(n/b))`, int64, called once per replicate in replicate order.
- If any replicate's reference total is 0, the ratio interval is null; the kg interval is unaffected.
- Commit a reference index fixture for n = 10, b = 4.
