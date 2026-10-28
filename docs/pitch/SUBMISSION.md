# GridPilot: compute follows cleaner power

**Hard Tech Week 2026 · Torus bounty "Energy × AI Infrastructure"**, Option 2 (Compute Follows the Sun), with Option 1 (Rush Hour for Electrons) as its engine. Built by a solo developer working with AI agents.

## Links
- **Live dashboard:** https://gridpilot-htw.vercel.app/?year=test (opens on the sealed test year)
- **Pitch deck (web):** https://gridpilot-htw.vercel.app/deck/
- **Deck files:** GridPilot-deck.pptx / GridPilot-deck.pdf (in this folder)
- **Code:** https://github.com/ratulalahy/26_hard_tech_week_hackathon (private; access on request)

## What it is
GridPilot pairs a day-ahead grid "traffic report" with a router for AI jobs. For each job, the router decides whether it should **move** to a cleaner region, **wait** for a cleaner hour, or stay while a battery **stores** for the evening rush. It was tested in a simulated replay of a real GPU-cluster workload (888,224 jobs) on real EIA grid data, with Utah (PacifiCorp East) as the home region.

## Results (sealed 358-day test year, opened once after a configuration freeze)

| | Result |
|---|---|
| Move jobs to cleaner regions (fixed clean-region ranking) | **22.3% less attributed CO₂** [95% CI 17.3–27.2]; validation year 22.6% |
| Wait for cleaner hours in Utah only | 0.8% |
| Forecast-based routing vs the fixed ranking | no demonstrated benefit |
| If only small jobs (≤ 8 GPUs) can move | **3.2%** [1.9–4.7]; the top 1% of jobs use ~95% of the energy |
| Battery (4 MWh) aimed at carbon vs at the rush | ~4% CO₂ but adds CO₂ on a flat marginal basis, vs Utah's rush-hour draw 0.88 → 0.32 MW but only ~1% CO₂ |

**Takeaways:**
- Moving beats waiting.
- The saving depends on whether the largest jobs can move.
- Storage can be aimed at carbon or at the rush, not both.

## How we kept it honest
- **Free, open data only.** EIA-930 and EIA hourly CO₂, plus the Acme "Seren" GPU trace.
- **No lookahead.** Each value is used only after its publication delay.
- **Frozen before testing.** An independent rebuild from raw data reproduced the validation run hash for hash. The configuration was then frozen and tagged, and the sealed test year was opened once, with every read logged.
- **Pre-registered extras.** Secondary analyses were registered before the opening.
- **Independent reviews.** AI reviewers checked every piece, and all decisions are logged (`docs/decisions.md`).

**Limits:**
- Emissions are simulated and *attributed*, not measured avoided emissions.
- Mobility, capacity and transfer costs are assumptions.
- Prices are a wholesale scenario.
- Policy S is a baseline to pilot, not a deployment.

## App pages
- **Story:** a guided walkthrough.
- **Monitor:** the hour-by-hour replay.
- **Outlook:** a 7-day forecast.
- **Regions:** 10 US grids.
- **Prices:** the wholesale cost lens.
- **Evidence:** assumptions and the validation → test table.

## Run locally
```sh
git clone https://github.com/ratulalahy/26_hard_tech_week_hackathon.git
cd 26_hard_tech_week_hackathon && make web && cd web && npm run preview
# open http://127.0.0.1:4173/?year=test  ·  deck: docs/pitch/deck/index.html
```
