# Brief: Hard Tech Week Hackathon, Torus bounty

Both spec authors (Claude and Codex Sol) write from this brief. It records what the sponsor asked for and what the owner decided. It does not design the experiment.

## Event

- **What:** Hard Tech Week Hackathon (47G, Utah Tech Week, Nucleus).
- **Build window:** Mon 2026-10-26 5 PM to Wed 2026-10-28 5 PM MT.
- **Judging:** Wed 2026-10-28, 5:00–6:00 PM, at Aernata, 250 E 200 S, Suite 320, Salt Lake City.
  - Each team demos one-on-one to the bounty's judges.
  - The slot covers the demo and questions. Its length depends on the number of teams on the bounty: 25 min for 2 teams, 8 min for 6.
- **Winners:** announced Thu 2026-10-29 at Zero Gravity Summit.

## The Torus bounty (transcribed from the bounty slide)

"ENERGY × AI INFRASTRUCTURE — TORUS HACKATHON BOUNTY — $5K"

**Option 1: Rush Hour for Electrons**
- The grid has a rush hour: demand spikes, prices jump, solar fades. Most software ignores it.
- Build software that knows when the grid is jammed and stays out of traffic.
- Examples: a navigation app for electricity; a traffic report for tomorrow's grid; agents that schedule around clean power.
- Question: how would you manage the grid's congestion?
- Data: EIA · CAISO · ERCOT · Open-Meteo · Electricity Maps

**Option 2: Compute Follows the Sun**
- Power is cleaner and cheaper in different places at different times. AI jobs that can move, should.
- Build something that decides where and when compute should run.
- Examples: a job router that shows carbon saved; agents that bid for the cleanest slots; a live map of where to train right now.
- Question: how would you route the cheapest and cleanest energy?
- Data: EIA · NREL · NASA POWER · Open-Meteo · cluster traces

**Rules on the slide**
- "We don't expect you to be energy and grid experts — they are very complex systems. We care more about engineering skill and creativity."
- Free and open-source data only. Simulated data is fine if labeled.
- Judged on creativity, clarity of insight, and execution.

The kickoff deck's text calls it a $10K bounty; the slide and the event page say $5K.

## About Torus (public sources; these are company claims)

- Based in South Salt Lake, Utah.
- Makes flywheel and battery hybrid storage (Nova Spin, Nova Pulse) for AI data centers, industry and utilities. It positions the system to buffer the fast load swings of AI clusters.
- Has a 70 MW demand-response MOU with Rocky Mountain Power (PacifiCorp), tied to Utah's Operation Gigawatt (Feb 2025).
- Raised $200M (Magnetar, Sep 2025) and is building the GigaOne manufacturing campus in Salt Lake City.

Sources: torus.co news (2025-02-07), BusinessWire (2025-09-09), Battery Technology (2026-03-31).

## Owner decisions (2026-10-26)

| Topic | Decision |
|---|---|
| Direction | Option 1's day-ahead grid traffic report plus Option 2's AI-job router, evaluated in simulation on real data. No live hardware loop. |
| Hero region | Utah: PacifiCorp East, EIA balancing-authority code PACE. |
| The DGX Spark | Development and experiment machine only. Not part of the pitch. |
| Demo | From the owner's laptop, as an offline static build. |
| Priority | High-end visualization: a map, and the simulation made visible. |
| Order | Download and profile the data first, then design the experiment. The test window stays sealed during design. |
| Test window | The last 12 months, 2025-11-01 to 2026-10-31 (UTC). |
| Team | Solo owner plus agents. Claude Code builds; Codex plans and reviews. |
| Deadline | Experiments frozen Wed 11 AM; mostly done by Wed 2 PM. |

## Owner clarifications (2026-10-26 23:14 MT)

- **Primary objective approved:** emissions first. Minimize attributed operational emissions in the simulation, subject to deadlines and the same completed work. Report grid-stress exposure and wholesale energy-cost scenarios separately; do not silently trade them through arbitrary objective weights.
- **Delivery priority approved:** PACE first, regional overview. Build and verify the complete PACE forecast → router → replay → offline demo before extending experiment depth. Keep roughly ten BAs in the overview; full experiment depth is not required for every overview region.
- **Demo platform:** MacBook Pro, Chrome, offline static build. The experiment machine is not part of the product or pitch; no live hardware loop is needed.
- **Test-window correction:** retain the original sealed boundaries, but end evaluation at the frozen snapshot's availability cutoff. Do not claim a complete twelve-month evaluation if some hours have not happened or have not been published. This implements the existing plan-review correction, not a new holdout chosen after seeing outcomes.

## Constraints

- Free and open data only. Anything simulated or assumed is labeled as such, end to end.
- **Compute:** NVIDIA DGX Spark (GB10, aarch64, 128 GB unified memory, CUDA 13).
- **Demo:** on a laptop, offline.
- 48-hour build, one presenter, a slot of 8–25 minutes.

## What the spec must settle

- Hypotheses and target insights.
- Metrics and baselines.
- Splits: train, validation, and the sealed test window above.
- Forecast issue time and horizon.
- The grid-stress index, carbon accounting (average and marginal), and price signals.
- The region set (about 10 balancing authorities), chosen from the data profile.
- The workload: which trace, and the labeled job assumptions (deferrable share, allowed wait, interruptible, movable, energy per GPU-hour).
- Router policies, including a perfect-hindsight upper bound.
- The results contract: the artifacts and fields the dashboard reads.
- The story beats for the dashboard's story mode.
