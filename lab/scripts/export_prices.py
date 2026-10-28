"""Write results/prices.json: the price lens (Stage 3 T22; validation only, wholesale scenario).

    cd lab && uv run python scripts/export_prices.py --registered-run <abs runs/slice/<run_id>> \
        --ext-root <abs runs/ext>

The registered run must be the one named in results/manifest.json. The mobility ≤ 8 GPUs run is
the one results/extensions.json reports (<ext-root>/mobility_le_8gpus/<run_id>); without it the
artifact covers the registered policies only. The price manifest's sha256 is recorded before
the analysis and checked again after it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from gridpilot import price_lens as lens
from gridpilot.paths import DATA_DIR, RESULTS_DIR
from gridpilot.results import write_json_atomic


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registered-run", type=Path, required=True)
    ap.add_argument("--ext-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=RESULTS_DIR / "prices.json")
    a = ap.parse_args()
    man = json.loads((a.out.parent / "manifest.json").read_text())
    if a.registered_run.name != man["run_id"]:
        raise SystemExit(f"{a.registered_run} is not the registered run {man['run_id']}")
    ext_dir = None
    ext_path = a.out.parent / "extensions.json"
    if ext_path.exists():
        mob = json.loads(ext_path.read_text())["sensitivities"].get(lens.EXT_NAME, {})
        if mob.get("status") == "ok":
            ext_dir = a.ext_root / lens.EXT_NAME / mob["run_id"]
            if not ext_dir.is_dir():
                raise SystemExit(f"{ext_dir} (named in extensions.json) is missing")
    manifest = DATA_DIR / lens.MANIFEST
    sha_before = _sha(manifest)
    main_ = lens.compute(a.registered_run, ext_dir)
    alt = lens.compute(a.registered_run, ext_dir,
                       nodes={**lens.NODES, "CISO": lens.CISO_SENS_NODE})
    if _sha(manifest) != sha_before:
        raise SystemExit(f"{manifest} changed during the analysis: not a frozen snapshot")
    art = lens.build_artifact(main_, alt)
    art["prices"]["manifest_sha256"] = sha_before
    art["export_git_sha"] = _git("rev-parse", "HEAD")
    art["export_git_clean"] = _git("status", "--porcelain") == ""
    art["wallclock_generated_at"] = datetime.now(UTC).isoformat()
    art["reproduce"] = "make prices RUN_DIR=<abs path of the registered run>"
    write_json_atomic(a.out, art)
    print(lens.CAVEAT)
    print(f"priced hours {art['coverage']['priced_hours']['value']} of "
          f"{art['coverage']['window_hours']['value']}")
    rows = [("PG&E (shown)", art["policies"])]
    if "california_node" in art:
        rows.append(("SCE", art["california_node"]["alternative_policies"]))
    for label, pols in rows:
        print(f"California load zone: {label}. All $ are policy − U (+ = costs more than U).")
        print(f"{'policy':<22}{'cost $':>12}{'Δ vs U $':>12}{'Δ %':>8}{'level $':>10}"
              f"{'timing $':>10}{'$/t attr.':>11}  95% interval of Δ, primary block")
        for p, r in pols.items():
            pt = r["cost_per_attributed_tonne_usd_t"]["value"]
            iv = r.get("interval", {})
            b = str(iv["primary_block"]["value"]) if iv else None
            ci = iv["blocks"][b]["delta_vs_U_usd_ci95"]["value"] if iv else None
            d = r["decomposition_vs_U_usd"]
            civ = "—" if ci is None else f"[{ci[0]:+,.0f}, {ci[1]:+,.0f}] (b={b} weeks)"
            print(f"{p:<22}{r['cost_usd']['value']:>12,.0f}"
                  f"{r['delta_vs_U_usd']['value']:>+12,.0f}"
                  f"{r['delta_vs_U_frac']['value'] * 100:>+8.2f}{d['level_usd']['value']:>+10,.0f}"
                  f"{d['timing_usd']['value']:>+10,.0f}"
                  f"{'—' if pt is None else f'{pt:+,.1f}':>11}  {civ}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
