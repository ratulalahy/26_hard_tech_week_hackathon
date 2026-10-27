# GridPilot: judge Q&A (DRAFT)

**Status:** draft, Tue 2026-10-27 (D-063). Answers to the first eight questions start from Astra's judge-attack table (strategy review §2). Numbers marked *validation* come from the validation year (Nov 2024 – Oct 2025). `{{TEST: ...}}`, `{{STORAGE: ...}}` and `{{WATER: ...}}` are filled on Wednesday.

Keep each answer to one or two sentences, then offer the screen: "I can show you."

---

### The result

**1. "Why not just send everything to Bonneville?"**
We tested that idea: a fixed clean-region ranking with limited capacity (policy S) was our best policy on validation, and forecasting has not earned extra credit here. The limit is spare GPUs: each destination has an assumed 512 spare slots. With none, only waiting is left (0.7%), and doubling them takes the saving to 35% (validation scenario estimates).

**2. "Did you cut 22% of real-world emissions?"**
No. We cut the modeled emissions attributed to an identical workload in a simulated replay. These are attributed (EIA consumption-basis) emissions, not avoided emissions; we did not estimate how the grid's dispatch would respond.

**3. "Can those large training jobs actually move?"**
Mobility is assumed, and it is the lever. If only jobs of 8 GPUs or fewer may move, S's saving falls from 22.6% to about 3% (validation), because the largest 1% of jobs use 94% of the energy.

**4. "How did you guarantee deadlines?"**
Each job keeps its baseline reservation, its slot under stay-in-Utah, as a fallback, and runs exactly as long as it declared. Deadlines are met by construction (baseline bookings); production runtime uncertainty is untested.

**5. "Moving beats waiting by how much? Is it 30×?"**
About 22.5% versus under 1% on validation, both relative to running everything in Utah. On the test year it was {{TEST: S saving vs U, % [95% interval]}} versus {{TEST: best wait-only saving vs U, %}}. A ratio of two estimated savings isn't a quantity we'd headline.

**6. "Do the robustness checks back it up?"**
They keep the placement pattern under the specified changes: workload phase, a 2-hour transfer, a 24-hour delay, and observed-hours-only scoring. Those validation estimates span 20.2–23.2% on the consumption basis; on production-basis carbon it's 25.2–25.5%. Those are scenario estimates, not a confidence interval, and they don't test mobility, idle power or the reservation assumption itself.

**7. "Why isn't hindsight always best?"**
Our hindsight policy still schedules one job at a time, greedily; it's a diagnostic, not the optimum for the whole workload. Holding scarce Bonneville slots for a cleaner hour can push later jobs to dirtier sites.

**8. "Is this cheaper?"**
Cost was not the objective, and we haven't evaluated it on comparable fleet-wide prices. We downloaded CAISO prices, but that comparison is future work.

### Method

**9. "Why does a fixed ranking match machine learning?"**
The gap between regions is far larger than the hour-to-hour swing a forecast can catch, and jobs may wait at most 6 hours while the energy sits in multi-day runs. Only 29% of flexible energy had its whole decision window inside forecast coverage (validation). So we report no demonstrated aggregate benefit from dynamic search in this replay, which is narrower than "ML doesn't help".

**10. "Did you peek at the test year?"**
No. The test year was sealed during design, and it was opened once, after a recorded configuration freeze, through a logged entry point. Forecasts and the ranking only use data that EIA would already have published at the decision time; the assumed lag is 96 hours for carbon.

**11. "Isn't the booking calendar cheating?"**
It's an advance-reservation scenario: every policy, including stay-in-Utah, gets the same calendar, and each job's baseline slot is its fallback. Its effect on savings isn't signed, and the version without advance reservations was not run.

**12. "Average or marginal emissions?"**
Average: EIA's hourly consumption-basis estimate, which follows imports. Repricing the same schedules on production-basis carbon gives 25.5% for S (validation); a marginal number would need a dispatch model we don't have.

### Data and place

**13. "Where does the data come from?"**
- **Grid:** EIA-930 hourly demand, generation by fuel and interchange, plus EIA's hourly consumption-basis CO₂ estimates for four balancing areas.
- **Workload:** the public Acme trace from Shanghai AI Lab's Seren cluster (NSDI '24, CC-BY-4.0).
- **Map:** balancing-area boundaries from Electricity Maps and a Natural Earth basemap.

All of it is free and open, and every number on screen is labeled observed, measured, modeled, forecast, assumed or simulated.

**14. "Why Utah?"**
It's home ground for Torus, whose demand-response MOU with Rocky Mountain Power is tied to Utah's Operation Gigawatt, and the contrast is sharp. In our training data, PACE's hourly carbon intensity averaged about 580 g/kWh against about 90 for Bonneville; these are ranking means only, not emission factors. Its evening net-load peak (8 PM, 6,654 MW on a July 2025 weekday, validation year) is the rush hour we route around.

**15. "What machine did you use?"**
We ran the experiments on a DGX.

### Torus and storage

**16. "What does this have to do with Torus?"**
Moving work and storing energy act on different timescales and different loads. We first find what work can move. What's left in Utah is the load that storage could serve: {{STORAGE: residual Utah rush-hour load of the cluster after moving what can move, MW}} in our illustration. We don't model Torus devices or claim any grid capacity.

**17. "Does storage cut carbon here?"**
Only if the charging-hour intensity divided by round-trip efficiency is below the intensity it displaces. Ours gives {{STORAGE: % CO₂ change, fixed schedule, η 0.85}}, and {{STORAGE: range over η 0.75–0.90}} across the efficiency sweep. We keep negative results: losses can make it worse.

**18. "What about the peak?"**
During Utah's evening rush, the cluster's grid import goes from {{STORAGE: MW before}} to {{STORAGE: MW after}}, with a charging rebound of up to {{STORAGE: MW}}. Moved work adds {{STORAGE: destination MW}} at the destinations. That is a simulated contribution to load reduction, not accredited capacity or transmission relief.

**19. "What about fast swings: AI training power spikes, frequency?"**
Outside our hourly model. That's exactly where a flywheel-battery hybrid fits, and it's the interface we'd build next with real telemetry.

**20. "What about water?"**
It's an illustrative add-on for the validation year: generation-associated water from NREL factors times EIA-930 fuel mix, shown with and without hydro evaporation, plus a direct-cooling range from LBNL's 2024 report. The result is {{WATER: litres per MWh, Utah vs destinations, with/without hydro}}. It measures consumption, not withdrawal; it is production-side weighting, not flow tracing; and PACE is not the Great Salt Lake watershed, so we make no "water returned to the lake" claim.

### Next

**21. "What would you do next?"**
- **With an operator:** tag which real jobs can move, by checkpointing, data size and residency. That's the number that decides the saving.
- **The two cut tests:** run without advance reservations, and with runtime overruns.
- **With Torus:** couple the router's residual Utah load to storage dispatch, and add fast-timescale buffering from measured cluster power.
