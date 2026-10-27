"""`make data` (Stage 3 T12, final review A2): rebuild the pipeline's derived tables from the
raw cache, into `$GRIDPILOT_DATA_DIR`.

    cd lab && uv run python scripts/build_data.py [--overwrite]

1. `interim/eia930/balance.parquet`: `gridpilot.data.eia930.build_balance` over every
   `raw/eia930/EIA930_BALANCE_*.csv` (the raw-source parser; the table keeps every hour, and
   every reader of it is sealed);
2. `processed/carbon/carbon_hourly.parquet` and its lineage sidecar:
   `gridpilot.data.eia_co2.build_carbon` over the core BA workbooks (truncated at TEST_START).

Not rebuilt, because the pipeline does not read them: `interim/eia930/interchange.parquet`
(nothing reads interchange) and the map layers under `processed/geo/` (`make web` keeps the
committed `web/public/data/geo` layers when the data dir has none; `scripts/recon_geo.py`
rebuilds them).

The derived tables are pinned by hash in the freeze record (config/freeze.json), so the script
refuses to replace an existing table unless `--overwrite` is given: rebuild into a fresh data
dir (`GRIDPILOT_DATA_DIR=<new dir>`, with `raw/` and `manifests/` in it), never over the shared
one. Each table is written to a temp file and renamed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from gridpilot import paths
from gridpilot.data import eia930, eia_co2


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--overwrite", action="store_true",
                    help="replace existing derived tables (never on the shared data dir)")
    a = ap.parse_args(argv)
    data = paths.DATA_DIR
    balance = eia930.INTERIM_EIA_DIR / "balance.parquet"
    carbon = eia_co2.CARBON_PATH
    raw = sorted(eia930.RAW_EIA_DIR.glob("EIA930_BALANCE_*.csv"))
    if not raw:
        print(f"make data: no raw EIA-930 BALANCE files under {eia930.RAW_EIA_DIR}",
              file=sys.stderr)
        return 2
    exists = [p for p in (balance, carbon) if p.exists()]
    if exists and not a.overwrite:
        print(f"make data: refusing to replace {[str(p) for p in exists]} (pinned by the freeze "
              f"record); rebuild into a fresh GRIDPILOT_DATA_DIR, or pass --overwrite",
              file=sys.stderr)
        return 2
    print(f"make data: GRIDPILOT_DATA_DIR = {data}")
    out = {"data_dir": str(data), "tables": {}}
    t0 = time.perf_counter()
    tmp = balance.with_name(f".{balance.name}.{os.getpid()}.tmp")
    try:
        eia930.build_balance(raw, out_path=tmp)
        os.replace(tmp, balance)
    finally:
        tmp.unlink(missing_ok=True)
    out["tables"][str(balance.relative_to(data))] = {
        "sha256": _sha256(balance), "seconds": round(time.perf_counter() - t0, 1),
        "inputs": len(raw)}
    t0 = time.perf_counter()
    eia_co2.build_carbon()
    out["tables"][str(carbon.relative_to(data))] = {
        "sha256": _sha256(carbon), "seconds": round(time.perf_counter() - t0, 1),
        "inputs": len(eia_co2.CORE_BAS)}
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
