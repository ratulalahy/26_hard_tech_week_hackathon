"""Write results/water.json: the illustrative water footprint (Stage 3 T14, D-063; validation only).

    cd lab && uv run python scripts/export_water.py --registered-run <abs runs/slice/<run_id>>

The registered run must be the one named in results/manifest.json; the carbon accounting re-run
on its ledgers must reproduce results/metrics.json. The source PDFs are checked against the
committed data/manifests/water.json. The manifest gets a `water` pointer (artifact, kind, sha256,
canonical_sha256); no other field changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from gridpilot.paths import DATA_DIR, REPO_ROOT, RESULTS_DIR
from gridpilot.results import canonical_hash, validate_artifact, write_json_atomic
from gridpilot.water import from_run

# Committed with the code (not under GRIDPILOT_DATA_DIR): see the manifest's notes.location.
WATER_MANIFEST = REPO_ROOT / "data" / "manifests" / "water.json"


def patch_manifest(path: Path, art: dict, text: str) -> None:
    man = json.loads(path.read_text())
    man["water"] = {"artifact": "water.json", "kind": art["kind"],
                    "sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "canonical_sha256": canonical_hash(art)}
    write_json_atomic(path, man)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registered-run", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=RESULTS_DIR / "water.json")
    a = ap.parse_args()
    man = json.loads((a.out.parent / "manifest.json").read_text())
    if a.registered_run.name != man["run_id"]:
        raise SystemExit(f"{a.registered_run} is not the registered run {man['run_id']}")
    metrics = json.loads((a.out.parent / "metrics.json").read_text())
    art = from_run(a.registered_run, metrics, DATA_DIR, WATER_MANIFEST)
    errs = validate_artifact(art)
    if errs:
        raise SystemExit("invalid artifact:\n" + "\n".join(errs[:20]))
    text = write_json_atomic(a.out, art)
    patch_manifest(a.out.parent / "manifest.json", art, text)
    for p, r in art["policies"].items():
        g, d = r["generation_gal"], r["change_vs_U"]
        print(f"{p}: ex-hydro {g['ex_hydro']['value'] / 1e6:.3f} Mgal  hydro {g['hydro_evap']['value'] / 1e6:.3f}  "
              f"with {g['with_hydro']['value'] / 1e6:.3f}  Δex {d['ex_hydro_gal']['value'] / 1e6:+.3f}  "
              f"Δwith {d['with_hydro_gal']['value'] / 1e6:+.3f}  direct {r['direct_cooling_gal']['low']['value'] / 1e6:.3f}–"
              f"{r['direct_cooling_gal']['high']['value'] / 1e6:.3f} Mgal")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
