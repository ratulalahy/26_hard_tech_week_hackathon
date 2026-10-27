# Hard Tech Week Hackathon: Torus bounty plan

> Historical plan: later entries under **Amendments after approval** take precedence over earlier wording. A proposed owner decision stays pending until explicitly accepted. Current execution status is in `docs/HANDOFF.md`.

## Context

- **Event:** Hard Tech Week Hackathon. The build window runs from Mon Oct 26 5 PM to judging on Wed Oct 28 5 PM MT, at Aernata (250 E 200 S #320, SLC). Judging is a demo plus judge Q&A, 8–25 min per team.
- **Bounty:** Torus, "Energy × AI infrastructure", $5K.
  - Option 1, *Rush Hour for Electrons*: know when the grid is jammed and stay out of traffic.
  - Option 2, *Compute Follows the Sun*: decide where and when compute runs.
  - Judged on **creativity, clarity of insight and execution**. Free/open data only; simulated data is allowed if it is labeled.
- **Torus, for the pitch:** a SLC company making flywheel and battery storage for AI data centers and utilities. It has a 70 MW demand-response MOU with Rocky Mountain Power tied to Utah's Operation Gigawatt, so a Utah (PACE) angle speaks to the judges.
- **User decisions (Oct 26, ~10:45–11:00 PM):**
  - **Direction "A + C":** Option 1's day-ahead *grid traffic report* plus Option 2's *AI-job router*, evaluated in **simulation on real data**. There is no live hardware loop.
  - **Priority:** high-end visualization. A map, plus the simulation made visible.
  - **Data first:** download and profile the data, then design the experiment.
  - **DGX Spark = the lab only.** It is not part of the pitch; if asked: "we ran the experiments on a DGX."
  - **Demo:** from the user's laptop, as an offline static build. No tunnel.
  - **Team:** solo plus agents. Claude Code builds; **Codex plans and reviews alongside**.
  - **Check-ins:** gates plus phone pings; agents keep going overnight on reversible work.
  - **Deadline:** experiments are mostly done by **Wed 2 PM**.
- **Start state:**
  - `~/workspace/personal/projects/26_hard_tech_week_hackathon` is empty.
  - `github.com/ratulalahy/26_hard_tech_week_hackathon` is private and empty.
  - `gh` is authenticated. The GitHub MCP fails to connect (bad auth header), so we use the `gh` CLI.

## The project (working name "GridPilot"; the spec sets the final name)

> A traffic report for tomorrow's grid, and a router that keeps AI jobs out of rush hour, backtested on a year of real US grid data.

1. **Grid traffic report (Option 1).**
   - Day-ahead hourly forecasts for about 10 US balancing authorities (BAs), chosen from the data profile. Utah's PACE is the hero region.
   - Forecast targets: demand, a grid-stress index (defined in the spec), carbon intensity, and price where it is public.
   - Each forecast has prediction intervals and flagged rush-hour windows.
2. **AI-job router (Option 2), simulated.**
   - Replay a public GPU-cluster job trace across the 12-month test window.
   - Each job carries labeled assumptions: deferrable share, allowed wait, whether it can be interrupted, whether it can move regions, and energy per GPU-hour.
   - Policies: run-now · fixed off-peak rule · greedy on the current signal · **forecast-driven optimizer (ours)** · perfect-hindsight upper bound.
   - The router decides *when* and *where* each job runs.
3. **Utah headroom study (Should).**
   - How many MW of flexible AI load PACE could add if that load skips its worst N hours a year (the method of Duke's 2025 *Rethinking Load Growth*).
   - How much on-site storage covers the rest.

**Target insights.** Report what the data says, including small gains.
- How predictable tomorrow's rush hour is, compared with the utilities' own day-ahead forecasts.
- CO₂, dollars and rush-hour MWh saved, against how long jobs may wait.
- Time-shifting vs moving jobs between regions, and the share of hindsight savings our forecasts capture.
- For Utah: MW of headroom against curtailment hours, with and without storage.

## Phases

### Phase 0: Setup (right after approval, ~45 min)

- **Git and GitHub.**
  - `git init -b main`, plus `.gitignore` and `.env.example`; push to `origin`.
  - Labels: `track:data`, `track:forecast`, `track:router`, `track:viz`, `gate`.
  - One issue per Must item, plus a pinned **"Run log"** issue.
  - **PR flow:** one branch per task in its own worktree → PR → Codex review where the code touches leakage or metrics → **the lead squash-merges**. In this repo the lead merges; you can read any PR on GitHub.
- **`AGENTS.md`**, read by both Codex and Claude:
  - the goal and judging criteria;
  - the directory map;
  - the `make` commands;
  - data rules: test-window seal, no lookahead, provenance labels;
  - the review contract (every finding with severity and confidence, then a verdict line);
  - the autonomy boundaries.
  - It points Codex at `.claude/skills/*/SKILL.md` rather than linking them into the global `~/.codex/skills`.
- **`CLAUDE.md`:** `@AGENTS.md` plus Claude-only notes:
  - which skills to use;
  - DGX gotchas: aarch64, the cu130 torch index, `HF_HOME` / `UV_CACHE_DIR`;
  - effort guidance;
  - no `feature-dev:code-reviewer`.
- **`.claude/`:**
  - `settings.json`, written with the update-config skill: an allowlist for the safe commands unattended runs need (uv, pytest, make, npm, read-only git, `gh issue/pr`) and a deny for destructive ones (force-push, deleting `data/raw`).
  - Three small skills:
    - `experiment-protocol`: run directories, config + SHA + metrics, the seal, labels, what "done" means for a result;
    - `codex-gates`: when to call Sol vs Astra, the commands, the prompt template, the disposition table;
    - `viz-critique`: a hackathon rubric adapted from `bd_voice_ai_platform/.claude/skills/product-design`, plus the screenshot, critic and axe steps.
  - `agents/code-reviewer.md`: a full-coverage reviewer for quick in-session reviews.
- **Codex.**
  - Mark this repo as trusted in `~/.codex/config.toml`.
  - `scripts/review.sh` wraps `~/workspace/cogni_drift/review/bin/codex-review`, setting `REVIEW_ROOT=~/workspace/personal/projects/htw-review` and `DEV_REPO=<repo>`.
  - Run one tiny review to prove the wrapper works on this repo; if not, fall back to `codex exec --ephemeral` over a detached worktree.
  - **First Codex job: Sol reviews this plan** in the background (full coverage). Its findings are dispositioned before the spec.
- **Environments.**
  - `lab/` is a uv project with torch 2.13 cu130, the same build that works in `dgx-dev`; smoke-test it on the GPU.
  - `web/` is scaffolded by the UI track with npm (no global installs).
  - The context7 plugin covers library docs (deck.gl, MapLibre, ECharts, Polars, HiGHS).

### Phase 1: Data recon before design (~1–1.5 h, overlaps Phase 0)

- **Pull:**
  - EIA-930 from 2019 to now;
  - Open-Meteo archived forecasts for candidate BA points, finding where coverage starts;
  - price nodes: CAISO hubs, PACE through CAISO's western market, ERCOT hubs;
  - a public-domain BA boundary GeoJSON;
  - a Protomaps PMTiles US basemap extract;
  - two public GPU traces (Alibaba PAI 2020, Microsoft Philly).
- **Profile** into `docs/data-profile.md` with figures:
  - coverage and gaps per BA;
  - EIA adjusted vs raw values;
  - fuel-mix completeness;
  - rush-hour structure (daily and seasonal);
  - the utilities' own forecast error;
  - where archived weather forecasts start;
  - trace statistics: arrivals, durations, GPU counts;
  - **a recommended region set.**
- **Seal:** the test window (2025-11 to 2026-10) is checked only for completeness (row counts, missing hours). It is never plotted or summarized, so the design can't be tuned to it.

### Phase 2: Experiment design, with Codex (~1.5 h)

1. Claude writes `docs/superpowers/specs/2026-10-26-gridpilot-design.md` from `docs/brief.md` and the data profile.
2. At the same time, **Sol writes its own version** from the same inputs.
3. Every difference becomes a decision. Technical ones: the lead decides and records them. Product ones: you.
4. The spec covers:
   - hypotheses, metrics, baselines and splits;
   - the stress-index definition;
   - the job assumptions and the policies;
   - the **results contract**: the artifacts and fields the UI reads;
   - the story beats for the dashboard.
5. Astra soundness gate (fresh session), then fixes.
6. Builder check (from the brainstorming skill).
7. **G1.**

### Timeline and gates (MT)

| When | Work | Gate |
|---|---|---|
| Mon ~11:00 PM – ~2:30 AM | Phases 0–2 | **G1:** spec ready (ping). If you're asleep, agents build direction-independent foundations and you approve at G2 |
| ~2:30 – Tue 8 AM | Implementation plan, verified by Sol. Data pipeline; forecast baselines and evaluation harness; simulator and baseline policies, test-first; contract and fixtures. **UI:** 3 named visual directions as clickable prototypes on fixture data, published as private Artifacts for phone review | **G2** (~8 AM): approve the spec, check the data and first numbers, pick a visual direction. Start the `htw-ui` session |
| Tue 8 AM – 6 PM | LightGBM and foundation-model forecasts; optimizer and hindsight bound; cross-region routing; Utah study; dashboard on real results (merges around noon and 5 PM); first laptop dry-run | **G3** (~6 PM): do the numbers support the story? Pick the headline insights |
| Tue night | Robustness: prior year, second trace, sweeps, confidence intervals. Story mode polish; critique loop; draft of the 2-minute video | |
| Wed 8 – 11 AM | Astra results audit (claims vs evidence, leakage, baseline fairness, labels), then fixes | **G4** (11 AM): experiments frozen |
| Wed 11 AM – 2 PM | Fresh "tomorrow" forecast for Thursday baked in; final build; 5-slide backup deck and one-page summary; video | your 2 PM target |
| Wed 2 – 5 PM | Offline run on the laptop; three timed rehearsals (8 min plus Q&A); travel | judging at 5 PM |

## Experiment soundness (the spec makes these precise; Astra gates them)

- **Pre-registered.** Hypotheses, metrics, baselines and the test window are fixed in the spec before any test number is seen.
  - The test set is read only via `make eval-test`, and every read is logged.
- **Time splits.**
  - Train: from the start of archived weather forecasts (about 2022; the data profile confirms) to 2024-10.
  - Validate: 2024-11 to 2025-10.
  - **Test: 2025-11 to 2026-10.**
- **No lookahead.**
  - Forecasts are issued at a fixed time and use only data available then.
  - Weather comes from archived forecasts, never observed weather.
  - EIA's publication lag is respected.
  - Automated tests check for leakage.
- **Forecast baselines:**
  - persistence and seasonal naive;
  - the BA's own day-ahead demand forecast;
  - statsforecast (MSTL/ETS);
  - LightGBM with weather and calendar features;
  - zero-shot Chronos-2 and TimesFM 3 on the GPU.
- **Forecast metrics:** MAE/MAPE, CRPS with interval coverage, rush-hour precision and recall at k, and a Diebold–Mariano test against the best baseline.
- **Router evaluation.**
  - Paired comparisons: same jobs, same days.
  - 95% confidence intervals from a block bootstrap over weeks.
  - Sweeps over allowed wait (0–48 h), deferrable share, migration cost, forecast error and region set.
  - Robustness on the prior year and a second trace.
- **Carbon accounting.** Average intensity from the EIA-930 fuel mix is primary. Estimated marginal intensity, from a regression of hourly ΔCO₂ on Δdemand per BA, is the sensitivity check. Both are reported.
- **Prior art in the spec:**
  - Sukprasert et al. 2024, on the limits of carbon-aware shifting;
  - Wiesner et al. 2021;
  - Radovanović et al. 2022 (Google);
  - Norris et al. 2025 (Duke);
  - Emerald AI as the industry reference.
- **Labels.** Every input is tagged `measured`, `derived`, `assumed` or `simulated`, and the tag carries through the data, the results and the UI.
- **Reproducible.**
  - Pinned with `uv.lock`, fixed seeds and a data manifest with checksums.
  - Each run writes its config, git SHA and metrics.
  - `make reproduce` rebuilds `results/` from the raw cache.

## Data (✓ = verified tonight without a key)

| Source | Used for | Access |
|---|---|---|
| EIA-930 six-month bulk CSVs | hourly demand, the BA's day-ahead demand forecast, generation by fuel, interchange; all US BAs, through Oct 2026 | ✓ keyless |
| Open-Meteo historical-forecast + forecast | archived weather forecasts (features); Wednesday's live forecast | ✓ keyless |
| NASA POWER | solar irradiance cross-check | ✓ keyless |
| CAISO OASIS / ERCOT via `gridstatus` 0.37 | hub prices; PACE through CAISO's western market if available | public; Phase 1 confirms the nodes |
| Public GPU traces (Alibaba PAI 2020, Microsoft Philly) | job arrivals, durations, GPU counts | public download |
| BA boundaries + Protomaps PMTiles | map shapes and an offline basemap | public; Phase 1 picks the sources |
| EIA API v2 | freshest hours for Wednesday's forecast | free key (user) |

## Visualization (the priority: high-end, offline on the laptop)

- **One app, two modes.**
  - **Story mode** is a scroll-driven narrative that doubles as the pitch, in 7 beats:
    1. the grid has a rush hour;
    2. it's predictable;
    3. AI jobs can wait;
    4. route them (replay);
    5. what that's worth, with confidence intervals;
    6. Utah headroom (the Torus link);
    7. tomorrow's traffic report, generated Wednesday for Thursday.
  - **Explore mode** is for judge Q&A: any region, day, policy or wait window.
- **Map:** MapLibre GL and deck.gl, interleaved.
  - The basemap is an offline Protomaps PMTiles file with a custom theme.
  - Regions are extruded in 3D by stress, with smooth transitions.
  - Animated job flows (TripsLayer/ArcLayer) show cross-region moves, and rush hours pulse.
  - A synced 48 h scrubber has playback.
- **Signature charts, hand-tuned in D3/visx:**
  - a radial "grid clock" (hour × day of year);
  - a forecast fan chart against actuals;
  - the savings frontier: savings vs allowed wait, with CI ribbons and the share of hindsight;
  - a synced router-replay timeline, baseline vs ours.
- **Dense interactive charts:** Apache ECharts, themed from the same design tokens, for year-long hourly series with brush and zoom.
- **Motion:** GSAP + ScrollTrigger for story mode (pinning, scrubbing), CSS transitions elsewhere. `prefers-reduced-motion` is honored.
- **Craft.**
  - Design tokens: an exact hex palette checked with the dataviz skill's validator, a type scale and spacing.
  - Fonts self-hosted via @fontsource, so nothing needs a CDN.
  - Uncertainty is always shown, and every simulated or assumed value carries a badge.
- **Process.**
  - Use the frontend-design and dataviz skills to produce 3 named directions, for example "Mission Control" (dark, cinematic), "Grid Weather" (forecast-channel metaphor) and "Editorial" (light data journalism).
  - Publish them as private Artifacts; you pick one at G2.
  - Build the chosen one, then run a nightly critique loop:
    1. Playwright screenshots at 1440 and 400 px, light and dark.
    2. Codex image critic (every finding, with severity and confidence) plus axe.
    3. Fix.
- **Web stack:** Vite, React, TypeScript, Tailwind v4, Radix primitives, Zustand for the shared time and selection state, npm.
  - The contract is Pydantic → JSON Schema → TypeScript types, with fixtures labeled FIXTURE until real results land.
- **Performance budget:** 60 fps in the laptop's browser, with data pre-aggregated per view. Checked at Tuesday's dry-run.
- **Could:** plain-English captions written by local Qwen on the DGX and baked into the build.

## Lab stack

- **Python 3.12 + uv (`lab/`):**
  - data: Polars, DuckDB, Parquet;
  - forecasting: statsforecast, LightGBM 4.7, chronos-forecasting 2.3, timesfm 3.0;
  - optimizer and hindsight bound: highspy (HiGHS);
  - prices: gridstatus;
  - tests: pytest and hypothesis.
- All of these have aarch64 wheels (checked). The foundation models get their own dependency group if pins clash.

## How the agents run

| Role | Who | Does |
|---|---|---|
| Owner | user | product calls, gates, the pitch |
| Lead | this Claude Code session (Opus 5.5) | setup, spec, plans, data and experiments; at most 3 subagents at once, each in its own worktree; merges PRs |
| UI | a second Claude Code session in tmux (`htw-ui`), from G2 | the dashboard in its own worktree. Before G2, the lead runs the direction prototypes as subagent tasks |
| Planner and reviewer | Codex Sol 6.1 (`-p review`) | reviews this plan, writes its own spec, verifies the implementation plan, reviews leakage and metric code, critiques screenshots |
| Gate | Codex Astra (`-p astra`, fresh session) | the spec soundness gate and the results audit |

- **Skills:** brainstorming (spec) → writing-plans → subagent-driven-development, with using-git-worktrees and test-driven-development → verification-before-completion. frontend-design and dataviz for the UI.
- **Effort.**
  - Opus 5.5 at `high` for the spec and leakage-sensitive code, `medium` for routine building.
  - Sonnet 5.5 is allowed for mechanical subtasks.
  - Subagent briefs give the goal, the files and "done when", with no double-check clauses.
- **Long runs.** Jobs run in the background with a Monitor that fires on completion or failure (Traceback, Killed, NaN).
  - The plan checklist is the source of truth; a progress report is not completion.
- **Status.** The "Run log" issue has one status comment edited in place: step, last progress, evidence, blockers, next gate. Pushes go out at gates and on blockers.
- **Autonomy.** Agents proceed on reversible work in git, overnight too.
- **Agents stop and ask before they:**
  - change the direction;
  - cut a Must;
  - make anything public (repo visibility, hosting, tunnels);
  - spend money.

## Scope

- **Must:**
  - Phase 1 data profile;
  - about 10 BAs;
  - traffic-report forecasts vs baselines;
  - router backtest vs baselines and the hindsight bound, with confidence intervals;
  - PACE as the hero region;
  - story mode plus explore mode, with the offline map and scrubber, the grid clock, the router replay, the savings frontier, and method & data;
  - the offline laptop build.
- **Should:**
  - foundation-model forecasts;
  - cross-region routing with animated flows;
  - the Utah headroom study with storage;
  - price signals.
- **Could:**
  - Qwen captions;
  - power-level throttling, modeled from published curves;
  - bidding agents;
  - non-US regions.
- **Cut order if we're late:** Could items, then storage, then the foundation models, then cross-region routing. The Must list stays.

## Risks and mitigations

- **Archived weather forecasts start late.** Use a shorter training window, or models without weather features for the early years; the data profile decides.
- **Foundation-model packages clash on aarch64/cu130.** Give them their own venv; LightGBM carries the result.
- **The traces cover only 2–3 months.** Resample arrivals across the year, labeled `simulated`, and use the second trace for robustness.
- **Time-shifting gains turn out small, as the literature finds.** Say so; the insight becomes where the gains really are.
- **No usable BA boundary file.** Fall back to state outlines with BA hex tiles.
- **WebGL is slow on the laptop.** Pre-aggregate the data and dry-run on Tuesday. A static offline build and a video are the backups.
- **The Codex wrapper fights the new repo.** Fall back to direct `codex exec`.

## Repo layout

```
26_hard_tech_week_hackathon/
  AGENTS.md  CLAUDE.md  Makefile  README.md  .env.example  .gitignore
  .claude/settings.json  .claude/skills/{experiment-protocol,codex-gates,viz-critique}/  .claude/agents/code-reviewer.md
  docs/brief.md  docs/data-profile.md
  docs/superpowers/specs/2026-10-26-gridpilot-design.md  docs/superpowers/plans/
  docs/reviews/                # Codex prompts, outputs, disposition tables
  lab/                         # uv project: src/gridpilot/{data,features,forecast,carbon,sim,policies,eval,contract}, tests/, configs/
  results/                     # small committed JSON/Parquet that the UI reads
  web/                         # Vite app (story + explore)
  data/                        # gitignored raw/interim/processed; committed MANIFEST.json
  scripts/review.sh
```

## Your actions tonight (~10 min)

1. Submit the **Bounty Sign-Up Google Form** for Torus, and register for judging if you haven't.
2. Get a free EIA API key (eia.gov/opendata/register.php) and paste it when asked. It goes into the gitignored `.env`.
3. Run `/remote-control` so gate pings reach your phone.
4. Optional: run `/effort high` for tonight's work (this session is on max).
5. When convenient, tell me your laptop's OS and browser, for Tuesday's dry-run.

## Verification

- **`make test`:**
  - leakage tests: no feature uses data after the issue time;
  - simulator invariants: capacity respected, deadlines counted, energy conserved;
  - metric unit tests against hand-computed cases.
- **`make reproduce`** regenerates `results/` from the raw cache, and the hashes match.
- **Sanity checks.**
  - Forecasts beat persistence.
  - On the objective, hindsight ≥ optimizer ≥ baselines; if not, it's a bug.
  - Results hold across seeds and the prior year.
- **Codex.**
  - Sol's plan review and Astra's spec gate and results audit, each with every finding dispositioned.
  - No open critical or major findings from the image critic.
- **Dashboard:**
  - Playwright smoke test and screenshots;
  - axe reports 0 violations;
  - offline run on the laptop at 60 fps;
  - story mode fits 8 minutes over three timed rehearsals.

## Amendments after approval

- **2026-10-26 23:05 MT.** Codex's setup proposal was merged in, keeping one source of truth:
  - the `experiment-protocol` skill is named `hackathon-evidence`;
  - the evidence labels grew to six: observed, measured, forecast, modeled, assumed, simulated;
  - Codex, as planning partner, has its own checkout (`26_hard_tech_week_hackathon-codex`, branch `codex/planning`) and writes its own spec version there;
  - status between the agents lives in `docs/HANDOFF.md`.
- **2026-10-26 23:00 MT.** The basemap uses public-domain Natural Earth layers instead of Protomaps PMTiles, because the auto-mode classifier blocked downloading the `pmtiles` binary. PMTiles is still possible later, with the owner's OK.
- **The demo laptop** is a MacBook Pro running Chrome.
- **2026-10-26 23:35 MT, after Sol's plan review** (`docs/reviews/2026-10-26-plan-sol-r1-sol.md`, verdict not_ready, every finding dispositioned):
  - **Deadline (F03).** Wed 11:00 is the only experiment deadline. From 11:00 to 14:00 we only package frozen results.
  - **Gates (F02).** The gates are rebuilt around deliverables:
    1. G1: data viability plus the spec.
    2. G2, Tue ~08:00: spec approval if still pending, and the visual direction.
    3. G3, Tue ~14:00: the first complete slice — a PACE validation result inside the offline map and replay.
    4. Tue ~22:00: validation freeze; configs frozen at a recorded commit.
    5. Overnight: the sealed evaluation runs.
    6. Wed 08:00–11:00: Astra audit, then G4 freeze at 11:00.
    7. Wed by 14:00: presentation release.
  - **Seal and sanity rules (E01, E07).** Updated in `AGENTS.md` and the `hackathon-evidence` skill.
  - **Demo (V01, V02).**
    - A 4–5 minute core, with branches for longer slots.
    - A bundled launcher plus a single-file fallback.
    - A cold start on the MacBook with the network off, at both dry-runs.
  - **Visualization stack (V04).**
    - deck.gl and MapLibre for the map; ECharts as the only charting library; GSAP dropped.
    - One theme, desktop only.
    - Three named directions as single-screen static mockups, not prototypes.
  - **Environment (W05).** Keep install, load, infer and solve evidence for the exact pins. Foundation models are timeboxed to 2 h; LightGBM and the CPU core carry the result.
  - **Start state (W08).** This plan's "start state" is dated context. The current state lives in `docs/HANDOFF.md`.
  - **Owner decisions pending:**
    - F02: PACE-first vertical slice with a thinner regional overview;
    - E09: which objective is primary.

- **2026-10-26 23:13 MT, planning partner reconciliation (proposal; owner choices still pending).**
  - Keep the approved headline: Compute Follows the Sun, powered by a day-ahead traffic report; no hardware experiment or live execution loop is required.
  - Recommend a PACE forecast → causal router → offline replay as the first complete path, retaining about ten BAs in the overview. This does not cut or reclassify a Must without the owner's approval (F02).
  - Recommend attributed operational emissions as the primary objective, with identical completed work and service constraints; report net-load stress exposure and wholesale energy-cost scenarios separately. This remains an owner decision (E09), not an approved objective.
  - Use the shared, read-only data cache for planning. Claude owns ingestion; no duplicate downloads. Data profiles and manifest hashes, not the provisional library/model list, determine source-dependent design choices.
  - Author the independent spec only after reading the grid, workload/price and geo profiles. Until then, any source-dependent design is a proposal and the test seal stays closed.
  - The implementation contract must support an offline static laptop build: export frozen scenario results and a scenario-availability catalog; no backend, remote machine, API key, network font, or live inference is a core demo dependency.
  - Reconcile proposals before the fresh Astra gate. A review disposition marked "spec" is an unresolved requirement until the spec actually implements it and the gate verifies it; it is not evidence that the experiment is sound already.
  - Existing `make` targets, exact dependency pins and performance claims are acceptance work, not verified facts. Run the commands that exist; label proposed commands as planned until implemented.

- **2026-10-26 23:14 MT, owner decisions received (supersedes the pending F02/E09 choices above).**
  - **F02 approved:** PACE first, regional overview. A complete PACE path is mandatory; about ten BAs remain in the overview, with deeper regional experiments extended as time permits.
  - **E09 approved:** emissions first, with deadlines and common completed work as constraints. Stress exposure and wholesale cost remain separate reported outcomes.
  - These decisions are recorded in `docs/brief.md`; the independent specs must implement them rather than re-open the product choice.
