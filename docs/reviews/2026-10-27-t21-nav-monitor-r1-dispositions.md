# T21 review r1 (PR #101): dispositions

The review is `.superpowers/sdd/2026-10-27-stage3-freeze-test/t21-review.md` (independent Claude reviewer). It found 0 critical, 2 major and 8 minor findings; verdict not_ready. Each disposition below links to the fix-round commit on `s3/t21-nav`, rebased on origin/main after #94, #99 and #100.

| Finding | Disposition |
|---|---|
| **M1**: hour-mean load changes were presented as placements | **Fixed.** The panel is renamed "Load changes at the destinations". A visible line reads "Hour means of busy GPUs, not individual jobs". Consecutive same-direction changes merge into one ramp, and hourly changes under 8 GPUs (one node) are dropped; the threshold is stated on the page. Lines say "moved work running" or "moved work finishing". The S rule sentence appears once, above the list. The two traced jobs remain the only per-job entries. Tested in `nav.spec`: one line per ramp, and no "placed by S", "S rule" or "decision" in any line. |
| **M2**: the Utah-site week totals were misleading | **Fixed.** The line is removed. The rate panel now says the gap between the lines is not the saving. |
| **Lead**: the replay week is a quiet week | **Fixed.** A visible line in "The week, all sites" reads: 1.2% this week against 22.3% over the test year, and the top 1% of jobs (8,883) carry 95% of the energy. Both figures come from `metrics.json` (`contrasts` S vs U, b = 4; `workload.top_1pct_jobs_by_declared_gpu_h`). Tested. |
| **m1**: GPUs and jobs sat side by side in the PACE lane | **Fixed.** The lane reads "1,019 jobs of the week's 1,058 arrivals stayed in Utah". |
| **m2**: the S rule repeated in every line | **Fixed.** See M1. The traced jobs say "first feasible site in the frozen ranking" without repeating the numbers. |
| **m3**: the Monitor overflowed the fold at 1440 | **Fixed.** The header is shorter, "The week" moved to the right column, and the lanes and rate chart are shorter. At 1440×900 the lanes, the rate chart and the feed are all on one screen (`t21-monitor-playing-1440.png`). |
| **m4**: "Story" appeared twice in the bar | **Fixed.** The view tab is now "Walkthrough"; its hash is still `#story`, so every deep link is unchanged. |
| **m5**: `?year=` stayed sticky | **Fixed.** `?year=` is applied, remembered, then removed from the URL with `history.replaceState`, so a later switch wins on reload. Tested. |
| **m6**: phone layout | **Story fixed.** Below 800 px the beat charts are hidden behind a note ("laid out for a laptop screen"), and the beats keep the story; tested at 390, with no horizontal scroll. **Control room, cockpit and ribbon: deferred.** Their desktop layouts at 390 predate T21; the demo runs at 1440+. |
| **m7**: a11y checks were not gated | **Fixed.** `npm test` now includes `tests/a11y.spec.ts`. |
| **m8**: `npm test` needed a prior build | **Fixed.** `npm test` runs `npm run build` first. |
| **Lead**: the deck asked for a manual year switch | **Fixed.** The deck's dashboard buttons open `http://127.0.0.1:4173/?year=test#…`; `deck.spec` checks the new target. The "set the dashboard to Test year once" notes are removed, and `docs/pitch/narrative.md` setup uses `?year=test`. |
