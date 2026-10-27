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
