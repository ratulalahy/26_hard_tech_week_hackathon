# GridPilot: the 4:30 demo script

**Status:** post-test rewrite, Tue 2026-10-27 night. Every number is filled from committed JSON; the numbers card is `docs/pitch/numbers.md`, and each number below cites its JSON path in an HTML comment. Results-audit dispositions: `docs/reviews/2026-10-27-results-audit-claude-r1-dispositions.md`.

- **Window:** the whole demo runs with the switch on **Test year (sealed, opened once)**. Every on-screen number listed below is the test-mode value (audit F3). Where a beat speaks a validation number, the script says "validation" aloud.
- **Screen copy** is the dashboard's test view on `main`. Re-check each "on screen" line at the first rehearsal; if the screen changed, change the script, never the other way round.
- **Timing:** six beats, 598 spoken words (numerals counted as spoken: "22.3 percent" is 4 words), about 4:00 at 150 words a minute; with clicks it lands about 4:15, inside the 4:30 slot.
- **Setup:** Chrome, full screen, the offline build at `http://127.0.0.1:4173/`. Deep links: `#story-1` … `#story-6`, `#control`. Switch to Test year first and check the switch reads "Test year (sealed, opened once)".

| Beat | Time | Screen | Spoken words |
|---|---|---|---|
| 1 Utah's evening rush | 0:00–0:40 | `#story-1` | 94 |
| 2 One job: stay, wait or move | 0:40–1:14 | `#story-2` | 79 |
| 3 The whole test year | 1:14–2:12 | `#story-3` | 133 |
| 4 The condition: mobility | 2:12–2:53 | `#story-4` | 94 |
| 5 Store for what can't move | 2:53–3:45 | `#story-5` | 121 |
| 6 Close | 3:45–4:15 | `#control` | 77 |

**Cut list.** The cuts are pre-marked in the script as `[c1: …]` … `[c6: …]`. If a stopwatch rehearsal, clicks included, runs past about 4:20, drop them in order:

| Cut | Beat | Words dropped (spoken) | Text |
|---|---|---|---|
| c1 | 1 | 17 | "In our validation year, nine of ten US regions had dirtier rush hours; Bonneville was the exception." (stays in Q&A #43–#44) |
| c2 | 4 | 7 | "Our 72-GPU job would stay home." |
| c3 | 4 | 3 | "Both years agree." |
| c4 | 5 | 12 | "Seconds-scale buffering is outside our hourly model; that's the next interface." (stays in Q&A #40) |
| c5 | 6 | 6 | "Every assumption is one click away." |
| c6 | 3 | 5 | "Validation was 22.6." Only if pressed: the validation number then lives on the deck and in Q&A #1. |

c1–c5 save 45 spoken words (about 18 s); with c6, 50 (about 20 s). Never cut the mobility caveat (Beats 3, 4, 6), "attributed, not avoided", "simulated replay", the deadline caveat or the agent sentence.

---

## Beat 1 · 0:00–0:40 · Utah's evening rush

- **Show:** Story, step 1 (`#story-1`): the Utah July-weekday load chart with the carbon ribbon, and the heat map below.
- **On screen (test mode):** July 2026 weekdays; demand peaks at 5 PM; net load climbs to 8 PM, **6,182 MW**. <!-- results/test/grid-profile.json pace_july_weekday.net_load_mw[20] = 6181.96; .demand_mw argmax = 17; .month = 2026-07 -->

> This is Utah's grid, PACE, which serves much of Utah, on an average July weekday of our sealed, 358-day test year. Demand peaks around five. As solar fades, net load, what the rest of the fleet must carry, climbs to about sixty-two hundred megawatts at 8 PM: the grid's rush hour. [c1: In our validation year, nine of ten US regions had dirtier rush hours; Bonneville was the exception.]
>
> Picture a hypothetical 2,300-GPU AI cluster here. Our goal: cut the CO₂ attributed to its work, same work, same deadlines.

<!-- 9 of 10: results/overview.json regions.*.alignment.rush_verdict; BPAT rush_vs_mean_pct = -8.0 (validation) -->
<!-- 2,288 GPUs: results/test/manifest.json assumptions.home_slots -->

*Notes:*
- "As solar fades", never "after sunset".
- The ten-region line (c1) is validation-year (`overview.json`, the Regions page); it is not on this screen.
- The cluster size (2,288 GPUs, about 1.6 MW when fully busy) is **assumed**. <!-- fully busy: results/test/manifest.json assumptions.home_slots 2288 × kw_per_gpu 0.6 × pue 1.2 = 1.647 MW (derived) -->

---

## Beat 2 · 0:40–1:14 · One job: stay, wait or move

- **Show:** Story, step 2 (`#story-2`): job **5930563#c5**, its options table and "Where each policy put it".
- **On screen (test mode):** stay in Utah **2,098 kg**; move to the Northwest **362 kg**; S placed it in BPAT. <!-- results/test/job-replay.json illustrative_job.job_uid = 5930563#c5; available_actions[stay].co2_kg = 2098.4; available_actions[BPAT].co2_kg = 361.6; placements.S.site = BPAT -->

> One real job from a public GPU-cluster trace, replayed onto Utah: 72 GPUs, 104 hours of pre-training.
>
> Stay: about twenty-one hundred kilograms of attributed CO₂.
>
> Wait: it may start up to six hours late, which buys almost nothing against a 104-hour run.
>
> Move: half an hour of transfer, then the Northwest's hydro-heavy grid, about 360 kilograms. Moving means placing a job before it starts; nothing migrates mid-run.

<!-- 72 GPUs, 103.6 h: results/test/job-replay.json illustrative_job.gpus, .declared_duration_s; 6 h: results/test/job-replay.json illustrative_job.max_delay_s = 21600; 30 min: results/test/manifest.json assumptions.transfer_time_s = 1800 -->

*Notes:*
- The job was picked by a rule fixed before its outcome was seen: the GPU-hour-weighted median of the eligible flexible jobs (D-054). On the test year that rule picks a sibling of the validation job (#c5, not #c3).
- Don't quote the Decision cockpit's typical-day number here: it has no fleet contention.

---

## Beat 3 · 1:14–2:12 · The whole test year

- **Show:** Story, step 3 (`#story-3`): the interval chart, every policy's own 95% interval.
- **On screen (test mode):** S **22.3%**, its own 95% interval **17.3–27.2%**; waiting in Utah alone "under 1%" (W wait-only 0.77%); "70% of the energy S ran outside Utah ran in the Northwest"; the H3 sentence (no dynamic search beat S). <!-- results/test/metrics.json contrasts[S/U].blocks["4"].saving = 0.2226, .saving_ci95 = [0.1734, 0.2720]; contrasts[W_time/U] 0.0077, contrasts[L_time/U] 0.0079 -->

> We replayed 888 thousand jobs against hourly EIA carbon data, in a simulated replay. AI agents helped build and review it. We froze the configuration before opening the holdout once; the routing policy remains a fixed ranking.
>
> That fixed clean-region ranking, policy S, cut attributed emissions 22.3 percent, interval 17.3 to 27.2. [c6: Validation was 22.6.] Waiting in Utah alone: under 1 percent. 70 percent of the work that left Utah ran in the Northwest.
>
> These are attributed emissions, not avoided. Deadlines are met by construction, through baseline bookings, with exact declared runtimes.
>
> Forecast-based search showed no demonstrated aggregate routing benefit over the fixed ranking in this replay. So the ranking is the baseline to pilot, if the big jobs can move.

<!-- 888,224 jobs: results/test/metrics.json cohort.n_jobs -->
<!-- 358 days: derived, results/test/manifest.json split.eval_start 2025-11-01 → split.F 2026-10-25 (D-074) -->
<!-- 22.6: results/metrics.json contrasts[S/U].blocks["4"].saving = 0.2262 (validation) -->
<!-- 70%: derived, results/test/metrics.json policies.S.metrics.execution_kwh_by_site BPAT 1,735,162 / (BPAT + CISO 623,965 + NEVP 103,479) = 70.5% -->
<!-- no demonstrated benefit: results/test/metrics.json framing.placement_vs_timing (K − S +9.9 t [+0.8, +19.5]; W − S +3.9 t [−4.7, +13.8]; L − S +6.6 t [−2.0, +16.7]) -->
<!-- forecasts (Q&A only since this round): results/outlook.json skill_by_horizon (validation issues): BPAT/CISO/NEVP 9.9–23.4% with 90% intervals above zero; PACE 3.0–4.8%, every interval crosses zero (D-072) -->

*Notes:*
- The interval is S's own estimate, never a span across policies.
- "358 days": the test year ends at the snapshot's last complete day (Oct 24). Never say "a full year" or "twelve months".
- The forecast-skill sentence was cut for time; it lives in qa.md #13 and #16. The last sentence ("…if the big jobs can move") points at Beat 4.
- Never "simple rules beat AI". Never "the one to deploy". Never "30×".
- If asked "isn't 3.9 better than 3.2?", see qa.md #4.

---

## Beat 4 · 2:12–2:53 · The condition that decides it: mobility

- **Show:** Story, step 4 (`#story-4`). Point at the text. The map shows the test-year replay week (`results/test/job-replay.json`, titled "S: 22.3% less CO₂ · registered result · test year"); only the scenario toggle and the flexibility budget are validation-only, and they say so.
- **On screen (test mode):** "The largest 1% of jobs use **95%** of the energy"; "If only jobs of 8 GPUs or fewer may move, S, W and L cut **3.2–3.9%** on the test year instead of 22.3% (S 3.2%, 1.9–4.7%)". <!-- results/test/metrics.json workload.top_1pct_jobs_by_declared_gpu_h.energy_share = 0.9452; results/test/extras.json extensions.mobility_le_8gpus.vs_U.S["4"].saving = 0.0315, .saving_ci95 = [0.0189, 0.0467]; .W["4"] 0.0387, .L["4"] 0.0388 -->

> In this workload, the largest 1 percent of jobs use 95 percent of the energy.
>
> If only jobs of 8 GPUs or fewer may move, S's saving falls from 22.3 percent to 3.2; the forecast policies, which can also wait, reach 3.9. [c2: Our 72-GPU job would stay home.]
>
> Other changes matter much less: a two-hour transfer still gives about 20 percent; twice the spare capacity, 35. [c3: Both years agree.]
>
> So whether large training jobs can move is the lever. Here it's an assumption, not a measurement.

<!-- 20%: results/test/extras.json extensions.transfer_120min.vs_U.S["4"].saving = 0.1995 (validation results/extensions.json sensitivities.transfer_120min.policies.S.vs_U["4"] 0.2019) -->
<!-- 35: results/test/extras.json extensions.dest_slots_1024.vs_U.S["4"].saving = 0.3487 (validation 0.3502) -->

*Notes:*
- The transfer and capacity numbers are in the method drawer ("Robustness and sensitivity checks, test year", validation beside test), not on the Story screen.
- Validation was 22.6 → 3.2 [2.1–4.5]; say it only if asked. <!-- results/extensions.json sensitivities.mobility_le_8gpus.policies.S.vs_U["4"] = 0.0324 [0.0207, 0.0453] -->
- Say "ran outside Utah" (remote execution), not "moved": the ledger's "moved" also counts time shifts.

---

## Beat 5 · 2:53–3:45 · Store for what can't move

- **Show:** Story, step 5 (`#story-5`): the two-schedule table ("Carbon schedule (the headline)" and "Peak-aimed schedule (D-073)") and the bold flat-marginal line.
- **On screen (test mode):** carbon schedule CO₂ cut **4.0%**, flat-marginal basis adds **107 t**, average rush-hour draw 0.88 → 0.55 MW, yearly peak draw 1.64 → 1.65 MW, 6 of 14 rush hours; peak-aimed schedule **1.0%**, adds 77 t, **0.88 → 0.32 MW**, 1.64 → 1.65 MW, 10 of 14. <!-- results/test/extras.json storage.schedule_comparison.schedules.{carbon,peak}.cases.U["4"]: cut_frac 0.0395 / 0.0097; flat_marginal_cut_t −107.1 / −77.0; rush_import_before_mw 0.879; rush_import_after_mw 0.552 / 0.317; peak_import_before_mw 1.639 → peak_import_after_mw 1.647; rush_hours_discharging 6 / 10; storage.rush.n_hours 14 -->

> What about the work that can't move? We put an illustrative 4 megawatt-hour, 1 megawatt battery at the Utah site, with two fixed schedules registered before we opened the test year.
>
> Aimed at carbon, it cuts the cluster's attributed CO₂ about 4 percent, but on a flat marginal factor its losses add about 107 tonnes.
>
> Aimed at the rush, Utah's 14 tightest hours, it cuts the cluster's average draw from 0.88 to 0.32 megawatts, but CO₂ by only 1 percent. Neither lowers the site's yearly peak: charging fills the connection.
>
> So aim the battery at carbon or at the rush, not both. [c4: Seconds-scale buffering is outside our hourly model; that's the next interface.]

<!-- 4 MWh / 1 MW, η 0.85: results/test/extras.json storage.rule -->
<!-- 14 tightest hours: results/test/extras.json storage.rush.n_hours = 14, threshold_mw = 7207 (training years' top 1%) -->
<!-- registered: D-071 item 2 (carbon schedule from results/storage.json, training years 2022-01-01 to 2024-10-29), D-073 item 2b (peak schedule) -->

*Notes:*
- Not spoken (on screen): "Moving the small jobs and storing for the rest reaches 7.7 percent." <!-- results/test/extras.json storage.combined.move_and_store_cut_frac.A["4"] = 0.0774; .move_only_cut_frac = 0.0387 -->
- 85% round trip and the connection cap are on screen and in the notes, not spoken. The rush here is the 14 test-year hours at or above the training years' top-1% net load (7,207 MW), not the evening rush band of Beat 1 (7–11 PM on the test year; the validation year's band was 7–10 PM).
- Validation: carbon schedule 3.5%, and its rush draw fell only 1.12 → 1.04 MW; the peak schedule's rush effect was smaller on validation (1.12 → 0.90 MW). Say so if asked. <!-- results/extras-validation.json storage_peak.schedules.{carbon,peak}.cases.U["4"] -->
- Torus is the audience: don't name its products as modeled. Never call the hindsight heuristic a "bound" or "optimal". Don't put a price on MW.

---

## Beat 6 · 3:45–4:15 · Close

- **Show:** the Control room (`#control`), test mode: the hero and its mobility line, with the Utah rush strip at the bottom.
- **On screen (test mode):** hero "Sealed test year, simulated replay: moving Utah's AI jobs cut their CO₂ by 22.3%; waiting in Utah alone cut it by 0.8%"; "Its own 95% interval 17.3–27.2%"; mobility line "**3.2–3.9%** (scenario estimates)"; rush strip "net-load peak 8 PM, 6,182 MW". <!-- results/test/metrics.json contrasts[S/U].blocks["4"]; contrasts[W_time/U], [L_time/U]; results/test/extras.json extensions.mobility_le_8gpus.vs_U.{S,W,L}["4"] -->

> In a simulated replay of a sealed test year, a fixed clean-region ranking cut the attributed emissions of the same work 22.3 percent, and 3.2 if only small jobs can move. [c5: Every assumption is one click away.]
>
> For an operator: first find which work can move. Then size storage for the Utah load that can't, aimed at carbon or at the rush. The fixed ranking is the baseline to pilot. Thank you.

---

## Spoken-route rules

- Keep: "simulated replay"; "attributed, not avoided"; "deadlines met by construction (baseline bookings)"; "exact declared runtimes"; "358 days" at the first "sealed test year"; "PACE, which serves much of Utah"; "baseline to pilot"; "forecast-based search showed no demonstrated aggregate routing benefit over the fixed ranking in this replay".
- Never: "30×"; "proves" or "confirms"; "avoided" except in "not avoided"; "deploy"; "simple rules beat AI"; "a full year"; any Torus partnership or program claim (removed pending an owner source, audit F25).
- The headline is S's own number and interval; the validation 22.6% is said beside it, unless cut c6 is used.
- The headline sentence ends "…if the big jobs can move", the mobility number follows within the minute (Beat 4), and both are said together in Beat 6.
- One click away for Q&A: the full policy table (Control room right panel), the method drawer's test-year sections (checks, storage, water, seasons, forecast skill, the validation → test drift table), the Outlook page (live, issued Oct 27 10:00 MT for Oct 28 – Nov 3; Utah shown at its seasonal average because its forecast doesn't beat it), the Prices page (validation, wholesale scenario) and the Regions page (validation).

## What changed from the draft (for the owner)

- All beats run on the test year and speak the test-mode screen (F3). The job is #c5 (2,098 vs 362 kg), July 2026 is 6,182 MW.
- Deep links fixed: the job is `#story-2`, the aggregate `#story-3`, mobility `#story-4`, storage `#story-5` (the draft's `#story-3`/`#story-5` pointed at the wrong steps).
- "Our day-ahead forecasts follow Utah's daily swing" is gone (F4); "the one to deploy" became "baseline to pilot".
- The mobility caveat is the test value, 3.2% (F2); scenario numbers are test with validation agreeing (F9).
- Storage is pitched honestly: about 4% on carbon, +107 t on a flat marginal basis, peak-aimed 0.88 → 0.32 MW for only 1%, no lower yearly peak (F5).
- One sentence on the agent-built process (Sol's agent-angle review).
- Fix round r1 (pitch review): script cut from 676 written / about 727 spoken words to 598 spoken, with a real cut list; "358 days" moved to the first mention; Beat 4 map note corrected; citations for the delay, transfer and fully-busy power corrected.
