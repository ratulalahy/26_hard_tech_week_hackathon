# Repository commands. AGENTS.md ("Commands") lists them; every listed command must work.
# Data is read from $GRIDPILOT_DATA_DIR (default: ./data). Worktrees point it at the main checkout:
#   export GRIDPILOT_DATA_DIR=/home/nvidia/workspace/personal/projects/26_hard_tech_week_hackathon/data

NOTEBOOKS := $(sort $(wildcard notebooks/[0-9][0-9]_*.ipynb))
NB_FROM_LAB := $(addprefix ../,$(NOTEBOOKS))

.PHONY: test notebooks profile slice web

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
WINDOW ?= validation
slice:
	cd lab && uv run python scripts/run_slice.py --window $(WINDOW)

# The dashboard's validation-year grid context (Task 8): results/grid-profile.json.
# RUN_DIR: the registered slice run (default runs/slice/<results/manifest.json run_id>).
profile:
	cd lab && uv run python scripts/export_grid_profile.py
	cd lab && uv run python scripts/export_workload_profile.py $(if $(RUN_DIR),--run-dir $(RUN_DIR),)

# The dashboard: copy results/*.json and the map layers into web/public/data, then build web/dist.
# Needs the web dependencies (cd web && npm ci). Without a data dir it keeps the committed map layers.
web:
	cd web && npm run data && npm run build
