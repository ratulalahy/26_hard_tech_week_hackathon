# Repository commands. AGENTS.md ("Commands") lists them; every listed command must work.
# Data is read from $GRIDPILOT_DATA_DIR (default: ./data). Worktrees point it at the main checkout:
#   export GRIDPILOT_DATA_DIR=/home/nvidia/workspace/personal/projects/26_hard_tech_week_hackathon/data

NOTEBOOKS := $(sort $(wildcard notebooks/[0-9][0-9]_*.ipynb))
NB_FROM_LAB := $(addprefix ../,$(NOTEBOOKS))

.PHONY: test data notebooks profile slice need-run-dir ext-runs extensions storage outlook overview prices flows water case-days extras-validation web freeze

test:
	cd lab && uv run pytest

# Rebuild the pipeline's derived tables from data/raw into $(GRIDPILOT_DATA_DIR) (Stage 3 T12, A2):
# interim/eia930/balance.parquet, then processed/carbon/carbon_hourly.parquet (+ lineage). The
# freeze record pins these by hash, so it refuses to replace an existing table: point
# GRIDPILOT_DATA_DIR at a fresh data dir (raw/ and manifests/ in it). ARGS=--overwrite replaces.
data:
	cd lab && uv run python scripts/build_data.py $(ARGS)

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

# Stage 3 T15 (D-064): results/scenario-flows.json (per scenario and policy S/W/L: the saving
# copied from metrics/extensions.json, remote execution by site, retiming, replay-week arcs) and
# results/flexibility-budget.json (the registered primary's energy by what S, W and L did with it).
# RUN_DIR (required): the registered run or its equal-ledger reproduction; the scenario runs are the
# ones extensions.json names under EXT_ROOT. Re-reads ledgers only; validation only. About 15 s.
flows: need-run-dir
	cd lab && uv run python scripts/export_flows.py --run-dir $(RUN_DIR) --ext-root $(EXT_ROOT)

# The water illustration (Stage 3 T14, D-063; validation only): results/water.json and the
# manifest's `water` pointer. RUN_DIR (required): the registered run. The source PDFs are checked
# against the committed data/manifests/water.json.
water: need-run-dir
	cd lab && uv run python scripts/export_water.py --registered-run $(RUN_DIR)

# "Utah's toughest grid days" (Stage 3 T16, D-066; validation only, illustrative):
# results/case-days.json and the manifest's `case_days` pointer. The pre-registered top 3
# validation days by PACE daily maximum net load, day-sliced from RUN_DIR's ledgers.
case-days: need-run-dir
	cd lab && uv run python scripts/export_case_days.py --registered-run $(RUN_DIR)

# The validation counterparts of the pre-registered test-year extras (Stage 3 T20, D-071):
# results/extras-validation.json (the seasonal split, forecast skill, the frozen p10/p90 intervals
# and the L permutation importance on validation). The test run reads it; it never recomputes it.
extras-validation: need-run-dir
	cd lab && uv run python scripts/export_extras_validation.py --registered-run $(RUN_DIR)

# The grid outlook (Stage 3 T19): results/outlook.json. Default: the validation-dated demo
# (ISSUE=<validation date>, default 2024-10-31). LIVE=1: the live outlook from a fresh EIA download,
# refused until a completed test run exists (results/test/manifest.json, T13); every read of the
# fresh files is logged in results/outlook_reads.jsonl.
outlook:
	cd lab && uv run python scripts/outlook.py $(if $(LIVE),--live,$(if $(ISSUE),--issue $(ISSUE),))

# The ten-region overview (Stage 3 T18; validation only): results/overview.json, the existing
# forecasters' day-ahead skill per region (consumed CO2 intensity, net load and its stress
# percentile, against persistence and climatology), typical-day profiles, clean vs rush hours and
# the median daily swing. Run directory: runs/overview/<UTC>/. About 10–15 minutes.
overview:

	cd lab && uv run python scripts/export_overview.py
# The price lens (Stage 3 T22; validation only, wholesale scenario): results/prices.json, the
# registered ledgers (and the mobility <= 8 GPUs W run from EXT_ROOT) priced at CAISO/WEIM
# real-time LMPs. RUN_DIR (required): the registered run.
prices: need-run-dir
	cd lab && uv run python scripts/export_prices.py --registered-run $(RUN_DIR) --ext-root $(EXT_ROOT)

# The dashboard's validation-year grid context (Task 8): results/grid-profile.json.
# RUN_DIR: the registered slice run (default runs/slice/<results/manifest.json run_id>).
profile:
	cd lab && uv run python scripts/export_grid_profile.py
	cd lab && uv run python scripts/export_workload_profile.py $(if $(RUN_DIR),--run-dir $(RUN_DIR),)

# The dashboard: copy results/*.json and the map layers into web/public/data, then build web/dist.
# Needs the web dependencies (cd web && npm ci). Without a data dir it keeps the committed map layers.
web:
	cd web && { [ -d node_modules ] || npm ci; } && npm run data && npm run build

# The configuration freeze record (Stage 3 T12): config/freeze.json from HEAD, validated with the
# seal, plus the lead's commit/tag/push commands. ARGS=--dry-run prints it instead; ARGS may add
# --registered-run <abs dir> (default runs/slice/<run_id>). Refuses on a dirty tree, a lab/ tree
# that the rebuild evidence did not rebuild, or any prior opening of the sealed window.
freeze:
	cd lab && uv run python scripts/write_freeze.py $(ARGS)
