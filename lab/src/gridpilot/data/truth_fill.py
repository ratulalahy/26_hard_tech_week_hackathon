"""F14.6 scoring truth fill (pre-registered; spec §15 F14.6, Task 7 amendment step 4).

For every BA and every UTC hour h in [start, end), the scoring truth is the first
available of:

1. EIA consumption-basis CI (`modeled`: EIA's estimated consumption-basis hourly CO₂
   intensity; spec §4, §11, F7);
2. EIA production-basis CI for the same hour (`modeled` substitute);
3. our EIA-930 fuel-mix CI for the same hour (`gridpilot.carbon.fuel_mix_ci`, the
   grid-profile formula over adjusted generation; `modeled`);
4. the mean of the tier-1 values at the same UTC hour over the 7 preceding days,
   h − 24 h … h − 168 h, counting only hours that have a tier-1 value (`modeled`).

Forecasts are never used as fill. Each hour records its tier. An hour with no value after
tier 4 keeps a null `ci_g_kwh` and a null `tier`; `fill_mask` closes exactly those hours
(the F3/F12.1 closure calendar), so the mask always comes from the same filled truth.

**Seal (F8).** Every function takes a `window` (`gridpilot.window.Window`, default
validation). Outside the test window: a range reaching past TEST_START raises, inputs are
read through `drop_sealed`, and an input frame holding a sealed row raises. With the test
window (test mode only, Stage 3 T11 B2) the bound is F_test and the inputs are read through
`gridpilot.seal.sealed_read`: the test carbon table and the EIA-930 balance table.

Output: `ba, ts_utc, ci_g_kwh, tier` (Utf8, datetime[us, UTC], Float64, Int8) on the full
hourly grid of [start, end) for every requested BA, sorted by ba then ts_utc. It is the
frame `gridpilot.eval.TruthTable` accepts.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

import polars as pl

from gridpilot import seal
from gridpilot.carbon import fuel_mix_ci
from gridpilot.data.eia930 import PARTITION_FUELS
from gridpilot.data.eia_co2 import CARBON_PATH, CARBON_TEST_REL, CORE_BAS
from gridpilot.paths import INTERIM_DIR
from gridpilot.splits import drop_sealed
from gridpilot.window import Window, resolve

BALANCE_PATH = INTERIM_DIR / "eia930" / "balance.parquet"
TIERS = (1, 2, 3, 4)
# EIA consumption-basis intensity is EIA's own estimate: modeled (lead ruling, spec §4,
# §11, F7), like every fill tier.
TIER_EVIDENCE = {1: "modeled", 2: "modeled", 3: "modeled", 4: "modeled"}
TIER_SOURCE = {
    1: "EIA's estimated consumption-basis hourly CO₂ intensity (BA workbook)",
    2: "EIA production-basis CO2 intensity, same hour (BA workbook)",
    3: "EIA-930 fuel-mix CI, same hour (adjusted generation x EIA direct factors)",
    4: "mean of tier-1 values at the same UTC hour over the 7 preceding days",
}
BASES = ("consumption", "production")
# Production-basis repricing (T10): the same tiers with production as tier 1.
TIER_SOURCE_PRODUCTION = {
    1: "EIA production-basis CO2 intensity (BA workbook)",
    2: "EIA's estimated consumption-basis hourly CO₂ intensity, same hour (BA workbook)",
    3: "EIA-930 fuel-mix CI, same hour (adjusted generation x EIA direct factors)",
    4: "mean of tier-1 (production-basis) values at the same UTC hour over the 7 preceding "
       "days",
}
SAME_HOUR_DAYS = 7
H = timedelta(hours=1)
SCHEMA = {"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"), "ci_g_kwh": pl.Float64,
          "tier": pl.Int8}


def _window(start: datetime, end: datetime, window: Window | None = None) -> Window:
    w = resolve(window, "truth fill")
    for name, t in (("start", start), ("end", end)):
        if not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None:
            raise ValueError(f"{name} must be a timezone-aware datetime, got {t!r}")
        if t.minute or t.second or t.microsecond:
            raise ValueError(f"{name} must be a UTC hour start, got {t}")
    if not end > start:
        raise ValueError(f"empty window [{start}, {end})")
    bound = w.read_end
    if start >= bound or end > bound:
        raise ValueError(f"truth fill window [{start}, {end}) reaches past the read bound "
                         f"{bound.isoformat()} (TEST_START outside test mode): the sealed window "
                         f"is never read (F8)")
    return w


def _no_sealed(frame: pl.DataFrame, what: str, window: Window | None = None) -> None:
    bound = resolve(window, what).read_end
    if frame.height and frame["ts_utc"].max() >= bound:
        raise ValueError(f"{what} holds a row at or after the read bound {bound.isoformat()} "
                         f"(a sealed-window row outside test mode); pass pre-seal input only "
                         f"(F8)")


FUEL_COLS = [f"gen_{f}_adj_mw" for f in PARTITION_FUELS]


def load_fuel_mix_ci(start: datetime, end: datetime, bas: Sequence[str] = CORE_BAS, *,
                     window: Window | None = None) -> pl.DataFrame:
    """Our fuel-mix CI (`ba, ts_utc, ci_g_kwh`) from the EIA-930 balance table over
    [start, end); the seal is applied in the lazy scan, so sealed rows never load. With the
    test window: through `sealed_read`."""
    w = _window(start, end, window)
    if w.is_test:
        s = seal.require_active("load_fuel_mix_ci(test)")
        frame = seal.sealed_read(
            s.data_path(seal.BALANCE_REL), purpose="F14.6 tier 3: EIA-930 fuel-mix CI (test)",
            columns=["ba", "ts_utc", *FUEL_COLS], time_range=(start, end),
            where=pl.col("ba").cast(pl.Utf8).is_in(list(bas)))
        return (frame.select(pl.col("ba").cast(pl.Utf8), "ts_utc",
                             fuel_mix_ci().cast(pl.Float64).alias("ci_g_kwh"))
                .sort("ba", "ts_utc"))
    lazy = (drop_sealed(pl.scan_parquet(BALANCE_PATH))
            .filter(pl.col("ba").cast(pl.Utf8).is_in(list(bas))
                    & (pl.col("ts_utc") >= start) & (pl.col("ts_utc") < end)))
    return (lazy.select(pl.col("ba").cast(pl.Utf8), "ts_utc",
                        fuel_mix_ci().cast(pl.Float64).alias("ci_g_kwh"))
            .collect().sort("ba", "ts_utc"))


def load_eia_carbon(start: datetime, end: datetime, bas: Sequence[str] = CORE_BAS, *,
                    window: Window | None = None) -> pl.DataFrame:
    """EIA consumption and production basis (`ba, ts_utc, ci_consumed_g_kwh,
    ci_generated_g_kwh`) over [start, end), seal applied in the scan. With the test window:
    the test carbon table through `sealed_read`."""
    w = _window(start, end, window)
    cols = ["ba", "ts_utc", "ci_consumed_g_kwh", "ci_generated_g_kwh"]
    if w.is_test:
        s = seal.require_active("load_eia_carbon(test)")
        return seal.sealed_read(
            s.data_path(CARBON_TEST_REL), purpose="F14.6 tiers 1-2 and 4: EIA carbon (test)",
            columns=cols, time_range=(start, end),
            where=pl.col("ba").is_in(list(bas))).sort("ba", "ts_utc")
    return (drop_sealed(pl.scan_parquet(CARBON_PATH))
            .filter(pl.col("ba").is_in(list(bas)) & (pl.col("ts_utc") >= start)
                    & (pl.col("ts_utc") < end))
            .select(*cols)
            .collect().sort("ba", "ts_utc"))


def fill_truth(
    start: datetime,
    end: datetime,
    bas: Sequence[str] = CORE_BAS,
    *,
    carbon: pl.DataFrame | None = None,
    fuel_ci: pl.DataFrame | None = None,
    basis: str = "consumption",
    window: Window | None = None,
) -> pl.DataFrame:
    """The F14.6 scoring truth over [start, end) (see the module docstring).

    `carbon` (ba, ts_utc, ci_consumed_g_kwh, ci_generated_g_kwh) and `fuel_ci` (ba, ts_utc,
    ci_g_kwh) default to the frozen snapshot. Tier 4 reads tier-1 values up to 7 days
    before `start`, so pass inputs from start − 7 d. `window` sets the read bound (default
    validation: TEST_START; test: F_test, inputs through `sealed_read`).

    `basis="production"` (Stage 3 T10 repricing; spec §10 check 6) applies the same tiers
    with production as tier 1: 1 production basis, 2 consumption basis (same hour), 3 our
    fuel-mix CI, 4 the 7-day same-hour mean of tier-1 (production) values.
    """
    if basis not in BASES:
        raise ValueError(f"basis must be one of {BASES}, got {basis!r}")
    w = _window(start, end, window)
    lo = start - SAME_HOUR_DAYS * 24 * H
    if carbon is None:
        carbon = load_eia_carbon(lo, end, bas, window=w)
    if fuel_ci is None:
        fuel_ci = load_fuel_mix_ci(start, end, bas, window=w)
    _no_sealed(carbon, "carbon", w)
    _no_sealed(fuel_ci, "fuel_ci", w)
    first, second = (("ci_consumed_g_kwh", "ci_generated_g_kwh") if basis == "consumption"
                     else ("ci_generated_g_kwh", "ci_consumed_g_kwh"))
    c = carbon.select(pl.col("ba").cast(pl.Utf8), "ts_utc",
                      pl.col(first).cast(pl.Float64).alias("t1"),
                      pl.col(second).cast(pl.Float64).alias("t2"))
    f = fuel_ci.select(pl.col("ba").cast(pl.Utf8), "ts_utc",
                       pl.col("ci_g_kwh").cast(pl.Float64).alias("t3"))
    for name, frame in (("carbon", c), ("fuel_ci", f)):
        if frame.select(pl.struct("ba", "ts_utc").is_duplicated().any()).item():
            raise ValueError(f"{name} has duplicate (ba, ts_utc) rows")
    # Non-finite values count as absent.
    finite = [pl.when(pl.col(k).is_finite()).then(pl.col(k)).otherwise(None).alias(k)
              for k in ("t1", "t2")]
    c = c.with_columns(finite)
    f = f.with_columns(pl.when(pl.col("t3").is_finite()).then(pl.col("t3"))
                       .otherwise(None).alias("t3"))

    hours = pl.datetime_range(lo, end - H, interval="1h", time_unit="us", time_zone="UTC",
                              eager=True).alias("ts_utc")
    grid = pl.DataFrame({"ba": list(bas)}, schema={"ba": pl.Utf8}).join(
        hours.to_frame(), how="cross")
    g = (grid.join(c, on=["ba", "ts_utc"], how="left")
         .join(f, on=["ba", "ts_utc"], how="left")
         .sort("ba", "ts_utc"))
    # Dense grid per BA, so a shift of 24k rows is exactly 24k hours earlier.
    lags = [pl.col("t1").shift(24 * k).over("ba") for k in range(1, SAME_HOUR_DAYS + 1)]
    g = g.with_columns(pl.mean_horizontal(lags).alias("t4"))
    tier = (pl.when(pl.col("t1").is_not_null()).then(1)
            .when(pl.col("t2").is_not_null()).then(2)
            .when(pl.col("t3").is_not_null()).then(3)
            .when(pl.col("t4").is_not_null()).then(4))
    out = (g.filter(pl.col("ts_utc") >= start)
           .select("ba", "ts_utc",
                   pl.coalesce("t1", "t2", "t3", "t4").alias("ci_g_kwh"),
                   tier.alias("tier"))
           .cast(SCHEMA)
           .sort("ba", "ts_utc"))
    if out["ts_utc"].max() >= w.read_end:  # belt and braces
        raise AssertionError("truth fill produced an hour past the read bound")
    return out


def fill_mask(filled: pl.DataFrame) -> pl.DataFrame:
    """`ba, ts_utc, truth_ok`: closed exactly where no value is left after tier 4."""
    return filled.select("ba", "ts_utc", pl.col("ci_g_kwh").is_not_null().alias("truth_ok"))


def tier_counts(filled: pl.DataFrame) -> dict[str, dict[str, int]]:
    """Hours per tier per BA, plus `missing` (no value after tier 4)."""
    out: dict[str, dict[str, int]] = {}
    for ba in filled["ba"].unique().sort().to_list():
        t = filled.filter(pl.col("ba") == ba)["tier"]
        row = {str(k): int((t == k).sum()) for k in TIERS}
        row["missing"] = int(t.null_count())
        out[ba] = row
    return out


def missing_hours(filled: pl.DataFrame) -> list[dict]:
    """Every (ba, hour) still missing after tier 4, as ISO strings (expect none)."""
    m = filled.filter(pl.col("ci_g_kwh").is_null())
    return [{"ba": b, "ts_utc": t.isoformat()} for b, t in m.select("ba", "ts_utc").iter_rows()]
