#!/usr/bin/env bash
# Codex reviews for this repository, through the shared codex-review wrapper.
# The wrapper pins the commit, runs Codex in a detached review worktree, adds the
# read-only prefix and the review contract, and logs every call to its ledger.
# Usage and the Sol/Astra split: .claude/skills/codex-gates/SKILL.md
set -euo pipefail

export REVIEW_ROOT="${REVIEW_ROOT:-$HOME/workspace/personal/projects/htw-review}"
export DEV_REPO="${DEV_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
exec "$HOME/workspace/cogni_drift/review/bin/codex-review" "$@"
