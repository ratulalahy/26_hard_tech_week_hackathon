# Task 8 fix round 2 (from the re-check of 859b65e; every number traced correctly)

Work on `s2/task-8`. First rebase onto `origin/main`, which now includes D-054–D-056 and housekeeping. Fix the items below, re-run axe and the offline test, re-shoot only the changed views, and push. Append "Fix round 2" to the report.

## Blockers
- **N1 (Story 3 copy).** Use exactly: "It was picked by a rule fixed before seeing its outcome: the GPU-hour-weighted median of the eligible flexible jobs. The registered count-median job runs only 3 minutes; see how this job was chosen." No "registered in advance" for the v2 criterion.
- **N2 (Story 4 title).** Compute it from `metrics.policies.W.metrics.execution_kwh_by_site`, scoped to the year, e.g. "Over the year, {p}% of the moved energy went to the Northwest". Add a note that in the replay week California took more GPU-hours. No hard-coded share.
- **N3 / #20 (1440 right dock).** "Where the work went", with its destination rows, must be fully visible at 1440×900. In compact heights, drop the prose or the key, or give the section a minimum height of about 140 px.

## Also fix
- **N4.** At 1440 the Story 5 table shows every row: the panel scrolls, or rows tighten below 1000 px of height.
- **#14 (remaining whitespace in Story steps 3, 5 and 6).** Fill or shrink the panels to their content. Anchor the cards to the top.
- **#19 (residues).**
  - Region cards must not leave label fragments. Hide any city or state label a card overlaps, or keep the cards clear of label anchors.
  - Remove the declutter slack, so no label is partly under a dock.
  - Fix the IPCO/Boise collision.
  - At 1440, keep "San Diego" and the arc label clear of the caption.
- **N5.** Wait mode with no gain reads "Runs in Utah at 7 PM; waiting does not help".
- **N6.** Add a Starts column (Denver time) to the Story 3 placements table, so the delay before moving is visible.
- **N7.** Add a caption to the Story 4 inset: "Regions: typical July day, 7 PM · Arcs: replay week Nov 4–10, 2024".
- **N8.** Keep the CISO callout inside the cockpit inset at both widths.
- **N9.** Hover titles use plain-language role strings, not raw notes.
- **N10.** The rush shading covers the full 7 PM–10 PM band (offset by half a category).
- **N11.** "0.06 GPU-hours".
- **N12.** Derive the "June–September evenings" phrase from `counts_month_hour`.
- **N13.** Add the adjusted-demand envelope sentence to limitation 1's plain version.
- **N14.** Close the left-dock gap at 1440; make the Nevada strip visible at 1728.
- **N15.** Let the forecast y-axis fit the data range, not start at 0, since it is a line chart. Label the axis.
