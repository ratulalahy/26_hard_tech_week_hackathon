# Strategy review r1: Astra (gpt-6-astra, high). Owner-requested; Codex run 4

- **Run:** 20261027T202743Z-f1a7b0
- **Reviewed:** main @ 754781d
- **Prompt:** `docs/reviews/prompts/2026-10-27-plan-astra-r1.md`

## Review (verbatim)

The entry has a credible path to winning: **show that workload mobility matters far more than forecast sophistication, then show where storage complements limited mobility.** The main risks are overstating what the simulation proves, introducing an unsound storage “bound,” and leaving presentation and laptop verification too late.

I reviewed commit `754781d7f21415916102a86ee6f78800d681751f` read-only. No files were changed. I inspected the committed results, code, plans and screenshots; I did not run experiments, read sealed data, or rerun builds/tests.

Progress is substantial:

- `checkpoint-tue` exists at `e7b70cc`.
- All seven dashboard JSON copies match their `results/` originals; the three artifact hashes recorded in the manifest match.
- The extensions record matching primary-reproduction metrics and all nine policy ledgers. This is **not yet the independent rebuild from raw inputs** required before freeze.
- At this commit, storage, the freeze record and test results are absent; `Window.test()` still raises `NotImplementedError("T11…")`. Work on other branches is outside this review.

The validation evidence says:

| Comparison | Reduction in attributed operational CO₂ |
|---|---:|
| Static clean-region ranking S versus Utah-only U | **22.62%**, conditional 95% interval **18.36–26.82%** |
| Dynamic K/W/L versus U | **22.41–22.51%** |
| Waiting in Utah, W/L | **0.72–0.75%** |
| Mobility restricted to jobs ≤8 GPUs, S/W/L | **3.24–3.94%** |
| Destination capacity doubled, S/W/L | **34.89–35.02%** |
| Two-hour transfers, S/W/L | **20.19–20.25%** |

These are simulated, validation-only results. Sources: [metrics.json](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/results/metrics.json) and [extensions.json](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/results/extensions.json).

All effort estimates below are approximate person-hours, including focused verification.

**1. Plan and timeline risk**

- **F01 — Important; high confidence. Location: [Stage 3 plan, T11–T13](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/docs/superpowers/plans/2026-10-27-stage3-freeze-test.md:26).** The scientific order is correct: seal machinery → independent rebuild → freeze → test → audit. However, the pinned main has not completed the first three. **Failure:** “run overnight” becomes overnight implementation and debugging, consuming the audit window. **Correction:** make T11’s synthetic end-to-end refusal/read-log checks and T12’s raw-input rebuild the immediate critical path. Reserve a concrete checkpoint tonight for accepting or rejecting readiness to unseal. **Effort: 4–6 h; value: high.**

- **F02 — Important; high confidence. Location: [T12 rebuild/tree-hash requirement](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/docs/superpowers/plans/amendments/stage3-T12.md:54), [T10b deadline](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/docs/superpowers/plans/amendments/stage3-T10b.md:3).** Storage modifies `lab/`, while the freeze writer requires the rebuilt `lab/` tree to match the final candidate. **Failure:** storage lands after the independent rebuild and invalidates its evidence. **Correction:** merge all intended lab changes before the qualifying rebuild; target storage integration earlier than the 21:00 hard stop. Treat any later lab change as requiring renewed verification. **Effort: 0.5 h coordination, plus any necessary rebuild; value: high.**

- **F03 — Important; high confidence. Location: [D-061 pitch decision](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/docs/decisions.md:477).** Starting the deck, narrative and one-pager only after Wednesday’s audit creates an avoidable serial dependency. **Failure:** an audit finishing at 11:00 leaves three hours to settle claims, produce materials, rehearse and lock numbers. **Correction:** recommend that the owner amend D-061 to allow the narrative skeleton, visual sequence and Q&A tonight, with explicitly unresolved test-number placeholders. Finalize numerical claims after audit. **Effort: 1.5–2 h tonight; value: high.**

- **F04 — Important; high confidence. Location: [web/README.md](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/web/README.md), spec §11 laptop delivery.** The documented Mac path starts with `npm ci`; no actual-Mac acceptance evidence is present in the reviewed artifacts. **Failure:** dependency installation, WebGL, screen scaling or a missing launcher breaks the demo. **Correction:** rehearse the current validation build on the actual Mac tonight. Prepare the built assets, a verified localhost launcher, and a recording/static fallback; repeat a short acceptance check after final export. **Effort: 1–2 h; value: high.**

Cut first: new water/health modeling, weather-model retraining, additional scenario sweeps, a full-year curtailment ingestion, and exploratory UI work. Next simplify the proposed storage comparison by removing the unsupported optimality claim. Preserve the rebuild, seal, audit, signed outcomes and offline rehearsal. Any reduction of an owner-approved Must item needs the owner’s decision.

**2. Soundness of the claims**

- **F05 — Important; high confidence. Location: [run_slice.py, `s_ranking()`](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/lab/scripts/run_slice.py:218), [T12 test-ranking window](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/docs/superpowers/plans/amendments/stage3-T12.md:43).** S’s ranking uses carbon rows through October 28 without the 96-hour publication-lag filter applied to the forecasts. Some of those rows are unavailable at the first November 1 decisions; they are also unavailable at the stated October 29 fit time. **Failure:** the strongest baseline violates the entry’s own availability rule. **Correction:** apply the availability envelope at an explicit ranking-fit time, verify whether the ordering changes, and record the correction before freeze. An unchanged ordering could preserve schedules, but does not eliminate the provenance error. **Effort: 1–2 h plus reproduction if needed; value: high.**

- **F06 — Important; high confidence. Location: `metrics.framing`, proposed “30×” headline.** Approximately 30× is a ratio of two estimated reductions against U; it is neither 30× lower total emissions nor a clean additive decomposition of placement and waiting. A place-only matched ablation is absent. **Failure:** a judge asks what exactly was multiplied, and the headline collapses into qualifications. **Correction:** lead with **“about 22.5% versus less than 1% in this scenario.”** If retaining 30×, call it the ratio of point-estimated savings and use matched W/W-time or L/L-time comparisons. **Effort: 0.25 h for wording; 1 h for a paired ratio interval; value: high for wording, low for the extra interval.**

- **F07 — Important; high confidence. Location: `metrics.h2`, `metrics.framing`, `coverage_stratum`.** “S ties dynamic search” can imply demonstrated equivalence. W and L are not distinguishable from S; K is worse by about 10 t. H2 is inconclusive. Only **29.0% of flexible energy belongs to jobs whose complete decision window lies inside forecast coverage**. **Failure:** “ML adds no value” becomes a universal conclusion from a setting dominated by long jobs and climatological tails. **Correction:** say **“We found no demonstrated aggregate benefit from dynamic search over the fixed ranking in this replay.”** Explain the horizon limitation in Q&A. **Effort: 0.5 h; value: high.**

- **F08 — Important; high confidence. Location: `extensions.sensitivities.mobility_le_8gpus`, `metrics.workload`.** Mobility is the central condition, not a secondary caveat. The top 1% of replay jobs carries 94.1% of modeled execution energy. In the ≤8-GPU scenario, S changes placement for roughly 41% of jobs but executes only about 4.3% of energy remotely. **Failure:** impressive job counts obscure how little large-job energy can actually move. **Correction:** put the **22.6% → 3.2%** S comparison beside the headline, and consistently distinguish remote execution from the ledger’s broader “moved” definition, which includes time changes. **Effort: 0.5–1 h; value: high.**

- **F09 — Important; high confidence. Location: [manifest claim frame and limitations](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/results/manifest.json).** Whole-run advance reservations, exact declared runtimes and baseline-relative deadlines are accepted assumptions. Shadow-U and runtime-overrun checks were cut. **Failure:** “no missed deadlines” is heard as production reliability, or “same work” as equal useful model training. **Correction:** retain “deadlines met by construction”; describe conserved work as declared GPU-hours, including attempted work. Do not reopen these cut experiments now. **Effort: 0.5 h for claim/Q&A review; value: high.**

- **F10 — Important; high confidence. Location: `metrics.contrasts`, `extensions`, [headline aggregation](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/web/src/lib/data.ts:132).** The intervals condition on one replay and model; the phase checks reuse the same source trace. The dashboard also combines the outer endpoints of several policies’ intervals into one displayed range. **Failure:** judges interpret that range as one policy’s confidence interval or independent evidence across clusters. **Correction:** headline the selected policy’s own estimate and interval; retain other policies separately. Describe phase tests as alignment checks and the 20.2–23.2% extension span as scenario estimates, not a confidence interval. **Effort: 0.5–1 h; value: high.**

- **F11 — Important; high confidence. Location: spec §4/§15 F9, `manifest.not_run`, current results exports.** The product opens with grid rush hour, but exported policy results do not establish reduced rush-hour exposure. The omission list does not fully account for deferred stress evaluation, price accounting and other F9 extras. **Failure:** “we stay out of grid traffic” is asserted using carbon savings alone. **Correction:** explicitly inventory these omissions; either add the narrow peak-exposure analysis below or limit the claim to carbon attribution. **Effort: 0.5 h for inventory; 2–3 h for analysis; value: high.**

Prepare these one-line answers:

| Judge’s attack | Answer |
|---|---|
| “Why not just send everything to Bonneville?” | “We tested that principle: a capacity-constrained fixed ranking is our best validation policy; forecasting has not earned extra credit here.” |
| “Did you avoid 22% of real emissions?” | “No: we reduced modeled emissions attributed to an identical workload in simulation; we did not estimate the grid’s causal response.” |
| “Can those large training jobs actually move?” | “Mobility is assumed; restricting moves to ≤8-GPU jobs reduces savings to about 3–4%.” |
| “How did you guarantee deadlines?” | “Each job retains its baseline reservation, with exact assumed runtimes; production runtime uncertainty is untested.” |
| “What does 30× mean?” | “About 22.5% savings versus about 0.75%, both relative to Utah-only execution in this scenario.” |
| “Do the robustness checks confirm it?” | “They preserve the placement pattern under several specified changes; they do not validate untested mobility, idle-power or reservation assumptions.” |
| “Why is hindsight not always best?” | “Hindsight still uses a greedy per-job scheduler; it is not the optimum for the whole workload.” |
| “Is this cheaper?” | “Cost was not the optimization objective and has not yet been evaluated on comparable fleet-wide prices.” |

**3. Fit to Torus and the bounty**

The Option 2 fit is strong: a visible placement decision, real public inputs, finite capacity and an honest result. The storage bridge is sensible, but it needs to demonstrate a useful operating question rather than simply attach a battery curve.

Torus’s own technical brief emphasizes demand response, frequency/voltage support and hybrid storage. That supports a story about complementary timescales; it does not validate this illustrative battery’s parameters. [Torus technical brief](https://www.torus.co/news/technical-brief-rocky-mountain-power-and-torus-sign-mou-to-deploy-70-megawatts).

- **F12 — Critical; high confidence. Location: [T10b Strategy B](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/docs/superpowers/plans/amendments/stage3-T10b.md:24).** Greedy pairing of clean charging hours and dirty discharge hours is called “optimal” and a “hindsight upper bound.” Neither follows from the proposed algorithm. Chronology and state of charge couple decisions. **Failure:** an achievable heuristic is presented as a mathematical limit, or pairing implicitly discharges energy before charging it. **Correction:** the quickest fix is **“hindsight heuristic.”** A genuine bound needs an exact formulation or documented relaxation. Even an exact daily optimum only bounds policies with matching daily boundary conditions. **Effort: 0.25 h to rename; 2–4 h for a verified optimization formulation; value: high.**

- **F13 — Important; high confidence. Location: [T10b model and combined view](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/docs/superpowers/plans/amendments/stage3-T10b.md:14).** Initial/final state of charge, day-boundary carryover, charging connection limits and the combined accounting boundary are unspecified. At 24 MWh, `P=E/4` allows 6 MW charging, versus an assumed fully busy home-cluster execution load of about **1.65 MW**. **Failure:** free initial energy, repeated daily resets, unrealistic charging headroom, or mixing warm-up-inclusive storage totals with cohort-only router totals manufactures a benefit. **Correction:** define chronological SOC, terminal energy treatment, power limits and a common accounting window. Combined emissions must include residual Utah imports, remote execution and transfer energy exactly once. **Effort: 1.5–3 h; value: high.**

- **F14 — Important; high confidence. Location: D-061 and T10b’s marginal-proxy fallback; [grid profile §8](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/docs/data-profile/grid.md:413).** Storage can increase emissions through losses. A range of regression coefficients is insufficient to price charging and discharging by hour, and high regression fit does not identify causal marginal emissions. **Failure:** a weak or adverse result gets converted into “storage saves carbon.” **Correction:** show the break-even condition:
  
  \[
  \text{charging intensity}/\eta < \text{displaced intensity}.
  \]
  
  Retain negative results. If the proxy lacks a defensible hourly assignment, show a labeled threshold scenario rather than an annual avoided-emissions total. **Effort: 0.5–1 h; value: high.**

- **F15 — Important; high confidence. Location: T10b’s carbon-only outputs and the bounty in `docs/brief.md`.** A four-hour energy-shifting illustration does not evaluate Torus’s fast power-quality role, and carbon-minimizing discharge need not coincide with Utah’s rush hour. **Failure:** the sponsor sees a generic battery appendix rather than a useful interface to its business. **Correction:** show **Utah grid import before/after**, battery MW/MWh, charge rebound and residual demand during defined peak hours. Label fast buffering as a future interface, outside the hourly model. **Effort: 2–3 h; value: high.**

- **F16 — Minor; high confidence. Location: branding, map labels and Story 4.** “Compute Follows the Sun” overstates the demonstrated mechanism: roughly two-thirds of L’s remote execution energy goes to hydro-heavy BPAT. PACE also extends beyond Utah. **Failure:** a geographically knowledgeable judge hears “solar chasing across Utah” when the evidence is mostly regional placement. **Correction:** use **“Compute follows cleaner power”** in the spoken result; introduce “PACE, the balancing area serving much of Utah.” **Effort: 0.25 h; value: medium.**

The strongest closing proposition is: **“First identify what workload can move. Then quantify the residual Utah load that storage could serve.”** It offers Torus an actionable planning interface without claiming device integration.

**4. Outside variables worth considering**

Add **at most one substantial analysis**, preferably peak relief. Prices are the best optional second addition. Weather and prices already being downloaded makes them cheaper to explore, but does not make them validated model inputs.

Every addition should use the validation window only, preserve the registered schedules and headline, carry its own source/version and assumptions, and remain clearly illustrative. Reopening weather/PUE or price work that was deferred requires a recorded scope decision.

| Addition | Exact source and concrete deliverable | Effort / value | Honest caveat |
|---|---|---|---|
| **Utah peak-load relief — first choice** | Existing EIA-930 PACE demand/wind/solar and registered ledgers; [EIA methodology](https://www.eia.gov/electricity/930-content/about.html). Report Utah import change during training-threshold rush hours, coincident peak reduction, and worst charging rebound. Use [Rocky Mountain Power demand response](https://www.rockymountainpower.net/savings-energy-choices/business/demand-response.html) as business context. | **2–3 h / high** | Simulated contribution to load reduction, not transmission congestion relief, accredited firm capacity or new interconnection capacity. Show destination load increases too. Do not multiply MW by an invented capacity price. |
| **Wholesale cost on fixed schedules** | Cached CAISO OASIS `PRC_RTPD_LMP`, version 3, market `RTPD`; `ELAP_PACE-APND`, `ELAP_BPAT-APND`, `ELAP_NEVP-APND`, with `TH_NP15_GEN-APND` explicitly a California hub proxy. Sources and exact queries are in `data/manifests/prices_caiso.json`; [CAISO price documentation](https://www.caiso.com/todays-outlook/prices). Produce a carbon-versus-wholesale-cost comparison, without rerouting. | **2–4 h / high** | Verify complete constituent intervals and comparable coverage first. Missing prices remain null. Include transfer and battery charging energy. This is neither a cloud bill nor retail savings; PACE has no pre-seal day-ahead history. |
| **Temperature-dependent PUE** | Cached Open-Meteo `temperature_2m_previous_day2` at the documented site proxies; [Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api). Reprice fixed schedules under a small set of explicitly assumed `PUE(T)` curves. Use [LBNL’s 2024 report](https://eta-publications.lbl.gov/publications/2024-lbnl-data-center-energy-usage-report) for cooling context. | **2–3 h / medium** | Forecast temperature is labeled `forecast`; the PUE response is `assumed`, resulting energy/carbon `modeled` or `simulated` as appropriate. There is no measured facility calibration. Temperature alone misses humidity, cooling design and utilization. Audit the loader’s one-hour timestamp convention. |
| **Water: direct cooling plus electricity** | [NREL/TP-6A20-50900](https://docs.nlr.gov/docs/fy11osti/50900.pdf) supplies technology/cooling-system water factors; LBNL’s report supplies data-center context. Show a range of direct cooling liters per IT-kWh, separately from generation-associated water. Add a small historical context panel from [USGS Saltair station 10010000](https://waterdata.usgs.gov/monitoring-location/USGS-10010000/), restricted to pre-seal dates. | **3–5 h / medium** | Distinguish consumption from withdrawal. Fuel-mix weighting is a production-side scenario, not consumption-flow tracing. PACE is not the Great Salt Lake watershed; hypothetical facilities have no verified water supplier. Do not claim liters “returned to the lake.” Hydro evaporation allocation can dominate and is uncertain. |
| **Curtailment coincidence** | [CAISO Production and Curtailments archive](https://www.caiso.com/library/production-curtailments-data), preferably a bounded pre-June-2025 period. Overlay California execution energy with curtailment hours; distinguish local congestion from system oversupply. | **2–4 h / medium** | The reporting format changed in June 2025. Coincidence is not demonstrated absorption of otherwise-curtailed power: the site may be on the wrong side of a constraint, and the historical dispatch did not include this load. Report overlap, not avoided curtailment. |
| **Health/air-quality context** | [EPA benefits-per-kWh regional screening estimates](https://www.epa.gov/statelocalenergy/estimating-health-benefits-kilowatt-hour-energy-efficiency-and-renewable-energy), including the 2024 technical report. An appendix could compare regional reference ranges for a clearly defined hypothetical energy-efficiency intervention. | **1–2 h / low** | Those factors are not hourly relocation damage estimates. Do not convert CO₂ savings into deaths avoided or Salt Lake City health benefits. A defensible routing assessment needs generator-level pollutant changes and source–receptor modeling; [AVERT/COBRA](https://www.epa.gov/cobra/cobra-questions-and-answers) describes that larger task. |
| **Better than another dataset: “What breaks the decision?”** | Existing scenario results plus transfer accounting. Show how much compatible spare GPU capacity, mobility and transfer overhead the placement decision tolerates. Derive an energy-overhead break-even threshold without inventing bandwidth measurements. | **1–2 h / high** | An analytical threshold is `modeled`; unrun combinations are not simulator results. Network topology, data residency, dataset size and hardware equivalence remain unresolved. |

**F17 — Important; high confidence. Location: proposed outside-data additions and D-058/F9 scope.** Adding several of these before freeze would create more unsupported claims than useful insight. **Failure:** rushed joins, geographic mismatches or post-result choice of favorable examples compromise the otherwise disciplined core. **Correction:** choose peak relief, optionally cost, and put the remaining sources in a clearly labeled future-work appendix. **Effort: 0.25 h prioritization; value: high.**

**5. Visualization and demo**

The screenshots show a coherent visual identity and substantial execution. The main presentation weakness is density.

- **F18 — Important; high confidence. Location: [Story.tsx](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/web/src/views/Story.tsx), `shots-build/story-6-1728.png`, T10b.** Six beats at 45 seconds already consume 4.5 minutes; seven consume 5.25 before transitions or questions. “Challenge it” is a dense table plus multiple paragraphs. **Failure:** the presenter spends the slot explaining policy letters and never lands the insight. **Correction:** use the five-beat sequence below; keep the full extension table for Q&A. **Effort: 1–2 h; value: high.**

- **F19 — Important; high confidence. Location: [ForecastPanel](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/web/src/views/Ribbon.tsx:126).** The shaded band is L ± the displayed week’s realized MAE. It is retrospective, not calibrated forecast uncertainty. **Failure:** the “tomorrow” screen suggests the interval was available at issue time. **Correction:** remove the band or explicitly label it “retrospective ±week MAE; not a prediction interval.” Do not introduce new calibration now. **Effort: 0.25–0.5 h; value: high.**

- **F20 — Important; high confidence. Location: [Cockpit.tsx](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/web/src/views/Cockpit.tsx:64), [plan.ts](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/web/src/lib/plan.ts).** The cockpit foregrounds a 76% illustrative saving from repeated typical-day profiles, without fleet contention or the registered cohort. The “illustrative” label exists, but does not explain the decisive difference. **Failure:** that becomes the number judges remember instead of the 22.6% fleet result. **Correction:** caption it “one hypothetical job; typical-day profile; capacity unconstrained,” and transition immediately to the aggregate. **Effort: 0.5 h; value: high.**

- **F21 — Minor; high confidence. Location: [Cockpit.tsx:84](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/web/src/views/Cockpit.tsx:84).** The hero clamps negative savings to zero. I found no negative move among the current allowed typical-day combinations, so this is a latent presentation defect. **Failure:** future/test profiles with an adverse move show “0% less” instead of an increase. **Correction:** preserve the sign and switch between “less” and “more.” **Effort: 0.25 h; value: medium.**

- **F22 — Minor; high confidence. Location: [Cockpit.tsx:87](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/web/src/views/Cockpit.tsx:87), `plan.ts`.** The displayed kWh is execution energy while the adjacent CO₂ includes transfer. **Failure:** an attentive judge cannot reconcile the stated total energy with the claimed extra 5%. **Correction:** label execution kWh separately and show transfer-inclusive total energy. **Effort: 0.25 h; value: medium.**

- **F23 — Minor; high confidence. Location: Control-room and Story 4 map captions; [store.ts](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/web/src/lib/store.ts:40).** July typical-day colors coexist with November replay-week arcs, and W is the default despite S being the likely deployed choice. Captions disclose the time mismatch, but the visual implication remains stronger. **Failure:** judges infer the arcs respond to the currently displayed hourly colors. **Correction:** present an explicitly static weekly-flow map, or align the layers; default the result narrative to S. **Effort: 0.5–1 h; value: medium.**

- **F24 — Minor; high confidence. Location: `shots-build/control-1440.png`.** Wait-only marks overlap their row-label area. **Failure:** the central “less than 1%” comparison is harder to read at laptop distance. **Correction:** inset the plot or put direct values beside labels. **Effort: 0.25 h; value: medium.**

- **F25 — Minor; high confidence. Location: Story 1 and Ribbon copy.** “After sunset” is stronger than the plotted evidence establishes; the charts demonstrate declining solar and an evening net-load peak. **Failure:** a local judge notices that summer sunset can occur later than the stated rush-hour onset. **Correction:** say “as solar fades.” **Effort: 0.1 h; value: low.**

A tighter **4:30 demo**, requiring **1–2 h preparation, high value**:

| Time | Beat |
|---|---|
| 0:00–0:35 | Utah’s evening net-load problem; introduce the hypothetical cluster and emissions objective. |
| 0:35–1:15 | One job: stay, wait or move. Explain that moving means placing an unstarted job at another site. |
| 1:15–2:15 | Aggregate: about 22.6% versus less than 1%; the fixed ranking performs best on validation. |
| 2:15–3:00 | The decisive constraint: ≤8-GPU mobility reduces savings to about 3–4%. |
| 3:00–4:10 | Storage illustration: residual Utah import, MW/MWh, losses and any carbon/peak tradeoff. |
| 4:10–4:30 | State the actual held-out result, its scope, and the next operator experiment. |

Drop the full forecast-family comparison, policy alphabet, nine-row robustness table and most method prose from the spoken route. Keep them one click away.

**6. Other things that could embarrass—or distinguish—the entry**

- **F26 — Important; high confidence. Location: `docs/data-profile/grid.md` marginal-emissions discussion versus the approved spec.** The older profile says a regression “identifies” marginal emissions and calls its marginal number the honest avoided-emissions answer. The approved spec correctly rejects that inference. **Failure:** a pitch-writing agent copies the older wording into the storage story. **Correction:** add a dated correction notice to the profile and make the approved spec’s interpretation authoritative in pitch materials. **Effort: 0.25 h; value: high.**

- **F27 — Minor; high confidence. Location: `docs/HANDOFF.md`, spec status line, [T12 decision-entry instruction](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/docs/superpowers/plans/amendments/stage3-T12.md:66).** The handoff remains stale, the approved spec still introduces itself as a candidate, and T12 requests D-061 although storage already occupies that ID. **Failure:** agents act on obsolete status or overwrite a decision identifier. **Correction:** refresh status pointers, assign the next unused decision ID, and preserve historical text with correction notes. **Effort: 0.5 h; value: medium.**

- **F28 — Important; medium confidence. Location: Stage 3’s references to the Stage 2 final review; task reports directed to `/tmp`; `docs/reviews/`.** The pinned review directory does not contain the cited Stage 2 final review and all its dispositions. **Failure:** the morning auditor spends scarce time reconstructing unresolved findings from ephemeral reports. **Correction:** commit the review/disposition records and a compact audit packet with the final candidate, run IDs, hashes and known deferrals. **Effort: 0.5–1 h; value: high.**

- **F29 — Minor; high confidence. Location: [T10b export labels](/home/nvidia/workspace/personal/projects/htw-review/plan-astra/docs/superpowers/plans/amendments/stage3-T10b.md:36).** T10b labels CO₂ outcomes `modeled` even though they arise from simulated storage dispatch; the evidence contract labels schedule outcomes `simulated`. **Failure:** the new artifact quietly weakens the otherwise consistent evidence vocabulary. **Correction:** use `simulated` for dispatch outcomes, with modeled CI and assumed efficiency linked as inputs; retain the separate `illustrative` scope. **Effort: 0.25 h; value: medium.**

Nothing found in the artifact-copy/hash checks that contradicts the reported validation progress. The principal scientific limitations are largely disclosed already. The winning move is to make those limitations productive: **the system tells an operator when simple placement is enough, when mobility constrains the opportunity, and what remains for local storage.**

The top five actions for the next 22 hours are:

| Priority | Action | Owner / agent | Effort | Target |
|---|---|---|---:|---|
| **1** | Resolve S’s availability cutoff; finish T11; rebuild the final lab tree from raw inputs; record and tag the freeze. | Claude lead + independent rebuild agent | **4–6 h** | Tonight, before unsealing |
| **2** | Correct storage optimality/SOC/accounting; prioritize residual Utah peak import and losses over extra curves. | Storage agent + reviewer | **3–5 h** | Before the qualifying rebuild |
| **3** | Amend D-061’s presentation sequencing; prepare the 4:30 narrative, one-pager skeleton and judge answers tonight. | Owner + planning partner | **1.5–2 h** | Tonight |
| **4** | Run the frozen test once, assemble the audit packet, complete the Astra audit and disposition every finding. | Claude lead + Astra reviewer | **2–4 h hands-on**, plus compute | Overnight–Wed 11:00 |
| **5** | Package and rehearse on the actual offline Mac; fix the forecast band and key display issues; repeat with final artifacts. | Owner + dashboard agent | **2–3 h** | First pass tonight; final pass before 14:00 |

Verdict: not_ready
## Dispositions (lead, 2026-10-27 ~16:00 MT)

| ID | Disposition |
|---|---|
| F01, F02 | **Accepted.** The critical path is: T11 fix round → T10b → the T12 rebuild on the final lab tree → freeze → test. Storage merges before the rebuild, and any later lab change re-triggers verification. |
| F03 | **Owner's decision.** Asked: amend D-061 so the narrative skeleton and Q&A can be drafted tonight with placeholders for the test numbers. |
| F04 | **Owner action.** Mac rehearsal tonight. A static fallback and launcher are added to the pitch prep. |
| F05 | **Fixed in the T11 fix round.** The S ranking applies the 96 h envelope at `fit_at`. Lead check: the ordering is unchanged in validation (BPAT 87.3 < CISO 202.4 < NEVP 324.1 < PACE 582.3) and in the test window (95.5 < 194.2 < 312.6 < 572.8), so validation schedules are unchanged (D-062). |
| F06, F07, F08, F10, F16, F19–F25 | **Accepted, as dashboard and pitch copy fixes after the test run.** Web changes after the freeze would block the entry point's clean-HEAD check until the test run is done. Planned changes: lead with "about 22.5% vs < 1%" and drop "30×" from headlines; "no demonstrated aggregate benefit from dynamic search in this replay"; S 22.6% → 3.2% beside the headline; the headline shows S's own estimate and interval; the extension span is called "scenario estimates"; the forecast band is labelled retrospective; the cockpit caption and sign fixed; kWh labels; S as the default; "as solar fades"; "Compute follows cleaner power"; "PACE, the balancing area serving much of Utah". |
| F09 | **Accepted** (already in the claim frame). Q&A wording is added to the pitch prep. |
| F11 | **Accepted.** Peak relief is added to T10b as a `peak_relief` block (the Utah rush-hour load under U vs S/W, plus destination increases). The `not_run` inventory adds the stress/price evaluation, deferred under F9. |
| F12–F15, F29 | **Sent to T10b as binding corrections:** "hindsight heuristic"; chronological SOC; a connection-limited charge rate; the common accounting window; an explicit break-even with negative results kept; Utah import before and after; `simulated` labels. |
| F17 | **Accepted.** Peak relief is folded into storage. Cost, PUE(T), water, curtailment and health go to a future-work appendix unless the owner chooses otherwise. |
| F18 | **Accepted.** The story stays at 6 beats; storage and peak relief replace "Challenge it"; the extension table moves to the drawer. The 4:30 demo outline is adopted for the pitch. |
| F26 | **Fixed in this PR:** a correction notice in `docs/data-profile/grid.md`. |
| F27 | **Fixed in this PR:** the spec status line, and T12's decision ID (now D-063 onward). HANDOFF is refreshed. |
| F28 | **Fixed in this PR:** the Stage 2 final review record is committed (`docs/reviews/2026-10-27-stage2-final-claude.md`). An audit packet is assembled after the test run (T13). |
