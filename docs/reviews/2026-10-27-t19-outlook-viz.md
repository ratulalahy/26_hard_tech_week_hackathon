# T19 outlook page: viz-critique self-pass (Claude, 2026-10-27)

Scope: `web/src/pages/Outlook.tsx` at `#outlook`, reading the validation-dated demo `results/outlook.json` (issue 2025-06-15 10:00 MDT). Shots: `docs/design/shots-build/outlook-1440.png`, `outlook-1728.png`. axe (WCAG 2.2 AA, `tests/a11y.spec.ts` "axe outlook"): 0 violations. Offline check (`tests/outlook.spec.ts`): no non-localhost request, no page error. The Codex image critique was not run (needs the owner's OK).

| view | rubric item | severity | evidence | disposition |
|---|---|---|---|---|
| outlook | Labels: a demo must say so | critical | first build had no demo marker | fixed: a "DEMO · validation date" banner names the issue date and says the live run replaces it |
| outlook | Layout at 1440 | major | an "Outlook" tab widened the nav into the window switch (first 1440 shot) | fixed: no tab; the page mounts at `#outlook` and T21's nav owns the link |
| outlook | Honest charts: axes | major | y labels "900" and "800" overlapped and collided with region names | fixed: shared y max rounded to 300, one interval per panel, wider label gutter |
| outlook | Insight first | major | title hard-coded "Utah is cleanest around midday" | fixed: the span is the most common start of Utah's cleanest 4 h block, from the data |
| outlook | Day cards wrapped at 1440 | minor | "move to Northwest hydro" wrapped on two lines | fixed: shorter card copy |
| outlook | Colour | minor | regions need identity without a categorical palette (tokens have none) | by design: small multiples on one shared y scale, the panel names the region; swatches use the carbon scale for magnitude only |
| outlook | Uncertainty | — | p10–p90 bands on every hour; skill table with its rule and out-of-fold coverage (78–80%, target 80%) | ok |
| outlook | Climatology days | minor | D+6/D+7 Utah fall back to the seasonal average | shown hatched on cards and table, shaded on the chart and named in the legend line |
| outlook | Bands barely widen with horizon | minor | validation residual quantiles change little from D+1 to D+7 (MAE grows ~1 g/kWh for Utah) | kept: this is the measured result, not a styling choice |

## Fix round r1 (review: `.superpowers/sdd/2026-10-27-stage3-freeze-test/t19-review.md`, not_ready)

| finding | disposition |
|---|---|
| M1 iid issue bootstrap | fixed (a475377): circular block bootstrap over consecutive daily issues; 7-day blocks decide, 14-day reported; 2,000 reps, seed 20261027 (`eval.bootstrap.block_indices`). The rule is unchanged. Every Utah day now fails (D+1 [−1.9, 10.5]%) and every destination day passes. The page copy comes from the data: "Utah's forecast is not reliably better than its seasonal average…". Cards show the point estimate only as "+4% vs avg, not distinguishable" |
| M2 dirty-tree export | fixed: `make outlook` at a475377 with a clean tree (`lineage.git_sha` a475377, `git_clean` true), then `make web`. The committed-outlook test asserts `git_clean` |
| m1 F8 guard blind to callbacks | partly fixed: `test_only_the_outlook_cli_uses_live_read` now counts any reference (call, callback, alias import, string). The F8 guard is unchanged: its allowlist is at the cap, and registering `live_read` there is the lead's call |
| m2 any path | fixed: `live_read` reads only `runs/outlook/<run id>/raw/<file>`. The dead `sealed_read` branch is removed |
| m3 weak opening check | fixed: needs the test manifest, a non-empty `results/test_reads.jsonl` and the local `config-freeze` tag |
| m4 live refit vs validation fit | fixed: a live limitation line |
| m5 demo in-sample | fixed: the demo issue is 2024-10-31, before the first skill issue; the overlap of its target days is disclosed |
| m6 staleness | fixed: `check_fresh` refuses a site whose newest row is older than 7 days before the issue |
| m7 live validator | fixed: the full `validate_artifact` except the sealed-timestamp check |
| m8 unlabelled numbers | fixed: the browser-side region mean is gone; each day card has an evidence chip |
| m9 year switch | fixed: hidden on `#outlook` |
| m10 shared scale | fixed: Utah has its own y scale and the destinations share one (stated on the page) |
| m11 dead code | fixed: `OutlookCard` removed; skill issues are sorted before the seal check |
| m12 raw-data rule | fixed: the AGENTS.md `make outlook` entry says downloads stay in the run directory |
| (new) axe scrollable region | fixed: the taller page scrolls, so the section is focusable (`tabIndex=0`); axe reports 0 violations |
