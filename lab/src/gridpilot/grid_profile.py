"""The dashboard's grid context (Task 8 amendment): `results/grid-profile.json`.

Validation year only, [2024-11-01T00Z, 2025-10-24T00Z) (eval_start to F); the sealed test
window is never read. Every number is a §11 envelope (`gridpilot.results.env`).

Contents, all on **America/Denver** clock hours (one clock for every BA, because the job
arrives in Utah and the views compare sites at the same instant):
- `ci.by_ba[BA]` for the four core sites: EIA consumption-basis CO2 intensity, **tier 1 only**
  (rows where EIA publishes a consumed value; no fills), as a 12 x 24 month x hour mean, the
  hour counts behind each cell, the all-days 24-hour profile and the year mean. `modeled`:
  EIA's consumption-basis intensity is an EIA estimate (spec §4, §11, F7; lead ruling R3).
  The hour counts are `measured`. The PACE row is the month x hour heatmap.
- `reference.us_avg_ci`: the US average generation-basis CO2 intensity for 2024, the colour
  scale's midpoint (785 lb CO2/MWh x 0.453592 = 356 g/kWh). `observed` (EIA's published
  annual figure; lead ruling R4).
- `pace_july_weekday`: Utah's mean July 2025 weekday (23 days, holidays included): adjusted
  demand with isolated spikes removed (`add_demand_clean`), solar, wind and net load
  (= demand − wind − solar). `observed`.
- `pace_top100_net_load`: where the validation year's 100 highest PACE net-load hours fall,
  as month x hour counts. `observed`.
- `context_year_mean_ci`: other western BAs' year mean of our EIA-930 fuel-mix intensity
  (production basis, `gridpilot.carbon.fuel_mix_ci`). `modeled`; map context only, never
  compared with the core sites' consumption basis.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import polars as pl

from gridpilot.carbon import fuel_mix_ci
from gridpilot.data.eia930 import PARTITION_FUELS, add_demand_clean
from gridpilot.results import SCHEMA_VERSION, env
from gridpilot.splits import TEST_START, drop_sealed

TZ_NAME = "America/Denver"
TZ = ZoneInfo(TZ_NAME)
WINDOW = (datetime(2024, 11, 1, tzinfo=UTC), datetime(2025, 10, 24, tzinfo=UTC))
MONTHS = [f"{y}-{m:02d}" for y, m in [(2024, 11), (2024, 12)] + [(2025, k) for k in range(1, 11)]]
CORE_BAS = ("PACE", "BPAT", "CISO", "NEVP")
# Western BAs drawn on the dashboard map (the gallery's hex map), excluding the core sites.
CONTEXT_BAS = ("AVA", "AZPS", "BANC", "CHPD", "DOPD", "EPE", "GCPD", "IID", "IPCO", "LDWP",
               "NWMT", "PACW", "PGE", "PNM", "PSCO", "PSEI", "SCL", "SRP", "TEPC", "TIDC",
               "TPWR", "WACM", "WALC", "WAUW")
TOP_K = 100
PROV = "grid-profile"
JULY_MONTH = "2025-07"  # the month of the weekday-load profile (America/Denver)
US_AVG_LB_PER_MWH = 785.0  # EIA, United States Electricity Profile 2024 (CO2 emission rate)
LB_TO_KG = 0.453592
US_AVG_SOURCE = ("EIA United States Electricity Profile 2024, "
                 "https://www.eia.gov/electricity/state/unitedstates/")
NO_HOURS = "no tier-1 hours in this cell of the validation window"


def check_window(start: datetime, end: datetime) -> None:
    if not end > start:
        raise ValueError(f"empty window [{start}, {end})")
    if end > TEST_START or start >= TEST_START:
        raise ValueError(f"window [{start}, {end}) reaches the seal at {TEST_START}")


def _guard(frame: pl.DataFrame, name: str) -> pl.DataFrame:
    """Refuse any sealed row; keep only the window."""
    if frame.height and frame["ts_utc"].max() >= TEST_START:
        raise ValueError(f"{name}: input holds sealed rows (ts >= {TEST_START})")
    s, e = WINDOW
    return frame.filter((pl.col("ts_utc") >= s) & (pl.col("ts_utc") < e))


def _local(frame: pl.DataFrame) -> pl.DataFrame:
    lt = pl.col("ts_utc").dt.convert_time_zone(TZ_NAME)
    return frame.with_columns(
        lt.dt.strftime("%Y-%m").alias("month"), lt.dt.hour().alias("hour"),
        lt.dt.date().alias("date"), lt.dt.weekday().alias("dow"))


DECIMALS = 4  # exported means are rounded so re-exports are byte-stable (parallel sums vary in the last bit)


def _r(v):
    return round(v, DECIMALS) if isinstance(v, float) else v


def _grid(agg: pl.DataFrame, col: str, fill) -> list[list]:
    look = {(r["month"], r["hour"]): _r(r[col]) for r in agg.iter_rows(named=True)}
    return [[look.get((m, h), fill) for h in range(24)] for m in MONTHS]


def typical_day_by_month(carbon: pl.DataFrame, ba: str) -> tuple[list[list], list[list]]:
    """12 x 24 mean tier-1 consumed CI (None where a cell has no hours) and the hour counts."""
    c = _local(carbon.filter((pl.col("ba") == ba) & pl.col("ci_consumed_g_kwh").is_not_null()))
    agg = c.group_by("month", "hour").agg(pl.col("ci_consumed_g_kwh").mean().alias("v"),
                                          pl.len().alias("n"))
    return _grid(agg, "v", None), _grid(agg, "n", 0)


def day_profile(carbon: pl.DataFrame, ba: str) -> tuple[list, list]:
    c = _local(carbon.filter((pl.col("ba") == ba) & pl.col("ci_consumed_g_kwh").is_not_null()))
    agg = c.group_by("hour").agg(pl.col("ci_consumed_g_kwh").mean().alias("v"),
                                 pl.len().alias("n"))
    look = {r["hour"]: (_r(r["v"]), r["n"]) for r in agg.iter_rows(named=True)}
    return [look.get(h, (None, 0))[0] for h in range(24)], [look.get(h, (None, 0))[1]
                                                             for h in range(24)]


def _net_load(balance: pl.DataFrame, ba: str = "PACE") -> pl.DataFrame:
    b = add_demand_clean(balance.filter(pl.col("ba") == ba))
    return _local(b.with_columns(
        (pl.col("demand_clean_mw") - pl.col("gen_wind_adj_mw").fill_null(0)
         - pl.col("gen_solar_adj_mw").fill_null(0)).alias("net_load_mw")))


def july_weekday_profile(balance: pl.DataFrame) -> dict:
    b = _net_load(balance).filter((pl.col("month") == JULY_MONTH) & (pl.col("dow") <= 5))
    agg = b.group_by("hour").agg(
        pl.col("demand_clean_mw").mean().alias("demand_mw"),
        pl.col("net_load_mw").mean().alias("net_load_mw"),
        pl.col("gen_solar_adj_mw").fill_null(0).mean().alias("solar_mw"),
        pl.col("gen_wind_adj_mw").fill_null(0).mean().alias("wind_mw")).sort("hour")
    look = {r["hour"]: r for r in agg.iter_rows(named=True)}
    out = {k: [_r(float(look[h][k])) if h in look and look[h][k] is not None else None
               for h in range(24)] for k in ("demand_mw", "net_load_mw", "solar_mw", "wind_mw")}
    out["n_days"] = b["date"].n_unique()
    return out


def top_k_net_load_counts(balance: pl.DataFrame, k: int = TOP_K) -> list[list[int]]:
    b = _net_load(balance).filter(pl.col("net_load_mw").is_not_null())
    top = b.sort(["net_load_mw", "ts_utc"], descending=[True, False]).head(k)
    agg = top.group_by("month", "hour").agg(pl.len().alias("n"))
    return _grid(agg, "n", 0)


def context_year_means(balance: pl.DataFrame) -> dict[str, float | None]:
    b = balance.filter(pl.col("ba").is_in(CONTEXT_BAS)).with_columns(fuel_mix_ci().alias("ci"))
    agg = b.group_by("ba").agg(pl.col("ci").mean().alias("v"))
    return {r["ba"]: _r(r["v"]) for r in agg.sort("ba").iter_rows(named=True)}


def _mean(vals, ns):
    tot = sum(v * n for v, n in zip(vals, ns, strict=True) if v is not None)
    n = sum(ns)
    return _r(tot / n) if n else None


def build_profile(carbon: pl.DataFrame, balance: pl.DataFrame) -> dict:
    """The enveloped grid-profile artifact from (carbon, balance) frames; validation year."""
    check_window(*WINDOW)
    carbon = _guard(carbon, "carbon")
    balance = _guard(balance, "balance")
    s, e = WINDOW
    by_ba = {}
    for ba in CORE_BAS:
        vals, counts = typical_day_by_month(carbon, ba)
        day, n = day_profile(carbon, ba)
        has_null = any(v is None for row in vals for v in row)
        pid = f"{PROV}:ci:{ba}"
        ym = _mean(day, n)
        by_ba[ba] = {
            "month_hour": env(vals, "g/kWh", "modeled", f"{pid}:month_hour",
                              reason=NO_HOURS if has_null else None),
            "month_hour_hours": env(counts, "hours", "measured", f"{pid}:month_hour_n"),
            "day": env(day, "g/kWh", "modeled", f"{pid}:day",
                       reason=NO_HOURS if any(v is None for v in day) else None),
            "year_mean": env(ym, "g/kWh", "modeled", f"{pid}:year_mean",
                             status="ok" if ym is not None else "unavailable",
                             reason=None if ym is not None else NO_HOURS),
            "n_hours": env(sum(n), "hours", "measured", f"{pid}:n_hours"),
        }
    jul = july_weekday_profile(balance)
    jnull = "no July weekday rows in the window"
    jp = {k: env(jul[k], "MW", "observed", f"{PROV}:pace_july:{k}",
                 reason=jnull if any(v is None for v in jul[k]) else None)
          for k in ("demand_mw", "net_load_mw", "solar_mw", "wind_mw")}
    counts = top_k_net_load_counts(balance)
    ctx = context_year_means(balance)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "grid-profile",
        "window": {"start": s.isoformat().replace("+00:00", "Z"),
                   "end": e.isoformat().replace("+00:00", "Z"),
                   "name": "validation year (eval_start to F); the test year is sealed"},
        "tz_display": TZ_NAME,
        "months": MONTHS,
        "hour_index": "index i of every 24-value series is the America/Denver clock hour i",
        "reference": {
            "us_avg_ci": env(US_AVG_LB_PER_MWH * LB_TO_KG, "g/kWh", "observed", US_AVG_SOURCE),
            "note": "US average CO2 intensity of generation, 2024 (785 lb/MWh); the colour "
                    "scale's midpoint, a national reference, not a consumption-basis value",
        },
        "ci": {
            "source": "EIA consumption-basis CO2 intensity (BA workbooks), tier 1 only: hours "
                      "EIA publishes; no fills. An EIA estimate, hence modeled",
            "by_ba": by_ba,
        },
        "pace_july_weekday": {
            "month": JULY_MONTH,  # the dashboard's load label reads this (T9 C8)
            "definition": "mean over July 2025 weekdays (America/Denver; holidays included) of "
                          "EIA-930 adjusted demand (isolated spikes removed), solar and wind; "
                          "net load = demand − wind − solar",
            "n_days": env(jul["n_days"], "days", "measured", f"{PROV}:pace_july:n_days"),
            **jp,
        },
        "pace_top100_net_load": {
            "definition": f"the {TOP_K} highest PACE net-load hours of the window, counted by "
                          "America/Denver month and hour",
            "k": env(TOP_K, "hours", "assumed", f"{PROV}:top100:k"),
            "counts_month_hour": env(counts, "hours", "observed", f"{PROV}:top100:counts"),
        },
        "context_year_mean_ci": {
            "definition": "unweighted hourly mean of our EIA-930 fuel-mix intensity (production "
                          "basis, adjusted generation x EIA direct factors); map context only",
            "by_ba": {ba: env(v, "g/kWh", "modeled", f"{PROV}:context:{ba}",
                              status="ok" if v is not None else "unavailable",
                              reason=None if v is not None else "no fuel-mix hours")
                      for ba, v in ctx.items()},
        },
    }


def load_inputs() -> tuple[pl.DataFrame, pl.DataFrame]:
    """Read the carbon and balance tables through the seal, restricted to the window."""
    from gridpilot.data.eia_co2 import CARBON_PATH
    from gridpilot.data.truth_fill import BALANCE_PATH

    s, e = WINDOW
    win = (pl.col("ts_utc") >= s) & (pl.col("ts_utc") < e)
    carbon = (drop_sealed(pl.scan_parquet(CARBON_PATH)).filter(win)
              .select("ba", "ts_utc", "ci_consumed_g_kwh").collect())
    cols = ["ba", "ts_utc", "demand_adj_mw"] + [f"gen_{f}_adj_mw" for f in PARTITION_FUELS]
    balance = (drop_sealed(pl.scan_parquet(BALANCE_PATH)).filter(win)
               .filter(pl.col("ba").cast(pl.Utf8).is_in(("PACE",) + CONTEXT_BAS))
               .select(cols).with_columns(pl.col("ba").cast(pl.Utf8)).collect())
    return carbon, balance
