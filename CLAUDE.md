@AGENTS.md

# Claude Code notes

- **Machine:** an NVIDIA DGX Spark (GB10, aarch64, CUDA 13, 128 GB unified memory).
  - PyTorch comes from the cu130 index (`https://download.pytorch.org/whl/cu130`). torch 2.13.0+cu130 is known to work.
  - `nvidia-smi` shows no memory figures on GB10, because the memory is unified. That is expected.
- **Caches:** `HF_HOME`, `UV_CACHE_DIR`, `PIP_CACHE_DIR` and `TORCH_HOME` live under `~/workspace/cache`, set in `~/.zshrc`. Download models only there.
- **Worktrees share the main checkout's data:**
  `export GRIDPILOT_DATA_DIR=/home/nvidia/workspace/personal/projects/26_hard_tech_week_hackathon/data`
- **Workflow:** superpowers:brainstorming (spec) → superpowers:writing-plans → superpowers:subagent-driven-development.
  - Run at most 3 subagents at once, each in its own worktree.
  - Use superpowers:test-driven-development for the simulator, the metrics and the leakage tests.
  - UI work uses frontend-design and the dataviz skill, then `.claude/skills/viz-critique`.
- **Reviews:** Codex runs through `scripts/review.sh` (see `.claude/skills/codex-gates`). For an in-session review, use the `code-reviewer` agent in `.claude/agents/`, never `feature-dev:code-reviewer`.
- **Status:** the pinned GitHub issue "Run log" carries one status comment, edited in place. Send push notifications only at gates and on blockers.
- **Effort:** Opus 5.5 at `high` for the spec and leakage-sensitive code, `medium` for routine work.
