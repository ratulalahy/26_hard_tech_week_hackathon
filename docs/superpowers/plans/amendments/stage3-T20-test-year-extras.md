# Stage 3 · T20: pre-registered test-year extras (D-071)

**Why.** The owner asked that the night not sit idle (2026-10-27, 16:55 MT). The extras so far are validation-only. This task pre-registers them on the sealed test year **before** the seal opens. They run in the same single logged opening (T13), or from that opening's own outputs. Everything here is written and frozen first, then executed, and every result is reported whatever it shows.

## Rules
- **The primary result is unchanged.** These are secondary and descriptive. None of them can replace the headline, the deployed policy (S), or any frozen decision field.
- **All code is in the frozen `lab/` tree.** That means: implemented, reviewed and merged before `make freeze`, then covered by the independent rebuild.
  - The validation path must stay byte-for-byte reproducible: canonical metrics hash e6ad2635…, and all 9 ledger hashes unchanged.
- **Every grid read on the test window goes through `gridpilot.seal.sealed_read`,** with a purpose string naming the D-071 item. There is no second opening: the extras run inside `run_slice --window test`, or in a post-step that this entry point invokes in the same session, under the same lock and witness.
- **Selection rules are fixed here,** not chosen after looking. Outputs go to `results/test/` with evidence labels, and say "test year, pre-registered secondary (D-071)".

## Items (each produces a section in `results/test/extras.json` or its own file)
1. **The extension scenarios on the test year.** These are the D-058 set: phases 49 and 98, destination slots 0 and 1,024, transfer 120 min, batch delay 24 h, and mobility ≤ 8 GPUs.
   - Use the frozen test forecasts, run in parallel.
   - Report CO₂ and saving vs U for U, S, W and L (or the policies the extension runner already uses), with the same interval method as the primary.
2. **Storage** (the D-061/D-067 method, unchanged):
   - Run the headline 4 MWh / 1 MW battery and the 8 MWh plateau on the test U ledger and on the test mobility ≤ 8 W ledger.
   - Use the same fixed training-year schedule and the same daily hindsight heuristic.
   - Report "move small + store", the flat-marginal skeptic line (618 g/kWh, labelled as the associational slope), and peak relief.
2b. **Peak-aimed storage schedule (added 18:40, before the opening; D-073).** The Q&A drill found that the fixed carbon schedule discharges at 21:00–02:00 and 06:00 local, missing 11 of the 12 net-load rush hours.
   - Add a second fixed schedule, derived from the **training year only**:
     - discharge in the 4 local hours that were most often among the day's top 4 net-load hours;
     - charge in the 4 hours that were most often the day's lowest net load.
   - Use the same battery, the same efficiency and the same site cap.
   - Run it on validation **and** the test year. Report rush-hour import, peak import, attributed CO₂ and the flat-marginal skeptic line, side by side with the carbon schedule.
   - It is reported as a design comparison, not a replacement for the carbon headline.
3. **Toughest days.** Apply the D-066 rule to the test window: the top 3 PACE days by daily max net load in [TEST_START, F).
   - Report U/S/W CO₂ by day, including transfer, with the execution, transfer and total checks.
   - Add the archived temperature context, labelled "Salt Lake City only".
4. **Water.** Apply the T14 method to the test ledgers, under both hydro-evaporation conventions. Make no water-saving claim, and report the sign under each convention.
5. **Seasonal split.** Report the saving of S and W vs U by meteorological season (DJF, MAM, JJA, SON) within [TEST_START, F), with block-bootstrap intervals where each season has at least 8 weeks. This is descriptive only.
6. **Forecast skill on the test year.** For each frozen forecast series:
   - MAE vs climatology, and vs EIA's day-ahead forecast where one exists;
   - the p10/p90 coverage of the frozen intervals.
   - **L permutation importance**: computed on validation and on the test year, per series, using the frozen L, scored on MAE and averaged over 5 fixed-seed shuffles (seed 20261027). Inputs are grouped as in the forecast module: calendar, weekly memory, most recent, recent level, missing-data flags. Report it whatever it shows.
7. **Validation → test drift table.** For every headline number and every item above, report validation, test, and the difference. No item is dropped for looking bad.

## Out of scope
- Any change to the primary scenario, the policies, the forecasts or F.
- The mobility/capacity toggle UI (T15) and the flexibility budget read whatever the test outputs provide after merge. That is UI work, not new reads.

## Done when
- The tests pass, including a test that the validation hashes are unchanged and a synthetic test-window run of every item.
- The F8 guard is green, with every new read allowlisted by purpose.
- The PR is reviewed and merged before the freeze. The T12 rebuild is then rerun on the final `lab/` tree.
