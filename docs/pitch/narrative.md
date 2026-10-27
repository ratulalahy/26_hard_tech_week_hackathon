# GridPilot: the 4:30 demo script (DRAFT)

**Status:** draft, Tue 2026-10-27 evening (D-063). Fill in and finalise on Wednesday after the test run and the Astra audit.

- `{{TEST: ...}}`: a sealed test-year number. It is filled from `results/test/` only after the audit.
- `{{STORAGE: ...}}`: the storage and peak-relief piece (T10b, `results/storage.json`), which is still being built.
- Every number written out here is from the **validation year** (Nov 2024 – Oct 2025), and the script says "validation" wherever one is spoken.
- **Timing:** Astra's 4:30 outline (strategy review §5, adopted in the F18 disposition).
- **Word budget:** about 150 spoken words a minute, so about 650 words in all. Each beat lists its budget.
- **Setup:** Chrome, full screen, the offline build at `http://127.0.0.1:4173/`. Deep links work: `#story-1` … `#story-6`. Set the window switch to **Test year** before starting, and check that the switch label shows it (T11).

---

## Beat 1 · 0:00–0:35 · Utah's evening rush (about 85 words)

- **Show:** Story, step 1 (`#story-1`): the Utah July-weekday load chart with the carbon ribbon, and the year heat map below.
- **Number on screen:** **net-load peak 8 PM, 6,654 MW** (PACE, July 2025 weekdays, validation year, observed EIA-930).

> This is Utah's grid: PACE, the balancing area serving much of Utah. Here's a July weekday from our validation year. Demand peaks around five. Then, as solar fades, net load, the part the rest of the fleet has to carry, keeps climbing to about sixty-six hundred megawatts at 8 PM. That's the grid's rush hour.
>
> Now picture a hypothetical 2,300-GPU AI cluster in Utah. Our objective is emissions first: cut the CO₂ attributed to its work, with the same work done by the same deadlines.

*Notes:* say "as solar fades", never "after sunset" (F25). The cluster size (2,288 GPUs, about 1.6 MW when fully busy) is **assumed**.

---

## Beat 2 · 0:35–1:15 · One job: stay, wait or move (about 100 words)

- **Show:** Story, step 3 (`#story-3`): job 5930563#c3, with its options table and "Where each policy put it".
- **Number on screen:** **2,728 kg if it stays vs 336 kg in the Northwest** (one validation-year job; option CO₂ modeled, placements simulated).

> Here's one real job from a public GPU-cluster trace, replayed onto Utah: 72 GPUs, 104 hours of pre-training. Three choices.
>
> Stay: about twenty-seven hundred kilograms of attributed CO₂.
>
> Wait: it may start up to six hours late. Against a 104-hour run, six hours buys almost nothing, so the wait-only policies leave it in Utah.
>
> Move: half an hour of transfer, then it runs on the Northwest's hydro-heavy grid for about 340 kilograms.
>
> Moving means placing a job that hasn't started yet at another site with spare GPUs. Nothing migrates mid-run. That's one job from the validation year. Now the whole year.

*Notes:* the job was picked by a rule fixed before its outcome was seen: the GPU-hour-weighted median of the eligible flexible jobs (D-054). Don't use the Decision cockpit's 76% here, because it is a typical-day illustration with no fleet contention (F20).

---

## Beat 3 · 1:15–2:15 · The aggregate: moving vs waiting (about 150 words)

- **Show:** Story, step 5 (`#story-5`) in the **test-year** window: the interval chart and the policy table.
- **Number on screen:** **S: {{TEST: S saving vs U, % [95% interval]}}**, which is S's own estimate and interval, not a span across policies (F10).
- **Caption beside it** (must be visible at the same time as the headline): *Validation: 22.6% → about 3% if only jobs of ≤8 GPUs may move.*

> We replayed the whole workload, {{TEST: cohort size, jobs}} jobs, against hourly EIA carbon data. This is a simulated replay.
>
> On the validation year, the answer was about 22.5 percent versus under 1 percent: moving work cut attributed emissions by about 22.5 percent, and waiting in Utah alone by under 1.
>
> Then we froze everything and opened the sealed test year once. The fixed clean-region ranking, policy S, cut {{TEST: S saving vs U, % [95% interval]}}. Waiting alone cut {{TEST: best wait-only saving vs U, % [95% interval]}}. Compute follows cleaner power: {{TEST: share of S's remote execution energy in BPAT, %}} of the work that left Utah ran in the Northwest.
>
> To be precise: these are attributed emissions, on EIA's consumption basis, not avoided emissions. And deadlines are met by construction, through baseline bookings, with exact declared runtimes. Runtime uncertainty is untested.
>
> Our day-ahead forecasts follow Utah's daily swing, but we found no demonstrated aggregate benefit from dynamic search in this replay. The simple ranking is the one to deploy.

*Notes:*
- Don't say "30×".
- If the test result breaks the validation pattern, say so plainly and use the test number. Never swap in the validation number.
- The last sentence depends on `{{TEST: K, W, L minus S, t [95% interval]}}`. If any dynamic policy beats S with an interval that excludes zero, rewrite that sentence.

---

## Beat 4 · 2:15–3:00 · The condition that decides it: mobility (about 110 words)

- **Show:** Story, step 5, scrolled to "A few large jobs carry the result". Then open **Method & evidence** at the "Does it hold?" scenario table. That table now lives in the drawer; it was formerly the "Challenge it" step (F18).
- **Number on screen:** **22.6% → 3.2%** (S, validation; only jobs of ≤8 GPUs may move; scenario estimate [2.1–4.5%]).

> Here's the condition. In this workload, the largest 1 percent of jobs use 94 percent of the energy.
>
> If only jobs of 8 GPUs or fewer may move, S's validation saving falls from 22.6 percent to about 3 percent. Only about 4 percent of the energy runs outside Utah. Our 72-GPU job would stay home.
>
> Other changes moved the number much less. With a two-hour transfer it's about 20 percent. With twice the spare capacity at the destinations it's 35. These are scenario estimates on the validation year.
>
> So whether large training jobs can move is the lever. In our study that is an assumption, not something we measured.

*Notes:*
- Use "ran outside Utah" (remote execution), not "moved", because the ledger's "moved" also counts time shifts (F08).
- The scenario runs were validation only (D-058); none was rerun on the test year. Say so if asked.

---

## Beat 5 · 3:00–4:10 · Store for what can't move (about 170 words)

- **Show:** Story, step 6, the storage and peak-relief beat ("Move what you can, store for what you can't"), which replaces "Challenge it" once T10b merges. Point to the Utah day strip with the charge and discharge windows, then the before/after import bars.
- **Number on screen:** **{{STORAGE: Utah rush-hour grid import of the cluster, MW, before → after}}** (illustrative, simulated dispatch, validation year).

> What about the work that can't move? That's where storage comes in.
>
> We took the Utah cluster's residual load, {{STORAGE: load case, e.g. the ≤8-GPU-mobility residual at PACE}}, and added an illustrative store at the site: {{STORAGE: E MWh / P MW}}, with charging limited to {{STORAGE: connection limit, MW}}, an assumed 85 percent round-trip efficiency, and state of charge tracked hour by hour.
>
> Two questions.
>
> **Carbon.** Storage only helps when the charging-hour intensity, divided by efficiency, is below the intensity it displaces. In Utah, a fixed daily schedule gives {{STORAGE: % CO₂ change, fixed schedule, η 0.85 [η 0.75–0.90 range]}}, and a hindsight heuristic gives {{STORAGE: % CO₂ change, hindsight heuristic}}. Losses cost {{STORAGE: MWh lost per year}}.
>
> **Peak.** During Utah's evening rush, the cluster's grid import drops from {{STORAGE: MW before}} to {{STORAGE: MW after}}. The price is a charging rebound of up to {{STORAGE: worst rebound, MW}}. The work we moved adds {{STORAGE: destination load increase, MW}} elsewhere, and we count that too.
>
> This is an hourly energy model. Fast buffering, seconds rather than hours, is outside it. That's the next interface.

*Notes:*
- Torus is the audience; don't name its products as modeled.
- If the carbon result is zero or negative, say it: "in Utah, losses eat the carbon gain; the value is the peak" (F14).
- Never call the hindsight result a "bound" or "optimal" (F12).
- Don't put a price on MW.

---

## Beat 6 · 4:10–4:30 · Close (about 55 words)

- **Show:** the Control room, with the Utah rush window visible in the bottom strip.
- **Number on screen:** **{{TEST: S saving vs U, %}}** (the headline card, test year).

> In a simulated replay of the sealed test year, the fixed ranking cut attributed emissions by {{TEST: S saving vs U, %}} on the same declared work. Every assumption is one click away.
>
> For an operator, the order is: first identify what work can move. Then quantify the residual Utah load storage could serve.
>
> Thank you.

---

## Spoken-route rules (checklist for the final pass)

- Keep: "simulated replay"; "attributed (EIA consumption-basis) emissions, not avoided emissions"; "deadlines met by construction (baseline bookings)"; "exact declared runtimes; runtime uncertainty untested"; "no demonstrated aggregate benefit from dynamic search in this replay"; "Compute follows cleaner power"; "PACE, the balancing area serving much of Utah".
- Lead with "about 22.5% vs under 1%" (validation), then the test number with S's own interval.
- The mobility caveat is on screen beside the headline.
- Never "30×" as a headline. Never "proves" or "confirms". "Avoided" appears only in "not avoided emissions".
- One click away for Q&A: the full policy table (Story 5), the Day ribbon forecast panel (its band reads "retrospective ±week MAE; not a prediction interval", F19), the Decision cockpit (one hypothetical job, typical-day profile, capacity unconstrained), and the method drawer.

## Placeholders to fill on Wednesday

| Placeholder | Source |
|---|---|
| `{{TEST: S saving vs U, % [95% interval]}}` | `results/test/metrics.json` → `contrasts` S vs U, block 4 |
| `{{TEST: best wait-only saving vs U, % [95% interval]}}` | the same, W_time and L_time vs U |
| `{{TEST: K, W, L minus S, t [95% interval]}}` | the same, K/W/L vs S |
| `{{TEST: cohort size, jobs}}` | `cohort.n_jobs` |
| `{{TEST: share of S's remote execution energy in BPAT, %}}` | `policies.S.metrics.execution_kwh_by_site` |
| `{{STORAGE: ...}}` | `results/storage.json` (T10b), with the `peak_relief` block |
