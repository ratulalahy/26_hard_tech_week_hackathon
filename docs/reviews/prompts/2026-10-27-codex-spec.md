You are Codex, the planning partner on this repository: a 48-hour hackathon entry for the Torus bounty (judging Wed 2026-10-28 17:00 MT). Write your own complete experiment design spec, independently of any other draft.

## Read

Work in your own checkout (`26_hard_tech_week_hackathon-codex`, branch `codex/planning`). Run `git pull --rebase origin main` first; all paths below are relative to it.
- `AGENTS.md`: rules and roles.
- `docs/brief.md`: the bounty and the owner decisions. These are binding:
  - emissions first;
  - PACE first with a ~10-BA overview;
  - experiments freeze Wed 13:00.
- `docs/plan/2026-10-27-plan-v2.md`: the approved plan, including "What the data changed" and its amendments. Move vs wait is in the core.
- `docs/reviews/2026-10-26-plan-sol-r1-sol.md`: the plan review and its dispositions. Every item marked "spec" is a requirement your spec must actually meet.
- `docs/data-profile/grid.md`, `docs/data-profile/workloads-prices.md` and `docs/data-profile/geo.md`: what the data supports. Respect their "Implications" and answer their "Open questions" where you can.

Do not read anything outside your checkout. In particular, skip `/tmp`, other worktrees and any file named `spec-draft*`. Write the spec to `docs/superpowers/specs/2026-10-26-gridpilot-design-codex.md`, commit it on `codex/planning`, push, and add a dated entry to `docs/HANDOFF.md`. Change nothing else.

## The spec must settle, concretely

Give numbers, definitions, file names and column names. Mark every assumption `assumed`.

1. **The question.** The central question, the hypotheses and the registered comparisons: primary vs secondary vs exploratory, selected on validation.
2. **Splits.** The train start per model family, validation, and the sealed test window with its availability cutoff. The seal-opening protocol: the config freeze, the read log, re-reads.
3. **Availability table.** For every input: event time, availability time at issue, and vintage. Cover EIA demand, fuel mix, interchange, EIA CO₂, the BA's own day-ahead forecast (DF), Open-Meteo Previous Runs and prices.
4. **The traffic report.**
   - Issue time and horizon.
   - Targets: demand, net load, a net-load stress proxy, carbon intensity.
   - Models, including the weather decision (option a, b or c from `grid.md`, with reasons), baselines and DF alignment.
   - Calibration, metrics, and dependence-aware inference.
5. **Carbon accounting.** EIA hourly CO₂ (production and consumption) as primary, fuel-mix CI as fallback, the marginal proxy as an exploratory sensitivity. Specify the wording rules.
6. **The workload.**
   - Acme Seren as primary and PAI 2020 for robustness.
   - Reconstruction rules, the week-block mapping aligned by local wall clock, seeds, scale and the GPU capacity cap.
   - The energy boundary: 0.7 kWh per GPU-hour, swept 0.4–2.0.
   - Flexibility per job class: deferrable, allowed wait, interruptible with restart cost, movable.
7. **Policies.**
   - Run now; the calendar rule; the scheduler fed a seasonal profile; the scheduler fed our forecast; certified perfect hindsight.
   - What each policy knows (no future arrivals) and the end-of-horizon rule.
   - Move vs wait across PACE and 3–5 neighbours, with destination capacity and migration rules so that "always go to BPAT" is not trivial.
   - The solver, its runtime budget and fallback.
8. **The objective.** Emissions first, with deadlines and identical completed work as constraints. Tie-break rules. Stress and wholesale cost are reported, never optimized.
9. **Accounting and statistics.** A common cohort, warm-up and drain, backlog, energy reconciliation, a paired block bootstrap over common weeks, and trace-seed uncertainty.
10. **Secondary insight.** "Clean hours ≠ rush hours": how it is measured across BAs.
11. **Results contract.** The artifacts and fields the offline dashboard reads, an evidence label on every field, lineage, and the scenario catalog.
12. **Story beats.** A 4–5 minute core, the branches, and what disappears if a Should is cut.
13. **Limitations** and their honest wording.
14. **Cut order** if time runs short.
15. **Open questions** for the owner, as a short list at the end.
