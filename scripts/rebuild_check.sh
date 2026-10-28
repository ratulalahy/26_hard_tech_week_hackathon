#!/usr/bin/env bash
# Stage 3 T12 step 2 (F12.6): the independent clean rebuild of the registered validation run.
#
#   scripts/rebuild_check.sh <commit> <scratch dir> <clone source> <shared data dir>
#
# 1. a fresh clone of <commit> from <clone source> into <scratch>/repo;
# 2. a fresh data dir <scratch>/data: raw/ a read-only symlink to <shared data dir>/raw,
#    manifests/ copied from the clone's git tree, interim/ and processed/ empty;
# 3. `make data` in the clone into that data dir (balance and carbon rebuilt from raw);
# 4. `run_slice --no-export --out <scratch>/runs` on the validation window (fresh forecasts);
# 5. <scratch>/timing.json: the commands and their wall times, for scripts/rebuild_compare.py.
# It never writes into <shared data dir>, and never opens the sealed window.
set -euo pipefail
commit=$1 scratch=$2 source=$3 shared=$4
[ ! -e "$scratch/repo" ] || { echo "rebuild: $scratch/repo exists; use a fresh scratch dir" >&2; exit 2; }
mkdir -p "$scratch"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
declare -a cmds secs
step() {  # step <name> <command...>
  local name=$1; shift
  local t0; t0=$(date +%s.%N)
  echo "== $name: $*"
  "$@"
  cmds+=("$name"$'\t'"$*")
  secs+=("$name"$'\t'"$(echo "$(date +%s.%N) - $t0" | bc)")
}
step clone git clone --quiet --no-checkout "$source" "$scratch/repo"
step checkout git -C "$scratch/repo" checkout --quiet --detach "$commit"
test "$(git -C "$scratch/repo" rev-parse HEAD)" = "$(git -C "$scratch/repo" rev-parse "$commit^{commit}")"
step data_dir bash -c "mkdir -p '$scratch/data/interim' '$scratch/data/processed' && ln -s '$shared/raw' '$scratch/data/raw' && cp -r '$scratch/repo/data/manifests' '$scratch/data/manifests'"
export GRIDPILOT_DATA_DIR="$scratch/data"
step make_data make -C "$scratch/repo" data
mkdir -p "$scratch/runs"
step run_slice bash -c "cd '$scratch/repo/lab' && uv run python scripts/run_slice.py --window validation --no-export --out '$scratch/runs'"
python3 - "$scratch/timing.json" "$started" "${#cmds[@]}" "${cmds[@]}" "${secs[@]}" <<'EOF'
import json, sys
out, started, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
cmds, secs = sys.argv[4:4 + n], sys.argv[4 + n:4 + 2 * n]
json.dump({"started_at": started,
           "commands": [{"step": c.split("\t", 1)[0], "command": c.split("\t", 1)[1]} for c in cmds],
           "wall_time_s": {s.split("\t")[0]: round(float(s.split("\t")[1]), 1) for s in secs}},
          open(out, "w"), indent=1)
EOF
echo "rebuild: done; run dir: $(ls -d "$scratch"/runs/2*Z)"
