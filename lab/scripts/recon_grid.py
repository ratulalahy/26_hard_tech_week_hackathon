"""EIA-930 data recon for the experiment design (docs/data-profile/grid.md).

Train + validation only: every statistic, figure and sample is computed on
``drop_sealed(balance)``. The sealed test window [2025-11-01Z, 2026-11-01Z) is touched once,
in ``test_window_completeness``, which returns row counts and missing hours and nothing else.

Usage: cd lab && uv run --with fastexcel python scripts/recon_grid.py [OUT_DIR]
Tables (markdown/CSV/JSON) go to OUT_DIR (default: a scratch dir); figures go to
docs/data-profile/figures/grid/.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from gridpilot.carbon import (
    EF_G_KWH,
    EF_OTHER_SENS_G_KWH,
    LB_TO_G,
    fuel_co2_kg,
    fuel_gen_total,
)
from gridpilot.data.eia930 import (
    INTERIM_EIA_DIR,
    PARTITION_FUELS,
    RAW_EIA_DIR,
    add_demand_clean,
)
from gridpilot.paths import REPO_ROOT
from gridpilot.splits import TEST_END, TEST_START, VALIDATION_START, drop_sealed

FIG_DIR = REPO_ROOT / "docs/data-profile/figures/grid"
OUT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/recon_grid")
CANDIDATES = ["PACE", "CISO", "ERCO", "BPAT", "PJM", "MISO", "SWPP", "NYIS", "ISNE", "SOCO",
              "FPL", "TVA", "DUK", "AZPS", "NEVP", "PSCO", "IPCO", "PACW"]
# EIA reports MISO in EST all year; its load is mostly in Central time, so local-clock profiles
# use America/Chicago for MISO. Every other BA uses the offset published on each row.
TZ_OVERRIDE = {"MISO": "America/Chicago"}
FULL_YEARS = list(range(2019, 2025))  # complete calendar years before the validation start
VAL_START, VAL_END = VALIDATION_START, TEST_START  # validation year: 2024-11-01 .. 2025-11-01
COMPLETENESS_CUTOFF = datetime(2026, 10, 25, tzinfo=UTC)  # last full day before retrieval

# Direct (combustion) CO2 factors, EIA FAQ "How much carbon dioxide is produced per kilowatthour
# of U.S. electricity generation?" (https://www.eia.gov/tools/faqs/faq.php?id=74&t=11), data
# year 2023, utility-scale incl. CHP: coal 2.31, natural gas 0.96, petroleum 2.46, all sources
# 0.81 lb CO2/kWh. 1 lb = 453.592 g. Non-fossil sources are 0 (EIA treats biomass, hydro,
# solar and wind as carbon neutral). "Unknown" takes the all-source US average (assumed);
# "Other" (biomass, waste, geothermal and, before 2024-07, storage) is 0 in the primary case and
# the all-source average in the sensitivity case.
# The factors and the formula live in gridpilot.carbon (shared with the F14.6 truth fill).
LB = LB_TO_G
EF = EF_G_KWH
EF_OTHER_SENS = EF_OTHER_SENS_G_KWH

INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#fcfcfb"
C1, C2, C3, C4, C5, C6, C7, C8 = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4",
                                  "#008300", "#6250d6", "#e34948")
SEQ = ["#fcfcfb", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": "#b9b8b1", "axes.labelcolor": INK2, "xtick.color": INK2,
    "ytick.color": INK2, "text.color": INK, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 8.5, "axes.titlesize": 9.5, "axes.titleweight": "bold", "legend.frameon": False,
    "lines.linewidth": 1.4, "figure.dpi": 150, "savefig.dpi": 150, "savefig.bbox": "tight",
})

TABLES: dict[str, str] = {}
NUMBERS: dict[str, object] = {}


def md(df: pl.DataFrame, floatfmt: str = "{:.1f}") -> str:
    cols = df.columns
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.iter_rows():
        cells = []
        for v in row:
            if isinstance(v, float):
                cells.append("" if np.isnan(v) else floatfmt.format(v))
            elif v is None:
                cells.append("")
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def save_table(name: str, df: pl.DataFrame, floatfmt: str = "{:.1f}") -> None:
    TABLES[name] = md(df, floatfmt)
    df.write_csv(OUT_DIR / f"{name}.csv")


# --------------------------------------------------------------------------------------------
# Load, seal, derive
# --------------------------------------------------------------------------------------------


def test_window_completeness(full: pl.DataFrame) -> pl.DataFrame:
    """Completeness of the sealed window: row counts and missing hours ONLY (no values)."""
    expected = int((COMPLETENESS_CUTOFF - TEST_START).total_seconds() // 3600)
    w = full.filter((pl.col("ts_utc") >= TEST_START) & (pl.col("ts_utc") < COMPLETENESS_CUTOFF))
    out = w.group_by("ba").agg(
        pl.len().alias("rows"),
        pl.col("demand_mw").is_not_null().sum().alias("demand_present"),
        pl.col("demand_forecast_mw").is_not_null().sum().alias("df_present"),
        pl.col("gen_gas_adj_mw").is_not_null().sum().alias("gas_present"),
    ).with_columns(
        pl.lit(expected).alias("expected_hours"),
        (expected - pl.col("rows")).alias("missing_rows"),
        (expected - pl.col("demand_present")).alias("missing_demand_hours"),
        (expected - pl.col("df_present")).alias("missing_df_hours"),
    ).sort("ba")
    return out.select("ba", "expected_hours", "rows", "missing_rows", "missing_demand_hours",
                      "missing_df_hours")


def add_derived(pre: pl.DataFrame) -> pl.DataFrame:
    """Local time, net load, production-based carbon intensity (all on adjusted values)."""
    local = (pl.col("ts_utc").dt.replace_time_zone(None)
             + pl.duration(hours=pl.col("utc_offset_h").cast(pl.Int64)))
    for ba, tz in TZ_OVERRIDE.items():
        local = pl.when(pl.col("ba") == ba).then(
            pl.col("ts_utc").dt.convert_time_zone(tz).dt.replace_time_zone(None)).otherwise(local)
    # Isolated single-hour spikes: the rule lives in gridpilot.data.eia930.add_demand_clean
    # (flagged hours and non-positive demand are nulled in demand_clean_mw).
    pre = add_demand_clean(pre)
    clean = pl.col("demand_clean_mw")
    return pre.with_columns(
        local.alias("ts_local"),
        (clean - pl.col("gen_wind_adj_mw").fill_null(0)
         - pl.col("gen_solar_adj_mw").fill_null(0)).alias("net_load_mw"),
        fuel_gen_total().alias("gen_fuel_total_mw"),
        fuel_co2_kg().alias("co2_kg"),  # MW x kg/MWh per hour
        fuel_co2_kg(other_sens=True).alias("co2_kg_sens"),
    ).with_columns(
        pl.when(pl.col("gen_fuel_total_mw") > 0)
        .then(pl.col("co2_kg") / pl.col("gen_fuel_total_mw")).alias("ci_g_kwh"),
        pl.when(pl.col("gen_fuel_total_mw") > 0)
        .then(pl.col("co2_kg_sens") / pl.col("gen_fuel_total_mw")).alias("ci_sens_g_kwh"),
        pl.col("ts_local").dt.hour().alias("hour_local"),
        pl.col("ts_local").dt.month().alias("month_local"),
        pl.col("ts_local").dt.date().alias("date_local"),
        pl.col("ts_utc").dt.year().alias("year"),
        pl.col("ts_local").dt.month().replace_strict(
            {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA",
             8: "JJA", 9: "SON", 10: "SON", 11: "SON"}, return_dtype=pl.Utf8).alias("season"),
    )


def val_year(df: pl.DataFrame) -> pl.DataFrame:
    return df.filter((pl.col("ts_utc") >= VAL_START) & (pl.col("ts_utc") < VAL_END))


# --------------------------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------------------------


def coverage(pre: pl.DataFrame) -> None:
    hours_in_year = {y: (datetime(y + 1, 1, 1) - datetime(y, 1, 1)).days * 24 for y in FULL_YEARS}
    hours_in_year[2025] = int((TEST_START - datetime(2025, 1, 1, tzinfo=UTC)).total_seconds() // 3600)
    per = pre.group_by("ba", "year").agg(
        pl.len().alias("rows"),
        pl.col("demand_mw").is_not_null().sum().alias("d_raw"),
        pl.col("demand_adj_mw").is_not_null().sum().alias("d_adj"),
        (pl.col("demand_forecast_mw") > 0).sum().alias("df"),
        pl.col("gen_fuel_total_mw").is_not_null().sum().alias("fuel"),
    ).with_columns(pl.col("year").replace_strict(hours_in_year, default=None).alias("exp"))
    per = per.filter(pl.col("exp").is_not_null())
    # All-BA summary: first/last hour with demand or generation, mean coverage.
    span = pre.group_by("ba").agg(
        pl.col("ts_utc").filter(pl.col("demand_mw").is_not_null() | pl.col("net_gen_mw").is_not_null())
        .min().dt.date().alias("first"),
        pl.col("ts_utc").filter(pl.col("demand_mw").is_not_null() | pl.col("net_gen_mw").is_not_null())
        .max().dt.date().alias("last"),
        pl.col("region").first().cast(pl.Utf8).alias("region"),
        pl.col("demand_adj_mw").mean().alias("mean_demand_mw"),
        pl.col("net_gen_adj_mw").mean().alias("mean_netgen_mw"),
    )
    tot = per.group_by("ba").agg(
        (pl.col("rows").sum() / pl.col("exp").sum() * 100).alias("rows_%"),
        (pl.col("d_raw").sum() / pl.col("exp").sum() * 100).alias("demand_raw_%"),
        (pl.col("d_adj").sum() / pl.col("exp").sum() * 100).alias("demand_adj_%"),
        (pl.col("df").sum() / pl.col("exp").sum() * 100).alias("df_%"),
        (pl.col("fuel").sum() / pl.col("exp").sum() * 100).alias("fuel_mix_%"),
    )
    allba = span.join(tot, on="ba").sort("region", "ba")
    save_table("coverage_all_bas", allba.with_columns(pl.col("first").cast(pl.Utf8),
                                                      pl.col("last").cast(pl.Utf8)))
    NUMBERS["n_bas_pre"] = allba.height
    NUMBERS["n_bas_full_demand_99"] = allba.filter(pl.col("demand_raw_%") >= 99).height

    cand = per.filter(pl.col("ba").is_in(CANDIDATES)).with_columns(
        (100 - pl.col("d_raw") / pl.col("exp") * 100).alias("miss_d_raw_%"),
        (100 - pl.col("df") / pl.col("exp") * 100).alias("miss_df_%"),
        (100 - pl.col("fuel") / pl.col("exp") * 100).alias("miss_fuel_%"))
    wide = cand.pivot(on="year", index="ba", values="miss_d_raw_%", sort_columns=True)
    save_table("missing_demand_raw_pct_by_year", wide.sort("ba"), "{:.2f}")
    wide = cand.pivot(on="year", index="ba", values="miss_df_%", sort_columns=True)
    save_table("missing_df_pct_by_year", wide.sort("ba"), "{:.2f}")
    wide = cand.pivot(on="year", index="ba", values="miss_fuel_%", sort_columns=True)
    save_table("missing_fuel_pct_by_year", wide.sort("ba"), "{:.2f}")

    # Figure: month x BA share of hours with raw demand (all BAs that report demand).
    m = pre.with_columns(pl.col("ts_utc").dt.truncate("1mo").alias("mon")).group_by("ba", "mon").agg(
        pl.col("demand_mw").is_not_null().mean().alias("share"),
        pl.col("gen_fuel_total_mw").is_not_null().mean().alias("fuel_share"))
    order = allba.filter(pl.col("mean_demand_mw").is_not_null()).sort("region", "ba")["ba"].to_list()
    months = sorted(m["mon"].unique().to_list())
    for col, fname, title in (("share", "coverage_demand_heatmap.png", "Share of hours with reported (raw) demand"),
                              ("fuel_share", "coverage_fuelmix_heatmap.png", "Share of hours with any fuel-mix value (adjusted)")):
        grid = np.full((len(order), len(months)), np.nan)
        idx = {b: i for i, b in enumerate(order)}
        jdx = {d: j for j, d in enumerate(months)}
        for b, d, s in m.select("ba", "mon", col).iter_rows():
            if b in idx:
                grid[idx[b], jdx[d]] = s
        fig, ax = plt.subplots(figsize=(10, 0.16 * len(order) + 1.2))
        cmap = matplotlib.colors.ListedColormap(SEQ[1:])
        im = ax.imshow(grid * 100, aspect="auto", cmap=cmap, vmin=80, vmax=100, interpolation="nearest")
        ax.set_yticks(range(len(order)), order, fontsize=6)
        ticks = [j for j, d in enumerate(months) if d.month == 1]
        ax.set_xticks(ticks, [months[j].year for j in ticks])
        ax.grid(False)
        ax.set_title(f"{title}, by BA and month (2019-01 to 2025-10, UTC; BAs grouped by EIA region)")
        cb = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01)
        cb.set_label("% of hours (values below 80% clipped)")
        fig.savefig(FIG_DIR / fname)
        plt.close(fig)


def adjusted_vs_raw(pre: pl.DataFrame) -> None:
    c = pre.filter(pl.col("ba").is_in(CANDIDATES))
    t = c.group_by("ba").agg(
        pl.len().alias("hours"),
        pl.col("demand_imputed").sum().alias("d_imputed"),
        (pl.col("demand_imputed") & pl.col("demand_mw").is_null()).sum().alias("d_filled_missing"),
        (pl.col("demand_imputed") & pl.col("demand_mw").is_not_null()).sum().alias("d_replaced"),
        ((pl.col("demand_adj_mw") - pl.col("demand_mw")).abs()
         .filter(pl.col("demand_imputed") & pl.col("demand_mw").is_not_null()).median()
         / pl.col("demand_adj_mw").mean() * 100).alias("d_replaced_med_change_%"),
        (pl.col("demand_mw") <= 0).sum().alias("d_raw_le0"),
        pl.col("net_gen_imputed").sum().alias("ng_imputed"),
        pl.col("interchange_imputed").sum().alias("ti_imputed"),
        (pl.col("fuel_imputed_n") > 0).sum().alias("hours_any_fuel_imputed"),
        ((pl.col("demand_adj_mw") - pl.col("demand_mw")).abs().sum()
         / pl.col("demand_adj_mw").sum() * 100).alias("d_abs_adj_energy_%"),
    ).sort("ba")
    save_table("adjusted_vs_raw", t, "{:.3f}")
    # Screens on the ADJUSTED series: isolated spikes, flat lines, energy balance.
    s = c.sort("ba", "ts_utc").with_columns(
        (pl.col("demand_adj_mw") != pl.col("demand_adj_mw").shift(1).over("ba")).fill_null(True)
        .cum_sum().over("ba").alias("run"))
    runs = s.group_by("ba", "run").agg(pl.len().alias("n"), pl.col("ts_utc").min().alias("t0")) \
        .filter(pl.col("n") >= 6)
    fl = runs.group_by("ba").agg(pl.len().alias("flat_runs_ge6h"), pl.col("n").sum().alias("flat_hours"),
                                 pl.col("t0").min().dt.date().cast(pl.Utf8).alias("first_flat"),
                                 pl.col("t0").max().dt.date().cast(pl.Utf8).alias("last_flat"))
    bal = c.filter(pl.col("demand_adj_mw") > 0).group_by("ba").agg(
        ((pl.col("demand_adj_mw") - (pl.col("net_gen_adj_mw") - pl.col("interchange_adj_mw"))).abs()
         / pl.col("demand_adj_mw") > 0.05).mean().mul(100).alias("hrs_imbalance_gt5pct"),
        pl.col("d_spike").sum().alias("isolated_spikes"))
    sp = bal.join(fl, on="ba", how="left").with_columns(
        pl.col("flat_runs_ge6h").fill_null(0), pl.col("flat_hours").fill_null(0)).sort("ba")
    save_table("adjusted_screens", sp, "{:.2f}")
    s.filter(pl.col("d_spike")).select("ba", "ts_utc", "demand_mw", "demand_adj_mw", "net_gen_adj_mw",
                                       "interchange_adj_mw").write_csv(OUT_DIR / "spike_examples.csv")


def fuel_mix(pre: pl.DataFrame) -> pl.DataFrame:
    v = val_year(pre)
    shares = []
    for f in PARTITION_FUELS:
        shares.append((pl.col(f"gen_{f}_adj_mw").fill_null(0).clip(lower_bound=0).sum()
                       / pl.col("gen_pos_total").sum() * 100).alias(f))
    pos_total = pl.sum_horizontal([pl.col(f"gen_{f}_adj_mw").fill_null(0).clip(lower_bound=0)
                                   for f in PARTITION_FUELS])
    sh = v.with_columns(pos_total.alias("gen_pos_total")).group_by("ba").agg(
        *shares,
        (pl.col("gen_fuel_total_mw").sum() / pl.col("net_gen_adj_mw").sum()).alias("fuelsum_over_ng"),
        ((pl.col("gen_fuel_total_mw") / pl.col("net_gen_adj_mw") - 1).abs() > 0.05).mean().alias("hrs_mismatch_gt5pct"),
        pl.col("gen_fuel_total_mw").is_null().mean().alias("hrs_no_fuel"),
    )
    cand_sh = sh.filter(pl.col("ba").is_in(CANDIDATES)).with_columns(
        (pl.col("hrs_mismatch_gt5pct") * 100), (pl.col("hrs_no_fuel") * 100)).sort("ba")
    keep = ["ba", "coal", "gas", "oil", "nuclear", "hydro", "wind", "solar", "geothermal",
            "battery", "other", "unknown", "fuelsum_over_ng", "hrs_mismatch_gt5pct", "hrs_no_fuel"]
    save_table("fuel_mix_validation_year", cand_sh.select(keep), "{:.1f}")
    # All-BA completeness of the fuel mix (pre-test).
    allc = pre.group_by("ba").agg(
        pl.col("gen_fuel_total_mw").is_not_null().mean().alias("hrs_with_fuel"),
        (pl.col("gen_fuel_total_mw").sum() / pl.col("net_gen_adj_mw").sum()).alias("fuelsum_over_ng"),
        ((pl.col("gen_other_adj_mw").fill_null(0).clip(lower_bound=0)
          + pl.col("gen_unknown_adj_mw").fill_null(0).clip(lower_bound=0)).sum()
         / pl.col("gen_fuel_total_mw").sum()).alias("other_unknown_share"),
    ).sort("ba")
    save_table("fuel_completeness_all_bas", allc, "{:.3f}")
    # Taxonomy change: "other" share before and after 2024-07 for candidates.
    tx = pre.filter(pl.col("ba").is_in(CANDIDATES) & (pl.col("ts_utc") >= datetime(2023, 7, 1, tzinfo=UTC))) \
        .with_columns((pl.col("ts_utc") >= datetime(2024, 7, 1, tzinfo=UTC)).alias("new_tax")) \
        .group_by("ba", "new_tax").agg(
            (pl.col("gen_other_adj_mw").fill_null(0).sum() / pl.col("gen_fuel_total_mw").sum() * 100).alias("other_%"),
            ((pl.col("gen_battery_adj_mw").fill_null(0) + pl.col("gen_geothermal_adj_mw").fill_null(0)).abs().sum()
             / pl.col("gen_fuel_total_mw").sum() * 100).alias("bat_geo_abs_%")) \
        .pivot(on="new_tax", index="ba", values=["other_%", "bat_geo_abs_%"]).sort("ba")
    save_table("taxonomy_change_other", tx, "{:.2f}")

    # Figure: stacked shares (validation year).
    order = cand_sh.sort("coal", descending=False)["ba"].to_list()
    fuels = [("coal", "Coal", "#52514e"), ("gas", "Gas", C2), ("oil", "Oil", C8),
             ("nuclear", "Nuclear", C7), ("hydro", "Hydro", C1), ("wind", "Wind", C3),
             ("solar", "Solar", C4), ("other_all", "Other/unknown/geo/storage", "#c9c8c1")]
    d = cand_sh.with_columns((pl.col("geothermal") + pl.col("battery") + pl.col("other")
                              + pl.col("unknown")).alias("other_all"))
    d = {r["ba"]: r for r in d.iter_rows(named=True)}
    fig, ax = plt.subplots(figsize=(8, 5.2))
    left = np.zeros(len(order))
    for key, label, color in fuels:
        vals = np.array([d[b][key] for b in order])
        ax.barh(order, vals, left=left, color=color, label=label, edgecolor=SURF, linewidth=1)
        left += vals
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of positive net generation (%), 2024-11 to 2025-10")
    ax.set_title("Generation mix by BA (EIA-930 adjusted values), sorted by coal share")
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=7.5)
    ax.grid(axis="y", visible=False)
    fig.savefig(FIG_DIR / "fuel_mix_candidates.png")
    plt.close(fig)
    return cand_sh


def rush_hour(pre: pl.DataFrame) -> None:
    c = pre.filter(pl.col("ba").is_in(CANDIDATES) & pl.col("demand_clean_mw").is_not_null()) \
        .with_columns(pl.col("demand_clean_mw").alias("demand_adj_mw"))
    v = val_year(c)
    mean_d = v.group_by("ba").agg(pl.col("demand_adj_mw").mean().alias("mu"))
    prof = v.join(mean_d, on="ba").group_by("ba", "season", "hour_local").agg(
        (pl.col("demand_adj_mw") / pl.col("mu")).mean().alias("d"),
        (pl.col("net_load_mw") / pl.col("mu")).mean().alias("nl")).sort("ba", "season", "hour_local")
    peaks = prof.group_by("ba", "season").agg(
        pl.col("hour_local").sort_by("d").last().alias("peak_hr_demand"),
        pl.col("hour_local").sort_by("nl").last().alias("peak_hr_netload"),
        ((pl.col("d").max() / pl.col("d").min() - 1) * 100).alias("daily_swing_demand_%"),
        ((pl.col("nl").max() / pl.col("nl").min() - 1) * 100).alias("daily_swing_netload_%"),
    ).filter(pl.col("season").is_in(["JJA", "DJF"])).sort("ba", "season")
    save_table("daily_profile_peaks", peaks, "{:.0f}")
    monthly = v.join(mean_d, on="ba").group_by("ba", "month_local").agg(
        (pl.col("demand_adj_mw") / pl.col("mu")).mean().alias("d"))
    mtab = monthly.group_by("ba").agg(
        pl.col("month_local").sort_by("d").last().alias("peak_month"),
        pl.col("month_local").sort_by("d").first().alias("low_month"),
        ((pl.col("d").max() / pl.col("d").min() - 1) * 100).alias("seasonal_swing_%"))
    save_table("monthly_profile", mtab.sort("ba"), "{:.0f}")

    # Figure: daily profiles small multiples.
    order = [b for b in CANDIDATES if b in prof["ba"].unique().to_list()]
    fig, axes = plt.subplots(3, 6, figsize=(14, 7), sharex=True, sharey=True)
    for ax, b in zip(axes.flat, order):
        p = prof.filter(pl.col("ba") == b)
        for season, color in (("JJA", C2), ("DJF", C1)):
            q = p.filter(pl.col("season") == season).sort("hour_local")
            ax.plot(q["hour_local"], q["d"], color=color, lw=1.6, label=f"Demand, {season}")
            ax.plot(q["hour_local"], q["nl"], color=color, lw=1.2, ls="--", label=f"Net load, {season}")
        ax.set_title(b)
        ax.set_xticks([0, 6, 12, 18, 23])
        ax.axhline(1, color=MUTED, lw=0.6)
    for ax in axes[-1]:
        ax.set_xlabel("Local hour (hour-beginning)")
    for ax in axes[:, 0]:
        ax.set_ylabel("MW / annual mean demand")
    h, lab = axes.flat[0].get_legend_handles_labels()
    fig.legend(h, lab, ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.03))
    fig.suptitle("Average daily shape, summer (JJA) vs winter (DJF), 2024-11 to 2025-10. Net load = demand - wind - solar",
                 fontweight="bold", y=1.0)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "daily_profiles.png")
    plt.close(fig)

    # Top-k hours and peak concentration (full calendar years 2019-2024).
    fy = c.filter(pl.col("year").is_in(FULL_YEARS))
    k = 100
    top = fy.with_columns(
        pl.col("demand_adj_mw").rank("ordinal", descending=True).over("ba", "year").alias("rk_d"),
        pl.col("net_load_mw").rank("ordinal", descending=True).over("ba", "year").alias("rk_nl"))
    topd = top.filter(pl.col("rk_d") <= k)
    topn = top.filter(pl.col("rk_nl") <= k)

    def top_summary(t: pl.DataFrame, tag: str) -> pl.DataFrame:
        return t.group_by("ba").agg(
            (pl.col("month_local").is_in([6, 7, 8, 9]).mean() * 100).alias(f"{tag}_in_JJAS_%"),
            (pl.col("month_local").is_in([12, 1, 2]).mean() * 100).alias(f"{tag}_in_DJF_%"),
            pl.col("hour_local").mode().first().alias(f"{tag}_modal_hour"),
            (pl.col("hour_local").is_between(16, 20).mean() * 100).alias(f"{tag}_16to20h_%"),
            (pl.col("date_local").n_unique() / len(FULL_YEARS)).alias(f"{tag}_days_per_yr"),
        )
    ts = top_summary(topd, "top100D").join(top_summary(topn, "top100NL"), on="ba").sort("ba")
    save_table("top100_hours", ts, "{:.0f}")

    conc = fy.group_by("ba", "year").agg(
        (pl.col("demand_adj_mw") >= 0.95 * pl.col("demand_adj_mw").max()).sum().alias("h95"),
        (pl.col("demand_adj_mw") >= 0.90 * pl.col("demand_adj_mw").max()).sum().alias("h90"),
        pl.col("date_local").filter(pl.col("demand_adj_mw") >= 0.95 * pl.col("demand_adj_mw").max())
        .n_unique().alias("days95"),
        (pl.col("net_load_mw") >= 0.95 * pl.col("net_load_mw").max()).sum().alias("nl_h95"),
        (pl.col("demand_adj_mw").mean() / pl.col("demand_adj_mw").max() * 100).alias("load_factor_%"),
        pl.col("demand_adj_mw").max().alias("peak_mw"),
    )
    cs = conc.group_by("ba").agg(
        pl.col("h95").median().alias("hrs_within5%_of_peak"),
        pl.col("days95").median().alias("days_within5%"),
        pl.col("h90").median().alias("hrs_within10%"),
        pl.col("nl_h95").median().alias("netload_hrs_within5%"),
        pl.col("load_factor_%").median().alias("load_factor_%"),
        pl.col("peak_mw").max().alias("max_peak_mw"),
        pl.col("h95").min().alias("h95_min"), pl.col("h95").max().alias("h95_max"),
    ).sort("ba")
    save_table("peak_concentration", cs, "{:.0f}")
    NUMBERS["pace_conc"] = cs.filter(pl.col("ba") == "PACE").to_dicts()
    NUMBERS["pace_conc_by_year"] = conc.filter(pl.col("ba") == "PACE").sort("year").to_dicts()

    # Figure: month x hour heatmaps of top-100 demand hours, pooled 2019-2024.
    fig, axes = plt.subplots(3, 6, figsize=(14, 6.6), sharex=True, sharey=True)
    cmap = matplotlib.colors.ListedColormap(SEQ)
    for ax, b in zip(axes.flat, order):
        g = np.zeros((12, 24))
        for mth, hr in topd.filter(pl.col("ba") == b).select("month_local", "hour_local").iter_rows():
            g[mth - 1, hr] += 1
        ax.imshow(g, aspect="auto", cmap=cmap, origin="upper", interpolation="nearest")
        ax.set_title(b)
        ax.grid(False)
        ax.set_yticks([0, 3, 6, 9], ["Jan", "Apr", "Jul", "Oct"])
        ax.set_xticks([0, 6, 12, 18, 23])
    for ax in axes[-1]:
        ax.set_xlabel("Local hour")
    fig.suptitle("Where the 100 highest-demand hours of each year fall (month x local hour, 2019-2024 pooled; darker = more)",
                 fontweight="bold", y=1.0)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "top100_hours_heatmap.png")
    plt.close(fig)

    # Figure: peak concentration bars.
    cs2 = cs.sort("hrs_within5%_of_peak")
    fig, ax = plt.subplots(figsize=(7, 5))
    y = np.arange(cs2.height)
    ax.barh(y + 0.2, cs2["hrs_within5%_of_peak"], height=0.4, color=C1, label="Demand")
    ax.barh(y - 0.2, cs2["netload_hrs_within5%"], height=0.4, color=C2, label="Net load")
    ax.set_yticks(y, cs2["ba"].to_list())
    ax.set_xlabel("Hours per year within 5% of the annual peak (median of 2019-2024)")
    ax.set_title("How concentrated the rush hour is")
    ax.legend(loc="lower right")
    ax.grid(axis="y", visible=False)
    fig.savefig(FIG_DIR / "peak_concentration.png")
    plt.close(fig)


def forecast_accuracy(pre: pl.DataFrame) -> None:
    # Score against reported demand on hours EIA did not impute (EIA's first imputation fallback
    # is the DF itself: 996 of 1,181 imputed candidate hours equal the DF) and that are not
    # isolated spikes.
    ok = (pl.col("demand_forecast_mw") > 0) & (pl.col("demand_mw") > 0)
    base = pre.filter(~pl.col("demand_imputed") & ~pl.col("d_spike")).select(
        "ba", "ts_utc", "year", "demand_forecast_mw", "demand_mw", "demand_adj_mw", "date_local",
        "hour_local")
    # Alignment check: compare DF shifted by k hours against demand.
    shifts = []
    for k in (-2, -1, 0, 1, 2):
        sh = base.select("ba", (pl.col("ts_utc") + pl.duration(hours=k)).alias("ts_utc"),
                         pl.col("demand_forecast_mw").alias("dfk"))
        j = base.filter((pl.col("ts_utc") >= VAL_START) & (pl.col("ts_utc") < VAL_END)).join(
            sh, on=["ba", "ts_utc"]).filter((pl.col("dfk") > 0) & (pl.col("demand_mw") > 0))
        shifts.append(j.group_by("ba").agg(
            ((pl.col("dfk") - pl.col("demand_mw")).abs() / pl.col("demand_mw")).mean().mul(100)
            .alias(f"mape_shift{k:+d}")))
    st = shifts[0]
    for s in shifts[1:]:
        st = st.join(s, on="ba")
    cols = [c for c in st.columns if c.startswith("mape_shift")]
    st = st.with_columns(pl.concat_list(cols).list.arg_min().alias("_i")).with_columns(
        pl.col("_i").replace_strict({0: -2, 1: -1, 2: 0, 3: 1, 4: 2}).alias("best_shift_h")).drop("_i")

    e = base.filter(ok).with_columns(
        ((pl.col("demand_forecast_mw") - pl.col("demand_mw")) / pl.col("demand_mw")).alias("pe"),
        ((pl.col("demand_forecast_mw") - pl.col("demand_adj_mw")) / pl.col("demand_adj_mw")).alias("pe_adj"))
    by_year = e.group_by("ba", "year").agg((pl.col("pe").abs().mean() * 100).alias("mape"))
    wide = by_year.pivot(on="year", index="ba", values="mape", sort_columns=True)
    v = e.filter((pl.col("ts_utc") >= VAL_START) & (pl.col("ts_utc") < VAL_END))
    vs = v.group_by("ba").agg(
        pl.len().alias("val_hours"),
        (pl.col("pe").abs().mean() * 100).alias("val_MAPE_raw"),
        (pl.col("pe_adj").abs().mean() * 100).alias("val_MAPE_adj"),
        (pl.col("pe").abs().median() * 100).alias("val_MdAPE"),
        (pl.col("pe").mean() * 100).alias("val_bias_%"),
        (pl.col("pe").abs() > 0.5).sum().alias("val_hrs_APE_gt50"),
    )
    # Daily peak: does the BA forecast pick the right hour, and how big is its peak error?
    daily = v.group_by("ba", "date_local").agg(
        pl.col("hour_local").sort_by("demand_mw").last().alias("h_act"),
        pl.col("hour_local").sort_by("demand_forecast_mw").last().alias("h_fc"),
        pl.col("demand_mw").max().alias("pk_act"), pl.col("demand_forecast_mw").max().alias("pk_fc"),
        pl.len().alias("n")).filter(pl.col("n") >= 23)
    dp = daily.group_by("ba").agg(
        ((pl.col("h_act") - pl.col("h_fc")).abs() <= 1).mean().mul(100).alias("val_peak_hour_hit_pm1h_%"),
        ((pl.col("pk_fc") - pl.col("pk_act")).abs() / pl.col("pk_act")).mean().mul(100).alias("val_daily_peak_MAPE"))
    st = st.with_columns(pl.min_horizontal(cols).alias("val_MAPE_best_shift"))
    out = vs.join(dp, on="ba", how="left").join(st, on="ba", how="left").join(wide, on="ba", how="left")
    out = out.filter(pl.col("val_hours") > 1000).sort("val_MAPE_raw")
    save_table("df_accuracy_all_bas", out, "{:.1f}")
    NUMBERS["df_val"] = out.filter(pl.col("ba").is_in(CANDIDATES)).select(
        "ba", "val_MAPE_raw", "val_MdAPE", "val_bias_%", "best_shift_h").to_dicts()

    # Figure: validation-year MAPE by BA, with 2019-2024 per-year values as dots.
    o = out.sort("val_MAPE_raw", descending=True)
    fig, ax = plt.subplots(figsize=(7.5, 0.17 * o.height + 1.2))
    y = np.arange(o.height)
    colors = [C2 if b in CANDIDATES else "#b9b8b1" for b in o["ba"].to_list()]
    ax.barh(y, o["val_MAPE_raw"].clip(upper_bound=40), color=colors, height=0.7)
    for yr in FULL_YEARS:
        if str(yr) in o.columns:
            ax.scatter(o[str(yr)].clip(upper_bound=40), y, s=6, color=INK2, zorder=3,
                       label="Calendar years 2019-2024" if yr == FULL_YEARS[0] else None)
    ax.set_yticks(y, o["ba"].to_list(), fontsize=6)
    ax.set_xlabel("MAPE of the BA's own day-ahead demand forecast vs reported demand (%), clipped at 40")
    ax.set_title("BA day-ahead forecast error (bars: validation year 2024-11 to 2025-10; orange = candidate BAs)")
    ax.legend(loc="lower right")
    ax.grid(axis="y", visible=False)
    fig.savefig(FIG_DIR / "df_mape.png")
    plt.close(fig)


def carbon(pre: pl.DataFrame, rec: list[str]) -> None:
    c = pre.filter(pl.col("ci_g_kwh").is_not_null())
    v = val_year(c)
    s = v.group_by("ba").agg(
        (pl.col("co2_kg").sum() / pl.col("gen_fuel_total_mw").sum()).alias("ci_mean_g_kwh"),
        (pl.col("co2_kg_sens").sum() / pl.col("gen_fuel_total_mw").sum()).alias("ci_sens_other"),
        pl.col("ci_g_kwh").quantile(0.1).alias("p10"), pl.col("ci_g_kwh").quantile(0.9).alias("p90"),
        pl.col("gen_fuel_total_mw").mean().alias("mean_gen_mw"),
    )
    d = v.group_by("ba", "date_local").agg(
        pl.col("ci_g_kwh").mean().alias("m"), pl.col("ci_g_kwh").min().alias("lo"),
        pl.col("ci_g_kwh").max().alias("hi"), pl.len().alias("n")).filter(pl.col("n") >= 20)
    ds = d.group_by("ba").agg(
        ((pl.col("hi") - pl.col("lo")).sum() / pl.col("m").sum() * 100).alias("daily_range_%"),
        ((pl.col("m") - pl.col("lo")).sum() / pl.col("m").sum() * 100).alias("best_hour_vs_daymean_%"))
    # A 1-h job that can wait up to W hours (perfect foresight): mean relative CI reduction.
    srt = v.sort("ba", "ts_utc").select("ba", "ts_utc", "ci_g_kwh")
    w = []
    for W in (6, 24):
        g = srt.with_columns(pl.col("ci_g_kwh").reverse().rolling_min(W + 1, min_samples=1)
                             .reverse().over("ba").alias("fut_min"))
        w.append(g.group_by("ba").agg(((pl.col("ci_g_kwh") - pl.col("fut_min")).sum()
                                       / pl.col("ci_g_kwh").sum() * 100).alias(f"wait{W}h_saving_%")))
    mon = v.group_by("ba", "month_local").agg(
        (pl.col("co2_kg").sum() / pl.col("gen_fuel_total_mw").sum()).alias("ci"))
    ms = mon.group_by("ba").agg(pl.col("ci").min().alias("month_min"), pl.col("ci").max().alias("month_max"),
                                pl.col("month_local").sort_by("ci").first().alias("cleanest_month"))
    corr = v.filter(pl.col("demand_adj_mw").is_not_null()).group_by("ba").agg(
        pl.corr("demand_adj_mw", "ci_g_kwh").alias("corr_demand_ci"))
    out = s.join(ds, on="ba").join(w[0], on="ba").join(w[1], on="ba").join(ms, on="ba").join(
        corr, on="ba", how="left").sort("ci_mean_g_kwh")
    out = out.filter(pl.col("mean_gen_mw") > 300)
    save_table("ci_all_bas_validation_year", out, "{:.0f}")
    cand = out.filter(pl.col("ba").is_in(CANDIDATES))
    save_table("ci_candidates_validation_year", cand.with_columns(pl.col("corr_demand_ci") * 100), "{:.1f}")

    # Rush-hour CI: CI in each year's top-100 demand hours vs the year's generation-weighted mean.
    fy = pre.filter(pl.col("ba").is_in(CANDIDATES) & pl.col("year").is_in(FULL_YEARS)
                    & pl.col("ci_g_kwh").is_not_null() & pl.col("demand_adj_mw").is_not_null())
    rk = fy.with_columns(pl.col("demand_adj_mw").rank("ordinal", descending=True).over("ba", "year").alias("rk"))
    rh = rk.group_by("ba", "year").agg(
        (pl.col("co2_kg").filter(pl.col("rk") <= 100).sum() / pl.col("gen_fuel_total_mw").filter(pl.col("rk") <= 100).sum()
         / (pl.col("co2_kg").sum() / pl.col("gen_fuel_total_mw").sum()) * 100 - 100).alias("x"))
    rhs = rh.group_by("ba").agg(pl.col("x").median().alias("ci_top100_vs_mean_%")).sort("ba")
    save_table("ci_rush_hour", rhs, "{:.0f}")

    # Cross-region room (validation year), recommended set.
    rv = v.filter(pl.col("ba").is_in(rec)).select("ba", "ts_utc", "ci_g_kwh")
    piv = rv.pivot(on="ba", index="ts_utc", values="ci_g_kwh").drop_nulls()
    arr = piv.select(rec).to_numpy()
    cleanest = np.array(rec)[arr.argmin(axis=1)]
    share_clean = {b: float((cleanest == b).mean() * 100) for b in rec}
    pace = piv["PACE"].to_numpy()
    NUMBERS["cross_region"] = {
        "hours": int(arr.shape[0]),
        "mean_spread_max_minus_min_g_kwh": float((arr.max(1) - arr.min(1)).mean()),
        "pace_minus_cleanest_mean_g_kwh": float((pace - arr.min(1)).mean()),
        "pace_minus_cleanest_rel_%": float(((pace - arr.min(1)) / pace).mean() * 100),
        "share_hours_cleanest_%": share_clean,
    }
    rec2 = [b for b in rec if b != "BPAT"]
    arr2 = piv.select(rec2).to_numpy()
    cl2 = np.array(rec2)[arr2.argmin(axis=1)]
    NUMBERS["cross_region"]["share_hours_cleanest_excl_BPAT_%"] = {b: float((cl2 == b).mean() * 100) for b in rec2}
    NUMBERS["cross_region"]["pace_vs"] = {
        b: {"mean_diff_g_kwh": float((pace - piv[b].to_numpy()).mean()),
            "share_hours_other_cleaner_%": float((piv[b].to_numpy() < pace).mean() * 100)}
        for b in rec if b != "PACE"}
    # PACE time-shift vs region-shift: best of both within 24 h.
    NUMBERS["pace_ci"] = cand.filter(pl.col("ba") == "PACE").to_dicts()

    # Figures: CI bars with P10-P90; diurnal CI; month heatmap.
    o = cand.sort("ci_mean_g_kwh")
    fig, ax = plt.subplots(figsize=(7, 5))
    y = np.arange(o.height)
    ax.barh(y, o["ci_mean_g_kwh"], color=[C2 if b == "PACE" else C1 for b in o["ba"].to_list()], height=0.6)
    ax.errorbar(o["ci_mean_g_kwh"], y, xerr=[o["ci_mean_g_kwh"] - o["p10"], o["p90"] - o["ci_mean_g_kwh"]],
                fmt="none", ecolor=INK2, elinewidth=1, capsize=2)
    ax.set_yticks(y, o["ba"].to_list())
    ax.set_xlabel("Production-based CO2 intensity (g/kWh), 2024-11 to 2025-10; whiskers: hourly P10-P90")
    ax.set_title("Average carbon intensity of generation, by BA (modeled: EIA-930 mix x EIA factors)")
    ax.grid(axis="y", visible=False)
    fig.savefig(FIG_DIR / "ci_by_ba.png")
    plt.close(fig)

    prof = v.filter(pl.col("ba").is_in(CANDIDATES)).group_by("ba", "season", "hour_local").agg(
        (pl.col("co2_kg").sum() / pl.col("gen_fuel_total_mw").sum()).alias("ci"))
    order = [b for b in CANDIDATES if b in prof["ba"].unique().to_list()]
    fig, axes = plt.subplots(3, 6, figsize=(14, 7), sharex=True, sharey=True)
    for ax, b in zip(axes.flat, order):
        p = prof.filter(pl.col("ba") == b)
        for season, color in (("JJA", C2), ("MAM", C3), ("DJF", C1)):
            q = p.filter(pl.col("season") == season).sort("hour_local")
            ax.plot(q["hour_local"], q["ci"], color=color, lw=1.5, label=season)
        ax.set_title(b)
        ax.set_xticks([0, 6, 12, 18, 23])
    for ax in axes[-1]:
        ax.set_xlabel("Local hour")
    for ax in axes[:, 0]:
        ax.set_ylabel("g CO2/kWh")
    h, lab = axes.flat[0].get_legend_handles_labels()
    fig.legend(h, lab, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.03))
    fig.suptitle("Carbon intensity by local hour and season (2024-11 to 2025-10; modeled)", fontweight="bold", y=1.0)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "ci_diurnal.png")
    plt.close(fig)

    mm = mon.filter(pl.col("ba").is_in(CANDIDATES))
    order2 = o["ba"].to_list()
    g = np.full((len(order2), 12), np.nan)
    for b, mth, ci in mm.select("ba", "month_local", "ci").iter_rows():
        if b in order2:
            g[order2.index(b), mth - 1] = ci
    fig, ax = plt.subplots(figsize=(7.5, 5))
    im = ax.imshow(g, aspect="auto", cmap=matplotlib.colors.ListedColormap(SEQ[1:]), interpolation="nearest")
    ax.set_yticks(range(len(order2)), order2)
    ax.set_xticks(range(12), ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.grid(False)
    for i in range(g.shape[0]):
        for j in range(12):
            if not np.isnan(g[i, j]):
                ax.text(j, i, f"{g[i, j]:.0f}", ha="center", va="center", fontsize=5.5,
                        color="white" if g[i, j] > np.nanpercentile(g, 60) else INK)
    ax.set_title("Monthly mean CO2 intensity (g/kWh), Nov 2024 - Oct 2025 (modeled)")
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.01).set_label("g CO2/kWh")
    fig.savefig(FIG_DIR / "ci_monthly_heatmap.png")
    plt.close(fig)

    # Scatter: when vs where.
    fig, ax = plt.subplots(figsize=(6.5, 4.6))
    for r in cand.iter_rows(named=True):
        ax.scatter(r["ci_mean_g_kwh"], r["wait24h_saving_%"], s=30, color=C2 if r["ba"] == "PACE" else C1, zorder=3)
        ax.annotate(r["ba"], (r["ci_mean_g_kwh"], r["wait24h_saving_%"]), textcoords="offset points",
                    xytext=(4, 3), fontsize=7.5, color=INK2)
    ax.set_xlabel("Mean CO2 intensity (g/kWh)")
    ax.set_ylabel("CO2 cut for a 1-h job allowed to wait <=24 h (%)")
    ax.set_title("Room for time-shifting vs how dirty the grid is (2024-11 to 2025-10, perfect foresight)")
    fig.savefig(FIG_DIR / "ci_shift_room.png")
    plt.close(fig)


def marginal_ci(pre: pl.DataFrame) -> None:
    """Marginal emission factor per BA: OLS slope of hourly dCO2 on d(net load), validation year.

    Siler-Evans et al. (2012) style regression on first differences. The regressor is net load
    (clean demand - wind - solar), the load left for dispatchable plants; d(total generation) is
    kept as a comparison (it is diluted by wind/solar ramps). Within-BA generation only, so
    imports are invisible. Regressor values beyond the 0.1/99.9 percentiles are dropped.
    """
    v = val_year(pre.filter(pl.col("ba").is_in(CANDIDATES))).sort("ba", "ts_utc").with_columns(
        pl.col("co2_kg").diff().over("ba").alias("dE"),
        pl.col("gen_fuel_total_mw").diff().over("ba").alias("dG"),
        pl.col("net_load_mw").diff().over("ba").alias("dNL"),
        (pl.col("ts_utc").diff().over("ba") == pl.duration(hours=1)).alias("cont"),
        (pl.col("hour_local") // 6).alias("block"),
    ).filter(pl.col("cont") & pl.col("dE").is_not_null())

    def slope(g: pl.DataFrame, xcol: str = "dNL") -> tuple[float, float]:
        g = g.drop_nulls([xcol])
        g = g.filter(pl.col(xcol).is_between(g[xcol].quantile(0.001), g[xcol].quantile(0.999)))
        x, y = g[xcol].to_numpy(), g["dE"].to_numpy()
        if len(x) < 100 or np.var(x) == 0:
            return float("nan"), float("nan")
        b = float(np.cov(x, y, bias=True)[0, 1] / np.var(x))
        r2 = float(np.corrcoef(x, y)[0, 1] ** 2)
        return b, r2

    rows = []
    for b in CANDIDATES:
        g = v.filter(pl.col("ba") == b)
        if g.height == 0:
            continue
        mef, r2 = slope(g)
        mef_g, r2_g = slope(g, "dG")
        blocks = {f"mef_{k * 6:02d}-{k * 6 + 6:02d}h": slope(g.filter(pl.col("block") == k))[0] for k in range(4)}
        avg = float(g["co2_kg"].sum() / g["gen_fuel_total_mw"].sum())
        rows.append({"ba": b, "avg_ci": avg, "mef_netload_g_kwh": mef, "r2_netload": r2, **blocks,
                     "mef_gen_g_kwh": mef_g, "r2_gen": r2_g})
    save_table("marginal_ci_validation_year", pl.DataFrame(rows), "{:.2f}")


def eia_co2_crosscheck(pre: pl.DataFrame) -> None:
    """Compare our modeled CI with EIA's own hourly CO2 estimate (per-BA workbooks)."""
    try:
        import fastexcel  # noqa: F401
    except ImportError:
        print("fastexcel missing; skip EIA CO2 cross-check")
        return
    rows = []
    for b in CANDIDATES:
        p = RAW_EIA_DIR / "ba_workbooks" / f"{b}.xlsx"
        if not p.exists():
            continue
        want = ["UTC time", "CO2 Emissions Generated", "Positive Generation",
                "CO2 Emissions Intensity for Generated Electricity",
                "CO2 Emissions Intensity for Consumed Electricity"]
        x = pl.read_excel(p, sheet_name="Published Hourly Data", columns=want,
                          schema_overrides={c: pl.Utf8 for c in want[1:]})
        x = x.with_columns(
            (pl.col("UTC time").cast(pl.Datetime("us")).dt.replace_time_zone("UTC")
             - pl.duration(hours=1)).alias("ts_utc"),
            *[pl.col(c).cast(pl.Float64, strict=False) for c in want[1:]])
        x = drop_sealed(x).filter(pl.col("ts_utc") >= VAL_START)
        ours = val_year(pre.filter(pl.col("ba") == b)).select("ts_utc", "ci_g_kwh", "co2_kg", "gen_fuel_total_mw")
        j = ours.join(x, on="ts_utc").drop_nulls(["ci_g_kwh", "CO2 Emissions Intensity for Generated Electricity"])
        if j.height == 0:
            continue
        eia_gen = j["CO2 Emissions Intensity for Generated Electricity"]
        rows.append({
            "ba": b, "hours": j.height,
            "eia_intensity_gen_mean_raw_units": float(eia_gen.mean()),
            "eia_tons_over_posgen_g_kwh": float(j["CO2 Emissions Generated"].sum() / j["Positive Generation"].sum() * 1000),
            "ours_g_kwh": float(j["co2_kg"].sum() / j["gen_fuel_total_mw"].sum()),
            "eia_gen_intensity_g_kwh": float(eia_gen.mean() * LB),
            "eia_consumed_intensity_g_kwh": float(j["CO2 Emissions Intensity for Consumed Electricity"].mean() * LB),
            "corr_hourly": float(np.corrcoef(j["ci_g_kwh"].to_numpy(), eia_gen.to_numpy())[0, 1]),
        })
    if rows:
        save_table("eia_co2_crosscheck", pl.DataFrame(rows), "{:.3f}")


def pace_week(pre: pl.DataFrame) -> None:
    """One summer week in PACE (train period): demand, BA forecast, net load, mix, CI."""
    w = pre.filter((pl.col("ba") == "PACE") & (pl.col("ts_local") >= datetime(2024, 7, 8))
                   & (pl.col("ts_local") < datetime(2024, 7, 15))).sort("ts_local")
    t = w["ts_local"].to_numpy()
    fig, axes = plt.subplots(3, 1, figsize=(10, 7.5), sharex=True, gridspec_kw={"height_ratios": [1.2, 1.2, 0.8]})
    ax = axes[0]
    ax.plot(t, w["demand_adj_mw"] / 1000, color=C1, lw=1.8, label="Demand (reported)")
    ax.plot(t, w["demand_forecast_mw"] / 1000, color=C2, lw=1.3, ls="--", label="PACE's own day-ahead forecast")
    ax.plot(t, w["net_load_mw"] / 1000, color=C3, lw=1.3, label="Net load (demand - wind - solar)")
    ax.set_ylabel("GW")
    ax.legend(ncol=3, loc="upper left", fontsize=7.5)
    ax.set_title("PACE (Utah hero region), 8-14 July 2024, local time: the rush hour is the late afternoon")
    ax = axes[1]
    stack = [("coal", "Coal", "#52514e"), ("gas", "Gas", C2), ("hydro", "Hydro", C1), ("wind", "Wind", C3),
             ("solar", "Solar", C4), ("other", "Other", "#c9c8c1")]
    ys = [w[f"gen_{f}_adj_mw"].fill_null(0).clip(lower_bound=0).to_numpy() / 1000 for f, _, _ in stack]
    ax.stackplot(t, ys, colors=[s[2] for s in stack], labels=[s[1] for s in stack], edgecolor=SURF, linewidth=0.3)
    ax.set_ylabel("GW generated in PACE")
    ax.legend(ncol=6, loc="upper left", fontsize=7.5)
    ax = axes[2]
    ax.plot(t, w["ci_g_kwh"], color=INK2, lw=1.5)
    ax.set_ylabel("g CO2/kWh")
    ax.set_xlabel("Local time (Mountain)")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "pace_week_jul2024.png")
    plt.close(fig)


def pace_neighbors() -> None:
    p = INTERIM_EIA_DIR / "interchange.parquet"
    if not p.exists():
        return
    x = drop_sealed(pl.read_parquet(p)).filter((pl.col("ba") == "PACE") & (pl.col("ts_utc") >= VAL_START))
    t = x.group_by("diba").agg(pl.col("interchange_mw").mean().alias("mean_mw_out_of_PACE"),
                               pl.len().alias("hours")).sort("mean_mw_out_of_PACE")
    save_table("pace_interchange_val_year", t.with_columns(pl.col("diba").cast(pl.Utf8)), "{:.0f}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    full = pl.read_parquet(INTERIM_EIA_DIR / "balance.parquet")
    save_table("test_window_completeness", test_window_completeness(full), "{:.0f}")
    pre = add_derived(drop_sealed(full))
    del full
    assert pre["ts_utc"].max() < TEST_START
    NUMBERS["pre_rows"] = pre.height
    NUMBERS["pre_range"] = [str(pre["ts_utc"].min()), str(pre["ts_utc"].max())]
    coverage(pre)
    adjusted_vs_raw(pre)
    fuel_mix(pre)
    rush_hour(pre)
    forecast_accuracy(pre)
    rec = ["PACE", "CISO", "BPAT", "AZPS", "NEVP", "PSCO", "ERCO", "SWPP", "MISO", "PJM"]  # recommended set
    carbon(pre, rec)
    eia_co2_crosscheck(pre)
    marginal_ci(pre)
    pace_week(pre)
    pace_neighbors()
    (OUT_DIR / "tables.md").write_text("\n\n".join(f"### {k}\n\n{v}" for k, v in TABLES.items()) + "\n")
    (OUT_DIR / "numbers.json").write_text(json.dumps(NUMBERS, indent=1, default=str))
    print("wrote", OUT_DIR, len(TABLES), "tables;", FIG_DIR)
    _ = TEST_END  # boundaries imported for documentation


if __name__ == "__main__":
    main()
