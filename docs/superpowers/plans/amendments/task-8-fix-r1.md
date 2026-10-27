# Task 8 fix round 1 (lead rulings on the independent critique; every finding gets fixed)

Work on s2/task-8. **Task 7 is in its own fix round.** When the lead tells you its new commits are on `origin/s2/task-7`, merge them again and re-run `copy-data` plus `make profile`. Schema changes are coming: `illustrative_job` (criterion v2), `illustrative_job_literal`, `h2.status`, new limitations, and evidence-label changes. Fix everything below; ruling text is verbatim where given.

## Rulings
- **R1. Policy names (critical #1, #2, #29).**
  - **The names:**
    - U: "U local (stay in Utah)"
    - G: "G earliest-finish (carbon-blind)"
    - S: "S static clean-region ranking"
    - K: "K climatology (seasonal average)"
    - W: "W weekly profile"
    - L: "L learned model"
    - H: "H hindsight (diagnostic)"
    - time-only rows: "W wait-only" and "L wait-only"
  - Read the roles from `metrics.policies[p].note`, so names cannot drift.
  - Put a one-line key in the Control room right dock.
  - Use one name per policy everywhere.
- **R2. Map context regions (#5).** Neutralise them: a flat sand fill with names and borders, and the modeled value in the tooltip only. Only the four core regions carry the carbon scale.
- **R3. Evidence class of EIA consumption-basis CI (#10).** **modeled**, per spec §4, §11 and F7, which are the majority and binding. Render it as "modeled · EIA estimate" everywhere: the map, strips, ribbon and the grid-profile export. Demand, net load and solar stay **observed**. The lead is telling Task 7 to make the same change in its exports.
- **R4. Midpoint (#11).**
  - `CI_MID = 356` g/kWh: EIA, *United States Electricity Profile 2024*, 785 lb CO₂/MWh × 0.453592 = 356 g/kWh. It is a national generation-basis annual average, used as a reference midpoint.
  - Export it as an envelope in `grid-profile.json`: evidence `observed`; provenance "EIA United States Electricity Profile 2024, https://www.eia.gov/electricity/state/unitedstates/".
  - Read it from there. The legend reads "356 · US avg 2024 (EIA)".
  - Update `docs/design/tokens.md` to match.
- **R5. Illustrative cockpit (#8).**
  - Apply the manifest's `transfer_time_s` and `transfer_energy_fraction` in `makePlan`.
  - Put "illustrative" in the hero line.
  - Promote the registered strip to 15/600, with the range.
- **R6. F7 headline sub-line (#9).** "Attributed operational CO₂ (EIA consumption basis, modeled), including {X} MWh of simulated transfer energy." X is read from metrics.
- **R7. Plain-language limitations (#12).**
  - Story 6 and the drawer body use plain-language versions. Write them, and keep them faithful.
  - The verbatim manifest text goes behind a "Source text" disclosure.
  - No internal codes (§, F-numbers, `ts_utc`) in visible copy outside that disclosure.
- **R8. Story order (#13).** Six steps, about 45 s each:
  1. the rush (load chart, with the heatmap as a sub-beat);
  2. tomorrow's report (forecasts, K included);
  3. one job: stay, wait or move;
  4. place the work: the map with W's arcs and "where the work went";
  5. the count: 22.4–22.6% vs 0.7%, then "forecast choice barely matters; placement dominates";
  6. challenge it.
- **R9. Story 5 claim (#3).** Use exactly: "Most jobs are tiny, but most of the energy, and most of the saving, sits in a few large jobs." Back it with a number from the data, such as the energy share of the top 1% of jobs. Add that number to an export if needed.
- **R10. Forecast chart (#4, #27).** Draw K too. The title gives the true range across all three models. Add a ±MAE band around L.

## Fix every other finding as the critique proposes
- #6: arc overlap and NEVP end labels; drop arcs under 1% of GPU-h.
- #7: an arc time-frame caption.
- #14: density and whitespace in Story steps 4–6.
- #15: cap the patience chart at about 180 px.
- #16: label solar; draw the cleanest band as a bracket.
- #17: heatmap legend and month labels.
- #18: no "avoided".
- #19: callout collisions, leader lines, hide callouts under docks, clip the map above the footer.
- #20: 1440 dock fit; keep a short footer with the time zone.
- #21: opaque drawer.
- #22: H open dashed dot; consistent names.
- #23: the "simulated" word; the "Start delay (transfer)" column; a compact table instead of a card grid.
- #24: "your limit" as a dashed ink line.
- #25: bar outlines.
- #26: axis-name collision.
- #28: a load y-scale.
- #30: "up to 6 h (1 h for eval jobs)".
- #31: read k; soften "coal".
- #32: ≤ 300 ms; no arcs in the watermark.
- #33: `engines` and a Node-version note in `web/README.md`. The Mac's Node version is unknown, so say "Node ≥ 22 recommended" and confirm the build works with `npm ci` on 22.
- #34: remove `motion` if unused; `#story-N` deep links; pause the watermark map's rendering.
- #35: interstates and more city labels from z 5.

## Finish
- Re-shoot all screenshots and re-run axe and the offline test.
- Append a "Fix round 1" section to /tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/task-8-report.md, with a disposition for every finding (#1–#35).
- **Screenshots in git:** keep only the 1728 set plus 2 at 1440, to cut repo weight. Delete the rest from the branch.
