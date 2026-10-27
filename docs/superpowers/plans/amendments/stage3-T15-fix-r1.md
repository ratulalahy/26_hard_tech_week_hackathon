# Stage 3 · T15 fix round 1 (review: spec ✅; exports exact; fix honesty and layout)

Work on `s3/t15`. Fix everything below, regenerate the exports and **all** screenshots after the final commit, and run the tests, axe and the offline test. Push, and append "Fix round 1" to the report.

## Important
- **I1.** The remote line uses `remote_execution_share` (execution basis, about 30.9%), so remote + retimed = moved. State the basis.
- **I2.** `retimed_home` counts **flexible jobs only**. Report home-queue slips of rigid jobs separately, or exclude them. Fix `DEFINITIONS` to match.
- **I3.** Must-stay comes first in the precedence. `capacity_blocked` = blocked & flexible & mobile. Record the "blocked but must-stay" remainder so the `blocked_kwh` cross-check still closes. Must-stay must be identical across policies.
- **I4.** The budget heading reads "Flexibility budget (registered run)" at every size. When the toggle isn't on the registered scenario, add "the toggle does not change this bar".
- **I5.** Beat 4 reuses the no-change note for S in the wait-only state.
- **I6.** At compact width the toggle fits on one row with the caption inline. The BPAT callout must be visible at 1440.
- **I7.** Tests assert exact text, ruling out the span, e.g. `/(?<![–\d.])22\.6%/`, and assert that the span text is absent.

## Minor (all)
- **M1.** In the test window, beat 4 falls back to `own(m, arcPolicy)` with window copy, and the test-year spec gets a story-4 wording check.
- **M2.** Budget headline: "46% sits in jobs flagged movable ({x}% fit a remote site); 54% must stay in Utah", with x computed.
- **M3.** Fix the left-dock clip at 1728 so the Nevada row is visible.
- **M4.** Use short policy names in the select below 1600 px.
- **M5.** Remove the beat-3 repetition.
- **M6.** Print "≈0%" and "<0.1 MWh".
- **M7.** Keep the sign in beat 4.
- **M8.** Add `flags_evidence: assumed` per bucket.
- **M9.** The Day ribbon shows each policy's own interval, not the outer span.
- **M10.** The drawer workload table notes that it is in W's terms, or switches to S.
- **M11.** No change; mention it in the disposition.
- **M12.** Regenerate the screenshots.
- **M13.** Correct the report. `make flows` uses the registered run `runs/slice/20261027T160656Z`, whose ledgers exist.
- **M14.** Fail when an explicit `--ext-root` is missing.
- **M15.** Window-aware copy for storage in the test window.
- **M16.** Use `useId()`.
- **M17.** Make the fixture's `co2_kg` consistent.

**Do not merge.** It merges after T13.
