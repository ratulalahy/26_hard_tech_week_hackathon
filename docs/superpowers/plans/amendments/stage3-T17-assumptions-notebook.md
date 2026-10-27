# Stage 3 · T17: "Assumptions vs reality, and what didn't work" notebook (owner, D-068)

Branch `s3/t17` from main. The notebook merges **before the freeze** if it is ready by about 20:30 MT; otherwise it merges after T13. It reads only committed `results/*.json` and docs. **No new simulation and no grid-data reads.** The F8 guard now scans `notebooks/` and must stay green.

## Deliverable
`notebooks/40_assumptions_and_reality.ipynb`, executed with outputs, with an HTML copy in `docs/evidence/` via `make notebooks`, following the house style of notebooks 01–05. It ends with "Decisions this supports" and the D-IDs.

## Sections
1. **Assumptions register.** A table built from `results/manifest.json` (claim frame, assumed values, limitations) and spec §7. Each row:
   - the assumption and our value;
   - where it is used;
   - evidence class;
   - how reality differs, in one plain sentence;
   - tested? If yes: which scenario, and the result read from `extensions.json` or `storage.json`. If no: why, with the D-ID.

   At least these rows:
   - flexible-job share and mobility of all flexible jobs;
   - 512 destination slots;
   - 30 min / 5% transfer;
   - 0.6 kW/GPU;
   - PUE 1.2;
   - advance bookings;
   - exact runtimes;
   - workload replay mapped to Utah;
   - consumption-basis attributed emissions;
   - the US-average 356 g/kWh colour midpoint;
   - storage η 0.85 and the connection limit;
   - the rush threshold.
2. **Negative and null results**, stated plainly, with numbers read from the results files (never typed):
   - waiting in Utah (W_time / L_time);
   - G at 0%;
   - H2 inconclusive (W − L);
   - H3 not supported (K worse than S; W and L not distinguishable from S);
   - the mobility ≤ 8 GPUs scenario;
   - dest-capacity 0;
   - storage on the flat-marginal threshold scenario (adds CO₂);
   - peak relief scale (MW vs Utah's peak);
   - production basis flattering hydro;
   - the illustrative-job literal rule picking a 3-minute job.
3. **"Would better (weather-aware) forecasts help?" Quantified with what we have:**
   - H, the hindsight router with perfect knowledge of actual carbon, against S, the fixed ranking, and against W and L: savings and intervals from `metrics.json`;
   - plus the share of flexible energy inside forecast coverage (`coverage_stratum`).

   **Conclusion, phrased honestly:** in this setup even perfect carbon foresight does not beat a fixed ranking, so weather-informed forecasts are unlikely to change the routing result. They may matter for peak-stress forecasting, which we did not evaluate.
4. **Not done, and why:** a table of the D-058 cuts, weather forecasts, foundation models (R4a / F12.9), shadow-U, runtime overrun and the missingness-blind sensitivity, each with its reason and decision ID.
5. **Reality-check questions** a judge might ask, each with the cell that answers it.

## Rules
- No banned words ("proves", "confirms", "avoided" outside "not avoided").
- Every number is read from the JSON files, with its evidence label shown.
- Keep it short and readable, about 15 cells.

## Report
Write `/tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/s3-t17-report.md`.

## Addendum (owner: every new component needs its visualization)
- **Export.** Also export the register and the negative results as `results/assumptions.json`. Every number comes from the existing results files, with its evidence label kept. Add the file to the envelope and sealed-date tests and to `copy-data`.
- **Dashboard.** Add a compact **"Assumptions & what didn't work"** section to the Method drawer with:
  - the register, as one row per assumption: value, how reality differs, tested? and the result;
  - the negative-results list;
  - the weather point (H ≈ S).

  Follow the tokens.md style, plain language, evidence chips, axe 0 and the offline test.
- Because this touches `web/`, the dashboard part merges **after T13**. The notebook itself may merge before the freeze, if it is ready.
