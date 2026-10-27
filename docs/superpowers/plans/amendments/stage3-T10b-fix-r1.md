# Stage 3 · T10b fix round 1 (storage review: all numbers verified; fix the presentation, the guard and the wording)

Work on `s3/t10b`. Re-export `storage.json`. Run the tests, axe and the offline test. Push. Append "Fix round 1" to the report.

## Required
1. **F8 guard compatibility.** Wrap both `truth_fill.parquet` reads as `drop_sealed(pl.read_parquet(...))`, with the reader as the direct first argument (`storage.py:377`, `:639`). Run T11's guard (`lab/tests/test_f8_guard.py` from `origin/s3/t11`) against your code until it is clean.
2. **AGENTS.md.** Replace "a daily hindsight bound" with "a daily hindsight heuristic (each day planned on its actual carbon)", and fix "about a minute" to the measured run time.
3. **Headline size (lead ruling).**
   - The headline is **4 MWh / 1 MW**: 3.5%.
   - State the binding limit in the sentence: charging is limited to the roughly 0.3–0.6 MW the site connection leaves free.
   - Keep 8 MWh as the plateau point in the curve.
   - Export daily throughput and full cycles per day for every size.
   - Add one sensitivity, the connection +25%, if it takes under 30 min; otherwise list it as not run.
   - Record the headline-size rule as illustrative.
4. **Beat 6 is about 80–100 words**, in this order: caveat → headline (4 MWh, 3.5%) → combined (move small + store) → **one bold skeptic line**. Move the break-even arithmetic, the B number, the schedule hours and the relief details into captions or the drawer. Keep at most two visuals: the curve and one of the import chart or the day strip. Move the relief table to the drawer.
5. **Make the skeptic result prominent.**
   - Add a third curve series, "flat marginal 618 g/kWh (threshold scenario)", which goes below zero.
   - Add the bold line: "On a flat marginal basis it may add about {X} t: storage only helps if charging carbon ÷ η < displaced carbon."
6. **Consistent flat scenario.** Use −(charged − shifted) × 618, which includes terminal energy. Export it for both strategies, all three η values, and the combined case.

## Also fix
- **#7.** "On our rough reference the charging hours are no cleaner on the margin (551 vs 550 g/kWh)."
- **#8.** "Over the validation window (Nov 2024–Oct 2025)."
- **#9.** Export the 95th and 98th percentile rush thresholds and their relief. Add "(12 hours on 9 days)" in the drawer.
- **#10.** Add scale: "one 2,288-GPU cluster; Utah's peak net load is about 8,200 MW".
- **#11.** Phrase B positively: "sees each day's actual carbon in advance; one possible plan, not a limit". Separate it visually from the router's relaxed-bound section.
- **#12.** Give the illustrative chip a neutral style, with no `data-ev`.
- **#13.** `e_mwh` is a selection rule: label it simulated and document the rule. Label the counts consistently as measured.
- **#14.** Disclose the end-of-window drain in the drawer.
- **#15.** Covered by item 6.
- **#16.** Covered by D-067 (the lead records it).
- **#17.** Make the AST test match `truth_fill` and `read_parquet`, or defer to T11's guard. Keep one.
- **#18.** Confirm that `copy-data` and the board pick up `manifest.storage`. T12 will enumerate `results/*.json`.
- **#19.** Add one drawer clause: "standby losses would reduce this, most at low utilisation".
