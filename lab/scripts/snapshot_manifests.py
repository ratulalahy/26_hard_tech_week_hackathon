"""Record a snapshot of the data manifests: sha256 of each manifest, its entry count
and total bytes. Analyses cite the snapshot id; a manifest marked "growing" is not
yet a frozen input.

    uv run python scripts/snapshot_manifests.py --growing openmeteo
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime

from gridpilot.paths import MANIFEST_DIR

SNAPSHOT = MANIFEST_DIR / "snapshot.json"


def entries(manifest: dict) -> list[dict]:
    """The per-file records of a manifest, whatever key the downloader used."""
    for key in ("files", "entries", "downloads", "outputs"):
        if isinstance(manifest.get(key), list):
            return manifest[key]
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--growing", nargs="*", default=[], help="manifest stems still being written")
    args = ap.parse_args()

    sources = {}
    for path in sorted(MANIFEST_DIR.glob("*.json")):
        if path == SNAPSHOT:
            continue
        raw = path.read_bytes()
        records = entries(json.loads(raw))
        sources[path.stem] = {
            "manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "files": len(records),
            "bytes": sum(r.get("bytes") or 0 for r in records),
            "status": "growing" if path.stem in args.growing else "frozen",
        }
    snapshot_id = hashlib.sha256(
        json.dumps({k: v["manifest_sha256"] for k, v in sources.items()}, sort_keys=True).encode()
    ).hexdigest()[:12]
    record = {
        "snapshot_id": snapshot_id,
        "taken_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": sources,
    }
    tmp = SNAPSHOT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2) + "\n")
    tmp.replace(SNAPSHOT)
    print(f"snapshot {snapshot_id}: {len(sources)} manifests -> {SNAPSHOT}")
    for name, s in sources.items():
        print(f"  {name:28s} {s['status']:8s} files={s['files']:<5} bytes={s['bytes']}")


if __name__ == "__main__":
    main()
