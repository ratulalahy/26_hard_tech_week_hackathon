"""EIA-930 hourly CO2 intensity, the carbon "truth" table (spec section 4, F3, F8).

Source: the per-BA workbooks in data/raw/eia930/ba_workbooks/{BA}.xlsx, sheet
"Published Hourly Data". Intensities there are lb CO2 per kWh; we store g/kWh
(x 453.592). The primary signal is the consumption-based intensity; the
production-based intensity is stored alongside. Both are `observed` EIA estimates
(EIA's own flow model, not a measured response to our load).

Time: the workbook's "UTC time" is hour-ending. `ts_utc` here is the hour start
(workbook time minus one hour).

Missing truth is explicit and never filled. The parsed table is a contiguous hourly
grid from the first to the last workbook hour, so an hour that is absent from the
workbook appears as a row with a null value and `null_reason == "missing_row"`.
`null_reason` describes the consumed-basis value (the primary signal); a negative
or unparseable production-basis value is also nulled, without its own reason.

    negative      the workbook value was below zero (EIA data-quality artefact)
    missing       the cell was empty
    non_numeric   the cell held text that is not a number
    missing_row   no workbook row for this hour

The stored parquet may include hours at or after the sealed test start; `load_carbon`
always drops them (gridpilot.splits.drop_sealed). `site_mask` is therefore computed
from sealed-safe data only, and the test-window mask is built by the test-evaluation
entry point.
"""

from __future__ import annotations

import os
from pathlib import Path

import polars as pl

from gridpilot.paths import PROCESSED_DIR, RAW_DIR
from gridpilot.splits import drop_sealed

LB_TO_G = 453.592
SHEET = "Published Hourly Data"
TIME_COL = "UTC time"
CONSUMED_COL = "CO2 Emissions Intensity for Consumed Electricity"
GENERATED_COL = "CO2 Emissions Intensity for Generated Electricity"

WORKBOOK_DIR = RAW_DIR / "eia930" / "ba_workbooks"
CARBON_PATH = PROCESSED_DIR / "carbon" / "carbon_hourly.parquet"
CORE_BAS = ("PACE", "CISO", "BPAT", "NEVP")

COLUMNS = ["ba", "ts_utc", "ci_consumed_g_kwh", "ci_generated_g_kwh", "null_reason"]


def _clean(raw: pl.Expr) -> tuple[pl.Expr, pl.Expr]:
    """(g/kWh value or null, reason or null) for a string column holding lb/kWh."""
    text = raw.str.strip_chars()
    num = text.cast(pl.Float64, strict=False)
    reason = (
        pl.when(text.is_null() | (text == "")).then(pl.lit("missing"))
        .when(num.is_null() | num.is_nan() | num.is_infinite()).then(pl.lit("non_numeric"))
        .when(num < 0).then(pl.lit("negative"))
    )
    value = pl.when(reason.is_null()).then(num * LB_TO_G)
    return value, reason


def parse_ba_workbook(path: Path, ba: str) -> pl.DataFrame:
    """One BA's hourly intensities as a contiguous hourly grid (see module docstring)."""
    raw = pl.read_excel(
        path, sheet_name=SHEET, engine="calamine",
        columns=[TIME_COL, GENERATED_COL, CONSUMED_COL],
        schema_overrides={GENERATED_COL: pl.Utf8, CONSUMED_COL: pl.Utf8},
    )
    cons, cons_reason = _clean(pl.col(CONSUMED_COL))
    gen, _ = _clean(pl.col(GENERATED_COL))
    rows = raw.select(
        (pl.col(TIME_COL).cast(pl.Datetime("us")).dt.replace_time_zone("UTC")
         - pl.duration(hours=1)).alias("ts_utc"),
        cons.alias("ci_consumed_g_kwh"),
        gen.alias("ci_generated_g_kwh"),
        cons_reason.alias("null_reason"),
    ).drop_nulls("ts_utc")
    if rows["ts_utc"].is_duplicated().any():
        raise ValueError(f"{ba}: duplicate UTC hours in {path.name}")
    grid = pl.select(pl.datetime_range(
        rows["ts_utc"].min(), rows["ts_utc"].max(), interval="1h", time_unit="us", time_zone="UTC",
    ).alias("ts_utc"))
    return (
        grid.join(rows, on="ts_utc", how="left", maintain_order="left")
        .with_columns(
            pl.lit(ba).alias("ba"),
            pl.when(pl.col("null_reason").is_null() & pl.col("ci_consumed_g_kwh").is_null())
            .then(pl.lit("missing_row")).otherwise(pl.col("null_reason")).alias("null_reason"),
        )
        .select(COLUMNS)
    )


def build_carbon(bas: tuple[str, ...] = CORE_BAS) -> Path:
    """Parse the BA workbooks and write carbon_hourly.parquet atomically (temp file, rename)."""
    frames = [parse_ba_workbook(WORKBOOK_DIR / f"{ba}.xlsx", ba) for ba in bas]
    out = pl.concat(frames).sort("ba", "ts_utc")
    CARBON_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CARBON_PATH.with_name(f".{CARBON_PATH.name}.{os.getpid()}.tmp")
    try:
        out.write_parquet(tmp)
        os.replace(tmp, CARBON_PATH)
    finally:
        tmp.unlink(missing_ok=True)
    return CARBON_PATH


def load_carbon(path: Path | None = None) -> pl.DataFrame:
    """The carbon truth table with every sealed-window hour dropped."""
    return drop_sealed(pl.read_parquet(path or CARBON_PATH))


def site_mask(carbon: pl.DataFrame) -> pl.DataFrame:
    """truth_ok per (ba, hour): False wherever the consumed-basis truth is null.

    The same mask applies to every policy (F3). Hours absent from `carbon` are not
    invented here; parse_ba_workbook already emits a row for every hour in range.
    """
    return carbon.select(
        "ba", "ts_utc", pl.col("ci_consumed_g_kwh").is_not_null().alias("truth_ok"),
    )
