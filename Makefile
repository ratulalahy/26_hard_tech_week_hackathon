# Repository commands. AGENTS.md ("Commands") lists them; every listed command must work.
# Data is read from $GRIDPILOT_DATA_DIR (default: ./data). Worktrees point it at the main checkout:
#   export GRIDPILOT_DATA_DIR=/home/nvidia/workspace/personal/projects/26_hard_tech_week_hackathon/data

NOTEBOOKS := $(sort $(wildcard notebooks/[0-9][0-9]_*.ipynb))
NB_FROM_LAB := $(addprefix ../,$(NOTEBOOKS))

.PHONY: test notebooks profile slice need-run-dir ext-runs extensions storage case-days web

test:
	cd lab && uv run pytest

# Re-execute every evidence notebook in place (outputs are committed), then export HTML copies.
# Timing metadata is off so that a re-run on the same data changes nothing.
notebooks:
	cd lab && uv run jupyter nbconvert --to notebook --execute --inplace \
		--ExecutePreprocessor.timeout=1800 --ExecutePreprocessor.record_timing=False $(NB_FROM_LAB)
	cd lab && uv run jupyter nbconvert --to html --output-dir ../docs/evidence $(NB_FROM_LAB)

# The registered validation run (phase 0) and the results export (Task 7): writes
# runs/slice/<UTC>/ and copies the evidence-enveloped artifacts into results/.
# WINDOW=fallback runs the 91-day fallback window (never the registered selection).
# WINDOW=test opens the sealed test window once, after the freeze (Stage 3 T11/T13); it refuses
# otherwise. ARGS='--rerun-reason "<text>"' reruns over a completed test run (logged).
WINDOW ?= validation
slice:
	cd lab && uv run python scripts/run_slice.py --window $(WINDOW) $(ARGS)

# The D-058 extensions (Stage 3 T10, validation only). `ext-runs` runs the seven extension
# scenarios, one process each in parallel, into runs/ext/<name>/<UTC>/ with the registered run's
# pinned forecasts; `extensions` writes results/extensions.json (production-basis repricing and
# common support from RUN_DIR's ledgers, plus each extension's latest run) and manifest.not_run.
# RUN_DIR (required): absolute path of the registered run, runs/slice/<run_id in
# results/manifest.json>. EXT_ROOT defaults to the runs/ext next to it, so a worktree uses the
# main checkout's runs. REPRO_RUN (required by `extensions`): a primary run made by this code
# (`make slice`-style, --no-export), recorded as primary_reproduction. A missing extension run
# fails the export; ALLOW_MISSING=1 exports it as not_run (the 21:00 hard stop, F9).
EXT_NAMES := phase_49 phase_98 dest_slots_0 dest_slots_1024 transfer_120min batch_delay_24h mobility_le_8gpus
EXT_ROOT ?= $(abspath $(RUN_DIR)/../../ext)
need-run-dir:
	@test -n "$(RUN_DIR)" || { echo "RUN_DIR=<abs path of the registered run> is required"; exit 2; }
ext-runs: need-run-dir
	mkdir -p $(EXT_ROOT) && cd lab && pids=""; for n in $(EXT_NAMES); do \
		uv run python scripts/run_slice.py --scenario $$n --out $(EXT_ROOT)/$$n \
			--forecast-run $(RUN_DIR)/forecast/$(notdir $(RUN_DIR)) > $(EXT_ROOT)/$$n.log 2>&1 & \
		pids="$$pids $$!:$$n"; \
	done; rc=0; for p in $$pids; do \
		wait $${p%%:*} || { echo "extension $${p#*:} failed (see $(EXT_ROOT)/$${p#*:}.log)"; rc=1; }; \
	done; exit $$rc
extensions: need-run-dir
	@test -n "$(REPRO_RUN)" || { echo "REPRO_RUN=<abs path of a primary run made by this code> is required"; exit 2; }
	cd lab && uv run python scripts/export_extensions.py --registered-run $(RUN_DIR) \
		--ext-root $(EXT_ROOT) --repro-run $(REPRO_RUN) $(if $(ALLOW_MISSING),--allow-missing,)

# The storage illustration (Stage 3 T10b, D-061; validation only): results/storage.json and the
# manifest's `storage` pointer. RUN_DIR (required): the registered run; EXT_ROOT (default: the
# runs/ext next to it) holds the mobility <= 8 GPUs run that results/extensions.json names.
storage: need-run-dir
	cd lab && uv run python scripts/export_storage.py --registered-run $(RUN_DIR) --ext-root $(EXT_ROOT)

# "Utah's toughest grid days" (Stage 3 T16, D-066; validation only, illustrative):
# results/case-days.json and the manifest's `case_days` pointer. The pre-registered top 3
# validation days by PACE daily maximum net load, day-sliced from RUN_DIR's ledgers.
case-days: need-run-dir
	cd lab && uv run python scripts/export_case_days.py --registered-run $(RUN_DIR)

# The dashboard's validation-year grid context (Task 8): results/grid-profile.json.
# RUN_DIR: the registered slice run (default runs/slice/<results/manifest.json run_id>).
profile:
	cd lab && uv run python scripts/export_grid_profile.py
	cd lab && uv run python scripts/export_workload_profile.py $(if $(RUN_DIR),--run-dir $(RUN_DIR),)

# The dashboard: copy results/*.json and the map layers into web/public/data, then build web/dist.
# Needs the web dependencies (cd web && npm ci). Without a data dir it keeps the committed map layers.
web:
	cd web && { [ -d node_modules ] || npm ci; } && npm run data && npm run build
