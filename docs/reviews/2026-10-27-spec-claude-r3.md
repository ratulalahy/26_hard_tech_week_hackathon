# Spec re-check r3: fresh-context Claude (Opus), standing in for the Codex gate re-check

- **Reviewed:** main @ 41b2e30, read-only. The reviewer read no grid data.
- **Substitution:** the owner's 3-run Codex budget leaves only the Wed results audit, so this re-check is a Claude substitution (`.claude/skills/codex-gates`).
- **Verdict:** `ready_with_minor_fixes`.
- **Overall:** "No design-level defect remains. The bound, the booking invariant, the prefix cohort and the claim frame are sound under the accepted advance-reservation scenario. What remains is exact one-line rules."

## Ratings of the Sol r2 dispositions

- **Adequate:** R1, R3 (for U), R4, R5, R7, R8 and R9.
- **Partial:** R2 (N1, N2, N9), R6 (N4), R10 (N12), R11 and R12 (N13), and the booking-support note (N6).

## Findings and dispositions

The fixes landed in spec F14 (commit: this PR).

| ID | Sev | Finding | Disposition |
|---|---|---|---|
| N1 | major | "Registered scenarios that need a common cohort" was undefined. | Fixed: F14.1 lists the U-changing sensitivities. |
| N2 | major | What U is (FIFO, insertion or EASY) was unspecified, and so was whether it is causal. | Fixed: F14.2 makes U reservation insertion (causal). |
| N3 | major | Which population the H2 decision rule applies to was ambiguous. | Fixed: F14.3 applies it to the full phase-0 cohort; the stratum is secondary. |
| N4 | minor | The fallback's initialisation and eval_start were not fixed. | Fixed: F14.4. |
| N5 | minor | The simultaneous-arrival order for non-U policies was unstated. | Fixed: F14.2. |
| N6 | major | The procedure after an accounting-support failure was undefined. | Fixed differently: F14.6 pre-registers a four-tier truth fill. A completeness check found a shared roughly 50 h gap at all sites in the sealed window, so the reviewer's "zero home capacity" would make long jobs unplaceable. |
| N7 | minor | The blocked counterfactual's candidate sets are not nested, so blocks can be counted spuriously. | Fixed: F14.7 uses the union of candidates and an improvement threshold. |
| N8 | minor | The F13 header's override scope was too narrow, and F9 still pointed to the F2 drain. | Fixed: the header is broadened and F9 points to F13.2/F14.4. |
| N9 | minor | The horizon, the meaning of F and the warm-up length were not fixed. | Fixed: F14.4. |
| N10 | minor | Half-open semantics, the transfer hour and the bound tolerance were unstated. | Fixed: F14.5. |
| N11 | minor | The RNG call, the zero-reference replicate and a fixture were not specified. | Fixed: F14.8. |
| N12 | minor | Obsolete inline plan text remained, and the amendment files were not in git. | Fixed: the plan's amendments list the obsolete text, and the files are committed under `docs/superpowers/plans/amendments/`. |
| N13 | minor | D-049 wording and counts, and the Sol rows had no commit. | Fixed: D-049 is edited, and the Sol rows cite 41b2e30. |
| N14 | minor | The benchmark pointer referenced a mutable branch, and validation-outcome status was unstated. | Fixed: the F12 intro cites 8f438aa and states that no policy result existed. |
| N15 | minor | When the blocked diagnostic is due was unstated. | Fixed: F14.7, after 18:00 and before freeze. |

**Gate:** passed (`ready_with_minor_fixes`, every finding dispositioned). Reviewed SHA 41b2e30; the fixes are in F14.
