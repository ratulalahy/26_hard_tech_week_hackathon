# Stage 2 final whole-branch review: fresh Claude (Opus)

- **Range:** b345866..e7b70cc (`checkpoint-tue`).
- **Verdict:** not_ready, for the freeze and the test. The validation core is sound.

## Sound
- No leakage path from sealed data into fits, decisions, artifacts or the UI.
- Transfer pricing is identical in all 4 places.
- Interval semantics are consistent.
- Results copies are byte-identical.
- Deterministic across two runs.

## Findings and dispositions

The full report text is in the session record. Every finding is summarised here with its disposition.

### (A) Before the freeze
| ID | Finding | Disposition |
|---|---|---|
| A1 | Registered run evidence only in a gitignored worktree | Fixed (D-057) |
| A2 | No independent clean rebuild, and no `make data` | Stage 3 T12 |
| A3 | No freeze record or deployed-policy selection | Stage 3 T12 |
| A4 | Wrong deadline text | Fixed (T9) |
| A5 | Headline missing the simulated frame and qualifiers | Fixed (T9) |
| A6 | No development-evidence limitation | Fixed (T9) |
| A7 | `observed` alias keys | Fixed (T9) |
| A8 | Carbon sidecar evidence label | Fixed (T9) |
| A9 | Two top-1% definitions | Fixed (T9) |
| A10 | Planner transfer pricing | Fixed (T9) |
| A11 | Headline wording "modeled" | Fixed (T9) |
| A12 | Bound text | Fixed (T9) |
| A13 | `not_run` disposition | Fixed (T9, T10) |
| A14 | Duplicated constants | Fixed (T9) |
| A15 | Untracked amendment | Fixed (D-057 PR) |
| A16 | No web/results byte test | Fixed (T9) |
| A17 | `make profile` docs | Fixed (T9) |

### (B) Before the test
| ID | Finding | Disposition |
|---|---|---|
| B1 | No test entry point or read log | Stage 3 T11 |
| B2 | Window switch through layers | Stage 3 T11 |
| B3 | No F8 guard test | Stage 3 T11 |
| B4 | Test F not frozen | Stage 3 T12 |
| B5 | Test S ranking and fit windows | Stage 3 T12, plus F05 envelope |
| B6 | Test namespace and UI | Stage 3 T11 |
| B7 | Provenance enforcement | Stage 3 T11 |

### (C) Can wait
| ID | Finding | Disposition |
|---|---|---|
| C1 | Simulate tests within one chunk | Deferred (low risk; full-year peak recheck is 0) |
| C2 | Empty blocks raise | Deferred |
| C3 | Two-replace window | Deferred |
| C4 | Framing double negative | Fixed (T9) |
| C5 | Evidence dicts | Fixed (T9) |
| C6 | Hard-coded UI duration | Fixed (T9) |
| C7 | Error chip | Fixed (T9) |
| C8 | Load month | Fixed (T9) |
| C9 | Monolithic `run_slice` | Partly addressed by the T10 refactor |
| C10 | `build_carbon` parses sealed rows in memory | Noted, compliant |
