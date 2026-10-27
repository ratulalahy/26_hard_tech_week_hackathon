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
    carbon, balance = ov.load_carbon(), ov.load_balance()
    art = ov.build_overview(carbon, balance, workers=a.workers)
    art["run_id"] = run_id

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
    for ba in art["order"]:
        r = art["regions"][ba]
        fc = r["forecast"]
        print(f"{ba:5s} CI {fc['ci']['model']} MAE {fc['ci']['mae']['value']:7.1f} "
              f"skill/P {fc['ci']['skill']['vs_persistence']['value']:+.2f} "
              f"skill/K {fc['ci']['skill']['vs_climatology']['value']:+.2f} | "
              f"NL {fc['net_load']['model']} skill/P {fc['net_load']['skill']['vs_persistence']['value']:+.2f} "
              f"skill/K {fc['net_load']['skill']['vs_climatology']['value']:+.2f} "
              f"top4 {fc['stress']['top4_precision'][fc['stress']['model']]['precision']['value']:.2f} | "
              f"rush {r['alignment']['rush_vs_mean_pct']['value']:+.1f}% "
              f"stress {r['alignment']['stress_vs_mean_pct']['value'] if r['alignment']['stress_vs_mean_pct']['value'] is not None else float('nan'):+.1f}% "
              f"rho {r['alignment']['spearman_ci_net_load']['value']:+.2f} "
              f"swing {r['swing']['median_g']['value']:.0f} g")
    for d in art["dropped"]:
        print("dropped", d["ba"], d["reason"])


if __name__ == "__main__":
    main()
