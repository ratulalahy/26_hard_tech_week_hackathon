# Spec soundness gate, round 1: fresh-context Claude reviewer

- **Target:** `docs/superpowers/specs/2026-10-27-gridpilot-design.md` @ `b738df1`.
- **Prompt:** `docs/reviews/prompts/2026-10-27-spec-astra-r1.md`.
- **Reviewer:** a fresh-context Claude subagent, read-only. Astra was unavailable because the Codex workspace was out of credits.
- **Verdict:** `not_ready`.
- **Evidence the reviewer computed itself** (pre-seal or trace-only):
  - Seren R_max is 336 h.
  - Jobs over 512 GPUs carry 30.3% of GPU-hours.
  - The submit-time replay peaks at 3,082 busy GPUs against 2,288 slots, with 31 overload episodes per cycle. It still overloads at 1.25×.
  - Missing consumed-intensity hours: CISO 120 (validation), NEVP 4, BPAT 93 (training), PACE 0.

## Findings and dispositions

All fixes are in spec §15 (F1–F10) and the inline text fixes in `docs/superpowers/specs/2026-10-27-gridpilot-design.md`.

### Critical

| ID | Finding | Disposition |
|---|---|---|
| L3-1 | U, and likely every policy, is infeasible | Fixed: F1, deadlines relative to U |
| L7-1 | The full spec can't be built by 18:00 | Fixed: F9 minimal core and cut list |

### Major

| ID | Finding | Disposition |
|---|---|---|
| L1-1 | Validation window and drain are undefined | Fixed: F2 |
| L1-2 | The foundation model could leak the test window | Fixed: F8 |
| L2-1 | H2 is diluted by the forecast horizon | Fixed: F4, coverage stratum |
| L2-5 | No fallback when no policy is feasible | Fixed: F1 |
| L3-2 | Missing truth fails the total | Fixed: F3, site mask |
| L3-3 | The overrun stress is trivially infeasible | Deferred and redefined: F9 |
| L4-1 | Bootstrap concentration | Fixed: F6 |
| L5-1 | R1 used non-comparable numbers | Fixed: R1 rewritten |
| L6-2 | The NEVP fallback conflicted with D-029 | Fixed: fallback removed |
| L8-1 | U shown as "infeasible" in the story | Fixed: F1 |

### Minor

| ID | Disposition |
|---|---|
| L1-3, L3-8, L5-2 to L5-5, L6-3, L8-2, L8-3 | Fixed: F7 |
| L1-4, L2-3, L2-4 | Fixed: F5 |
| L1-5, L1-6 | Fixed: F8 |
| L2-2, L4-2, L4-3 | Fixed: F4 |
| L3-4 | Fixed: F2 |
| L3-5, L3-7, L4-4, L8-4 | Fixed: F6 |
| L3-6 | Fixed: F10 |
| L6-1, L6-5 | Fixed inline: four core sites; R6 sentence |
| L6-4 | Fixed: superseding entries D-044 to D-046 in `docs/decisions.md`; plan v2 amended |
| L6-6 | Fixed: F9 hard stop at 21:00 |
| L8-5 | Accepted: the scale answer is prepared for Q&A; the primary result stays unscaled |

**Re-check:** this round goes to the Astra gate, pre-approved budget run #1, at high effort after 03:14 MT.
