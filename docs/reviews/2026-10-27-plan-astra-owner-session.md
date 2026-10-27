# Strategy review: Astra, from the owner's own Codex session (pasted by the owner, 2026-10-27 ~16:25 MT)

The text was relayed by the owner. It is reproduced as received, then reconciled with the lead's Astra run (`2026-10-27-plan-astra-r1-astra.md`).

## Summary of its recommendations
- Keep the core. Sharpen it around the question: "Which flexibility is actually worth having: waiting, moving the workload, or shifting its electricity supply?"
- **Interactive mobility toggle.** "Large jobs must stay in Utah" changes the map, and the benefit falls from about 22.5% to 3–4%. A destination-capacity toggle uses the already-computed scenarios.
- **Flexibility-budget view.** Show the work that can move, can wait, must stay, or is blocked by capacity, sized by energy rather than job count.
- **Storage with strict accounting.** Not an automatic upper bound: call it a hindsight heuristic, or solve and certify. Enforce losses, power limits, continuous SOC, and matching start and end energy. It must earn its benefit after losses.
- **Demo sequence:**
  1. one long-running Utah job;
  2. stay, wait or move;
  3. the aggregate, and that a simple policy performs well;
  4. lock large jobs to Utah;
  5. storage for the remaining load, then the evidence.

  Move tables, abbreviations and long prose into the evidence view.
- **First outside-the-box choice:** a Utah site-power curve (when routing or storage reduces grid draw, and whether charging creates a new peak).
- **Defer** water, health and temperature-dependent cooling. Curtailment source continuity is uncertain: CAISO's old daily reports stopped in June 2025.
- Settle the sequence and rehearse tonight; final numbers come after the test and the audit. Protect the Wed 13:00 experiment freeze and the 14:00 presentation lock.

## Reconciliation with the lead's Astra run
- **Both runs agree** on the direction, storage strictness, peak relief / the site-power curve as the first extra, demo density, and drafting the pitch tonight.
- **New in this run:** the mobility/capacity toggle and the flexibility-budget view (adopted as T15, D-064).
- **Disagreement:** water. This run defers it; the lead's run ranked it below peak relief. The owner chose to build it anyway (D-064), with the stated caveats.
