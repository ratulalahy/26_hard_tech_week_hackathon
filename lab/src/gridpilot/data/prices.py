"""Wholesale electricity prices: CAISO OASIS LMPs and ERCOT settlement point prices.

Raw files are the zips in data/raw/prices/<iso>/ (see data/manifests/prices_<iso>.json and
lab/scripts/recon_prices_download.py). Loaders return a tidy table, one row per
interval x node, with `ts_utc` as the interval start in UTC. Values are `observed`.

The sealed test window applies: call gridpilot.splits.drop_sealed(df, "ts_utc") before any
statistic, figure or printed sample. Completeness checks (row counts, missing hours) are
the only exception, and `completeness()` below reports only those.

Coverage notes (recon, 2026-10-27):
- CAISO OASIS keeps a rolling ~39 months: the earliest DAM day online was 2023-07-16.
- PACE (ELAP_PACE-APND, DGAP_PACE-APND) has 15-minute WEIM real-time prices throughout,
  but day-ahead prices only since EDAM go-live (first operating day with data
  2026-04-30), which is inside the sealed window.
- ERCOT hub prices come from the yearly NP4-180-ER (DAM) and NP6-785-ER (RTM) archives.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import polars as pl

from gridpilot.paths import RAW_DIR

CAISO_DIR = RAW_DIR / "prices" / "caiso"
ERCOT_DIR = RAW_DIR / "prices" / "ercot"

CAISO_HUBS = ["TH_NP15_GEN-APND", "TH_SP15_GEN-APND", "TH_ZP26_GEN-APND"]
PACE_NODES = ["ELAP_PACE-APND", "DGAP_PACE-APND"]
ERCOT_HUBS = ["HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST", "HB_HUBAVG", "HB_BUSAVG"]

PRICE_COLUMNS = ["ts_utc", "iso", "market", "node", "interval_min", "lmp", "energy",
                 "congestion", "loss", "ghg"]
_LMP_TYPES = {"LMP": "lmp", "MCE": "energy", "MCC": "congestion", "MCL": "loss", "MGHG": "ghg"}
_INTERVAL_MIN = {"dam": 60, "rtpd": 15, "rtm": 15}


# ------------------------------------------------------------------------- CAISO


def read_oasis_zip(path: Path) -> pl.DataFrame | None:
    """One OASIS SingleZip (CSV inside). Returns None for an OASIS 'no data' reply."""
    z = zipfile.ZipFile(path)
    names = z.namelist()
    if not names or any(n.endswith(".xml") for n in names):
        return None
    frames = [pl.read_csv(z.read(n), infer_schema_length=0) for n in names]
    return pl.concat(frames, how="diagonal_relaxed")


def load_caiso(market: str = "dam", groups: tuple[str, ...] = ("core", "weim"),
               nodes: list[str] | None = None) -> pl.DataFrame:
    """CAISO LMPs from the raw OASIS zips. market: 'dam' (hourly) or 'rtpd' (15-minute FMM)."""
    frames = []
    for group in groups:
        for path in sorted((CAISO_DIR / market / group).glob("*.zip")):
            df = read_oasis_zip(path)
            if df is None:
                continue
            price_col = next(c for c in ("MW", "PRC", "VALUE") if c in df.columns)
            frames.append(df.select(
                pl.col("INTERVALSTARTTIME_GMT").str.to_datetime("%Y-%m-%dT%H:%M:%S%:z",
                                                                time_zone="UTC").alias("ts_utc"),
                pl.col("NODE").alias("node"),
                pl.col("LMP_TYPE").alias("lmp_type"),
                pl.col(price_col).cast(pl.Float64).alias("price"),
            ))
    if not frames:
        return pl.DataFrame(schema={c: pl.Float64 for c in PRICE_COLUMNS})
    long = pl.concat(frames).unique(["ts_utc", "node", "lmp_type"], keep="first")
    if nodes:
        long = long.filter(pl.col("node").is_in(nodes))
    wide = long.pivot(on="lmp_type", index=["ts_utc", "node"], values="price",
                      aggregate_function="first").rename(
        {k: v for k, v in _LMP_TYPES.items() if k in long["lmp_type"].unique().to_list()})
    for col in _LMP_TYPES.values():
        if col not in wide.columns:
            wide = wide.with_columns(pl.lit(None, dtype=pl.Float64).alias(col))
    return wide.with_columns(
        pl.lit("caiso").alias("iso"), pl.lit(market).alias("market"),
        pl.lit(_INTERVAL_MIN[market]).alias("interval_min"),
    ).select(PRICE_COLUMNS).sort("node", "ts_utc")


# ------------------------------------------------------------------------- ERCOT


def _read_ercot_zip(path: Path) -> pl.DataFrame:
    import pandas as pd  # openpyxl engine; the archives are xlsx with one sheet per month

    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith(".xlsx"))
        sheets = pd.read_excel(io.BytesIO(z.read(name)), sheet_name=None, dtype=str)
    return pl.concat([pl.from_pandas(s) for s in sheets.values()], how="diagonal_relaxed")


def load_ercot(market: str = "dam", points: list[str] | None = None,
               years: list[int] | None = None) -> pl.DataFrame:
    """ERCOT hub/load-zone settlement point prices. market: 'dam' (hourly) or 'rtm' (15-min).

    Delivery times are hour-ending Central Prevailing Time; the repeated hour at the fall
    DST change is flagged 'Y' and mapped to the later (standard-time) instant."""
    points = points or ERCOT_HUBS
    frames = []
    for path in sorted((ERCOT_DIR / market).glob("*.zip")):
        year = int(path.stem.rsplit("_", 1)[-1])
        if years and year not in years:
            continue
        raw = _read_ercot_zip(path)
        point_col = "Settlement Point" if "Settlement Point" in raw.columns else "Settlement Point Name"
        raw = raw.filter(pl.col(point_col).is_in(points))
        if market == "dam":
            he = pl.col("Hour Ending").str.slice(0, 2).cast(pl.Int32)
            minute = pl.lit(0)
        else:
            he = pl.col("Delivery Hour").cast(pl.Float64).cast(pl.Int32)
            minute = (pl.col("Delivery Interval").cast(pl.Float64).cast(pl.Int32) - 1) * 15
        start_local = (pl.col("Delivery Date").str.to_date("%m/%d/%Y").cast(pl.Datetime("us"))
                       + pl.duration(hours=he - 1, minutes=minute))
        amb = pl.when(pl.col("Repeated Hour Flag") == "Y").then(pl.lit("latest")).otherwise(
            pl.lit("earliest"))
        frames.append(raw.select(
            start_local.dt.replace_time_zone("America/Chicago", ambiguous=amb,
                                             non_existent="null")
            .dt.convert_time_zone("UTC").alias("ts_utc"),
            pl.col(point_col).alias("node"),
            pl.col("Settlement Point Price").cast(pl.Float64).alias("lmp"),
        ))
    df = pl.concat(frames).drop_nulls("ts_utc").unique(["ts_utc", "node"], keep="last")
    for col in ("energy", "congestion", "loss", "ghg"):
        df = df.with_columns(pl.lit(None, dtype=pl.Float64).alias(col))
    return df.with_columns(
        pl.lit("ercot").alias("iso"), pl.lit(market).alias("market"),
        pl.lit(_INTERVAL_MIN[market]).alias("interval_min"),
    ).select(PRICE_COLUMNS).sort("node", "ts_utc")


# ------------------------------------------------------------------------ helpers


def to_hourly(df: pl.DataFrame) -> pl.DataFrame:
    """Average sub-hourly prices to hours (UTC hour start). Hourly input passes through."""
    return (
        df.with_columns(pl.col("ts_utc").dt.truncate("1h"))
        .group_by("ts_utc", "iso", "market", "node")
        .agg(pl.col("lmp").mean(), pl.len().alias("n_intervals"))
        .sort("node", "ts_utc")
    )


def completeness(hourly: pl.DataFrame, start, end) -> pl.DataFrame:
    """Rows and missing hours per node in [start, end). Counts only, no price values,
    so it is safe on the sealed test window."""
    expected = int((end - start).total_seconds() // 3600)
    window = hourly.filter((pl.col("ts_utc") >= start) & (pl.col("ts_utc") < end))
    return window.group_by("node").agg(
        pl.len().alias("rows"),
        pl.col("ts_utc").min().alias("first"),
        pl.col("ts_utc").max().alias("last"),
    ).with_columns(
        pl.lit(expected).alias("expected_hours"),
        (pl.lit(expected) - pl.col("rows")).alias("missing_hours"),
    ).sort("node")
