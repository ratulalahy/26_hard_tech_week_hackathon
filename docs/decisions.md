# Decision log

Every design decision so far, with who made it, when, the evidence behind it and the alternatives it rules out. The log is for two readers: judges asking "how do you know?", and the owner following what the agents did and why.

- **Sources.** Backfilled on 2026-10-27 from [the brief](brief.md) (owner decisions), [plan v2](plan/2026-10-27-plan-v2.md) (decisions table, data consequences, amendments), [plan v1](plan/2026-10-26-hackathon-plan.md) (amendments), [Sol's plan review](reviews/2026-10-26-plan-sol-r1-sol.md) (the rule changes its dispositions caused), the [handoff](HANDOFF.md) and the three data profiles ([grid](data-profile/grid.md), [workloads and prices](data-profile/workloads-prices.md), [geo](data-profile/geo.md)).
- **Evidence notebooks.** The data-driven entries link to executed notebooks in [`notebooks/`](../notebooks/), which render on GitHub; HTML copies are in [`docs/evidence/`](evidence/). `make notebooks` rebuilds both from the cached data.
- **Times** are Mountain Time (MDT, UTC−6) for 2026-10-26/27. Where a document's stated time disagrees with the git commit that recorded it, the entry uses the commit time and gives the stated one (D-009 to D-017, D-043): a decision cannot be recorded before it is made.
- **Who:** *owner*; *Claude* (lead agent); *Codex* (planning partner); *Sol review* (a Codex review whose finding Claude dispositioned into a rule). "Astra" is the owner's Codex planning session.
- **Rules of the log.** One decision per entry, numbered in order of time. A later decision that changes an earlier one supersedes it; the old entry stays, marked. Execution status lives in the handoff, not here.

## Index

| ID | When (MT) | Decision | Who | Status |
|---|---|---|---|---|
| [D-001](#d-001--build-a-day-ahead-grid-traffic-report-and-a-simulated-ai-job-router) | 10-26 22:45 | Traffic report + simulated AI-job router; headline "Compute Follows the Sun" | owner | active |
| [D-002](#d-002--utahs-pace-is-the-hero-region) | 10-26 22:45 | Utah's PACE is the hero region | owner | active |
| [D-003](#d-003--the-dgx-is-the-lab-the-demo-is-an-offline-build-on-the-owners-macbook) | 10-26 22:45 | DGX is the lab; offline demo on the owner's MacBook | owner | active |
| [D-004](#d-004--high-end-visualization-is-the-priority) | 10-26 22:45 | High-end visualization is the priority | owner | active |
| [D-005](#d-005--solo-owner-plus-agents-claude-builds-codex-plans-and-reviews) | 10-26 22:45 | Solo owner + agents; Claude builds, Codex plans and reviews | owner | active |
| [D-006](#d-006--profile-the-data-first-seal-the-last-12-months) | 10-26 22:45 | Profile the data first; seal the last 12 months | owner | active |
| [D-007](#d-007--natural-earth-basemap-instead-of-protomaps-pmtiles) | 10-26 23:00 | Natural Earth basemap, no PMTiles | Claude | active |
| [D-008](#d-008--six-evidence-labels-one-source-of-truth-per-topic) | 10-26 23:05 | Six evidence labels; one source of truth per topic | Codex | active |
| [D-009](#d-009--the-seal-opens-only-after-spec-approval-and-frozen-configs) | 10-26 23:08 | Seal opens only after spec approval and frozen configs | Sol review | active |
| [D-010](#d-010--only-a-certified-hindsight-optimum-is-a-bug-check) | 10-26 23:08 | Only a certified hindsight optimum is a bug check | Sol review | active |
| [D-011](#d-011--attributed-operational-emissions-never-avoided-co2) | 10-26 23:08 | "Attributed operational emissions", never "avoided CO₂" | Sol review | active |
| [D-012](#d-012--net-load-stress-proxy-never-congestion) | 10-26 23:08 | "Net-load stress proxy", never "congestion" | Sol review | active |
| [D-013](#d-013--fair-baselines-and-a-forecast-value-ablation) | 10-26 23:08 | Fair baselines and a forecast-value ablation | Sol review | active |
| [D-014](#d-014--account-for-all-work-map-traces-in-seeded-blocks) | 10-26 23:08 | Account for all work; map traces in seeded blocks | Sol review | active |
| [D-015](#d-015--one-experiment-deadline-wed-1100) | 10-26 23:08 | One experiment deadline, Wed 11:00 | Sol review | superseded by D-043 |
| [D-016](#d-016--a-45-minute-core-demo-one-charting-library-one-theme) | 10-26 23:08 | 4–5 min core demo; one charting library; one theme | Sol review | active |
| [D-017](#d-017--wholesale-scenario-labels-pace-price-regimes-kept-apart) | 10-26 23:08 | Wholesale-scenario labels; PACE price regimes kept apart | Sol review | active |
| [D-018](#d-018--emissions-first) | 10-26 23:14 | Emissions first | owner | active |
| [D-019](#d-019--pace-first-with-a-10-ba-overview) | 10-26 23:14 | PACE first, with a ~10-BA overview | owner | active |
| [D-020](#d-020--the-test-window-ends-at-the-snapshots-availability-cutoff) | 10-26 23:14 | Test window ends at the snapshot's availability cutoff | owner | active |
| [D-021](#d-021--two-independent-specs-then-reconcile-then-a-fresh-gate) | 10-26 23:19 | Two independent specs, reconciled, then a fresh gate | Claude | active |
| [D-022](#d-022--hour-beginning-utc-everywhere) | 10-27 00:15 | Hour-beginning UTC everywhere | Claude | active |
| [D-023](#d-023--clean-the-demand-target-never-score-imputed-hours) | 10-27 00:15 | Clean the demand target; never score imputed hours | Claude | active |
| [D-024](#d-024--the-bas-own-forecast-is-a-baseline-never-a-feature) | 10-27 00:15 | The BA's own forecast is a baseline, never a feature | Claude | active |
| [D-025](#d-025--honest-weather-only-weather-free-primary-model) | 10-27 00:15 | Honest weather only; weather-free primary model | Claude | active |
| [D-026](#d-026--stop-the-historical-forecast-download-extend-previous-runs) | 10-27 00:15 | Stop the Historical Forecast download; extend Previous Runs | Claude | active |
| [D-027](#d-027--eias-hourly-co2-is-the-primary-carbon-signal) | 10-27 00:15 | EIA's hourly CO₂ is the primary carbon signal | Claude | active |
| [D-028](#d-028--report-average-and-marginal-never-headline-the-average-gain) | 10-27 00:15 | Report average and marginal; never headline the average gain | Claude | active |
| [D-029](#d-029--move-vs-wait-is-in-the-core-with-capacity-limits) | 10-27 00:15 | Move vs wait in the core, with capacity limits | owner | active |
| [D-030](#d-030--second-insight-clean-hours--rush-hours) | 10-27 00:15 | Second insight: clean hours ≠ rush hours | Claude | active |
| [D-031](#d-031--rush-hour-defined-per-ba-by-percentile-forecast-demand-and-net-load) | 10-27 00:15 | Rush hour per BA by percentile; forecast demand and net load | Claude | active |
| [D-032](#d-032--the-core-region-set) | 10-27 00:15 | The core region set | Claude | active |
| [D-033](#d-033--acme-seren-is-the-primary-trace) | 10-27 00:15 | Acme Seren is the primary trace | Claude | active |
| [D-034](#d-034--job-model-every-gpu-hour-counts-waits-are-assumed-capacity-is-capped) | 10-27 00:15 | Job model: every GPU-hour counts; waits assumed; capacity capped | Claude | active |
| [D-035](#d-035--07-kwh-per-gpu-hour-swept-0420) | 10-27 00:15 | 0.7 kWh per GPU-hour, swept 0.4–2.0 | Claude | active |
| [D-036](#d-036--week-block-bootstrap-aligned-by-local-wall-clock) | 10-27 00:15 | Week-block bootstrap aligned by local wall clock | Claude | active |
| [D-037](#d-037--prices-are-a-should-on-pace-real-time-test-channel-pre-registered) | 10-27 00:15 | Prices are a Should; PACE real-time; test channel pre-registered | Claude | active |
| [D-038](#d-038--impeccable-in-this-repo-only-no-ui-ux-pro-max) | 10-27 00:15 | Impeccable in this repo only; no UI UX Pro Max | owner | active |
| [D-039](#d-039--four-light-design-directions-picked-at-g2) | 10-27 00:15 | Four light design directions, picked at G2 | owner | active |
| [D-040](#d-040--private-links-an-ssh-tunnel-and-pull-and-run-for-viewing-the-ui) | 10-27 00:15 | Private links, SSH tunnel and pull-and-run for the UI | owner | active |
| [D-041](#d-041--an-evidence-trail-notebooks-and-this-log) | 10-27 00:15 | An evidence trail: notebooks and this log | owner | active |
| [D-042](#d-042--ba-polygons-from-electricity-maps-fitted-to-natural-earth) | 10-27 00:17 | BA polygons from Electricity Maps, fitted to Natural Earth | Claude | active |
| [D-043](#d-043--freeze-wed-1300-checkable-version-tue-1800) | 10-27 00:17 | Freeze Wed 13:00; checkable version Tue 18:00 | owner | active |

## Monday 2026-10-26: direction and rules

### D-001 · Build a day-ahead grid traffic report and a simulated AI-job router
- **When:** 2026-10-26 22:45 MT. **Who:** owner.
- **Decision:** combine the bounty's two options: Option 1's day-ahead "traffic report" for the US grid and Option 2's AI-job router, evaluated in simulation on real data. The headline is Option 2, *Compute Follows the Sun*; the traffic report is its engine. There is no live hardware loop.
- **Evidence:** [brief, owner decisions](brief.md#owner-decisions-2026-10-26); [plan v2, decisions to date](plan/2026-10-27-plan-v2.md#decisions-to-date). The bounty asks for both "a traffic report for tomorrow's grid" and "a job router that shows carbon saved".
- **Rejected:** Option 1 alone (no compute story); Option 2 alone (no forecasting engine); a live hardware or control loop (not needed for judging, and not reproducible in 48 h).

### D-002 · Utah's PACE is the hero region
- **When:** 2026-10-26 22:45 MT. **Who:** owner.
- **Decision:** PacifiCorp East (EIA code PACE) is the region every result is shown for first.
- **Evidence:** the sponsor's Utah link ([brief, About Torus](brief.md#about-torus-public-sources-these-are-company-claims): a 70 MW demand-response MOU with Rocky Mountain Power). The data later backed the choice: PACE reports demand in 99.99 % of hours, is the dirtiest grid in the set (554 g/kWh, 45 % coal), has a narrow rush hour (about 34 h/yr within 5 % of peak) and a beatable BA forecast (4.0 % MAPE) ([nb01 §1, §3–§5](../notebooks/01_grid_profile.ipynb); [grid §10](data-profile/grid.md#10-recommended-bas-10-core-2-optional)).
- **Rejected:** CISO or ERCO as the hero (larger, better-known markets, but no sponsor link).

### D-003 · The DGX is the lab; the demo is an offline build on the owner's MacBook
- **When:** 2026-10-26 22:45 MT; platform clarified 23:14 (MacBook Pro, Chrome). **Who:** owner.
- **Decision:** the DGX Spark runs development and experiments only and is not part of the pitch. The demo runs from the owner's laptop as an offline static build.
- **Evidence:** [brief, owner decisions and clarifications](brief.md#owner-clarifications-2026-10-26-2314-mt).
- **Rejected:** a live demo from the DGX; a hosted or tunnelled demo during judging.

### D-004 · High-end visualization is the priority
- **When:** 2026-10-26 22:45 MT. **Who:** owner.
- **Decision:** a map, and the simulation made visible, get priority over breadth of models.
- **Evidence:** [brief, owner decisions](brief.md#owner-decisions-2026-10-26); judging is on creativity, clarity of insight and execution.
- **Rejected:** a notebook- or slide-only entry.

### D-005 · Solo owner plus agents: Claude builds, Codex plans and reviews
- **When:** 2026-10-26 22:45 MT. **Who:** owner.
- **Decision:** Claude Code is the lead (data pipeline, experiments, dashboard, merges to `main`); Codex writes its own spec, reviews evidence and drafts the narrative; Codex reviews run in fresh sessions and never edit.
- **Evidence:** [brief](brief.md#owner-decisions-2026-10-26); [AGENTS.md, Roles](../AGENTS.md#roles).
- **Rejected:** a single agent doing everything (no independent check).

### D-006 · Profile the data first; seal the last 12 months
- **When:** 2026-10-26 22:45 MT (boundaries coded in `lab/src/gridpilot/splits.py`, commit `763bff5` at 22:52). **Who:** owner.
- **Decision:** download and profile the data before designing the experiment. The test window [2025-11-01Z, 2026-11-01Z) is sealed during design: nothing reads its values except completeness checks.
- **Evidence:** [brief](brief.md#owner-decisions-2026-10-26); the profiles and every notebook apply `gridpilot.splits.drop_sealed` first and show the window only as counts ([nb01 §1.2](../notebooks/01_grid_profile.ipynb), [nb02 §5](../notebooks/02_weather_honesty.ipynb), [nb04 §2, §6](../notebooks/04_prices.ipynb)).
- **Rejected:** designing first and fetching data later; a random or cross-validated holdout (leaks seasonality and lets design choices see test hours).

### D-007 · Natural Earth basemap instead of Protomaps PMTiles
- **When:** 2026-10-26 23:00 MT. **Who:** Claude.
- **Decision:** use public-domain Natural Earth layers for the offline basemap; later the map needs no tile server at all (local GeoJSON plus one relief PNG).
- **Evidence:** [plan v1, amendment 23:00](plan/2026-10-26-hackathon-plan.md#amendments-after-approval): the auto-mode classifier blocked downloading the `pmtiles` binary; [geo, basemap layers](data-profile/geo.md#basemap-layers-natural-earth-public-domain): 5.3 MB for the whole basemap.
- **Rejected:** Protomaps PMTiles (needs a binary and a local range-request server, and OpenStreetMap attribution); online tiles (break the offline demo).

### D-008 · Six evidence labels; one source of truth per topic
- **When:** 2026-10-26 23:00–23:05 MT (commit `a85e957`). **Who:** Codex (setup proposal), merged by Claude.
- **Decision:** every field that reaches `results/`, the UI or a slide carries one of six labels: observed, measured, forecast, modeled, assumed, simulated. Rules live in `AGENTS.md`, decisions in the brief, the plan in `docs/plan/`, status in `docs/HANDOFF.md`; Codex works in its own checkout.
- **Evidence:** [plan v1, amendment 23:05](plan/2026-10-26-hackathon-plan.md#amendments-after-approval); [AGENTS.md, Data rules](../AGENTS.md#data-rules).
- **Rejected:** plan v1's four labels (measured, derived, assumed, simulated), which could not tell an observation from a forecast; separate `CONTEXT.md`/`PLAN.md` copies.

### D-009 · The seal opens only after spec approval and frozen configs
- **When:** 2026-10-26 23:08 MT (commit `1bdb079`; the disposition table is headed 23:30). **Who:** Sol review (finding E01), dispositioned by Claude.
- **Decision:** the test window opens only after the spec is approved **and** the model and policy configurations are frozen at a recorded commit. Each read logs its input, code and config hashes and its purpose. Numbers shown at G2 and G3 are validation results.
- **Evidence:** [review, E01 and dispositions](reviews/2026-10-26-plan-sol-r1-sol.md#dispositions-claude-2026-10-26-2330-mt); [AGENTS.md, Data rules](../AGENTS.md#data-rules).
- **Rejected:** plan v1's rule, which opened the seal at spec approval while models and thresholds could still change (test-driven tuning).

### D-010 · Only a certified hindsight optimum is a bug check
- **When:** 2026-10-26 23:08 MT. **Who:** Sol review (E07).
- **Decision:** the one ordering treated as a bug check is that a solver-certified hindsight optimum, on the same objective and feasible set, scores at least as well as every feasible policy. Every other ordering (our optimizer vs a baseline, a forecast vs persistence) is a result, and negative results are reported.
- **Evidence:** [review, E07](reviews/2026-10-26-plan-sol-r1-sol.md#dispositions-claude-2026-10-26-2330-mt); [plan v2, verification](plan/2026-10-27-plan-v2.md#verification).
- **Rejected:** plan v1's "hindsight ≥ optimizer ≥ baselines, otherwise it's a bug" and "forecasts beat persistence", which would have treated honest losses as bugs to fix against the test window.

### D-011 · "Attributed operational emissions", never "avoided CO2"
- **When:** 2026-10-26 23:08 MT. **Who:** Sol review (E13, E14).
- **Decision:** results are worded as attributed operational emissions under a named accounting basis (production or consumption); the marginal-emissions regression is an exploratory association proxy fitted on development data, with its instability reported.
- **Evidence:** [review, E13/E14](reviews/2026-10-26-plan-sol-r1-sol.md#dispositions-claude-2026-10-26-2330-mt). The data made this concrete: on PACE's average intensity a 24 h wait cuts 33 %, but the same schedule scored on the marginal proxy saves about 0 % ([nb05 §2](../notebooks/05_carbon_when_vs_where.ipynb)).
- **Rejected:** a "CO₂ saved" headline from average intensity; treating the regression as a causal marginal estimate.

### D-012 · "Net-load stress proxy", never "congestion"
- **When:** 2026-10-26 23:08 MT. **Who:** Sol review (I01).
- **Decision:** the grid-stress metric is named a net-load stress proxy, states what it measures, is checked against prices where they exist, and is never called congestion or reliability risk.
- **Evidence:** [review, I01](reviews/2026-10-26-plan-sol-r1-sol.md#dispositions-claude-2026-10-26-2330-mt); prices rank with net load (Spearman 0.53–0.77) far better than with demand (0.16–0.40) ([nb04 §5](../notebooks/04_prices.ipynb); [workloads-prices §2.7](data-profile/workloads-prices.md#27-price-vs-demand-peaks)).
- **Rejected:** calling high-load percentiles "congestion" without transmission data.

### D-013 · Fair baselines and a forecast-value ablation
- **When:** 2026-10-26 23:08 MT. **Who:** Sol review (E06, I02).
- **Decision:** every policy gets the same jobs, capacity, constraints, issue times and scoring hours. Baselines include a seasonal-profile scheduler and a static best-site baseline chosen on validation. The same scheduler runs on a seasonal signal, our forecast and hindsight, and time-only, place-only and combined routing are reported separately.
- **Evidence:** [review, E06/I02](reviews/2026-10-26-plan-sol-r1-sol.md#dispositions-claude-2026-10-26-2330-mt); the data shows why place-only must be separated: moving a PACE job beats waiting by a wide margin ([nb05 §3](../notebooks/05_carbon_when_vs_where.ipynb)).
- **Rejected:** crediting the forecast with gains that come from generic flexibility or from always choosing a cleaner region.

### D-014 · Account for all work; map traces in seeded blocks
- **When:** 2026-10-26 23:08 MT. **Who:** Sol review (E08, E11, E15).
- **Decision:** a common accounting cohort across policies, with warm-up and drain periods; completed work, deadline misses, backlog, wait percentiles and an energy reconciliation are reported next to any saving. The trace is mapped onto the year with a seeded, block-based scheme, described as a "synthetic workload scenario over real grid hours", with common time blocks across regions and policies in the bootstrap.
- **Evidence:** [review, E08/E11/E15](reviews/2026-10-26-plan-sol-r1-sol.md#dispositions-claude-2026-10-26-2330-mt); [nb03 §6](../notebooks/03_workloads.ipynb).
- **Rejected:** savings manufactured by unfinished work; independent arrival resampling, which destroys the campaigns that carry the GPU-hours.

### D-015 · One experiment deadline, Wed 11:00
- **When:** 2026-10-26 23:08 MT (plan v1 amendment headed 23:35). **Who:** Sol review (F03). **Status:** superseded by D-043.
- **Decision:** Wed 11:00 was made the only experiment deadline; 11:00–14:00 only packages frozen results.
- **Evidence:** [review, F03](reviews/2026-10-26-plan-sol-r1-sol.md#dispositions-claude-2026-10-26-2330-mt).
- **Rejected:** plan v1's "experiments mostly done by Wed 2 PM", which contradicted the 11 AM freeze.

### D-016 · A 4–5 minute core demo, one charting library, one theme
- **When:** 2026-10-26 23:08 MT. **Who:** Sol review (V01, V04), partly accepted by Claude.
- **Decision:** a 4–5 minute core demo with optional branches for longer slots; deck.gl + MapLibre for the map and ECharts as the only charting library; GSAP dropped; one theme, desktop only; design directions as single-screen static mockups.
- **Evidence:** [review, V01/V04](reviews/2026-10-26-plan-sol-r1-sol.md#dispositions-claude-2026-10-26-2330-mt): judging slots run 8–25 minutes including questions ([brief, Event](brief.md#event)).
- **Rejected:** an 8-minute story; D3/visx + ECharts + GSAP; light and dark themes; clickable prototypes per direction.

### D-017 · Wholesale-scenario labels; PACE price regimes kept apart
- **When:** 2026-10-26 23:08 MT. **Who:** Sol review (D03, D05).
- **Decision:** dollar figures are labelled "wholesale energy-cost scenarios", never bills. PACE's EDAM day-ahead regime (from 2026-05-01) is kept separate from its earlier WEIM real-time prices.
- **Evidence:** [review, D03/D05](reviews/2026-10-26-plan-sol-r1-sol.md#dispositions-claude-2026-10-26-2330-mt); PACE has no day-ahead price before 2026-05-01, and every EDAM hour is in the sealed window ([nb04 §6](../notebooks/04_prices.ipynb), counts only).
- **Rejected:** hub prices presented as a facility bill; one stitched PACE price series.

### D-018 · Emissions first
- **When:** 2026-10-26 23:14 MT. **Who:** owner (answered in the Codex planning session).
- **Decision:** the router minimizes attributed operational emissions; deadlines and identical completed work are hard constraints. Grid-stress exposure and wholesale cost are reported separately and never weighted into the objective.
- **Evidence:** [brief, clarifications](brief.md#owner-clarifications-2026-10-26-2314-mt); resolves Sol's E09 (an ambiguous weighted objective). The data shows why the outcomes must stay separate: in PACE the cleanest and the busiest hours differ ([nb05 §4](../notebooks/05_carbon_when_vs_where.ipynb)).
- **Rejected:** a weighted carbon/cost/stress objective; cost-first; stress-first.

### D-019 · PACE first, with a ~10-BA overview
- **When:** 2026-10-26 23:14 MT. **Who:** owner.
- **Decision:** build and verify the complete PACE path (forecast → router → replay → offline demo) before extending depth; keep about ten BAs in the overview without full experiment depth for each.
- **Evidence:** [brief, clarifications](brief.md#owner-clarifications-2026-10-26-2314-mt); resolves Sol's F02 (scope beyond the time available). The region set is in D-032 ([nb01 §5](../notebooks/01_grid_profile.ipynb)).
- **Rejected:** full experiment depth across all ten BAs.

### D-020 · The test window ends at the snapshot's availability cutoff
- **When:** 2026-10-26 23:14 MT. **Who:** owner (implementing Sol's F01).
- **Decision:** keep the sealed boundaries, but end the evaluation at the frozen snapshot's last complete day, and state the days covered. No "complete twelve-month" claim.
- **Evidence:** [brief, clarifications](brief.md#owner-clarifications-2026-10-26-2314-mt); in the snapshot every candidate BA has all 8,592 rows to 2026-10-25 (a few lack demand), and PACE's forecast already runs 24 hours past its last reported demand hour ([nb01 §1.2](../notebooks/01_grid_profile.ipynb), counts only).
- **Rejected:** a different complete-year holdout chosen after the fact; claiming a full year that has not happened.

### D-021 · Two independent specs, then reconcile, then a fresh gate
- **When:** 2026-10-26 23:19 MT (commit `e826c4d`; the handoff entry is headed 23:25). **Who:** Claude.
- **Decision:** Claude's spec draft stays outside the repo until Codex's independent version is pushed. If the owner is asleep, Claude runs Codex non-interactively and fresh (`codex exec -p plan`) to write it on `codex/spec-proposal`. Differences become decisions; a fresh Astra session gates the reconciled spec.
- **Evidence:** [handoff, 23:25](HANDOFF.md#2026-10-26-2325-mt-claude); [plan v2, first actions 5–6](plan/2026-10-27-plan-v2.md#first-actions-after-approval-in-order); prompt committed in `124ac99`.
- **Rejected:** a single-author spec; letting Codex read Claude's draft first (the two would stop being independent).

## Tuesday 2026-10-27: what the data changed

Entries D-022 to D-037 are the design consequences of the three data profiles, recorded in [plan v2, "What the data changed"](plan/2026-10-27-plan-v2.md#what-the-data-changed-design-consequences) (commit `b2b89ea`, 00:15). The spec settles their details; it may not reverse them without a new entry.

### D-022 · Hour-beginning UTC everywhere
- **When:** 2026-10-27 00:15 MT. **Who:** Claude.
- **Decision:** every table keys on `ts_utc`, the start of the hour in UTC. Local time is used only for calendar features and display, from one IANA zone per BA; MISO uses America/Chicago because EIA publishes it in EST all year.
- **Evidence:** [grid §2](data-profile/grid.md#2-the-tidy-table) (EIA labels the end of the hour; a test pins the seal boundary), [grid, implications](data-profile/grid.md#implications-for-the-experiment-design); [nb01 §0, §3](../notebooks/01_grid_profile.ipynb).
- **Rejected:** EIA's hour-ending labels (a half-open window would then include the wrong hour); EIA's local-time column (wrong for MISO).

### D-023 · Clean the demand target; never score imputed hours
- **When:** 2026-10-27 00:15 MT. **Who:** Claude.
- **Decision:** forecast EIA's adjusted demand with isolated spikes (> 15 % from both neighbours' mean while they agree within 10 %) and values ≤ 0 removed; score only hours EIA did not impute; report how many hours each rule removes.
- **Evidence:** PACE reported 12,566 MW on 2021-09-13 21Z against 6,512 MW of generation minus interchange, and that one hour turns PACE's 2021 "hours within 5 % of peak" from 40 into 1; 996 of 1,181 imputed candidate-BA hours are exact copies of the BA's forecast ([nb01 §2](../notebooks/01_grid_profile.ipynb); [grid §4](data-profile/grid.md#4-outliers-and-adjusted-vs-raw-values)).
- **Rejected:** raw demand (EIA replaced absurd raw values); adjusted demand without a spike filter; rebuilding demand from generation minus interchange (fails by definition in BPAT and CISO).

### D-024 · The BA's own forecast is a baseline, never a feature
- **When:** 2026-10-27 00:15 MT. **Who:** Claude.
- **Decision:** the BA's day-ahead demand forecast (DF) is a baseline to beat, never a model input, because EIA publishes it around 11:00 ET on the day it forecasts. It is aligned per BA on the validation year only (PJM +1 h; CISO +1 h from mid-2022; PACE 0) and scored without imputed hours.
- **Evidence:** [nb01 §4](../notebooks/01_grid_profile.ipynb) (alignment by year; PACE 4.0 % MAPE with +2.7 % bias); [grid §7](data-profile/grid.md#7-the-bas-own-day-ahead-forecast-the-baseline).
- **Rejected:** the DF as a feature (lookahead); scoring PJM and CISO as published without saying so; choosing alignments on the test year.

### D-025 · Honest weather only; weather-free primary model
- **When:** 2026-10-27 00:15 MT. **Who:** Claude.
- **Decision:** archived weather enters only from Open-Meteo's Previous Runs API, chosen per target hour by `weather.safe_previous_day` (`_previous_day2`, or `_previous_day1` where it was already published). The primary model is weather-free (long history); a weather-augmented model is compared on validation, and the spec picks the temperature-honest or skewed-training option.
- **Evidence:** the unsuffixed Previous Runs series equals the Historical Forecast in 100 % of 40,417 overlapping hours (a 0–5 h nowcast); all three variables exist as `_previous_day2` only from 2024-02-17 ([nb02 §1–§4](../notebooks/02_weather_honesty.ipynb); [grid §9](data-profile/grid.md#9-archived-weather-forecasts-open-meteo)).
- **Rejected:** Historical Forecast or unsuffixed Previous Runs values as features (they leak); observed weather; the Single Runs API (data only from 2026-04-02, inside the seal).

### D-026 · Stop the Historical Forecast download; extend Previous Runs
- **When:** 2026-10-27 00:15 MT (plan v2, first action 1). **Who:** Claude.
- **Decision:** stop the leftover Historical Forecast download and start the queued Previous Runs set (secondary load centres plus wind and solar sites, honest `_previous_day2`, from 2024-01).
- **Evidence:** [nb02 §0](../notebooks/02_weather_honesty.ipynb): the Historical Forecast archive holds 6 of 17 primary points (MISO_IND partial); [plan v2, first actions](plan/2026-10-27-plan-v2.md#first-actions-after-approval-in-order).
- **Rejected:** finishing the Historical Forecast back to 2019 for all points. Consequence: the spec's skewed-training option (c) has Historical Forecast features only for those 6 points.

### D-027 · EIA's hourly CO2 is the primary carbon signal
- **When:** 2026-10-27 00:15 MT. **Who:** Claude.
- **Decision:** the primary average-intensity signal is EIA's own hourly CO₂ estimate (per-BA workbooks), on both production and consumption bases, reported side by side. Our fuel-mix × EIA-factor intensity is the transparent fallback and the input to the marginal proxy.
- **Evidence:** our intensity tracks EIA's hour by hour (correlation about 0.97 or more for every BA except AZPS); the consumption basis is 2.2–3× the production basis for hydro importers (BPAT 102 vs 34 g/kWh, IPCO 249 vs 103) ([nb05 §1](../notebooks/05_carbon_when_vs_where.ipynb); [grid §5, §8](data-profile/grid.md#5-fuel-mix-and-the-carbon-intensity-method)).
- **Rejected:** fuel-mix intensity as the primary signal (EIA's BA-specific factors are better); production basis only (flatters hydro destinations).

### D-028 · Report average and marginal; never headline the average gain
- **When:** 2026-10-27 00:15 MT. **Who:** Claude.
- **Decision:** time-shifting results in PACE are reported on average and consumption bases with the marginal proxy beside them ("skeptic mode" in the UI). An average-intensity saving is never presented as avoided emissions.
- **Evidence:** a 24 h wait cuts PACE's average-intensity CO₂ by 33 %, but the marginal proxy is 497–658 g/kWh in every block; scored on it, the same schedule saves about 0 %, and a schedule built on it at most about 10 % ([nb05 §2](../notebooks/05_carbon_when_vs_where.ipynb); [grid §8](data-profile/grid.md#8-carbon-intensity-room-for-when-and-where)).
- **Rejected:** "33 % CO₂ avoided by waiting"; marginal intensity as the primary objective (not identifiable for CISO, BPAT, AZPS, NEVP, IPCO, PACW).

### D-029 · Move vs wait is in the core, with capacity limits
- **When:** 2026-10-27 00:15 MT. **Who:** owner.
- **Decision:** cross-region moves are in the core experiment: Utah plus 3–5 neighbours, with destination capacity limits and migration rules.
- **Evidence:** moving a PACE job to BPAT, CISO or NEVP cuts 94 %, 65 % and 42 % (production basis; 82 %, 67 %, 44 % on consumption), against 33 % for a 24 h wait; BPAT is cleaner than PACE in 100 % of hours, so without limits the answer is always "go to BPAT" ([nb05 §3](../notebooks/05_carbon_when_vs_where.ipynb); [plan v2, decisions](plan/2026-10-27-plan-v2.md#decisions-to-date)).
- **Rejected:** plan v1's time-only core with cross-region routing as a Should; unconstrained moves.

### D-030 · Second insight: clean hours ≠ rush hours
- **When:** 2026-10-27 00:15 MT. **Who:** Claude.
- **Decision:** the story's second insight is that, in Utah, the cleanest hours are not the rush hours. The emissions-first router moves PACE work from coal nights to solar middays, not out of the 17:00–20:00 peak; grid-stress hours avoided are a secondary, separately reported outcome.
- **Evidence:** PACE demand and intensity correlate at −0.18 and its top-100 demand hours are only 3 % dirtier than average; in NYIS, ISNE, PJM and DUK they are 20–36 % dirtier ([nb05 §4](../notebooks/05_carbon_when_vs_where.ipynb); [grid §8](data-profile/grid.md#8-carbon-intensity-room-for-when-and-where)).
- **Rejected:** assuming that avoiding the rush hour and cutting carbon are the same objective.

### D-031 · Rush hour defined per BA by percentile; forecast demand and net load
- **When:** 2026-10-27 00:15 MT. **Who:** Claude.
- **Decision:** rush-hour definitions are per BA and percentile-based, with bootstrap intervals; the traffic report forecasts both demand and net load.
- **Evidence:** hours within 5 % of the peak range from 9.5 (BPAT) to 95 (ERCO) a year, and from 21 to 40 for PACE across years; PACE's net-load peak is later (19–20 h) and more concentrated (11 h) than its demand peak ([nb01 §3](../notebooks/01_grid_profile.ipynb); [grid §6](data-profile/grid.md#6-rush-hour-structure)).
- **Rejected:** one fixed top-k rule for every BA; a demand-only rush hour.

### D-032 · The core region set
- **When:** 2026-10-27 00:15 MT. **Who:** Claude.
- **Decision:** PACE (hero), BPAT, CISO, NEVP, AZPS, PSCO, ERCO, SWPP, MISO, PJM; optional IPCO and NYIS. WACM and WAUW stay out.
- **Evidence:** every core BA reports demand in ≥ 99.75 % of hours and has all 8,592 sealed-window rows; together they span hydro to coal and solar-driven to flat carbon ([nb01 §1, §5](../notebooks/01_grid_profile.ipynb); [grid §10](data-profile/grid.md#10-recommended-bas-10-core-2-optional)). WACM and WAUW retire on 2026-04-01, inside the test window ([nb01 §1.2](../notebooks/01_grid_profile.ipynb), counts only).
- **Rejected:** PACW (forecast degraded to 11.5 %, implausible gas reporting); FPL (6.3 % of 2022 demand missing); TVA, DUK, SOCO, ISNE (good data, but flat carbon that duplicates PJM and MISO); PSEI, SPA, FPC, WALC, LDWP (forecast errors of 16–120 % or demand gaps).

### D-033 · Acme Seren is the primary trace
- **When:** 2026-10-27 00:15 MT. **Who:** Claude.
- **Decision:** Acme Seren (2023, LLM development) is the primary workload; Alibaba PAI 2020 is the robustness trace; the Alibaba 2026 spot trace only anchors the share operators already treat as preemptible.
- **Evidence:** Acme is the only LLM-era trace with true timestamps and operator job types ([nb03 §1–§2](../notebooks/03_workloads.ipynb); [workloads §1.1](data-profile/workloads-prices.md#11-candidates)).
- **Rejected:** Microsoft Philly (2017, no job type or GPU model); SenseTime Helios (fewer fields than PAI); Alibaba's 2026 ASI and MaaS releases (too large, no arrival times, or inference only).

### D-034 · Job model: every GPU-hour counts, waits are assumed, capacity is capped
- **When:** 2026-10-27 00:15 MT. **Who:** Claude.
- **Decision:** every GPU-hour counts as load whatever the job's final state. The levers are start time and pause/resume of long jobs. Allowed wait is an *assumed* sweep (0–48 h), deferrable share is swept between the 2.4 % already preemptible and the ~91 % that is batch work, pauses carry an assumed restart cost, and multi-node jobs move only before they start. A GPU capacity cap is mandatory, with the trace's own run-now schedule as the baseline.
- **Evidence:** jobs over 6 h are 1.1 % of Seren's jobs and 89 % of its GPU-hours; "cancelled" is how 67 % of its GPU-hours end; queues are a median of 1 s, so no tolerance to waiting is measured; the cluster runs flat at 61 % of 2,288 GPUs, 84 % on busy days ([nb03 §2–§4](../notebooks/03_workloads.ipynb); [workloads §1.9](data-profile/workloads-prices.md#19-features-that-can-ground-the-labeled-assumptions)).
- **Rejected:** counting only completed jobs; "jobs moved" as a metric (evaluations are 65 % of jobs and 6 % of GPU-hours); deferral without a capacity cap.

### D-035 · 0.7 kWh per GPU-hour, swept 0.4–2.0
- **When:** 2026-10-27 00:15 MT. **Who:** Claude.
- **Decision:** 0.6 kWh of IT energy per busy A100-class GPU-hour × PUE 1.2 ≈ 0.7 kWh at the meter (*modeled*), swept from about 0.4 to 2.0.
- **Evidence:** measured Acme server power: busy band 4.3–4.9 kW per 8 GPUs, mean 2.9 kW; the H100-class system maximum gives the upper bound ([nb03 §5](../notebooks/03_workloads.ipynb); [workloads §1.7](data-profile/workloads-prices.md#17-energy-per-gpu-hour)).
- **Rejected:** board TDP alone (misses the server and cooling); a per-job utilization model (utilization varies tenfold and is unknown for Acme jobs).

### D-036 · Week-block bootstrap aligned by local wall clock
- **When:** 2026-10-27 00:15 MT. **Who:** Claude.
- **Decision:** stretch the trace to a year by drawing whole trace weeks with replacement, aligned by weekday and local wall-clock hour (10:00 at the cluster becomes 10:00 MT), one seed per replicate; state the scale multiplier for any Utah-scale scenario.
- **Evidence:** traces cover 10–24 weeks; UTC alignment would shift the cluster's working-hours pattern by 14 hours; Seren as recorded is about 0.5–0.85 MW of IT load ([nb03 §6](../notebooks/03_workloads.ipynb); [workloads §1.8](data-profile/workloads-prices.md#18-mapping-a-weeks-long-trace-onto-the-12-month-grid-window)).
- **Rejected:** tiling the trace in order; a generative Poisson model (loses campaign burstiness); seasonal replay; alignment by UTC.

### D-037 · Prices are a Should, on PACE real-time; test channel pre-registered
- **When:** 2026-10-27 00:15 MT. **Who:** Claude.
- **Decision:** prices are a Should, labelled "wholesale scenario". PACE's price channel trains and validates on the WEIM real-time price (`ELAP_PACE-APND`); whether the test window uses real-time throughout or EDAM day-ahead from 2026-05-01 is recorded before the seal opens. The stress proxy is built on net load.
- **Evidence:** CAISO prices are keyless only from 2023-07-16; ERCOT from 2010; PACE has no day-ahead history before EDAM; price peaks follow net load ([nb04 §1–§6](../notebooks/04_prices.ipynb); [workloads §2](data-profile/workloads-prices.md#2-wholesale-prices)).
- **Rejected:** a PACE day-ahead history that does not exist; price as the objective (D-018); a CAISO hub as PACE's price without saying so (PACE real-time is cheaper in 86 % of hours, correlation 0.61).

### D-038 · Impeccable in this repo only; no UI UX Pro Max
- **When:** 2026-10-27 00:15 MT. **Who:** owner.
- **Decision:** the Impeccable design skill is vendored at a pinned commit into this repository only, with no global changes and no Codex hooks; UI UX Pro Max is not installed.
- **Evidence:** [plan v2, decisions to date](plan/2026-10-27-plan-v2.md#decisions-to-date) and first action 4.
- **Rejected:** a global install; UI UX Pro Max.

### D-039 · Four light design directions, picked at G2
- **When:** 2026-10-27 00:15 MT. **Who:** owner.
- **Decision:** after design research, four light directions are mocked up with real data (three by Claude, one by Astra), and the owner picks one at G2. No dark theme.
- **Evidence:** [plan v2, decisions and UI/UX track](plan/2026-10-27-plan-v2.md#uiux-track).
- **Rejected:** plan v1's three directions, including the dark "Mission Control".

### D-040 · Private links, an SSH tunnel and pull-and-run for viewing the UI
- **When:** 2026-10-27 00:15 MT. **Who:** owner.
- **Decision:** the owner sees UI work through private Artifact links, an SSH tunnel to the DGX dev server, or pulling and running the app on the MacBook.
- **Evidence:** [plan v2, seeing the UI from the MacBook](plan/2026-10-27-plan-v2.md#seeing-the-ui-from-the-macbook).
- **Rejected:** public hosting or public tunnels (making anything public needs the owner's approval).

### D-041 · An evidence trail: notebooks and this log
- **When:** 2026-10-27 00:15 MT. **Who:** owner.
- **Decision:** executed notebooks committed with outputs (rendering on GitHub), HTML exports in `docs/evidence/`, and this decision log, each notebook ending with the decisions it supports; `make notebooks` re-executes them.
- **Evidence:** [plan v2, evidence trail](plan/2026-10-27-plan-v2.md#evidence-trail-owner-request-credibility-and-understanding); the notebooks in [`notebooks/`](../notebooks/).
- **Rejected:** evidence that lives only in profiles, chat or slides.

### D-042 · BA polygons from Electricity Maps, fitted to Natural Earth
- **When:** 2026-10-27 00:17 MT (merged in PR #10, built earlier that night). **Who:** Claude.
- **Decision:** BA polygons come from Electricity Maps' zone geometries (AGPL-3.0), fitted to Natural Earth's land and simplified; SWPW is drawn as the union of WACM and WAUW (approximate); load-centre points come from a curated table.
- **Evidence:** [geo, why Electricity Maps](data-profile/geo.md#why-electricity-maps) and [how the polygons are built](data-profile/geo.md#how-the-ba-polygons-are-built): a gap-free, non-overlapping coverage whose area equals the land mask.
- **Rejected:** HIFLD Open control areas (retired), the EIA Energy Atlas layer (token required), NASA's mirror (refused connections), unlicensed ArcGIS re-uploads, the EIA Grid Monitor (13 regions only).

### D-043 · Freeze Wed 13:00; checkable version Tue 18:00
- **When:** 2026-10-27 00:17 MT (commit `cb1c6fb`; the brief and plan say 00:35). **Who:** owner. **Supersedes:** D-015.
- **Decision:** experiments freeze Wed 13:00 MT; final numbers are locked in the dashboard and deck by 14:00; after the freeze only logged bug-fix re-runs are allowed. A checkable version (tag `checkpoint-tue`, real validation results in the chosen design) is due Tue 18:00, and the configs for the sealed evaluation freeze around Tue 23:00.
- **Evidence:** [brief, deadline](brief.md#owner-decisions-2026-10-26); [plan v2, amendments](plan/2026-10-27-plan-v2.md#amendments).
- **Rejected:** the Wed 11:00 freeze (D-015).

## D-044 · 2026-10-27 02:50 MT · Spec reconciled: Codex base + amendments, gate fixes F1–F10
- **Decided by:** Claude (reconciliation); fresh-context gate review.
- **Decision:** `docs/superpowers/specs/2026-10-27-gridpilot-design.md` is the experiment spec.
  - Base: Codex's proposal.
  - Additions: R1–R6 from Claude's proposal, and gate fixes F1–F10.
  - Notable choices:
    - consumption-basis carbon;
    - non-preemptive gang jobs;
    - a continuous 161-day replay;
    - policies U/G/S/K/W/L/H;
    - deadlines relative to U.
- **Evidence:** `docs/reviews/2026-10-27-spec-gate-r1-claude.md`.
- **Supersedes:**
  - D-034, pause/resume as the main lever: primary jobs are non-preemptive now.
  - D-036, week-block bootstrap mapping: replaced by the continuous cycle replay.
  - Plan v2's model and policy names (LightGBM; P0–P4): replaced by HistGradientBoosting and U/G/S/K/W/L/H.

## D-045 · 2026-10-27 02:50 MT · Minimal honest core for Tue 18:00
- **Decided by:** Claude, on the gate's recommendation.
- **Decision:** spec §15 F9 defines what is built by 18:00, what comes after 18:00, and what is deferred or cut.
- **Evidence:** gate finding L7-1.

## D-046 · 2026-10-27 02:50 MT · Codex budget
- **Decided by:** owner.
- **Decision:** at most 3 pre-approved runs:
  - Astra spec gate, at high;
  - an optional Sol code review, at xhigh;
  - the Astra results audit, at high.

  Anything else needs the owner's yes.
- **Evidence:** `.claude/skills/codex-gates/SKILL.md`.

## D-047 · 2026-10-27 02:15 MT · Rigid jobs pinned to their U placement (spec F11)
- **Decided by:** lead (Claude), as an SDD ruling. It is reversible, and goes to the Astra gate as an explicit lens.
- **Decision:** zero-slack jobs (`deadline − duration ≤ U start`, which covers all non-flexible jobs) are pre-booked at their U site and start in every policy run. The search window for flexible jobs is `[arrival, deadline − duration]`.
- **Evidence:** the Task 4 implementer's slice benchmark found G with 11 late jobs and S with 5 at 1.0×, all on legal ledgers (PR #19 report).
- **Alternatives rejected:**
  - slack tolerance for rigid jobs, which breaks the owner's hard-deadline decision;
  - reporting lateness and relying on the F1 fallback, which would make the headline carry late jobs that are a scheduling artifact.

## D-048 · 2026-10-27 02:35 MT · F11 revised: bookings as fallback, not pins
- **Decided by:** lead (Claude), as an SDD ruling. It is reversible and goes to the Astra gate.
- **Decision:** replaces D-047.
  - Every job holds its U slot as a booking. A policy may move a job only to an on-time action that fits without disturbing any other booking.
  - Every policy is on time by construction.
  - The assumption that bookings are known in advance is labelled and disclosed.
- **Evidence:** the Task 4 task review (finding 4). Pins leaked future arrivals unlabelled, pinned queued mobile flexible jobs (biasing results toward U), and still left small-slack flexible jobs late.
- **Alternatives rejected:**
  - pins (D-047);
  - a slack tolerance, which breaks hard deadlines;
  - accepting lateness, which would make the headline carry a scheduling artifact.

## D-049 · 2026-10-27 02:35 MT · Astra spec gate r1: not_ready → fixes F12
- **Decided by:** lead (Claude). Every finding is dispositioned; the claim reframing goes to the owner at G1.
- **Decision:** 22 findings, of which 11 are important and 11 minor (corrected per Sol r2 R12). 21 were dispositioned as fixed, of which Sol r2 rated 6 partial and 1 inadequate (E2); 1 is deferred (A3); none is rejected.
  - The main reframing: the experiment is an **advance-reservation scheduling scenario** (F11 bookings and the F3 closure calendar are both assumed and advance-known), with baseline-relative deadlines and exact declared runtimes. It is not a historical online-router claim.
  - Causal sensitivities (shadow-U, and the missingness-blind scheduling sensitivity of F13.6) are deferred until after 18:00.
- **Evidence:** `docs/reviews/2026-10-27-spec-astra-r1-astra.md`.
- **Alternatives rejected:** adopting shadow U as the primary design. If no job moves away from PACE, it makes time-only savings exactly zero by construction, so it would answer a different question.

## D-050 · 2026-10-27 02:37 MT · Owner accepts the advance-reservation claim frame; Sol re-checks the gate
- **Decided by:** owner.
- **Decision:**
  - The headline is framed as a simulated advance-reservation scheduling scenario, with baseline-relative deadlines and exact declared runtimes (F12.5, F12.7). The shadow-U causal version is a sensitivity.
  - The spec re-check uses the optional Sol slot (budget run 2 of 3) at xhigh, instead of a second Astra run.
- **Evidence:** the owner's answers in session; `docs/reviews/2026-10-27-spec-astra-r1-astra.md`.

## D-051 · 2026-10-27 02:52 MT · Sol r2 re-check: not_ready → F13 (precision fixes)
- **Decided by:** lead (Claude).
- **Decision:** Sol's 12 findings and one interaction note are adopted as spec §15 F13. Sol stated that validation-only implementation proceeds now.
- **Re-check:** a fresh-context Claude reviewer re-checks F13. This is a substitution, since the budget's last run is reserved for the Wed results audit.
- **Evidence:** `docs/reviews/2026-10-27-spec-sol-r2-sol.md`.

## D-052 · 2026-10-27 03:05 MT · Gate passes: fresh Claude re-check ready_with_minor_fixes → F14
- **Decided by:** lead (Claude). The Codex re-check is substituted per the budget (D-046, D-050).
- **Decision:** N1–N15 are adopted as spec F14, with one change.
  - For N6, the reviewer proposed closing PACE capacity in missing hours. Instead, F14.6 pre-registers a four-tier truth fill (consumption → production → fuel mix → 7-day same-hour mean, with tiers 2–4 labelled modeled).
  - Why: the completeness check found a shared roughly 50 h gap across all four BAs in the sealed window, 24 h of it with no EIA data at all. Closing capacity for 50 h would make long jobs unplaceable.
  - The spec gate is passed (G1 condition) at 41b2e30 + F14.
- **Completeness check (counts only, values never read):** missing consumed-basis hours in [TEST_START, 2026-10-27T05Z]:
  - PACE 51 (gaps of 50 h and 1 h), of which 24 h have no production basis and no fuel mix;
  - CISO 138 (78 with no production basis; 54 of those have fuel mix);
  - BPAT 51; NEVP 51.
  - Last hour present: 2026-10-27T05Z.
- **Evidence:** `docs/reviews/2026-10-27-spec-claude-r3.md`.

## D-053 · 2026-10-27 04:41 MT · G2 visual direction: round-3 layouts with the Utah palette
- **Decided by:** owner; the palette construction is the lead's.
- **Decision:** the round-3 dashboard concepts are kept ("dashboard looks good"). The colour changes to meaningful, Utah-warm colour: a diverging carbon scale (green cleaner, sand at the assumed US-average 380 g/kWh, Utah orange to canyon red dirtier), a deep-blue router action, a neutral caution hatch for rush hour, and a warm salt-flat ground.
- **Evidence:** the owner's G2 message; validator results in `docs/design/tokens.md`; screenshots in `docs/design/concepts/shots/round4/`.
- **Open:** source the US-average midpoint from EIA. Which layouts Task 8 builds first is to be confirmed by the owner.

## D-054 · 2026-10-27 ~06:00 MT · Illustrative job: criterion v2, the GPU-hour-weighted median
- **Decided by:** lead (Claude), on the Task 7 reviewer's proposal.
- **Decision:** the §11 literal rule (the job nearest the median GPU-hours) picks a 1-GPU, 203 s SFT job, because the median of the eligible set is 0.056 GPU-h. The story instead shows the job at the GPU-hour-weighted median of the same eligible set: 5930563#c3, Pretrain, 72 GPUs, 103.6 h. The literal job is kept in the export as `illustrative_job_literal`.
- **Why it doesn't search for wins:** the criterion uses only workload attributes and the policy-independent U replay; no outcome was consulted. The disclosure text is exported verbatim.
- **Evidence:** `results/job-replay.json` (`illustrative_job.criterion`, `.disclosure`).

## D-055 · 2026-10-27 ~06:15 MT · EIA consumption-basis CO₂ intensity is `modeled`; the colour midpoint is 356 g/kWh
- **Decided by:** lead (Claude), as a ruling on a spec inconsistency flagged by the dashboard critic.
- **Decision (label):** EIA's hourly consumption-basis CO₂ intensity is labelled **modeled** ("EIA estimate") in every export and in the UI, per spec §4, §11 and F7, which override F14.6's looser wording. EIA-930 demand, net load and solar stay **observed**.
- **Decision (midpoint):** the diverging colour midpoint is the US 2024 average, 785 lb CO₂/MWh = **356 g/kWh**, from the EIA United States Electricity Profile 2024 (https://www.eia.gov/electricity/state/unitedstates/). It is exported in `results/grid-profile.json` with that provenance. It is a national generation-basis annual reference, not a consumption-basis hourly value, and the legend states this.
- **Evidence:** Task 8 critique findings #10 and #11; `docs/design/tokens.md`.

## D-056 · 2026-10-27 ~06:20 MT · Validation result recorded (registered run 20261027T122317Z)
- **Decided by:** this is a record, not a choice. The numbers come from `make slice` at a clean commit; canonical metrics hash `f45821c0…`.
- **Result (validation year, phase 0, conditional temporal block-resampling 95% intervals, b = 4):**
  - Moving with S, K, W or L cuts attributed CO₂ by 22.4–22.6% against U (S: 22.62% [18.36, 26.82]).
  - Waiting in Utah alone (time-only) saves 0.72–0.75%.
  - G (carbon-blind earliest finish) saves 0.01%.
  - Every policy is on time and above the relaxed bound (3,501.3 t).
  - H2 (W vs L) is inconclusive.
  - H3 is not supported: no dynamic search beats S, and K emits 10.0 t more than S.
- **Interpretation (carried into the narrative):** placement dominates timing, mostly through moving work to BPAT. The top 1% of jobs (9,180) carry 94% of the energy.
- **Evidence:** `results/metrics.json` (`framing`, `policies`, `workload`); `results/manifest.json` (claim frame and limitations).

## D-057 · 2026-10-27 07:50 MT · The registered validation run is preserved outside the agent worktree
- **Decided by:** lead (Claude), from the Stage 2 final review (finding A1).
- **Decision:** the run directory `runs/slice/20261027T122317Z/` (178 MB; ledgers, bookings, truth_fill, forecasts, cohort, config) is preserved in three ways:
  - copied to the main checkout's `runs/slice/`, which is gitignored;
  - archived at `~/workspace/personal/projects/htw-archive/runs/slice/`;
  - its source worktree is locked.
- **Code reference:** the code commit 9c05198 was squash-merged into main as 2e6b6fc, so 9c05198 is tagged `run-20261027T122317Z` and the tag is pushed.
- **File hashes:** `docs/evidence/run-20261027T122317Z.sha256` (25 files).

## D-058 · 2026-10-27 ~07:55 MT · Extensions before the 21:00 cutoff: the robustness pack and key sensitivities
- **Decided by:** owner.
- **Run, on validation only:**
  - production-basis repricing;
  - common support on filled hours;
  - workload phases 49 and 98;
  - sensitivities: destination capacity 0 and 1,024; transfer time 120 min; batch delay 24 h; mobility limited to jobs of 8 GPUs or fewer.
- **Cut, reported as `not_run` with a reason:**
  - the shadow-U (no advance booking) sensitivity;
  - the remaining §7 sensitivities (PUE, power, transfer energy, idle power, flexibility shares, 1.25× home capacity runs);
  - the missingness-blind scheduling sensitivity.
- **Evidence:** the owner's answer in session; Stage 3 plan `docs/superpowers/plans/2026-10-27-stage3-freeze-test.md`.
