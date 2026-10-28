"""Write results/overview.json: the ten-region traffic-report overview (Stage 3 T18; validation only).

    cd lab && uv run python scripts/export_overview.py     # or: make overview

Reads the cached EIA tables and BA workbooks through the seal (`drop_sealed`), runs the existing
forecasters per region on the validation-selection issues and profiles the validation window
(`gridpilot.overview`). The run's config, git state and artifact go to runs/overview/<UTC>/; the
artifact is validated (every number enveloped, no sealed timestamp) and written atomically to
results/overview.json. About 10–15 minutes (one process per region; the gradient-boosting fits dominate).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import yaml

from gridpilot import forecast as F
from gridpilot import overview as ov
from gridpilot.paths import REPO_ROOT, RESULTS_DIR
from gridpilot.results import write_json_atomic


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True,
                          check=False).stdout


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workers", type=int, default=min(10, os.cpu_count() or 1))
    ap.add_argument("--out-root", default=str(REPO_ROOT / "runs" / "overview"))
    a = ap.parse_args()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    # lineage first: the tree must be clean before anything is written (results/ is tracked)
    sha, status = _git("rev-parse", "HEAD").strip(), _git("status", "--porcelain")
    carbon, balance = ov.load_carbon(), ov.load_balance()
    art = ov.build_overview(carbon, balance, workers=a.workers)
    art["run_id"] = run_id
    art["lineage"] = {"git_sha": sha, "git_clean": status.strip() == "",
                      "run_dir": f"runs/overview/{run_id}", "command": "make overview",
                      "inputs_sha256": ov.input_hashes()}

    root = os.path.abspath(a.out_root)
    tmp, final = os.path.join(root, f".tmp-{run_id}-{os.getpid()}"), os.path.join(root, run_id)
    os.makedirs(tmp)
    try:
        cfg = {"run_id": run_id, "regions": list(ov.OVERVIEW_BAS), "zones": ov.OVERVIEW_TZ,
               "window": [ov.WINDOW[0].isoformat(), ov.WINDOW[1].isoformat()],
               "fit_at": F.VAL_FIT_AT.isoformat(), "history_start": F.VAL_HISTORY_START.isoformat(),
               "selection_end": F.SELECTION_END.isoformat(), "envelope_h": F.ENVELOPE_H,
               "hgb": {**F.HGB_PARAMS, "max_leaf_nodes_grid": list(F.MAX_LEAF_NODES)},
               "stress_quantile": ov.STRESS_Q, "rush_k": ov.RUSH_K,
               "min_coverage": ov.MIN_COVERAGE, "inputs_sha256": ov.input_hashes()}
        with open(os.path.join(tmp, "config.yaml"), "w") as f:
            f.write(yaml.safe_dump(cfg, sort_keys=False))
        with open(os.path.join(tmp, "git.txt"), "w") as f:
            f.write(f"sha {_git('rev-parse', 'HEAD').strip()}\nstatus:\n{_git('status', '--porcelain')}")
        write_json_atomic(Path(tmp) / "overview.json", art)
        os.rename(tmp, final)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    out = RESULTS_DIR / "overview.json"
    write_json_atomic(out, art)
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB) and {final}")
    def cell(sk):
        lo_hi = sk["ci90"]["value"]
        iv = "[  n/a  ]" if lo_hi is None else f"[{lo_hi[0]:+.2f},{lo_hi[1]:+.2f}]"
        return f"{sk['point']['value']:+.2f}{iv}{'*' if sk['verdict'] == 'beats' else ' '}"

    for ba in art["order"]:
        r = art["regions"][ba]
        fc, al = r["forecast"], r["alignment"]
        rv = al["rush_vs_mean_pct_ci90"]["value"]
        print(f"{ba:5s} CI {fc['ci']['model']} {fc['ci']['mae']['value']:6.1f} "
              f"P {cell(fc['ci']['skill']['vs_persistence'])} "
              f"K {cell(fc['ci']['skill']['vs_climatology'])} | NL {fc['net_load']['model']} "
              f"P {cell(fc['net_load']['skill']['vs_persistence'])} "
              f"K {cell(fc['net_load']['skill']['vs_climatology'])} | "
              f"rush {al['rush_vs_mean_pct']['value']:+.1f}% [{rv[0]:+.1f},{rv[1]:+.1f}] "
              f"{al['rush_verdict']} | swing {r['swing']['median_g']['value']:.0f} g")
    print("lineage", art["lineage"]["git_sha"], "clean" if art["lineage"]["git_clean"] else "DIRTY")
    for d in art["dropped"]:
        print("dropped", d["ba"], d["reason"])


if __name__ == "__main__":
    main()
