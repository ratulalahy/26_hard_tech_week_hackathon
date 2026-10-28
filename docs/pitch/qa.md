# GridPilot: judge Q&A

**Status:** post-test rewrite, Tue 2026-10-27 night. Numbers are from the sealed test year (358 days, Nov 1 2025 – Oct 24 2026) unless marked *validation* (Nov 2024 – Oct 2025). Every number is on the numbers card, `docs/pitch/numbers.md`, and cites its JSON path in a comment here. This file folds in the useful answers of the adversarial drill (PR #89, `docs/pitch/qa-drill.md` on `origin/pitch/qa-drill`), updated to test-year numbers.

**Answer rule:** one or two sentences, at most about 40 words, then offer the screen: "I can show you."

**Rehearse these nine first:** #2, #3, #4, #9, #13, #19, #29, #34, #35 (attributed vs avoided; marginal hydro; big jobs can't move; "just Bonneville"; forecasts useless; did you peek; moving costs more; storage adds CO₂; does the battery hit the rush).

---

### A. The result

**1. "What exactly did you find?"**
In a simulated replay of 358 days of a sealed test year, a fixed clean-region ranking cut the attributed CO₂ of identical work by 22.3% [17.3, 27.2]; waiting in Utah alone cut under 1%. Validation was 22.6%. <!-- results/test/metrics.json contrasts[S/U].blocks["4"].saving 0.2226, .saving_ci95 [0.1734, 0.2720]; contrasts[W_time/U] 0.0077, contrasts[L_time/U] 0.0079; results/metrics.json contrasts[S/U].blocks["4"].saving 0.2262 -->

**2. "Attributed, not avoided: did a single tonne leave the atmosphere?"** *(critical)*
We didn't model how dispatch responds, so we don't claim avoided tonnes. Attributed is the hourly, location-based accounting an operator reports; we cut it 22.3% for identical work. Avoided tonnes need a dispatch model. <!-- results/test/metrics.json contrasts[S/U].blocks["4"].saving 0.2226; results/test/manifest.json claim_frame -->
- Don't say: "we cut 22% of emissions", "real-world reduction", "Scope 2 compliant".

**3. "New load in Bonneville is met at the margin by gas or imports, not hydro. Isn't 95 g/kWh fiction for incremental load?"** *(critical)*
It may well be. Hydro is energy-limited, so new Northwest load can be met at the margin by gas or imports, and average intensity can't settle that. Repricing on production-basis carbon gave 25.5% (validation); neither number is marginal. <!-- config/freeze.json s_ranking.mean_consumed_ci_g_kwh.BPAT 95.5; results/extensions.json repricing.by_policy.S.production.vs_U["4"].saving 0.2549 -->
- Don't say: "the hydro serves our load", "marginal would be similar".

**4. "Large training jobs can't move: data, checkpoints, interconnect. So your real number is 3%?"** *(critical)*
It could be. The largest 1% of jobs carry 95% of the energy. If only jobs of ≤ 8 GPUs may move, S saves 3.2% [1.9, 4.7] and the forecast policies, which can also wait, about 3.9%. An operator's audit of which jobs can move decides it. <!-- results/test/metrics.json workload.top_1pct_jobs_by_declared_gpu_h.energy_share 0.9452; results/test/extras.json extensions.mobility_le_8gpus.vs_U.S["4"] 0.0315 [0.0189, 0.0467], .W["4"] 0.0387, .L["4"] 0.0388 -->
- If only small jobs move, adding waiting to the ranking is worth about 0.7 points (3.9% vs 3.2%): the dynamic policies beat S there because S never waits (audit F14). Validation: S 3.2%, W 3.9%. <!-- results/extensions.json sensitivities.mobility_le_8gpus.policies.{S,W}.vs_U["4"] 0.0324, 0.0390 -->
- Don't say: "big jobs can easily move"; "3% is the floor" (with no spare capacity it's 0.8%).

**5. "Moving beats waiting by how much? Is it 30×?"**
About 22% against under 1% on the test year (22.6% against 0.7% on validation), both relative to running everything in Utah. A ratio of two estimated savings isn't a quantity we'd headline. <!-- results/test/metrics.json contrasts[{S,K,W,L}/U] 22.0–22.3%; contrasts[{W_time,L_time}/U] 0.77%, 0.79% -->

**6. "How did you guarantee deadlines?"**
Each job keeps its baseline reservation, its slot under stay-in-Utah, as a fallback, and runs exactly as long as it declared. Deadlines are met by construction (baseline bookings); zero late jobs in every policy is a property of that scenario, not of production. Runtime uncertainty is untested. <!-- results/test/metrics.json policies.*.metrics.late_jobs = 0 -->

**7. "Do the robustness checks back it up?"**
They keep the pattern under the specified one-axis changes. On the test year, workload phase shifts of 49 and 98 days, a 2-hour transfer and a 24-hour delay give 19.9–23.3% (S, W, L); validation gave 20.2–23.2%, including observed-hours-only scoring (22.5%). Scenario estimates, not a confidence interval; they don't test mobility, idle power or the reservation assumption. <!-- results/test/extras.json extensions.{phase_49,phase_98,transfer_120min,batch_delay_24h}.vs_U.{S,W,L}["4"].saving min 0.1995 max 0.2329; results/extensions.json sensitivities.*.policies.S.vs_U["4"], common_support.by_policy.S.vs_U["4"].saving 0.2246 -->
- Production-basis carbon: 25.1–25.5% across the movers, 25.5% for S (validation only; not rerun on test). <!-- results/extensions.json repricing.by_policy.{K,W,L,S}.production.vs_U["4"].saving -->

**8. "If a few large jobs carry it, isn't the result just outliers?"**
The reverse: removing the 10 largest source jobs raises S's saving, to 25.6% (validation 25.1%). Concentration matters through mobility, not outlier sensitivity. <!-- results/test/metrics.json influence.by_k["10"].saving_vs_U.S 0.2558; results/metrics.json 0.2513 -->

### B. "It's just 'move to Bonneville'"

**9. "So the insight is 'run on Northwest hydro, not Utah coal'? A spreadsheet tells me that."** *(critical)*
The direction is obvious; the sizes and the conditions weren't. On identical work, place gives 22.3% and time under 1%. A sorted list matched every forecast policy. And it falls to about 3% unless large jobs can move. That's the planning decision. <!-- results/test/metrics.json contrasts[S/U].blocks["4"].saving 0.2226; contrasts[{W_time,L_time}/U] 0.0077, 0.0079; framing.placement_vs_timing; results/test/extras.json extensions.mobility_le_8gpus.vs_U.S["4"] 0.0315 -->
- Don't say: "our AI discovered", "non-obvious routing", "30×".

**10. "Why not just send everything to Bonneville?"**
That's what a fixed clean-region ranking does, limited by spare GPUs: each destination has an assumed 512 spare slots <!-- results/test/manifest.json assumptions.destination_slots.{CISO,BPAT,NEVP} 512 -->. With none, only waiting is left (0.8%); doubling them takes the saving to 35%. <!-- results/test/extras.json extensions.dest_slots_0.vs_U.W["4"] 0.0077; extensions.dest_slots_1024.vs_U.S["4"] 0.3487 -->

**11. "Then why not just build the data center in the Northwest?"**
Siting is the bigger lever, and our numbers agree: the frozen ranking's training means are about 573 g/kWh for Utah against 96 for Bonneville. Routing is for capacity already being built in Utah, and for work that can't relocate. <!-- config/freeze.json s_ranking.mean_consumed_ci_g_kwh PACE 572.8, BPAT 95.5 -->
- Don't say: "routing beats siting".

**12. "You picked the dirtiest home region you could. Doesn't that inflate the saving?"**
A coal-heavy home next to a hydro neighbour is the best case for moving, and we say so. From Colorado or MISO the number would differ; we didn't run other home regions. <!-- results/overview.json (PR #93) regions.{PACE,PSCO,MISO,BPAT}.alignment.mean_ci 564, 391, 441, 101 (validation) -->

### C. Forecasts

**13. "Hindsight ties the fixed ranking. So your day-ahead traffic report is useless for the result?"** *(critical)*
For the router, yes, and we say it: forecast-based search showed no demonstrated aggregate routing benefit over the fixed ranking in this replay, and perfect hindsight ties S (+1.6 t [−7.1, +11.8]). The forecasts earn their keep elsewhere: 10–23% better than a seasonal average at the destinations (validation). <!-- results/test/metrics.json contrasts[H/S].blocks["4"].diff_kg −1631 [−11803, 7051] (reference − candidate; H emits 1.6 t more); results/outlook.json (PR #93) skill_by_horizon.{BPAT,CISO,NEVP} -->
- Don't say: "our ML drives the savings"; "simple rules beat AI" (no LLM or other scheduler was tested; this is one replay).

**14. "Why does a fixed ranking match machine learning?"**
The gap between regions is far larger than the hour-to-hour swing a forecast can catch, jobs may wait at most 6 hours, and 63% of the energy sits in runs over a day. Only 29% of flexible energy had its whole decision window inside forecast coverage. <!-- results/test/manifest.json workload.energy_share_gt_24h 0.634; results/test/metrics.json coverage_stratum.share_flexible_energy_in_coverage 0.2901 -->

**15. "Your carbon-aware search K did worse than a sorted list. You built a model that loses?"**
Yes: K emitted 9.9 t more than S, interval +0.8 to +19.5 t (unadjusted for the three comparisons; borderline). Holding scarce clean slots for forecast-cleaner hours pushes later jobs to dirtier sites. W and L are not distinguishable from S (+3.9 t [−4.7, +13.8]; +6.6 t [−2.0, +16.7]). <!-- results/test/metrics.json framing.placement_vs_timing; contrasts[{K,W,L}/S].blocks["4"].diff_kg, .diff_kg_ci95 (field is S − candidate; signs flipped here) -->

**16. "Is your Utah forecast any good?"**
Not reliably better than a seasonal average: on validation, the 7-day-block interval crosses zero on every day from D+1 to D+7. On the test year its error is 16% below the seasonal average for W and 8% for L, with no interval, and the frozen 80% bands covered only 69–77%. So the outlook shows Utah's seasonal average, flagged as such. <!-- results/outlook.json (PR #93) skill_by_horizon.PACE.*.skill_ci90; days_with_skill_home 0; results/test/extras.json forecast_skill.series.PACE.ci_consumed.models.{W,L}.mae_vs_climatology 0.842, 0.921; .models.{K,W,L}.interval.coverage 0.703, 0.768, 0.688 -->
- Don't say: "our forecasts follow Utah's daily swing" (audit F4).

**17. "No weather inputs? Of course your forecast loses."**
The frozen models use no weather, on purpose (D-066). Hindsight with perfect carbon foresight ties S, so no forecast, weather or not, can lift the routing result in this replay. Weather would help the outlook, not the headline.

**18. "Your skill intervals changed after review. Isn't that p-hacking?"**
The change made our result weaker: review found iid intervals overstated Utah's skill, and the 7-day block intervals removed the Utah claim. We kept the correction (D-072).

### D. The seal and the statistics

**19. "Did you peek at the test year?"** *(critical; audit F1 wording)*
No values. The test year was opened once, at 19:23 MT on Oct 27, after a tagged configuration freeze, through a logged entry point; all 69 reads are in `results/test_reads.jsonl`. Before that, by design, we only counted which test hours were present, to set the cutoff and the fill rule for missing hours. One blocked early attempt and one printed price-file header (no values; prices aren't a test input) are disclosed in our decision log. Forecasts and the ranking only use data EIA would already have published under our assumed lags (96 h for carbon).
- Sources: D-052, D-060, D-071, D-072, D-074; `results/test_reads.jsonl` (69 `read` events; invocation 2026-10-28T01:22:53Z).
- Don't say: "nobody ever touched the test data"; "impossible to cheat".

**20. "Validation chose the models. Aren't validation numbers optimistic?"**
Yes, validation is development evidence; that's why the test year exists. The headline is the test number, 22.3%, beside validation's 22.6%. <!-- results/test/metrics.json contrasts[S/U].blocks["4"].saving 0.2226; results/metrics.json contrasts[S/U].blocks["4"].saving 0.2262 --> Every pre-registered test-year extra is reported whatever it showed.

**21. "Nine policies, seven scenarios, extras: a multiple-comparisons garden?"**
One registered primary contrast, S vs U. The scenarios and extras were pre-registered before the opening (D-071, D-073) and are reported whatever they show, never pooled or headlined. The K-vs-S interval is unadjusted, so we call it borderline.

**22. "What does your 95% interval cover?"**
Week-to-week variation of grid and workload within this one replay, resampled in 4-week blocks. It doesn't cover the assumptions (mobility, spare slots, carbon basis), which matter far more; that's why the scenario table sits beside it.
- Don't say: "we're 95% confident the real saving is 17–27%". <!-- results/test/metrics.json contrasts[S/U].blocks["4"].saving_ci95 [0.1734, 0.2720]; n_weeks 51, reps 2000 -->

**23. "Why is the test year 358 days, and why were 8,003 jobs dropped?"**
The data snapshot's last complete day is Oct 24, 2026. Arrivals after Oct 15, 23:04 UTC are excluded so every job's deadline falls before that cutoff: 8,003 jobs, 3.1% of GPU-hours, the same jobs for every policy (validation: 1,203 jobs, 3.9%). The rule was fixed before scoring. <!-- results/test/metrics.json cohort.n_excluded 8003, cohort.excluded_gpu_h 382,074, covered.arrivals[1] 2026-10-15T23:03:57Z; results/metrics.json cohort.n_excluded 1203 -->

**24. "About 50 hours of the window have no EIA carbon. Could the fill drive the result?"**
The four-tier fill was pre-registered (D-052), and on the test year only 0.12–0.13% of the movers' energy is priced on filled hours. On validation, dropping every job that touches a filled hour gave 22.5% against 22.6%; that check wasn't rerun on test. <!-- results/test/metrics.json policies.*.metrics.kwh_share_tier_ge2; results/extensions.json common_support.by_policy.S.vs_U["4"].saving 0.2246 -->

### E. Replay vs reality

**25. "A Shanghai cluster's trace on a hypothetical Utah cluster against modeled carbon. What's real?"**
Measured: job sizes, durations and arrivals from the public Acme trace. Observed or EIA-modeled: the hourly grid data. Assumed: cluster size, power, mobility, spare slots. Simulated: placements. Every number on screen carries its label.

**26. "How do you know the simulator is right?"**
An independent rebuild reproduced every validation ledger exactly (D-074). Every policy completes exactly the requested GPU-seconds with zero capacity violations and sits above a relaxed lower bound (3,184 t on test). It hasn't been checked against a production scheduler. <!-- results/test/metrics.json relaxed_bound.primary 3,184,387 kg; docs/evidence/rebuild-20261027.json -->

**27. "2,300 GPUs is 1.6 MW. Real campuses are hundreds of megawatts. Does this scale?"**
Not linearly. Spare capacity at the clean sites binds: 0.8% with no slots, 22.3% with 512, 35% with 1,024. <!-- results/test/extras.json extensions.dest_slots_0.vs_U.W["4"] 0.0077; contrasts[S/U] 0.2226; extensions.dest_slots_1024.vs_U.S["4"] 0.3487; 1.6 MW: storage.schedule_comparison.schedules.carbon.cases.U["4"].peak_import_before_mw 1.639 --> At campus scale, moving 30% of the load <!-- results/test/metrics.json policies.S.metrics.remote_energy_share 0.2998 --> needs firm destination capacity and transmission. That's the operator conversation.
- Don't say: "scales to gigawatts".

**28. "Thirty minutes to move a multi-day pre-train is fantasy."**
The 30 minutes and 5% transfer energy are assumptions. At a 2-hour transfer S still saves 20%. We don't model egress cost, dataset staging or residency; that's the mobility question we flag as the lever. <!-- results/test/extras.json extensions.transfer_120min.vs_U.S["4"] 0.1995 -->

### F. Cost

**29. "Moving costs more. Who pays a premium to look green?"** *(critical)*
In a wholesale scenario on the validation year, moving costs $16–22k more a year (+7–9%) on a $240k energy bill, about $21 per attributed tonne for S, because Utah is a cheap node ($28.7/MWh against $34.7 in Bonneville). Data centers pay retail, so this is a scenario, not a bill. <!-- results/prices.json (PR #93) california_node.range.{S,W,L}.delta_vs_U_usd [16.2k, 22.4k], .delta_vs_U_frac [0.068, 0.093]; policies.S.cost_per_attributed_tonne_usd_t 21.2; policies.U.cost_usd 240,420; prices.mean_usd_mwh.PACE 28.7, .BPAT 34.7 -->
- Don't say: "it's cheaper", "cost-neutral", "marginal abatement cost".

**30. "Waiting is cheaper and cleaner. Wouldn't a rational operator just wait?"**
Waiting saves about 0.8% on cost and under 1% on CO₂, both small. Moving buys 22% for about $21 an attributed tonne. Whether that's worth it is the operator's call; we make the trade explicit. <!-- results/prices.json (PR #93) policies.W_time.delta_vs_U_frac −0.0079 -->

**31. "Why price California at PG&E?"**
It was an unregistered choice made during the build (D-072), so we show SCE too: +7.1% against +9.3% for S. The range is the answer; the bootstrap doesn't cover the node choice. The router never saw a price. <!-- results/prices.json (PR #93) california_node.range.S.delta_vs_U_frac [0.0709, 0.0930]; note -->

### G. Torus and storage

**32. "What does this have to do with Torus?"**
Moving work and storing energy act on different timescales and different loads. First find what work can move; what's left in Utah is the load storage could serve: if only jobs of ≤ 8 GPUs move, the cluster still draws 0.83 MW from Utah in the 14 tightest test-year hours. We don't model Torus devices or claim any grid capacity. <!-- results/test/extras.json storage.schedule_comparison.schedules.carbon.cases.mobility_le_8gpus_W["4"].rush_import_before_mw 0.831 (validation results/storage.json cases.mobility_le_8gpus_W.import_at_headline.A.rush_before_mw 1.045) -->

**33. "Why Utah?"**
It's Torus's home grid, and the contrast is sharp: the frozen ranking's training means are about 573 g/kWh for PACE against 96 for Bonneville; these are ranking means, not emission factors. Its evening net-load peak, about 6,200 MW at 8 PM averaged over July 2026 weekdays, is the rush we route around. <!-- config/freeze.json s_ranking.mean_consumed_ci_g_kwh PACE 572.8, BPAT 95.5; results/test/grid-profile.json pace_july_weekday.net_load_mw[20] 6182 (validation: 6,654 MW, July 2025 weekdays) -->
- "Home grid" rests on Torus being based in South Salt Lake (`docs/brief.md`). Any demand-response or "Operation Gigawatt" claim is removed pending an owner source (audit F25).

**34. "On a flat marginal basis your battery adds CO₂. So storage is bad for carbon here?"** *(critical)*
On a flat marginal factor, yes: losses add about 107 t at 4 MWh. On hourly average intensity, the carbon schedule cuts 4.0% (validation 3.5%; 2.0–4.2% across 75–90% efficiency). Carbon is storage's weak case here; aiming at the rush is the stronger one. <!-- results/test/extras.json storage.schedule_comparison.schedules.carbon.cases.U["4"].flat_marginal_cut_t −107.1, .cut_frac 0.0395; results/storage.json cases.U.strategies.A.{0.75,0.85,0.90}.cut_frac[3] 0.0199, 0.0351, 0.0420 -->
- Storage only helps if charging-hour intensity ÷ efficiency is below the intensity it displaces. Losses: about 169 MWh a year. <!-- storage.cases.U.A["4"].losses_mwh 169.3 -->

**35. "Does the battery actually hit Utah's rush?"** *(critical)*
Only if you aim it there. The carbon schedule discharges in 6 of the 14 rush hours (0.88 → 0.55 MW). The peak-aimed schedule, registered before the opening, discharges in 10 and cuts the cluster's average rush draw to 0.32 MW, but CO₂ by only 1.0%. Aim it at carbon or at the rush, not both. <!-- results/test/extras.json storage.schedule_comparison.schedules.{carbon,peak}.cases.U["4"].rush_hours_discharging 6, 10; .rush_import_after_mw 0.552, 0.317; peak .cut_frac 0.0097; D-073 -->
- On validation the carbon schedule's rush effect was tiny (1.12 → 1.04 MW, 1 of 12 hours); the year matters. <!-- results/extras-validation.json storage_peak.schedules.carbon.cases.U["4"] -->
- Don't say: "storage shaves Utah's peak", "the battery covers the rush".

**36. "Charging pushes your site to its connection limit. Haven't you made the interconnection problem worse?"**
Slightly, in this illustration: under either schedule the site's highest hourly draw goes from 1.64 to its 1.65 MW connection, because charging fills the headroom. Peak import does not fall. <!-- storage.schedule_comparison.schedules.{carbon,peak}.cases.U["4"].peak_import_before_mw 1.639, .peak_import_after_mw 1.647 -->
- Don't say: "reduces peak demand".

**37. "Your router adds load in Bonneville during Utah's rush. Aren't you exporting your peak?"**
We count it. In Utah's 14 rush hours, S lowers the cluster's Utah load by 0.22 MW and adds 0.20 MW in Bonneville and 0.04 MW in California. Bonneville's own rush hours are its cleaner ones (validation), but someone still serves that load. <!-- results/test/extras.json storage.peak_relief.S.{PACE,BPAT,CISO}.rush_change_vs_U_mw −0.222, +0.204, +0.040; results/overview.json (PR #93) regions.BPAT.alignment.rush_vs_mean_pct −8.0 -->

**38. "Move and store together: what's the best if big jobs stay home?"**
Move the small jobs and store for the rest: 7.7% at 4 MWh, against 3.9% for moving alone, as a ratio of totals rather than our interval method. <!-- results/test/extras.json storage.combined.move_and_store_cut_frac.A["4"] 0.0774, .move_only_cut_frac 0.0387 -->

**39. "Why 4 MWh / 1 MW? Did you pick it after seeing results?"**
Yes, after validation, and it's labelled that way: sized to the charging room the connection leaves free, not an optimum. 8 MWh adds little (4.2% on test). No degradation, capex or self-discharge: an hourly illustration, not a business case. <!-- results/test/extras.json storage.cases.U.A["8"].cut_frac 0.0419; D-067 -->

**40. "What about fast swings: AI training power spikes, frequency?"**
Outside our hourly model. That needs measured, sub-second cluster power; it's the interface we'd build next, with Torus.

**41. "What about water?"**
An illustration on both years, and we make no water-saving claim. Moving work lowers generation water if hydro evaporation is excluded (−19%, test year) and raises it about 2.7× if it's included. It's consumption, not withdrawal, production-side weighting, and PACE isn't the Great Salt Lake watershed. <!-- results/test/extras.json water.policies.S.change_vs_U.ex_hydro_frac −0.186, .with_hydro_frac +1.741; water.claim "none" (validation results/water.json policies.S.change_vs_U −20.5%, +145%) -->

### H. Grid context

**42. "Nine of ten regions have dirtier rush hours, yet waiting buys under 1%. Contradiction?"**
No. The rush hours are dirtier, but 63% of the energy is in jobs longer than a day, and jobs may wait at most 6 hours. Even with a 24-hour allowance, waiting alone reaches only 1.5%. The swing is there; this workload can't use it. <!-- results/test/extras.json extensions.batch_delay_24h.vs_U.W_time["4"] 0.0148; results/overview.json (PR #93) rush_verdict -->

**43. "Is '9 of 10' meaningful? Some margins are tiny."**
The margins vary: Utah +20%, Colorado +18%, Texas +17%; California +2%, Arizona and PJM +3–4%; Bonneville −8%. It's a validation-year pattern across regions, not a test. <!-- results/overview.json (PR #93) regions.*.alignment.rush_vs_mean_pct -->

**44. "Does the result hold across seasons?"**
Pre-registered seasonal split on the test year, S vs U: winter 26%, spring 21%, summer 28%, autumn 13%. Autumn's weeks join the window's two ends, Nov 2025 and Sep–Oct 2026. <!-- results/test/extras.json seasonal.seasons.{DJF,MAM,JJA,SON}.policies.S.blocks["4"].saving 0.261, 0.215, 0.285, 0.133 -->

**45. "What did the router do on Utah's toughest days?"**
Rule fixed in advance: the 3 days with the highest peak net load (D-066). On the test year S cut the cluster's CO₂ by 7%, 15% and 29% on Aug 20, Jul 23 and Jul 11, 2026. <!-- results/test/extras.json toughest_days.days[*].policies.S.co2_change_vs_U_frac −0.069, −0.151, −0.292 -->

### I. Data, novelty and next

**46. "Where does the data come from?"**
- **Grid:** EIA-930 hourly demand, generation by fuel and interchange, and EIA's hourly consumption-basis CO₂ estimates, for the four router sites and ten regions in the overview.
- **Workload:** the public Acme trace from Shanghai AI Lab's Seren cluster (NSDI '24, CC-BY-4.0).
- **Weather:** Open-Meteo archived forecasts (the toughest-days case study only).
- **Water:** NREL technical-report consumption factors and the LBNL 2024 data-center report.
- **Prices:** CAISO/WEIM real-time LMPs (the wholesale scenario).
- **Map:** balancing-area boundaries from Electricity Maps and a Natural Earth basemap.

All free and open; every number on screen is labelled observed, measured, modeled, forecast, assumed or simulated.

**47. "WattTime, Electricity Maps, Google's carbon-intelligent computing already do this. What's new?"**
They publish signals, or shift work inside one fleet. We add an open, sealed-test comparison of time against place on identical work, with capacity and deadlines: time-shifting in Utah is under 1%, and job mobility, not forecast quality, decides the result.
- Don't say: "first ever"; claims about those companies' internals.

**48. "Who buys this?"**
Today it's an analysis and an open tool, not a company. The buyer is an operator deciding where flexible capacity goes, or a utility sizing demand response. The first product is a "which jobs can move" audit; the fixed ranking is the baseline to pilot.

**49. "Did AI build this?"**
AI agents helped build and review it. We froze the configuration before opening the holdout once; the routing policy remains a fixed ranking. Reviews ran in separate sessions, and their findings, including ones that weakened our claims, are in the decision log.
- Don't say: "agents validated the science", "bias eliminated", productivity numbers.

**50. "What machine did you use?"**
An NVIDIA DGX Spark.

**51. "What would you do next?"**
- **With an operator:** tag which real jobs can move (checkpointing, data size, residency). That's the number that decides the saving.
- **The two cut tests:** run without advance reservations, and with runtime overruns.
- **With Torus:** couple the router's residual Utah load to storage dispatch, and add fast-timescale buffering from measured cluster power.
