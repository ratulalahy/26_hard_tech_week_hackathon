# GridPilot: adversarial judge Q&A drill (FB-a)

**Status:** drill, Tue 2026-10-27 evening, for the Wed 17:00 MT judging. It complements `qa.md`; it does not replace it. **Every number here is from the validation year** (Nov 2024 – Oct 2025) unless it is a `{{TEST: …}}` placeholder. Those are filled from `results/test/` after the opening and the audit, as in `qa.md`.

**How it was made.** I tried a local model as the hostile panel. `ollama` holds `qwen3.6:35b-a3b-mtp` and `qwen3.5:122b-a10b`. The 35B model crashed in llama-server's MTP speculative decoder on every request. I did not load the 122B model: at 81 GB it would leave about 10 GB of the DGX's shared memory for the other sessions running tonight. So the four personas below were played by Claude, working from the committed numbers. No test-window data was read, and `make slice` was not run.

**Personas:** **G** a grid-operations engineer (WECC balancing authority); **T** the Torus energy-storage product lead; **M** an ML skeptic; **V** a deep-tech VC.

**Severity** (how much damage the question does if it's answered badly):
- **critical:** a bad answer sinks credibility on a judging criterion;
- **major:** a visible dent;
- **minor:** a detail.

**Sources** (short names used below):

| Short | File | Note |
|---|---|---|
| `M` | `results/metrics.json` | registered run 20261027T160656Z |
| `E` | `results/extensions.json` | |
| `ST` | `results/storage.json` | |
| `MF` | `results/manifest.json` | |
| `O` | `results/outlook.json` | on `origin/s3/t19-outlook` |
| `OV` | `results/overview.json` | on `origin/s3/t18-overview`; its skill numbers are being revised, so quote them as "about" or not at all |
| `P` | `results/prices.json` | on `origin/s3/t22-prices` |

`D-xxx` refers to `docs/decisions.md`.

**Answer rule:** at most 40 words, then "I can show you."

---

## The eight most dangerous questions

Rehearse these out loud. Their full entries are below.

| # | Question (short) | Why it's dangerous |
|---|---|---|
| Q1 | "Attributed, not avoided: did a single tonne leave the atmosphere?" | It attacks the headline's meaning. |
| Q2 | "Incremental load in BPAT is met by gas at the margin, not hydro." | The grid engineer's home turf; an easy overclaim. |
| Q13 | "So the insight is 'run on Oregon hydro, not Utah coal'?" | It attacks creativity and insight together. |
| Q16 | "Large jobs can't move, so your real number is 3%?" | It's true unless it's framed right. |
| Q20 | "On a flat marginal basis your battery adds CO₂." | The Torus judge's core question; our own result. |
| Q21 | "Your fixed storage schedule discharges after the 7–8 PM rush." | **New finding:** 11 of 12 rush hours fall outside the discharge window. |
| Q27 | "S ≈ H: the day-ahead traffic report is useless for the result?" | Half the title rides on the forecast. |
| Q33 | "Moving costs 7–9% more. Who pays to look green?" | `qa.md` #8 currently says cost wasn't evaluated, which is wrong. |

---

## A. Carbon accounting

**Q1 · G · critical.** "'Attributed, not avoided.' So you have no evidence a single tonne left the atmosphere. Why should I care?"
- **Answer:** Right, we didn't model how dispatch responds. Attributed is the hourly, location-based accounting an operator reports. We moved 22.6% of it for identical work. Avoided tonnes need a dispatch model; that's the next step, and we won't claim them.
- **Don't say:** "we cut 22% of emissions"; "avoided"; "real-world reduction"; "Scope 2 compliant" (we did not check any standard).
- **Source:** `M.contrasts` S vs U; `MF.claim_frame`.

**Q2 · G · critical.** "When 1 MW shows up in Bonneville, the marginal unit is gas or imports, not hydro. Isn't 87 g/kWh fiction for incremental load?"
- **Answer:** It may well be. Hydro is energy-limited, so new Northwest load can be met at the margin by gas or imports. Average intensity can't settle that. Production-basis repricing gives 25.5%; neither number is marginal.
- **Don't say:** "the hydro serves our load"; "BPAT's marginal emissions are low"; "marginal would be similar".
- **Source:** `E.repricing` S production 25.49%; `qa.md` #12.

**Q3 · G · major.** "Consumption basis follows imports. Moving load to an exporter just reshuffles who gets credit for the hydro, doesn't it?"
- **Answer:** At grid scale, partly yes. Attribution reallocates, and a 1.6 MW cluster is a price-taker. Our claim covers this workload's accounting, not WECC-wide emissions. That's the attributed-versus-avoided line again, stated plainly.
- **Don't say:** "net reduction for the Western grid".
- **Source:** `MF.claim_frame`, `MF.limitations`.

**Q4 · G · minor.** "EIA gives Canadian imports the US-average rate. Isn't Bonneville's number contaminated?"
- **Answer:** That's EIA-930's convention, and it's in our limitations. If BC imports are hydro, the convention probably makes BPAT look *dirtier*, which would understate our saving. That's an inference; we didn't test it.
- **Don't say:** "it doesn't matter"; "we corrected for it".
- **Source:** `MF.limitations[1]`.

## B. Simulated replay vs reality

**Q5 · M · critical.** "A Shanghai cluster's trace, replayed on a hypothetical Utah cluster, against modeled carbon. What part of this is real?"
- **Answer:** Measured: job sizes, durations and arrivals from the public Acme trace. Observed or EIA-modeled: the hourly grid data. Assumed: cluster size, power, mobility, spare slots. Simulated: placements. Every number carries its label.
- **Don't say:** "validated"; "deployed"; "real cluster"; any tonnes without "simulated".
- **Source:** `MF.assumptions`; evidence labels in every results file.

**Q6 · M · major.** "How do you know the simulator is right?"
- **Answer:** An independent rerun reproduced every policy's ledger bit-for-bit. Every policy completes exactly the requested GPU-seconds, with zero capacity violations, zero late jobs, and every policy sits above a relaxed lower bound of 3,501 t. It has not been checked against a production scheduler.
- **Don't say:** "proven correct"; "matches reality".
- **Source:** `E.primary_reproduction.ledgers_equal` (all true); `M.policies.*.conserved`, `.capacity_violations`; `M.relaxed_bound`.

**Q7 · V · major.** "2,288 GPUs is 1.6 MW. Real AI campuses are hundreds of megawatts. Does any of this scale?"
- **Answer:** Not linearly. Spare capacity at the clean sites binds: with zero slots the saving is 0.7%, with 512 it's 22.6%, with 1,024 it's 35%. At campus scale, moving 30% of load needs firm destination capacity and transmission. That's the operator conversation.
- **Don't say:** "scales to gigawatts"; "Operation Gigawatt could save X tonnes".
- **Source:** `E.sensitivities.dest_slots_0` (W 0.72%), `dest_slots_1024` (S 35.0%).

**Q8 · M · major.** "512 spare GPUs per destination: where did that come from? It sets your result."
- **Answer:** It's assumed (spec §7), not measured. So we show the curve instead of one number: 0.7% with none, 22.6% at 512, 35% at 1,024. The headline is conditional on the clean sites having room.
- **Don't say:** "a realistic spare capacity"; "industry-standard".
- **Source:** `MF.assumptions.destination_slots`; `E.sensitivities`.

**Q9 · M · minor.** "Your 95% interval comes from bootstrapping weeks of one replay. What uncertainty does it actually cover?"
- **Answer:** Week-to-week variation of grid and workload within this replay, in 4-week blocks. It doesn't cover the assumptions (mobility, slots, carbon basis), and those matter far more. That's why the sensitivity table sits beside the interval.
- **Don't say:** "we're 95% confident the real saving is 18–27%".
- **Source:** `M.contrasts[1].blocks.4`; `qa.md` #6.

## C. "The 22% is just 'move to Bonneville hydro'"

**Q13 · V · critical.** "So your insight is 'run in Oregon on hydro, not in Utah on coal.' A spreadsheet tells me that. Where's the creativity?"
- **Answer:** The direction is obvious; the sizes and the conditions weren't. On identical work, place gives 22.6% and time gives 0.7%. A sorted list matches every forecast policy. And the saving falls to 3–4% unless large jobs can move. That's the planning decision.
- **Don't say:** "our AI discovered"; "non-obvious routing"; "30×".
- **Source:** `M.contrasts` (S, W_time vs U; K/W/L/H vs S); `E.sensitivities.mobility_le_8gpus`.

**Q14 · G · major.** "Sixty-nine percent of the remote work went to Bonneville. Hydro is seasonal: does the ranking hold in late summer?"
- **Answer:** The ranking is fixed from training means, but the carbon we charge is hourly EIA data, so low-water months are priced in. The pre-registered seasonal split on the test year: {{TEST: seasonal split of S saving vs U}}.
- **Don't say:** "hydro is always clean"; "we checked every month" (validation monthly results are not exported).
- **Source:** `M.policies.S.metrics.execution_kwh_by_site` (BPAT 1,757 of 2,545 MWh remote); D-071 (seasonal split).

**Q15 · V · major.** "Then why not just build the data center in the Northwest? Why route at all?"
- **Answer:** Siting is the bigger lever, and our numbers agree: training means of about 582 g/kWh in Utah against 87 in Bonneville. Routing is for capacity that is already being built in Utah and for the work that can't relocate.
- **Don't say:** "routing beats siting".
- **Source:** `MF.s_ranking.mean_consumed_ci`.

**Q40 · V · major.** "You picked the dirtiest home region you could. Doesn't that inflate the saving?"
- **Answer:** A coal-heavy home next to a hydro neighbour is the best case for moving; we say so. Utah is also Torus's grid. From a home like Colorado or MISO the number would differ. We didn't run other home regions.
- **Don't say:** "it generalises to any US region".
- **Source:** `OV.regions.*.alignment.mean_ci` (PACE 564, PSCO 391, MISO 441, BPAT 101, validation).

## D. Mobility

**Q16 · T/G · critical.** "Large training jobs can't move: data, checkpoints, interconnect. So your real number is 3%, right?"
- **Answer:** It could be. The top 1% of jobs carry 94% of the energy. If only jobs of 8 GPUs or fewer move: S 3.2%, W 3.9%. Placing a checkpointed pre-train elsewhere at start is plausible but unmeasured. An operator's audit decides it.
- **Don't say:** "big jobs can easily move"; "3% is the floor" (it isn't; zero mobility is 0.7%).
- **Source:** `E.sensitivities.mobility_le_8gpus` (S 4,518 t, W 4,487 t vs U 4,670 t); `M.workload.top_1pct…energy_share` 0.941.

**Q17 · M · major.** "Who decided 46% of GPU-hours are flexible? It's an assumption with a hash function."
- **Answer:** Correct: flexibility is set by job type plus a fixed sha256 parity split, which is about 42% of jobs and 46% of GPU-hours. It's assumed, not observed. The all-flexible and no-flexible sensitivities were cut (D-058).
- **Don't say:** "measured flexibility"; "typical of real clusters".
- **Source:** `M.cohort.flex_shares`; `MF.scenarios_for_A.primary.note`.

**Q18 · V · minor.** "Under the realistic mobility case, your on-stage 72-GPU job stays in Utah. Why show it?"
- **Answer:** A rule fixed before outcomes picked it: the GPU-hour-weighted median job (D-054). It shows the mechanism of stay, wait or move, not the typical outcome. Under the 8-GPU rule it stays home, and we say so.
- **Don't say:** "a typical job".
- **Source:** `results/job-replay.json` `illustrative_job.criterion`; D-054.

**Q19 · M · minor.** "If a few large jobs carry it, isn't the result just outliers?"
- **Answer:** The reverse. Removing the 10 largest source jobs *raises* S's saving from 22.6% to 25.1%. Concentration matters for mobility, not for outlier sensitivity.
- **Don't say:** "outliers don't matter" (they matter through mobility).
- **Source:** `M.influence.by_k.10.saving_vs_U.S` 0.2513.

## E. Storage (the Torus questions)

**Q20 · T · critical.** "On a flat marginal factor your battery adds CO₂. So storage is bad for carbon here?"
- **Answer:** On a flat marginal factor, yes: losses add about 109 t a year at 4 MWh. On hourly average intensity, the fixed schedule cuts 3.5% (2.0–4.2% across 75–90% efficiency). Carbon is storage's weak case here; peak and power quality are the stronger ones.
- **Don't say:** "storage cuts carbon"; "green battery"; "hindsight bound" (D-061/F12: it's a heuristic).
- **Source:** `ST.cases.U.strategies.A.0.85` (`cut_frac`[4 MWh] 0.0351, `flat_marginal_cut_t` −108.5); η 0.75 0.0199, η 0.90 0.0420; D-067.

**Q21 · T · critical** (new finding). "Utah's rush is at 7–8 PM. Your fixed schedule discharges from 9 PM. Doesn't it miss the peak?"
- **Answer:** Mostly, yes. Eleven of the twelve rush hours fall before the discharge window. The schedule lowers rush-hour import only from 1.12 to 1.04 MW; a day-ahead hindsight plan reaches 0.46. The schedule targets carbon, not net load. A peak-aimed dispatch is the next build.
- **Don't say:** "storage shaves Utah's peak"; "the battery covers rush hour".
- **Source:** `ST.schedule.discharge_hours` [0,1,6,21,22,23]; `ST.rush.by_local_hour` (17:1, 19:3, 20:7, 21:1); `ST.cases.U.import_at_headline` A 1.116→1.036 MW, B →0.461 MW.

**Q22 · G/T · major.** "Charging pushes your site's maximum draw up to its connection limit. Haven't you made the interconnection problem worse?"
- **Answer:** In this illustration, slightly: the site's highest hourly import goes from 1.64 to its 1.65 MW connection cap, because charging fills the headroom. That's why charging is capped at the connection; only about 0.3–0.6 MW is free to charge.
- **Don't say:** "reduces peak demand"; "no grid impact".
- **Source:** `ST.cases.U.import_at_headline.A` (peak 1.639→1.647 MW); `ST.assumptions.connection_mw`; D-067.

**Q23 · T · critical.** "What does Torus actually get from this?"
- **Answer:** A sizing input and an honest boundary. After moving what can move, the cluster still draws about 1.04 MW from Utah in rush hour. Hourly carbon arbitrage alone is thin, at 3.5%. The value has to come from peak response, demand response and seconds-scale buffering.
- **Don't say:** "Torus's flywheels would cut X"; any Torus product modeled; a dollar value per MW.
- **Source:** `ST.cases.mobility_le_8gpus_W.import_at_headline.A.rush_before_mw` 1.045; `ST.cases.U` 3.5%; `qa.md` #16.

**Q24 · T · major.** "Why 4 MWh / 1 MW? Did you pick it after seeing the results?"
- **Answer:** Yes, and it's labelled that way. We sized it to the charging room the connection leaves free, chose it after validation, and it isn't an optimum. Eight megawatt-hours gives 3.8%, where the curve flattens.
- **Don't say:** "optimal size".
- **Source:** `ST.headline.rule`, `.plateau_e_mwh` 8; `ST.cases.U.strategies.A.0.85.cut_frac`[8 MWh] 0.0381; D-067.

**Q25 · T · minor.** "No degradation, no capex, no self-discharge. Is this a storage analysis at all?"
- **Answer:** It's an hourly energy-and-carbon illustration, not a business case; those costs are listed as ignored. At 4 MWh it cycles about 0.7 times a day, so degradation would matter for a real case.
- **Don't say:** "bankable"; "payback".
- **Source:** `ST.assumptions.ignored`; `ST.cases.U.strategies.A.0.85.cycles_per_day`[4 MWh] 0.69.

**Q26 · T · major.** "Moving combined with storage: what's the best you can do if big jobs stay home?"
- **Answer:** Move the small jobs and store for the rest: about 7.3% at 4 MWh, against 3.9% for moving alone, on a ratio of totals rather than our interval method. That's the realistic-mobility story for a storage company.
- **Don't say:** "doubles the saving" without "under ≤8-GPU mobility".
- **Source:** `ST.combined.move_and_store_cut_frac.A`[4 MWh] 0.0730; `.move_only_cut_frac` 0.0390.

**Q52 · T · major.** "Your router adds 0.22 MW to Bonneville during Utah's rush. Aren't you just exporting your peak?"
- **Answer:** We count it. During Utah's rush hours, S lowers the cluster's Utah load by 0.26 MW and adds 0.22 MW in Bonneville and 0.03 MW in California. Bonneville's own rush hours are its cleaner ones, but somebody still serves that load.
- **Don't say:** "net peak reduction"; "relieves the grid".
- **Source:** `ST.peak_relief.policies.S`; `OV.regions.BPAT.alignment.rush_vs_mean_pct` −7.9%.

## F. Forecasts

**Q27 · M · critical.** "Hindsight ties the fixed ranking. So your day-ahead traffic report, half your title, is useless for the result?"
- **Answer:** For the router, yes, and we say it: no dynamic policy beats S, and perfect foresight ties it (H − S is −0.5 t, interval −9.9 to +8.0 t). The outlook's value is elsewhere: destination forecasts beat seasonal averages by 10–23%.
- **Don't say:** "our ML drives the savings"; "the forecast picks the cleanest hours" (S doesn't read it).
- **Source:** `M.contrasts[13]` (H vs S); `O.skill_by_horizon` (BPAT/CISO/NEVP); `O.limitations[3]`.

**Q28 · M · critical.** "Your Utah forecast isn't better than a seasonal average. Why show a forecast at all?"
- **Answer:** For Utah we don't: the outlook shows the seasonal average, flagged as such, because the 7-day-block interval crosses zero on every day from D+1 to D+7 (skill about 3–5%). Model forecasts appear only where they earn it: the three destinations.
- **Don't say:** "accurate day-ahead Utah forecast"; "4% better" without "not reliably".
- **Source:** `O.days[*].regions.PACE` (`best_model_skill_ci90` e.g. D+1 [−0.019, 0.105]); `O.days_with_skill_home` 0; D-072.

**Q29 · M · major.** "Your carbon-aware search K did significantly worse than a sorted list. You built a model that loses?"
- **Answer:** Yes: K emitted 10 t more than S, interval +1.5 to +19.3 t. Holding scarce clean slots for forecast-cleaner hours pushes later jobs to dirtier sites, and per-job greedy search isn't a fleet optimum. That's a finding, not noise.
- **Don't say:** "within noise" (true for W and L, not for K).
- **Source:** `M.contrasts[10]`; `M.framing.greedy_search`.

**Q30 · M · major.** "Your script says forecasts 'follow Utah's daily swing'. Now you say they don't beat average. Which is it?"
- **Answer:** Both, for different questions. Utah's daily swing is large (median about 340 g/kWh) and a calendar profile already captures it. Our models follow it but don't reliably beat that profile.
- **Don't say:** "the forecast predicts the swing better than anything else".
- **Source:** `OV.regions.PACE.swing.median_g` 342 (validation); `O.skill_by_horizon.PACE`.

**Q31 · M · major.** "No weather inputs? Of course your forecast loses."
- **Answer:** The frozen models use no weather; we ruled it out on purpose (D-066). Hindsight with perfect carbon foresight ties S, so no forecast, weather or not, can lift the routing result in this replay. Weather would help the outlook, not the headline.
- **Don't say:** "weather wouldn't help forecasting".
- **Source:** D-066, D-068; `M.contrasts[13]`.

**Q32 · M · minor.** "Your skill intervals changed after review. Isn't that p-hacking?"
- **Answer:** The change made our result *weaker*. Review found that iid intervals overstated Utah's skill. We switched to 7-day block intervals, and that removed the Utah claim. We kept the correction.
- **Don't say:** "the numbers didn't change".
- **Source:** D-072.

## G. Cost

**Q33 · V · critical.** "Moving costs 7–9% more. Who pays a premium to look green?"
- **Answer:** At wholesale real-time prices, moving costs $17–22k more on a $240k bill, about $21 per attributed tonne, because Utah is the cheapest node ($28.7/MWh against $34.7 in Bonneville). Data centers pay retail contracts, so this is a scenario, not a bill.
- **Don't say:** "it's cheaper"; "cost-neutral"; "marginal abatement cost" (it's attributed, average-basis).
- **Source:** `P.policies.S` (`delta_vs_U_usd` 22,361, `cost_per_attributed_tonne_usd_t` 21.2); `P.california_node.range.S` [+7.1%, +9.3%]; `P.prices.mean_usd_mwh`; `P.caveat`.

**Q34 · V · major.** "Waiting is cheaper *and* cleaner. Wouldn't a rational operator just wait?"
- **Answer:** Waiting saves 0.8% on cost and 0.7% on CO₂, both small. Moving buys 22.6% for about $21 an attributed tonne. Whether that's worth it is the operator's call; we make the trade explicit.
- **Don't say:** "every operator's carbon price exceeds $21" (we have no source).
- **Source:** `P.policies.W_time` (`delta_vs_U_frac` −0.0079); `M.contrasts[6]`.

**Q35 · G · major.** "Why price California at PG&E? That's arbitrary."
- **Answer:** It is: an unregistered choice made during the build (D-072). We show SCE as well, +7.1% against +9.3%. The range is the answer; our bootstrap whiskers don't cover the node choice.
- **Don't say:** "PG&E is the right node".
- **Source:** `P.california_node`; D-072.

**Q36 · V · minor.** "Did the router see prices?"
- **Answer:** No. Prices were applied to the registered schedules afterwards. A cost-aware objective is future work.
- **Don't say:** "cost-optimised".
- **Source:** `P.note`.

## H. Transfer, latency, data gravity

**Q37 · V/G · critical.** "Moving a multi-day pre-train means terabytes of data and checkpoints. Thirty minutes is fantasy."
- **Answer:** The 30 minutes and the 5% extra energy are assumptions. At a 2-hour transfer, S still saves 20.2%. We don't model egress cost, dataset staging or residency. Those are the mobility question we flag as the lever.
- **Don't say:** "data transfer is negligible"; "data is already replicated".
- **Source:** `E.sensitivities.transfer_120min` (S 3,727 t vs U 4,670 t); `MF.assumptions.transfer_*`.

**Q38 · G · minor.** "What about latency-sensitive inference?"
- **Answer:** Out of scope. We route only batch jobs from the trace (pre-train, fine-tune, multimodal, eval), placed before they start; nothing migrates mid-run and nothing serves users.
- **Don't say:** "works for inference too".
- **Source:** `MF.scenarios_for_A.primary.note`; narrative Beat 2.

**Q39 · M · minor.** "Transfer energy at 5% of IT energy: where's that from?"
- **Answer:** It's assumed (F7); the 0% and 20% sensitivities were cut. Transfer is about 44 t of S's 3,613 t, so doubling it wouldn't change the picture much.
- **Don't say:** "measured network energy".
- **Source:** `M.policies.S.metrics.transfer_co2_kg` 44,269; `E.not_run`.

## I. Grid context (the ten-region overview)

**Q49 · G · major.** "In 9 of 10 regions the rush hours are dirtier, yet waiting only buys 0.7%. Isn't that a contradiction?"
- **Answer:** No. The rush hours are dirtier, but 63% of the energy is in jobs longer than 24 hours, and jobs may wait at most 6. Even with a 24-hour allowance, waiting reaches only 1.4%. The swing is there; this workload can't use it.
- **Don't say:** "time-shifting never works" (it's this workload).
- **Source:** `MF.workload.energy_share_gt_24h` 0.634; `E.sensitivities.batch_delay_24h` (W_time 4,605 t vs 4,670 t); `OV`.

**Q50 · G · minor.** "Some of your 'dirtier rush hours' are +2%, in California. Is '9 of 10' meaningful?"
- **Answer:** The margin varies: Utah +20%, Colorado +18%, Texas +17%; California +2%, Arizona and PJM +4%; Bonneville −8%. There are no intervals on these, so read it as a pattern, not a test.
- **Don't say:** "every grid's peak is dirtier".
- **Source:** `OV.regions.*.alignment.rush_vs_mean_pct` (T18 is being revised; re-check before quoting).

**Q51 · V · minor.** "What did your router do on Utah's toughest grid days?"
- **Answer:** The rule was fixed before we looked: the 3 days with the highest daily-maximum net load (D-066). {{T16: validation toughest-days U vs S/W, from results on s3/t16}}; on the test year, {{TEST: toughest days U vs S}}.
- **Don't say:** "it saved the grid on those days".
- **Source:** D-066, D-071.

## J. Novelty and business

**Q41 · V · critical.** "WattTime, Electricity Maps and Google's carbon-intelligent computing already do this. What's new?"
- **Answer:** They publish signals, or shift work inside one company's fleet. We add an open, sealed-test comparison of time against place on identical work, with capacity and deadlines. It shows time-shifting in Utah is under 1%, and that job mobility, not forecast quality, decides the result.
- **Don't say:** "first ever"; "nobody does carbon-aware scheduling"; claims about those companies' internals.
- **Source:** `M.contrasts`; `E.sensitivities.mobility_le_8gpus`; D-059.

**Q42 · V · major.** "Who buys this? What's the business?"
- **Answer:** Today it's an analysis and an open tool, not a company. The buyer is an operator deciding where flexible capacity goes, or a utility sizing demand response. The first product is a "which jobs can move" audit.
- **Don't say:** market-size numbers; "SaaS for every data center".
- **Source:** `qa.md` #21.

**Q43 · V · minor.** "If the winning policy is a sorted list, what's defensible?"
- **Answer:** Nothing in the policy, and that's the finding. The value is the evidence discipline (a sealed test, logged reads, labelled numbers) and the mobility audit that turns this into an operator's number.
- **Don't say:** "proprietary algorithm".
- **Source:** D-059, D-060.

## K. The test seal

**Q44 · M · critical.** "Your own log says an agent tried to open the seal early, and another read a post-seal file. Why trust the seal?"
- **Answer:** Because we logged and disclosed both. The early attempt was blocked and had no freeze record to run against (D-060). The price-file touch printed column names and nodes, no values; prices aren't a test input (D-072). The opening itself is gated and logged.
- **Don't say:** "nobody ever touched the test data"; "impossible to cheat".
- **Source:** D-060, D-072; AGENTS.md (entry point, `test_reads.jsonl`, witness file).

**Q45 · M · major.** "Your validation year chose the models and was profiled before the design. Aren't the validation numbers optimistic?"
- **Answer:** Yes; validation is development evidence, and that's why the test year exists. On stage the headline is the test number, {{TEST: S saving vs U, % [95% interval]}}. If it breaks the pattern, we say so.
- **Don't say:** "validation and test agree" before the audit.
- **Source:** `MF.limitations[5]`; narrative Beat 3 notes.

**Q46 · M · major.** "Nine policies, seven sensitivities, extras… a multiple-comparisons garden?"
- **Answer:** There is one registered primary contrast, S vs U, and the hypotheses were registered before the opening. Sensitivities are labelled exploratory and never pooled or headlined. The test-year extras were pre-registered and are reported whatever they show (D-071).
- **Don't say:** "all significant".
- **Source:** `E.note`; D-059, D-071.

**Q47 · M · minor.** "EIA revises its files. Your test year is provisional data."
- **Answer:** Yes. We replay a revised snapshot frozen by hash, not real-time vintages, and the 2025–26 emission factors may be provisional. The test cutoff is 2026-10-25: 358 days.
- **Don't say:** "final data".
- **Source:** `MF.limitations[0]`, `[6]`; D-071.

**Q48 · G · major.** "About 50 hours of the test window have no EIA carbon. Could the fill drive your result?"
- **Answer:** The four-tier fill was pre-registered (D-052). On validation, dropping every job that touches a filled hour gives 22.5% against 22.6%. Test year: {{TEST: common-support S saving vs U, if run}}.
- **Don't say:** "no missing data".
- **Source:** D-052; `E.common_support.by_policy.S.vs_U.4.saving` 0.2246.

---

## Deduplication against `qa.md`

These drill questions were folded into existing `qa.md` entries instead of being repeated:

| Drill topic | Covered by |
|---|---|
| Why not send everything to Bonneville | `qa.md` #1, extended by Q13/Q15 |
| Deadlines, runtime overrun | #4 |
| The 30× ratio | #5 |
| Hindsight not best | #7 (Q27 adds the S ≈ H framing) |
| Advance-reservation calendar | #11 |
| Average vs marginal | #12 (Q2 is the harder version) |
| Data sources | #13 |
| Fast swings and power quality | #19 |
| Water | #20 |

Numbers Q10–Q12 are unused: those drafts (runtime overrun, the reservation calendar, which carbon basis) were folded into `qa.md` #4, #11 and #12. The drill has **49 questions** (Q1–Q9 and Q13–Q52): 14 critical, 22 major and 13 minor.

---

## Proposed edits to `qa.md` (not applied)

Status codes: **WRONG** means it contradicts committed or branch results; **WEAK** means it's true but invites one of the attacks above; **FILL** means a placeholder can now be filled from validation results.

| # | Status | Problem | Proposed replacement (or addition) |
|---|---|---|---|
| **8** "Is this cheaper?" | **WRONG** once T22 merges | It says cost "hasn't been evaluated" and "that comparison is future work". T22 priced the ledgers. | "No. At wholesale real-time prices, moving costs 7–9% more ($17–22k on $240k), about $21 per attributed tonne, because Utah is the cheapest node. Waiting alone is 0.8% cheaper. Data centers pay retail, so it's a scenario." (`P`; D-072) |
| **3** mobility | WEAK | "about 3%" is S only; W is 3.9%. | "…S's saving falls from 22.6% to 3.2% (W: 3.9%) (validation)…" (`E.sensitivities.mobility_le_8gpus`) |
| **6** robustness | WEAK (minor) | "25.2–25.5%" on production basis leaves out K (25.1%). | Say "about 25% on production-basis carbon (S 25.5%)", or "25.1–25.5% across the movers". (`E.repricing`) |
| **9** "Why does a fixed ranking match ML?" | WEAK | It doesn't use the new outlook result. | Append: "And our Utah day-ahead forecast is not reliably better than its seasonal average (7-day block intervals cross zero on D+1–D+7); the destinations' forecasts are 10–23% better." (`O`; D-072) |
| **10** "Did you peek?" | WEAK | A flat "No" invites Q44. It omits the counts-only completeness check (D-052), the blocked early attempt (D-060) and the post-seal price-file column print (D-072). | "No values. Before the freeze we only counted missing hours. Two disclosed touches: a blocked early attempt with no freeze record, and one post-seal price file's column names, no values; prices aren't a test input. The opening is gated and logged." |
| **14** "Why Utah?" | WEAK | The "70 MW demand-response MOU … tied to Operation Gigawatt" claim has no source in the repo beyond `docs/plan/2026-10-26-hackathon-plan.md`. A Torus judge will know the exact terms. | Check it against a public source before saying it, or drop the specifics: "Utah is Torus's home grid." Add: "Its rush hours run about 20% dirtier than its average (validation, `OV`)." |
| **16** "What does this have to do with Torus?" | FILL | `{{STORAGE: residual Utah rush-hour load}}` | "about 1.04 MW of rush-hour Utah draw after moving ≤8-GPU jobs (validation, `ST.cases.mobility_le_8gpus_W.import_at_headline.A.rush_before_mw`)" |
| **17** "Does storage cut carbon?" | FILL + WEAK | Placeholders are fillable. "Losses can make it worse" is vaguer than our own result (D-067 says to show the skeptic result prominently). | "Ours gives −3.5% (fixed schedule, η 0.85), −2.0% to −4.2% over η 0.75–0.90. On a flat marginal factor it **adds** about 109 t through losses." (`ST.cases.U`) |
| **18** "What about the peak?" | FILL + WEAK | Placeholders are fillable, and the honest numbers are weak: the fixed schedule misses the 7–8 PM rush (Q21). "Charging rebound" undersells it: the site's maximum import rises to the connection cap. | "Rush-hour import goes 1.12 → 1.04 MW on the fixed schedule (0.46 with daily hindsight); charging takes the site to its 1.65 MW connection cap. Moving adds 0.22 MW in Bonneville. Simulated; not accredited capacity." (`ST`) |
| **19** fast swings | WEAK | "That's exactly where a flywheel-battery hybrid fits" names Torus's product category as if it were modeled. The narrative rule (Beat 5 notes) says not to. | "Outside our hourly model. That needs measured, sub-second cluster power. It's the interface we'd build next, with Torus." |
| **1** | OK | Could add that K is significantly worse than S. | Optional. |
| **13** | WEAK (minor) | "CO₂ estimates for four balancing areas" undersells the scope: the overview covers ten. | "…for the four router sites, and ten in the overview." |
| **20** water | FILL pending | `{{WATER}}` | Fill from T14 (`origin/s3/t14-water`) after it merges. |

**Elsewhere in `docs/pitch/`** (outside the qa.md scope, flagged for the narrative owner):
- `narrative.md` Beat 3: "Our day-ahead forecasts follow Utah's daily swing" invites Q28/Q30. Suggested: "Our forecasts beat seasonal averages at the destinations, not in Utah, and the router doesn't need them."
- `one-pager.md` ("Cost was not evaluated") and `deck-outline.md` line 86 ("cost not evaluated") become wrong when T22 merges.
- Beat 5's script says storage helps "during Utah's evening rush". With the fixed schedule that's largely untrue (Q21); lead with the carbon and connection result, or rebuild the dispatch.
