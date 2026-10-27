"""Write results/workload-profile.json: how much energy and saving sits in the largest jobs.

    cd lab && uv run python scripts/export_workload_profile.py [--run-dir runs/slice/<id>] [--policy W]

By default it reads the registered run named in results/manifest.json (runs/slice/<run_id>).
It recomputes per-job accounting from that run's ledgers and truth fill (validation only).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gridpilot.paths import REPO_ROOT, RESULTS_DIR
from gridpilot.results import write_json_atomic
from gridpilot.workload_profile import from_run


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--policy", default="W")
    a = ap.parse_args()
    run_id = json.loads((RESULTS_DIR / "manifest.json").read_text())["run_id"]
    run_dir = Path(a.run_dir) if a.run_dir else REPO_ROOT / "runs" / "slice" / run_id
    if run_dir.name != run_id:
        raise SystemExit(f"{run_dir} is not the registered run {run_id} (results/manifest.json)")
    art = from_run(run_dir, a.policy)
    out = RESULTS_DIR / "workload-profile.json"
    write_json_atomic(out, art)
    t = art["top"][1]
    print(f"wrote {out}: top 1% of jobs hold {t['energy_share']['value']:.1%} of energy and "
          f"{t['saving_share']['value']:.1%} of {a.policy}'s saving")


if __name__ == "__main__":
    main()
