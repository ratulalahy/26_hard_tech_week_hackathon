"""Where the data lives. GRIDPILOT_DATA_DIR overrides the default, so worktrees
can share the main checkout's downloads."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.environ.get("GRIDPILOT_DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
MANIFEST_DIR = DATA_DIR / "manifests"
RESULTS_DIR = REPO_ROOT / "results"
