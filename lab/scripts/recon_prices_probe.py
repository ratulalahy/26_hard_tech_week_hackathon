"""Probe CAISO OASIS: which price nodes and markets return data, one day each.

Run once during the data recon. For any query inside the sealed test window
(gridpilot.splits) it prints only row counts, never values.

    cd lab && uv run python scripts/recon_prices_probe.py
"""

from __future__ import annotations

import io
import time
import zipfile
from datetime import UTC, datetime, timedelta

import httpx
import polars as pl

from gridpilot.splits import TEST_START

OASIS = "https://oasis.caiso.com/oasisapi/SingleZip"
QUERIES = {
    "DAM": ("PRC_LMP", 12, "DAM"),
    "RTPD_15min": ("PRC_RTPD_LMP", 3, "RTPD"),
    "RTD_5min": ("PRC_INTVL_LMP", 3, "RTM"),
}


def oasis_csv(client: httpx.Client, queryname: str, version: int, start: datetime,
              end: datetime, **params) -> tuple[pl.DataFrame | None, str]:
    q = {
        "queryname": queryname,
        "version": version,
        "resultformat": 6,
        "startdatetime": start.strftime("%Y%m%dT%H:%M-0000"),
        "enddatetime": end.strftime("%Y%m%dT%H:%M-0000"),
        **params,
    }
    r = client.get(OASIS, params=q)
    time.sleep(6)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    if any(n.endswith(".xml") for n in names):
        xml = z.read(names[0]).decode(errors="replace")
        code = xml.split("<m:ERR_CODE>")[1].split("<")[0] if "<m:ERR_CODE>" in xml else "?"
        desc = xml.split("<m:ERR_DESC>")[1].split("<")[0] if "<m:ERR_DESC>" in xml else xml[:200]
        return None, f"no data (ERR {code}: {desc})"
    frames = [pl.read_csv(z.read(n), infer_schema_length=0) for n in names]
    return pl.concat(frames, how="diagonal"), "ok"


def probe(client, market: str, node: str, day: datetime, days: int = 1) -> None:
    queryname, version, run = QUERIES[market]
    start = day.replace(hour=8)  # 00:00 Pacific standard time
    end = start + timedelta(days=days)
    df, status = oasis_csv(client, queryname, version, start, end, market_run_id=run, node=node)
    sealed = end > TEST_START
    tag = "SEALED: count only" if sealed else "pre-seal"
    if df is None:
        print(f"{market:11s} {node:24s} {day:%Y-%m-%d} +{days}d [{tag}] -> {status}", flush=True)
        return
    lmp = df.filter(pl.col("LMP_TYPE") == "LMP") if "LMP_TYPE" in df.columns else df
    msg = f"{market:11s} {node:24s} {day:%Y-%m-%d} +{days}d [{tag}] -> {lmp.height} LMP rows"
    if not sealed:
        val_col = next(c for c in ("MW", "PRC", "VALUE") if c in lmp.columns)
        vals = lmp[val_col].cast(pl.Float64)
        msg += f"; mean {vals.mean():.2f} $/MWh, min {vals.min():.2f}, max {vals.max():.2f}"
    print(msg, flush=True)


def main() -> None:
    pre = datetime(2025, 10, 1, tzinfo=UTC)
    edam = datetime(2026, 6, 1, tzinfo=UTC)  # inside the sealed window: counts only
    with httpx.Client(timeout=120) as client:
        probe(client, "DAM", "TH_NP15_GEN-APND,TH_SP15_GEN-APND", pre)
        probe(client, "DAM", "ELAP_PACE-APND", pre)
        probe(client, "RTPD_15min", "ELAP_PACE-APND", pre)
        probe(client, "RTD_5min", "ELAP_PACE-APND", pre)
        probe(client, "RTPD_15min", "ELAP_PACE-APND", datetime(2025, 9, 1, tzinfo=UTC), days=31)
        probe(client, "RTD_5min", "ELAP_PACE-APND", datetime(2025, 9, 1, tzinfo=UTC), days=31)
        probe(client, "DAM", "ELAP_PACE-APND", edam)
        probe(client, "DAM", "DGAP_PACE-APND", edam)
        probe(client, "DAM", "ELAP_PACE-APND", datetime(2026, 10, 1, tzinfo=UTC))
        probe(client, "DAM", "TH_NP15_GEN-APND", datetime(2022, 1, 1, tzinfo=UTC), days=31)


if __name__ == "__main__":
    main()
