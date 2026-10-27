# Stage 3 · T15: mobility/capacity toggle and flexibility budget (D-064; validation only; merges AFTER the test run)

Branch `s3/t15` from main. **Do not merge before the test run.** The lead merges after T13. **The seal holds:** validation year only, existing pre-seal loaders, and the F8 guard stays green. Use the registered validation scenarios only; **no new simulations.**

## Exports (lab), both new `results/*.json` files and enveloped
1. **`results/scenario-flows.json`.** For each already-computed validation scenario:
   - registered primary;
   - `mobility_le_8gpus`;
   - `dest_slots_0` (wait only);
   - `dest_slots_1024`.

   Per policy S/W/L, include:
   - the saving vs U, with its interval, copied from `metrics.json` / `extensions.json` (do not recompute);
   - remote execution energy by site (MWh) and the remote share of energy;
   - the replay-week arcs (GPU-h and jobs per destination), from that scenario's ledgers under `runs/ext/<name>/<run>/` and `runs/slice/20261027T173750Z`.

   **Distinguish remote execution from "moved"**, which includes retiming at home (Astra F08). Evidence: `simulated`. The scenario knobs are `assumed`.
2. **`results/flexibility-budget.json`.** From the registered primary ledgers and jobs (policy S as the default, plus W), split cohort execution energy (MWh, fsum) into:
   - (a) moved to a remote site;
   - (b) retimed at home, a flexible job started later;
   - (c) flexible and mobile, but stayed at its booking (no better option);
   - (d) must stay: not flexible or not mobile (assumed flags);
   - (e) capacity-blocked: the F14.7 blocked energy from the diagnosed run's `blocked` column, if present; otherwise `not_run` with a reason.

   Give each bucket's MWh, its share, its job count, and the share of the policy's CO₂ saving it carries. Evidence: `simulated`, with the flags labelled `assumed`.

Add both files to the envelope and sealed-date tests and to `copy-data`. Add a `make flows` target.

## Dashboard (web)
- **Control room toggle.** Add a segmented control above the map, "Which jobs can move?", with four options:
  - All flexible jobs (registered);
  - Only jobs ≤ 8 GPUs;
  - No remote capacity (wait only);
  - Double remote capacity.

  Switching changes the arcs, the "where the work went" rows and the hero number to that scenario's estimate.
  - Labels: the registered scenario says "registered result"; the others say "scenario estimate (validation)".
  - The transition takes ≤ 300 ms and respects reduced motion.
  - The default is the registered scenario, with policy **S** as the default (Astra F23).
- **Flexibility budget.** One horizontal stacked bar or treemap sized by energy, buckets (a)–(e) with direct labels, shown in the Control room and reused in the Story "lock large jobs" beat. The headline is one sentence, e.g. "{x}% of the energy sits in jobs that can move; {y}% must stay in Utah". Colours: green for moved, blue for the router's action, ink/neutral for must-stay, and a hatch for blocked, following tokens.md.
- **Story sequence (D-064):**
  1. one job;
  2. stay, wait or move;
  3. the aggregate (a simple policy does well);
  4. lock large jobs to Utah (uses the toggle state);
  5. storage and the site-power curve (from T10b; if not merged yet, leave that beat's content and coordinate);
  6. the evidence.

  Move tables, policy letters and long prose into the Method drawer.
- **Copy fixes from Astra:**
  - F06: "about 22.5% vs under 1%"; no "30×" headline.
  - F07: "no demonstrated aggregate benefit from dynamic search in this replay".
  - F10: the headline is S's own estimate and interval; the extension span is called "scenario estimates".
  - F16: "Compute follows cleaner power"; "PACE, the balancing area serving much of Utah".
  - F19: label the forecast band "retrospective ±week MAE; not a prediction interval".
  - F20: the cockpit caption reads "one hypothetical job; typical-day profile; capacity unconstrained".
  - F21: keep the sign on negative savings.
  - F22: separate the execution kWh from the total including transfer.
  - F25: "as solar fades".
- Axe 0, offline test pass, and screenshots at 1728 and 1440 of the toggle states and the budget.

## Report
Write `/tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/s3-t15-report.md`.
