# Handoff between Claude and Codex

This is the shared status board for the two agents. It says where things stand and what each agent needs from the other.

Other topics have their own single source:
- rules: `AGENTS.md`;
- owner decisions: `docs/brief.md`;
- the approved plan: `docs/plan/2026-10-26-hackathon-plan.md`;
- the design: the spec, once written.

Each entry is dated in Mountain Time (MDT, UTC−6) and cites its evidence: a commit, a path or a command. The newest entry goes first.

## Checkouts

| Agent | Checkout | Branch |
|---|---|---|
| Claude (lead, implementation) | `~/workspace/personal/projects/26_hard_tech_week_hackathon` | `main` and task branches |
| Codex (planning, evidence review, narrative) | `~/workspace/personal/projects/26_hard_tech_week_hackathon-codex` | `codex/planning` |

- Both push to `github.com/ratulalahy/26_hard_tech_week_hackathon`. Codex syncs with `git pull --rebase origin main`.
- **The data is shared, not copied.** Read it from `/home/nvidia/workspace/personal/projects/26_hard_tech_week_hackathon/data`, with `GRIDPILOT_DATA_DIR` set to that path.
- Never download duplicates, and never write into the other agent's checkout.
- Codex's own sandbox cannot start on this machine. Interactive Codex runs with approvals, or with `danger-full-access` inside its own checkout only.

## Entries

### 2026-10-26 23:05: Claude

**Done**
- The repo skeleton is on `main`:
  - `AGENTS.md` and `CLAUDE.md`;
  - `docs/brief.md` and the approved plan;
  - the `lab/` uv project, with the sealed split boundaries in `lab/src/gridpilot/splits.py`;
  - `scripts/review.sh`;
  - the shared skills in `.claude/skills/`. `.agents/skills` links to the same folder.
- Codex's setup proposal is merged in, keeping one source of truth:
  - its ownership split and its six evidence labels are in `AGENTS.md`;
  - its evidence skill is `hackathon-evidence`;
  - its CONTEXT and PLAN content already lives in `docs/brief.md` and the approved plan.
- Codex's checkout is created at the path above, on `codex/planning`.

**Running**
- Data recon, by three agents. Results expected around 00:30 on `main`:
  - **Grid:** EIA-930 from 2019 to now, plus Open-Meteo archived forecasts. Both the Historical Forecast and the Previous Runs APIs are being checked, to settle which one gives an honest day-ahead weather input. Output: `docs/data-profile/grid.md`.
  - **Workloads and prices:** two public GPU traces, plus CAISO and ERCOT day-ahead prices, including any PACE price. Output: `docs/data-profile/workloads-prices.md`.
  - **Map:** BA polygons and a Natural Earth basemap. Output: `docs/data-profile/geo.md`.
- Sol 6.1 is reviewing the plan (workstream `plan-sol`). Its output goes to `docs/reviews/`.

**Direction** (owner, 22:45)
- Option 1's day-ahead grid traffic report plus Option 2's AI-job router, evaluated in simulation on real data.
- The headline is Compute Follows the Sun; the traffic report is its engine.
- Utah's PACE is the hero region.
- The DGX is only the lab. The demo runs offline in Chrome on a MacBook Pro.

**Next for Codex**
1. When the data profile lands on `main`, write your own version of the experiment spec from `docs/brief.md` and `docs/data-profile/*.md`.
2. Put it in `docs/superpowers/specs/2026-10-26-gridpilot-design-codex.md` on `codex/planning`, push, and add an entry here.

Claude writes its version at the same time. The differences become decisions, and then a fresh Astra session gates the merged spec.

Please don't create CONTEXT.md or PLAN.md copies. Propose edits to `docs/brief.md` or to the plan on your branch instead.

**Time check:** it is Monday ~23:05 MDT. Experiments freeze Wed 11:00, the cutoff is Wed 14:00, and judging is Wed 17:00.
