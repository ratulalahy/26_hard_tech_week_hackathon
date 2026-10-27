# Stage 3 · T14: water footprint illustration (D-063; validation only; merges AFTER the test run)

Branch `s3/t14-water` from main. **Do not merge before the test run.** The lead merges after T13. Illustrative and modeled. **The seal holds:** validation year only, pre-seal loaders only, and the F8 guard stays green.

## Sources (free; record each in `data/manifests/water.json` with URL, retrieval time, sha256 and licence)
- **NREL/TP-6A20-50900** (Macknick et al., *A Review of Operational Water Consumption and Withdrawal Factors for Electricity Generating Technologies*): https://docs.nlr.gov/docs/fy11osti/50900.pdf. Use the PDF only if the download succeeds. If it cannot be retrieved, stop and report; do not transcribe from memory.
  - Transcribe the **median operational water consumption** factors (gal/MWh) for the technology and cooling types you need, into `lab/src/gridpilot/data/water_factors.py`. Record the table number, page and units next to every value.
  - Write a test that pins the transcribed values.
- **LBNL 2024 US Data Center Energy Usage Report:** https://eta-publications.lbl.gov/publications/2024-lbnl-data-center-energy-usage-report. Take a stated range for direct data-center water use (WUE, L/kWh) with its citation. If no defensible range is stated, use a clearly `assumed` range and say so.

## Model
- **Generation-associated water intensity, per BA-hour:**
  - Σ_fuel (EIA-930 adjusted generation share × factor).
  - Fuel → technology mapping, documented and `assumed`: for example coal → recirculating-cooled steam; gas → combined cycle, recirculating; nuclear → recirculating; hydro → in-stream evaporation factor, **shown separately**; wind and solar PV → about 0.
  - Report the intensity **with and without hydro evaporation**, because the hydro allocation is uncertain and can dominate.
- **Policy water.** Apply to the registered ledgers (`runs/slice/20261027T173750Z`), using the same hourly energy as the carbon accounting, for U, S, W and L. Also add direct cooling water: IT kWh × the WUE range, shown separately.
- **Output:** gallons per year by policy, the change vs U, and the split by site.

## Caveats (verbatim in the export and the UI)
- "Consumption, not withdrawal."
- "Production-side fuel-mix weighting, not consumption-flow tracing."
- "Technology medians; plant-level cooling not modelled."
- "PACE is not the Great Salt Lake watershed; no claim of water returned to the lake."
- "Hydro evaporation allocation is uncertain; shown separately."

## Export and UI
- **Export:** `results/water.json`, enveloped. Factors are `observed (published)` or `assumed`; intensities and gallons are `modeled`; policy totals are `simulated`. `kind: "illustrative"`.
- **UI:** one compact panel in the Method drawer, plus one line in Story beat 6 or the Q&A view, e.g. "Moving work also shifts its water footprint: {Δ} gallons/year (illustrative)". No new story beat.
- Axe 0, offline pass, screenshots.

## Report
Write `/tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/s3-t14-report.md`.
