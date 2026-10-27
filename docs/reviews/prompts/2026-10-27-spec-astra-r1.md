Soundness gate for the reconciled experiment spec: `docs/superpowers/specs/2026-10-27-gridpilot-design.md`.

Context:
- Binding owner decisions: `docs/brief.md`.
- Rules: `AGENTS.md`.
- The data facts the spec must respect: `docs/data-profile/grid.md`, `workloads-prices.md`, `geo.md`, and the notebooks in `notebooks/`.
- The two independent proposals it reconciles are in `docs/superpowers/specs/` (`-codex.md` and `-claude.md`). §14 lists the amendments. §15 holds binding gate fixes F1–F11, which override earlier text. F1–F10 came from a fresh-context Claude gate (`docs/reviews/2026-10-27-spec-gate-r1-claude.md`); F11 is a ruling made during implementation.
- Time left: it is Tue 2026-10-27, about 02:00 MT. A checkable build with real validation results is due Tue 18:00; experiments freeze Wed 13:00.

Judge it as the skeptical energy-and-ML judge would, then as the engineer who must build it by 18:00. Answer each lens with findings, or with "nothing found":
1. **Information leakage and availability:** publication envelopes, fitted transforms, the as-of feature reconstruction, the hindsight and lower-bound definitions, and the seal-opening protocol.
2. **Comparator fairness and the H1–H4 logic:** the U/G/S/K/W/L/H policies, the time-only and place-only restrictions, and whether H2 really isolates forecast value.
3. **Work accounting and feasibility:** whether gang jobs, the replay cycle, capacity, warm-up and drain, the arrival cutoff, and runtime overrun can be implemented as written, and whether any rule makes the primary cohort trivially infeasible.
4. **Statistics:** block bootstrap, phase offsets, uncertainty claims, and the paired contrasts.
5. **Carbon accounting and claim wording:** consumption vs production, the marginal proxy, and the headline templates.
6. **The amendments R1–R6:** do they fit the base text, and do they create contradictions?
7. **Buildability by Tue 18:00:** which requirements should be explicitly deferred so that the core is real and honest in time? Name them.
8. **F11 (baseline bookings as fallback):** is it sound? Is the disclosed advance-calendar assumption acceptable? Does it bias any H1–H4 contrast, or make savings trivially small? Give a better causal alternative if there is one.
9. Anything else that would embarrass us in front of judges.
