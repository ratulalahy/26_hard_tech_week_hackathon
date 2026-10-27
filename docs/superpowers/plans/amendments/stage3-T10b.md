# Stage 3 · T10b: "Move what you can, store for what you can't" — storage illustration (owner D-061; validation only)

Branch `s3/t10b` from main. It must finish **before the freeze, about 21:00 MT**. This is an **illustrative, modeled** analysis, separate from the registered results and never part of the test scenario catalog. **The seal holds**: validation-year data only, and every read goes through the existing pre-seal loaders. The F8 guard test must stay green.

## Question
Our results show that waiting in Utah saves 0.7%, and that moving saves about 22.5% only if large multi-node jobs can move; if only jobs of 8 GPUs or fewer may move, the saving is 3–4%. For work that cannot move, can storage at the Utah cluster shift its *energy* from dirty hours to clean ones? How much CO₂ does that cut, at what storage size?

## Inputs (all validation year, all pre-seal)
- **Cluster load profile.** Hourly site energy at PACE, from the registered U ledger (`runs/slice/20261027T173750Z`, U ledger plus warm-up occupancy, or recompute from the ledger). Take busy GPUs × 0.60 kW × PUE 1.20, from `gridpilot.sim.power`.
- **A second load case.** The mobility ≤ 8 GPUs scenario's S or W ledger at PACE, from `runs/ext/mobility_le_8gpus/...`: the large jobs that stay home.
- **Carbon.** PACE hourly consumption-basis CI, as F14.6-filled truth, labelled modeled (EIA estimate). Use the registered run's `truth_fill.parquet`.
- **Marginal proxy, for the skeptic view.** The spec §10 / grid-profile PACE marginal proxy, if available. Otherwise state the 498–658 g/kWh range from `docs/data-profile/grid.md` §8 as a disclosed reference.

## Model
A storage system of energy E MWh and power P MW (default P = E/4) at the cluster.
- **Round-trip efficiency η:** 0.85, also run at 0.75 and 0.90. These values are `assumed`.
- **Losses** are counted in the charging energy. Ignore degradation, and state that you did.

**Strategy A, a fixed daily schedule (implementable, no forecasts).**
- Charge in a fixed set of hours: by default the 6 lowest-mean-CI local hours, chosen on **training-year** data [2022-01-01, 2024-10-29) only, so there is no validation peeking.
- Discharge into the cluster load in the highest-mean-CI hours of the same training profile.
- Simulate this hourly over the validation year: the battery's state of charge, its power and energy limits, discharge capped by the cluster load.

**Strategy B, a daily hindsight upper bound.** Each day, the optimal charge and discharge given that day's actual hourly CI. Use a simple greedy pairing of cheapest charge hours with dirtiest discharge hours, respecting power, energy and η. Label it "hindsight upper bound".

**Output for each strategy × η × load case.** Over E ∈ {0, 1, 2, 4, 8, 12, 16, 24} MWh:
- annual cluster CO₂ (t) and % cut vs no storage;
- MWh shifted;
- hours of cluster load equivalent;
- the same on the marginal proxy (skeptic).

Use fsum for totals.

**Combined view.** For the mobility ≤ 8 GPUs case, report the "move small, store for big" total cut, relative to U.

## Export
- `results/storage.json`. Every number goes in an envelope:
  - simulated for load-derived results;
  - modeled for CI and CO₂ results;
  - assumed for η, P/E and the schedule hours.
- It carries `kind: "illustrative"` and the note "not part of the registered experiment; validation-year profiles; storage not simulated in the scheduler".
- Add it to the envelope and sealed-date tests, `copy-data`, and `manifest.extensions` pointers.
- Add a `make storage` target (it needs `RUN_DIR` and `EXT_ROOT`).

## Dashboard
- **New story beat.** Insert "Move what you can, store for what you can't" before "Challenge it", so the story has 7 beats.
- **Content:**
  - a compact curve of % CO₂ cut vs storage MWh, with A as a solid line and B as a dashed line labelled "hindsight bound";
  - the Utah day strip with charge and discharge windows marked;
  - one sentence with the key number, for example "{E} MWh, about {h} hours of the cluster's load, cuts its CO₂ by {x}% with a fixed daily schedule";
  - the combined small-move-plus-storage number;
  - a skeptic line with the marginal-proxy result, in plain words.
- **Labels:** modeled, illustrative and assumed chips. Tokens.md colours; storage charge and discharge use the router blue only if it is the router's action. Otherwise use ink, and a teal outline for "stored".
- **Method drawer:** add a short "Storage illustration" paragraph with the assumptions.
- Keep the 1440 and 1728 layouts. Axe must stay at 0 violations and the offline test must pass.

## Tests
Use TDD:
- hand-checked toy days for both strategies (energy conservation, η losses, limits);
- the schedule hours come from training data only, which must be asserted;
- no sealed reads.

## Report
Write `/tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/s3-t10b-report.md`.
