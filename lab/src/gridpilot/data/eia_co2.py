"""EIA-930 hourly CO2 intensity, the carbon "truth" table (spec section 4, F3, F8).

Source: the per-BA workbooks in data/raw/eia930/ba_workbooks/{BA}.xlsx, sheet
"Published Hourly Data". Intensities there are lb CO2 per kWh; we store g/kWh
(x 453.592). The primary signal is the consumption-based intensity; the
production-based intensity is stored alongside. Both are EIA's estimated consumption- and
production-basis hourly CO₂ intensity: modeled (D-055; EIA's own flow model, not a measured
response to our load).

Time: the workbook's "UTC time" is hour-ending. `ts_utc` here is the hour start
(workbook time minus one hour). A row with a null or unparseable time raises.

Missing truth is explicit and never filled. The parsed table is a contiguous hourly
grid from the first to the last workbook hour, so an hour that is absent from the
workbook appears as a row with null values and reason `missing_row`. Each basis has
its own reason column (`null_reason` for consumed, `null_reason_generated` for
production); both use the same vocabulary:

    negative      the workbook value was below zero (EIA data-quality artefact)
    missing       the cell was empty
    non_numeric   the cell held text that is not a finite number (text, nan, inf)
    missing_row   no workbook row for this hour

Seal (F8): `build_carbon` truncates at TEST_START before writing, so the stored
parquet holds no sealed-window row. Sealed-window truth is not produced here; the
logged test-evaluation entry point will build it into a separate path. `load_carbon`
also applies `drop_sealed`, as a second guard.

`site_mask` is closed by default: any (ba, hour) with no carbon row is not ok.
Lineage is written next to the parquet as `carbon_hourly.meta.json`.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from gridpilot.paths import PROCESSED_DIR, RAW_DIR
from gridpilot.splits import TEST_START, drop_sealed

# The exact factor is 453.59237 g/lb; the spec pins 453.592, so we use that.
LB_TO_G = 453.592
SHEET = "Published Hourly Data"
TIME_COL = "UTC time"
CONSUMED_COL = "CO2 Emissions Intensity for Consumed Electricity"
GENERATED_COL = "CO2 Emissions Intensity for Generated Electricity"

WORKBOOK_DIR = RAW_DIR / "eia930" / "ba_workbooks"
CARBON_PATH = PROCESSED_DIR / "carbon" / "carbon_hourly.parquet"
META_NAME = "carbon_hourly.meta.json"
CORE_BAS = ("PACE", "CISO", "BPAT", "NEVP")

COLUMNS = ["ba", "ts_utc", "ci_consumed_g_kwh", "ci_generated_g_kwh", "null_reason",
           "null_reason_generated"]


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
    if raw.schema[TIME_COL] == pl.Utf8:  # a text cell made the column text: parse, else raise below
        time = pl.col(TIME_COL).str.to_datetime(time_unit="us", strict=False)
    else:
        time = pl.col(TIME_COL).cast(pl.Datetime("us"), strict=False)
    cons, cons_reason = _clean(pl.col(CONSUMED_COL))
    gen, gen_reason = _clean(pl.col(GENERATED_COL))
    rows = raw.select(
        (time.dt.replace_time_zone("UTC") - pl.duration(hours=1)).alias("ts_utc"),
        cons.alias("ci_consumed_g_kwh"),
        gen.alias("ci_generated_g_kwh"),
        cons_reason.alias("null_reason"),
        gen_reason.alias("null_reason_generated"),
    )
    if rows["ts_utc"].null_count():
        raise ValueError(f"{ba}: {rows['ts_utc'].null_count()} rows with a null or "
                         f"unparseable '{TIME_COL}' in {path.name}")
    if rows["ts_utc"].is_duplicated().any():
        raise ValueError(f"{ba}: duplicate UTC hours in {path.name}")
    grid = pl.select(pl.datetime_range(
        rows["ts_utc"].min(), rows["ts_utc"].max(), interval="1h", time_unit="us", time_zone="UTC",
    ).alias("ts_utc"))
    absent = pl.lit("missing_row")
    return (
        grid.join(rows.with_columns(pl.lit(True).alias("_present")), on="ts_utc", how="left",
                  maintain_order="left")
        .with_columns(
            pl.lit(ba).alias("ba"),
            pl.when(pl.col("_present").is_null()).then(absent)
            .otherwise(pl.col("null_reason")).alias("null_reason"),
            pl.when(pl.col("_present").is_null()).then(absent)
            .otherwise(pl.col("null_reason_generated")).alias("null_reason_generated"),
        )
        .select(COLUMNS)
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_carbon(bas: tuple[str, ...] = CORE_BAS) -> Path:
    """Parse the BA workbooks and write carbon_hourly.parquet plus its lineage sidecar.

    Rows at or after TEST_START are dropped before writing. Both files are written
    atomically (temp file, then rename); on failure the previous files are untouched.
    """
    sources = {ba: WORKBOOK_DIR / f"{ba}.xlsx" for ba in bas}
    frames = [parse_ba_workbook(p, ba) for ba, p in sources.items()]
    out = drop_sealed(pl.concat(frames).sort("ba", "ts_utc"))
    parquet, meta = CARBON_PATH, CARBON_PATH.with_name(META_NAME)
    parquet.parent.mkdir(parents=True, exist_ok=True)
    tmp_parquet = parquet.with_name(f".{parquet.name}.{os.getpid()}.tmp")
    tmp_meta = meta.with_name(f".{meta.name}.{os.getpid()}.tmp")
    try:
        out.write_parquet(tmp_parquet)
        lineage = {
            "evidence": "modeled",  # D-055: EIA's estimate, not an observation
            "source_workbooks_sha256": {f"{ba}.xlsx": _sha256(p) for ba, p in sources.items()},
            "sheet": SHEET,
            "unit": "lb/kWh",
            "g_per_lb_factor": LB_TO_G,  # exact is 453.59237; the spec pins 453.592
            "time_shift": "UTC end -> hour-start (-1h)",
            "cutoff_test_start": TEST_START.isoformat(),
            "built_at": datetime.now(UTC).isoformat(),
            "rows": out.height,
            "ts_utc_max": out["ts_utc"].max().isoformat(),
            "output_sha256": _sha256(tmp_parquet),
        }
        tmp_meta.write_text(json.dumps(lineage, indent=2) + "\n")
        os.replace(tmp_parquet, parquet)
        os.replace(tmp_meta, meta)
    finally:
        tmp_parquet.unlink(missing_ok=True)
        tmp_meta.unlink(missing_ok=True)
    return parquet


def load_carbon(path: Path | None = None) -> pl.DataFrame:
    """The carbon truth table with every sealed-window hour dropped."""
    return drop_sealed(pl.read_parquet(path or CARBON_PATH))


def site_mask(
    carbon: pl.DataFrame,
    start: datetime | None = None,
    end: datetime | None = None,
    bas: tuple[str, ...] | list[str] | None = None,
) -> pl.DataFrame:
    """truth_ok for every (ba, hour-start) in [start, end), closed by default (F3).

    truth_ok is False where the consumed-basis truth is null AND wherever `carbon` has
    no row for the key (hour outside a BA's stored range, or a BA with no rows). Defaults:
    `bas` = the BAs present in `carbon`, `start` = earliest hour, `end` = latest hour + 1 h.
    A window reaching TEST_START raises: the sealed window has no truth here.
    """
    if bas is None:
        bas = carbon["ba"].unique().sort().to_list()
    if carbon.height:
        start = start or carbon["ts_utc"].min()
        end = end or carbon["ts_utc"].max() + timedelta(hours=1)
    if start is None or end is None:
        raise ValueError("site_mask needs start and end when carbon is empty")
    if end > TEST_START:
        raise ValueError(f"site_mask window ends {end}, after TEST_START {TEST_START}")
    hours = pl.select(pl.datetime_range(
        start, end - timedelta(hours=1), interval="1h", time_unit="us", time_zone="UTC",
    ).alias("ts_utc"))
    grid = pl.DataFrame({"ba": list(bas)}, schema={"ba": pl.Utf8}).join(hours, how="cross")
    ok = carbon.select("ba", "ts_utc", pl.col("ci_consumed_g_kwh").is_not_null().alias("truth_ok"))
    return (
        grid.join(ok, on=["ba", "ts_utc"], how="left")
        .with_columns(pl.col("truth_ok").fill_null(False))
        .select("ba", "ts_utc", "truth_ok")
        .sort("ba", "ts_utc")
    )
