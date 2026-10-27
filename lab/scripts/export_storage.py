"""Write results/storage.json: the storage illustration (Stage 3 T10b, D-061; validation only).

    cd lab && uv run python scripts/export_storage.py --registered-run <abs runs/slice/<run_id>> \
        --ext-root <abs runs/ext>

The registered run must be the one named in results/manifest.json. The mobility ≤ 8 GPUs run is
the one results/extensions.json reports (<ext-root>/mobility_le_8gpus/<run_id>). The manifest gets
a `storage` pointer (artifact, sha256, canonical_sha256); no other field changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from gridpilot.paths import RESULTS_DIR
from gridpilot.results import canonical_hash, write_json_atomic
from gridpilot.storage import ETA_DEFAULT, from_runs


def patch_manifest(path: Path, art: dict, text: str) -> None:
    man = json.loads(path.read_text())
    man["storage"] = {"artifact": "storage.json", "kind": art["kind"],
                      "sha256": hashlib.sha256(text.encode()).hexdigest(),
                      "canonical_sha256": canonical_hash(art)}
    write_json_atomic(path, man)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registered-run", type=Path, required=True)
    ap.add_argument("--ext-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=RESULTS_DIR / "storage.json")
    a = ap.parse_args()
    man = json.loads((a.out.parent / "manifest.json").read_text())
    if a.registered_run.name != man["run_id"]:
        raise SystemExit(f"{a.registered_run} is not the registered run {man['run_id']}")
    ext = json.loads((a.out.parent / "extensions.json").read_text())
    mob = ext["sensitivities"]["mobility_le_8gpus"]
    if mob.get("status") != "ok":
        raise SystemExit("the mobility ≤ 8 GPUs extension did not run (extensions.json)")
    mob_dir = a.ext_root / "mobility_le_8gpus" / mob["run_id"]
    art = from_runs(a.registered_run, mob_dir)
    text = write_json_atomic(a.out, art)
    patch_manifest(a.out.parent / "manifest.json", art, text)
    eta = f"{ETA_DEFAULT:.2f}"
    for name, c in art["cases"].items():
        a_cut = c["strategies"]["A"][eta]["cut_frac"]["value"]
        b_cut = c["strategies"]["B"][eta]["cut_frac"]["value"]
        print(f"{name}: A {[round(x * 100, 2) for x in a_cut]} %  B {[round(x * 100, 2) for x in b_cut]} %")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
