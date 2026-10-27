"""Download keyless wholesale prices: CAISO OASIS (hubs, WEIM load points, PACE) and ERCOT hubs.

Raw files are kept exactly as served (zip) under data/raw/prices/<iso>/ and recorded
in data/manifests/prices_<iso>.json. Existing files are kept, never overwritten.

CAISO OASIS keeps a rolling ~39 months online (probe on 2026-10-27: earliest DAM day
2023-07-16), so the CAISO pull starts 2023-07-01. OASIS allows < 31 days per query and
about one request per 5 s; this script waits 6 s between requests.

    cd lab && uv run python scripts/recon_prices_download.py caiso ercot
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import time
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from gridpilot.paths import MANIFEST_DIR, RAW_DIR

OASIS = "https://oasis.caiso.com/oasisapi/SingleZip"
CAISO_START = datetime(2023, 7, 1, 8, tzinfo=UTC)  # 00:00 PST
CHUNK_DAYS = 30
SLEEP_S = 6.0

HUBS = ["TH_NP15_GEN-APND", "TH_SP15_GEN-APND", "TH_ZP26_GEN-APND"]
PACE = ["ELAP_PACE-APND", "DGAP_PACE-APND"]
# WEIM load aggregation points of candidate region-set BAs, plus CAISO's own load zones.
WEIM_ELAPS = [
    "ELAP_PACW-APND", "ELAP_NEVP-APND", "ELAP_AZPS-APND", "ELAP_BPAT-APND",
    "ELAP_IPCO-APND", "ELAP_PSEI-APND", "ELAP_SRP-APND", "ELAP_PNM-APND",
    "ELAP_LADWP-APND", "ELAP_TEPC-APND", "ELAP_PGE-APND",
]
DLAPS = ["DLAP_PGAE-APND", "DLAP_SCE-APND"]
NODE_GROUPS = {
    "core": HUBS + PACE + DLAPS,
    "weim": WEIM_ELAPS,
}
MARKETS = {
    # name: (queryname, version, market_run_id)
    "dam": ("PRC_LMP", 12, "DAM"),
    "rtpd": ("PRC_RTPD_LMP", 3, "RTPD"),  # 15-minute market (FMM), incl. WEIM
}

ERCOT_REPORTS = {"dam": 13060, "rtm": 13061}  # NP4-180-ER, NP6-785-ER
ERCOT_YEARS = range(2022, 2027)

CAISO_TERMS = "CAISO OASIS public market data, no registration; CAISO Conditions of Use: https://www.caiso.com/about/conditions-of-use"
ERCOT_TERMS = "ERCOT public MIS market information, no registration; ERCOT Terms of Use: https://www.ercot.com/about/terms"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _retrieved(old_entry: dict | None, dest: Path) -> str:
    """Recorded retrieval time, else the file's mtime (written once at download)."""
    value = (old_entry or {}).get("retrieved_at", "unknown")
    if value == "unknown":
        value = datetime.fromtimestamp(dest.stat().st_mtime, UTC).isoformat(timespec="seconds")
    return value


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _oasis_status(content: bytes) -> str:
    z = zipfile.ZipFile(io.BytesIO(content))
    names = z.namelist()
    if any(n.endswith(".xml") for n in names):
        xml = z.read(names[0]).decode(errors="replace")
        code = xml.split("<m:ERR_CODE>")[1].split("<")[0] if "<m:ERR_CODE>" in xml else "?"
        return f"no_data_err_{code}"
    return "ok"


def caiso(end: datetime | None = None, only: tuple[str, str] | None = None,
          reverse: bool = False) -> None:
    """Pull every (market, node group); `only=(market, group)` limits the pull to one pair.
    The manifest always lists every file present on disk."""
    end = end or datetime.now(UTC).replace(hour=8, minute=0, second=0, microsecond=0)
    manifest_path = MANIFEST_DIR / "prices_caiso.json"
    old = {f["path"]: f for f in _load_manifest(manifest_path).get("files", [])}
    files = []
    with httpx.Client(timeout=httpx.Timeout(60.0, read=300.0)) as client:
        for market, (queryname, version, run) in MARKETS.items():
            for group, nodes in NODE_GROUPS.items():
                chunks, start = [], CAISO_START
                while start < end:
                    chunks.append((start, min(start + timedelta(days=CHUNK_DAYS), end)))
                    start = chunks[-1][1]
                # reverse=True lets a second worker fill the same (market, group) from the end
                for start, stop in (reversed(chunks) if reverse else chunks):
                    rel = f"caiso/{market}/{group}/{queryname}_{start:%Y%m%d}_{stop:%Y%m%d}.zip"
                    dest = RAW_DIR / "prices" / rel
                    params = {
                        "queryname": queryname, "version": version, "resultformat": 6,
                        "market_run_id": run, "node": ",".join(nodes),
                        "startdatetime": start.strftime("%Y%m%dT%H:%M-0000"),
                        "enddatetime": stop.strftime("%Y%m%dT%H:%M-0000"),
                    }
                    url = str(httpx.URL(OASIS, params=params))
                    key = str(dest.relative_to(RAW_DIR.parent))
                    if dest.exists():
                        entry = {"retrieved_at": _retrieved(old.get(key), dest)}
                    elif only and (market, group) != only:
                        continue
                    else:
                        for attempt in range(1, 6):
                            r = client.get(url)
                            time.sleep(SLEEP_S)
                            if r.status_code == 200:
                                break
                            print(f"  HTTP {r.status_code} on {rel}, retry {attempt}", flush=True)
                            time.sleep(30 * attempt)
                        else:
                            raise RuntimeError(f"OASIS kept failing for {rel}")
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        if not dest.exists():  # another worker may have fetched it meanwhile
                            tmp = dest.with_suffix(".part")
                            tmp.write_bytes(r.content)
                            tmp.rename(dest)
                        entry = {"retrieved_at": now_iso()}
                    status = _oasis_status(dest.read_bytes())
                    files.append({
                        "url": url, "path": key, "retrieved_at": entry["retrieved_at"],
                        "bytes": dest.stat().st_size, "sha256": sha256_of(dest),
                        "market": market, "nodes": nodes, "status": status,
                        "start_utc": start.isoformat(), "end_utc": stop.isoformat(),
                    })
                    print(f"[caiso] {rel}: {status}, {dest.stat().st_size:,} B", flush=True)
    manifest = {
        "source": "prices/caiso",
        "title": "CAISO OASIS LMPs: day-ahead hourly (PRC_LMP DAM) and 15-minute real-time "
        "(PRC_RTPD_LMP RTPD) for trading hubs, PACE (ELAP/DGAP), WEIM ELAPs and CAISO DLAPs",
        "homepage": "https://oasis.caiso.com",
        "license": CAISO_TERMS,
        "notes": "OASIS keeps ~39 months online: the earliest DAM day available on 2026-10-27 "
        "was 2023-07-16, so 2022-01..2023-07-15 is not reachable here. PACE day-ahead prices exist "
        "only since EDAM go-live (2026), inside the sealed test window. Intervals are UTC "
        "(INTERVALSTARTTIME_GMT).",
        "files": files,
    }
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"[caiso] manifest -> {manifest_path}", flush=True)


def ercot() -> None:
    manifest_path = MANIFEST_DIR / "prices_ercot.json"
    old = {f["path"]: f for f in _load_manifest(manifest_path).get("files", [])}
    files = []
    with httpx.Client(timeout=httpx.Timeout(60.0, read=300.0), follow_redirects=True) as client:
        for market, rtid in ERCOT_REPORTS.items():
            list_url = f"https://www.ercot.com/misapp/servlets/IceDocListJsonWS?reportTypeId={rtid}"
            docs = client.get(list_url).json()["ListDocsByRptTypeRes"]["DocumentList"]
            by_year = {}
            for d in docs:
                name = d["Document"]["ConstructedName"]
                for y in ERCOT_YEARS:
                    if name.endswith(f"_{y}.zip"):
                        by_year[y] = d["Document"]
            for y in ERCOT_YEARS:
                doc = by_year[y]
                url = f"https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId={doc['DocID']}"
                dest = RAW_DIR / "prices" / "ercot" / market / doc["ConstructedName"]
                key = str(dest.relative_to(RAW_DIR.parent))
                if dest.exists():
                    retrieved = _retrieved(old.get(key), dest)
                else:
                    r = client.get(url)
                    r.raise_for_status()
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(r.content)
                    retrieved = now_iso()
                    time.sleep(2)
                files.append({
                    "url": url, "path": key, "retrieved_at": retrieved,
                    "bytes": dest.stat().st_size, "sha256": sha256_of(dest),
                    "market": market, "report_type_id": rtid, "year": y,
                    "publish_date": doc.get("PublishDate"),
                })
                print(f"[ercot] {key}: {dest.stat().st_size:,} B", flush=True)
    manifest = {
        "source": "prices/ercot",
        "title": "ERCOT historical settlement point prices for hubs and load zones: DAM hourly "
        "(NP4-180-ER, report 13060) and RTM 15-minute (NP6-785-ER, report 13061)",
        "homepage": "https://www.ercot.com/mp/data-products/data-product-details?id=NP4-180-ER",
        "license": ERCOT_TERMS,
        "notes": "One xlsx-in-zip per year. The current-year file is re-published as the year "
        "progresses. Delivery hours are hour-ending, Central Prevailing Time, with a DST flag.",
        "files": files,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"[ercot] manifest -> {manifest_path}", flush=True)


def main(argv: list[str]) -> None:
    """Arguments: ercot | caiso | caiso:<market>:<group> (e.g. caiso:rtpd:core)."""
    for name in argv or ["ercot", "caiso"]:
        if name.startswith("caiso:"):
            parts = name.split(":")
            caiso(only=(parts[1], parts[2]), reverse=parts[-1] == "rev")
        else:
            {"caiso": caiso, "ercot": ercot}[name]()


if __name__ == "__main__":
    main(sys.argv[1:])
