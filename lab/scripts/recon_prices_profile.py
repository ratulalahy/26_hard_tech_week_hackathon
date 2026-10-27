"""Profile wholesale prices for docs/data-profile/workloads-prices.md.

Seal: every statistic and figure uses gridpilot.splits.drop_sealed first. The sealed window
[2025-11-01Z, 2026-11-01Z) is reported only as completeness (rows, missing hours).
Demand comes read-only from the grid agent's data/interim/eia930/balance.parquet
(hour-beginning UTC), also passed through drop_sealed.

    cd lab && uv run python scripts/recon_prices_profile.py --stats /tmp/prices_stats.json \
        [--ercot-rtm-cache /tmp/ercot_rtm.parquet]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from gridpilot.data import prices as P
from gridpilot.paths import INTERIM_DIR, REPO_ROOT
from gridpilot.splits import TEST_END, TEST_START, VALIDATION_START, drop_sealed

FIG_DIR = REPO_ROOT / "docs" / "data-profile" / "figures" / "workloads-prices"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"

# (series key, iso, market, node, local tz, BA for demand, label)
SERIES = [
    ("np15_da", "caiso", "dam", "TH_NP15_GEN-APND", "America/Los_Angeles", "CISO", "CAISO NP15 hub, day-ahead"),
    ("sp15_da", "caiso", "dam", "TH_SP15_GEN-APND", "America/Los_Angeles", "CISO", "CAISO SP15 hub, day-ahead"),
    ("np15_rt", "caiso", "rtpd", "TH_NP15_GEN-APND", "America/Los_Angeles", "CISO", "CAISO NP15 hub, 15-min real-time"),
    ("pace_rt", "caiso", "rtpd", "ELAP_PACE-APND", "America/Denver", "PACE", "PACE load point (WEIM), 15-min real-time"),
    ("ercot_north_da", "ercot", "dam", "HB_NORTH", "America/Chicago", "ERCO", "ERCOT North hub, day-ahead"),
    ("ercot_houston_da", "ercot", "dam", "HB_HOUSTON", "America/Chicago", "ERCO", "ERCOT Houston hub, day-ahead"),
    ("ercot_west_da", "ercot", "dam", "HB_WEST", "America/Chicago", "ERCO", "ERCOT West hub, day-ahead"),
    ("ercot_south_da", "ercot", "dam", "HB_SOUTH", "America/Chicago", "ERCO", "ERCOT South hub, day-ahead"),
    ("ercot_north_rt", "ercot", "rtm", "HB_NORTH", "America/Chicago", "ERCO", "ERCOT North hub, 15-min real-time"),
]


def style() -> None:
    plt.rcParams.update({
        "figure.dpi": 130, "savefig.dpi": 160, "font.size": 9.5, "axes.edgecolor": INK2,
        "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True,
        "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
        "axes.spines.right": False, "legend.frameon": False, "figure.facecolor": "#fcfcfb",
        "axes.facecolor": "#fcfcfb", "lines.linewidth": 1.8,
    })


def save(fig, name: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / name, bbox_inches="tight")
    plt.close(fig)
    print(f"figure -> {FIG_DIR / name}")


def load_all_hourly(ercot_rtm_cache: Path | None) -> dict[str, pl.DataFrame]:
    caiso_dam = P.to_hourly(P.load_caiso("dam"))
    # WEIM ELAP real-time is profiled separately once its pull completes; core only here.
    caiso_rt = P.to_hourly(P.load_caiso("rtpd", groups=("core",)))
    ercot_dam = P.to_hourly(P.load_ercot("dam"))
    if ercot_rtm_cache and ercot_rtm_cache.exists():
        ercot_rt = P.to_hourly(pl.read_parquet(ercot_rtm_cache))
    else:
        ercot_rt = P.to_hourly(P.load_ercot("rtm"))
    return {("caiso", "dam"): caiso_dam, ("caiso", "rtpd"): caiso_rt,
            ("ercot", "dam"): ercot_dam, ("ercot", "rtm"): ercot_rt}


def completeness_table(tables: dict) -> list[dict]:
    """Rows and missing hours per node and window. Counts only (safe on the sealed window)."""
    windows = {
        "pre_validation": (None, VALIDATION_START),
        "validation_2024-11_2025-10": (VALIDATION_START, TEST_START),
        "sealed_test_2025-11_2026-10": (TEST_START, TEST_END),
    }
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    out = []
    for (iso, market), df in tables.items():
        for node in sorted(df["node"].unique().to_list()):
            d = df.filter(pl.col("node") == node)
            first = d["ts_utc"].min()
            for wname, (a, b) in windows.items():
                a2 = max(a, first) if a else first
                b2 = min(b, now)
                if b2 <= a2:
                    out.append({"iso": iso, "market": market, "node": node, "window": wname,
                                "rows": 0, "expected_hours": 0, "missing_hours": 0})
                    continue
                c = P.completeness(d, a2, b2)
                rows = int(c["rows"][0]) if c.height else 0
                exp = int((b2 - a2).total_seconds() // 3600)
                out.append({"iso": iso, "market": market, "node": node, "window": wname,
                            "first_in_window": str(a2), "rows": rows, "expected_hours": exp,
                            "missing_hours": exp - rows})
    return out


def edam_pace_first_day(tables: dict) -> dict:
    """Existence and completeness of PACE day-ahead prices (EDAM). No values."""
    d = tables[("caiso", "dam")].filter(pl.col("node").is_in(P.PACE_NODES))
    if d.is_empty():
        return {"rows": 0}
    return {node: {"first_hour_utc": str(g["ts_utc"].min()), "rows": g.height}
            for (node,), g in d.group_by("node")}


def series_frame(tables: dict, key: str) -> tuple[pl.DataFrame, dict]:
    spec = next(s for s in SERIES if s[0] == key)
    _, iso, market, node, tz, ba, label = spec
    df = tables[(iso, market)].filter(pl.col("node") == node).select("ts_utc", "lmp")
    df = drop_sealed(df).with_columns(
        pl.col("ts_utc").dt.convert_time_zone(tz).alias("local"))
    df = df.with_columns(pl.col("local").dt.hour().alias("hour"),
                         pl.col("local").dt.month().alias("month"),
                         pl.col("local").dt.date().alias("day"),
                         pl.col("local").dt.year().alias("year"))
    return df, {"iso": iso, "market": market, "node": node, "tz": tz, "ba": ba, "label": label}


def level_stats(df: pl.DataFrame) -> dict:
    s = df["lmp"]
    by_year = df.group_by("year").agg(
        pl.len().alias("hours"), pl.col("lmp").mean().alias("mean"),
        pl.col("lmp").median().alias("median"), pl.col("lmp").quantile(0.05).alias("p05"),
        pl.col("lmp").quantile(0.95).alias("p95"), (pl.col("lmp") < 0).mean().alias("share_negative"),
    ).sort("year")
    return {"first": str(df["ts_utc"].min()), "last": str(df["ts_utc"].max()), "hours": df.height,
            "mean": s.mean(), "median": s.median(), "p05": s.quantile(0.05), "p95": s.quantile(0.95),
            "p99": s.quantile(0.99), "max": s.max(), "min": s.min(),
            "share_negative": float((s < 0).mean()), "by_year": by_year.to_dicts()}


def shape_stats(df: pl.DataFrame) -> dict:
    prof = df.group_by("hour").agg(pl.col("lmp").mean()).sort("hour")
    season = df.with_columns(
        pl.when(pl.col("month").is_in([6, 7, 8, 9])).then(pl.lit("Jun-Sep"))
        .when(pl.col("month").is_in([3, 4, 5])).then(pl.lit("Mar-May"))
        .otherwise(pl.lit("Oct-Feb")).alias("season"))
    sp = season.group_by("season", "hour").agg(pl.col("lmp").mean()).sort("season", "hour")
    seasons = {}
    for (name,), g in sp.group_by("season"):
        v = g.sort("hour")["lmp"].to_numpy()
        seasons[name] = {"profile": v.round(2).tolist(), "peak_hour": int(np.argmax(v)),
                         "trough_hour": int(np.argmin(v)), "peak_minus_trough": float(v.max() - v.min())}
    v = prof["lmp"].to_numpy()
    # within-day spread: daily max - daily min, median over days
    daily = df.group_by("day").agg((pl.col("lmp").max() - pl.col("lmp").min()).alias("spread"),
                                   pl.col("lmp").arg_max().alias("imax"))
    return {"profile": v.round(2).tolist(), "peak_hour": int(np.argmax(v)), "trough_hour": int(np.argmin(v)),
            "peak_over_trough": float(v.max() / v.min()) if v.min() > 0 else None,
            "peak_minus_trough": float(v.max() - v.min()),
            "median_daily_spread": float(daily["spread"].median()), "by_season": seasons}


def spike_stats(df: pl.DataFrame) -> dict:
    out = {}
    years = df["ts_utc"].dt.epoch("s").max() - df["ts_utc"].dt.epoch("s").min()
    years = years / (365.25 * 86400)
    for thr in (100, 200, 500, 1000):
        sp = df.filter(pl.col("lmp") > thr)
        hod = np.bincount(sp["hour"].to_numpy(), minlength=24)
        mon = np.bincount(sp["month"].to_numpy(), minlength=13)[1:]
        out[f"gt_{thr}"] = {"hours": sp.height, "per_year": sp.height / years,
                            "share": sp.height / df.height,
                            "share_in_16_21_local": float(hod[16:21].sum() / max(sp.height, 1)),
                            "by_hour": hod.tolist(), "by_month": mon.tolist()}
    med = df.group_by("day").agg(pl.col("lmp").median().alias("dmed"))
    rel = df.join(med, on="day").filter((pl.col("dmed") > 5) & (pl.col("lmp") > 3 * pl.col("dmed")))
    hod = np.bincount(rel["hour"].to_numpy(), minlength=24)
    out["gt_3x_daily_median"] = {"hours": rel.height, "share": rel.height / df.height,
                                 "by_hour": hod.tolist(),
                                 "share_in_16_21_local": float(hod[16:21].sum() / max(rel.height, 1))}
    # concentration: share of the year's price-weighted cost in the top 5% of hours
    s = np.sort(df["lmp"].to_numpy())[::-1]
    pos = np.clip(s, 0, None)
    k = int(0.05 * len(s))
    out["top5pct_hours_share_of_positive_price_sum"] = float(pos[:k].sum() / pos.sum())
    return out


def demand_frame(ba: str) -> pl.DataFrame:
    bal = pl.scan_parquet(INTERIM_DIR / "eia930" / "balance.parquet").filter(
        pl.col("ba").cast(pl.Utf8) == ba).select(
        "ts_utc", pl.col("demand_adj_mw").alias("demand"),
        (pl.col("demand_adj_mw") - pl.col("gen_solar_adj_mw").fill_null(0)
         - pl.col("gen_wind_adj_mw").fill_null(0)).alias("net_load")).collect()
    return drop_sealed(bal)


def alignment_stats(df: pl.DataFrame, ba: str) -> dict:
    dem = demand_frame(ba)
    j = df.join(dem, on="ts_utc", how="inner").drop_nulls(["lmp", "demand", "net_load"])
    out = {"hours_joined": j.height}
    for col in ("demand", "net_load"):
        out[f"spearman_price_{col}"] = float(
            j.select(pl.corr("lmp", col, method="spearman")).item())
        daily = j.group_by("day").agg(
            pl.col("hour").sort_by("lmp").last().alias("h_price"),
            pl.col("hour").sort_by(col).last().alias(f"h_{col}"),
            pl.len().alias("n"),
        ).filter(pl.col("n") >= 22)
        diff = (daily["h_price"] - daily[f"h_{col}"]).abs()
        diff = np.minimum(diff.to_numpy(), 24 - diff.to_numpy())
        out[f"share_days_maxprice_within_1h_of_max_{col}"] = float((diff <= 1).mean())
        out[f"median_hour_max_{col}"] = float(daily[f"h_{col}"].median())
        out["median_hour_max_price"] = float(daily["h_price"].median())
        out[f"hist_hour_max_{col}"] = np.bincount(daily[f"h_{col}"].to_numpy(), minlength=24).tolist()
        out["hist_hour_max_price"] = np.bincount(daily["h_price"].to_numpy(), minlength=24).tolist()
        q95c = j[col].quantile(0.95)
        q95p = j["lmp"].quantile(0.95)
        top_c = j.filter(pl.col(col) >= q95c)
        out[f"mean_price_top5pct_{col}_hours"] = float(top_c["lmp"].mean())
        out[f"share_top5pct_price_hours_in_top5pct_{col}"] = float(
            j.filter(pl.col("lmp") >= q95p).select((pl.col(col) >= q95c).mean()).item())
    out["mean_price_all_hours"] = float(j["lmp"].mean())
    return out


def fig_daily_shape(stats: dict) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    panels = [
        (axes[0], [("np15_da", C1), ("sp15_da", C2), ("np15_rt", C3)], "CAISO (Pacific time)"),
        (axes[1], [("pace_rt", C1)], "PACE, Utah (Mountain time)"),
        (axes[2], [("ercot_north_da", C1), ("ercot_houston_da", C2), ("ercot_north_rt", C3)],
         "ERCOT (Central time)"),
    ]
    for ax, keys, title in panels:
        for key, color in keys:
            if key not in stats["series"]:
                continue
            prof = stats["series"][key]["shape"]["profile"]
            ax.plot(range(24), prof, color=color, marker="o", ms=2.5,
                    label=stats["series"][key]["meta"]["label"].split(", ")[-1]
                    if len(keys) > 1 else stats["series"][key]["meta"]["label"])
        ax.set(title=title, xlabel="Hour of day (local)", xticks=range(0, 24, 3))
        ax.title.set_fontsize(9.5)
        ax.legend(fontsize=7.5, loc="upper left")
    axes[0].set_ylabel("Mean price ($/MWh)")
    labels0 = ["NP15 day-ahead", "SP15 day-ahead", "NP15 real-time"]
    for line, lab in zip(axes[0].get_lines(), labels0):
        line.set_label(lab)
    axes[0].legend(fontsize=7.5, loc="upper left")
    labels2 = ["North day-ahead", "Houston day-ahead", "North real-time"]
    for line, lab in zip(axes[2].get_lines(), labels2):
        line.set_label(lab)
    axes[2].legend(fontsize=7.5, loc="upper left")
    fig.suptitle("Average daily price shape, before the sealed window (CAISO from 2023-07, ERCOT from 2022-01)",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    save(fig, "prices_daily_shape.png")


def fig_heatmaps(tables: dict) -> None:
    keys = [("np15_da", "CAISO NP15 day-ahead"), ("pace_rt", "PACE real-time (WEIM)"),
            ("ercot_north_da", "ERCOT North day-ahead")]
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.6))
    for ax, (key, title) in zip(axes, keys):
        df, meta = series_frame(tables, key)
        g = df.group_by("month", "hour").agg(pl.col("lmp").median()).sort("month", "hour")
        m = np.full((12, 24), np.nan)
        for r in g.iter_rows(named=True):
            m[r["month"] - 1, r["hour"]] = r["lmp"]
        im = ax.imshow(m, aspect="auto", cmap="Blues", origin="upper",
                       vmin=np.nanpercentile(m, 2), vmax=np.nanpercentile(m, 98))
        ax.set(title=title, xlabel=f"Hour of day ({meta['tz'].split('/')[-1].replace('_', ' ')})",
               yticks=range(12), yticklabels=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
                                              "Aug", "Sep", "Oct", "Nov", "Dec"],
               xticks=range(0, 24, 3))
        ax.grid(False)
        ax.title.set_fontsize(9.5)
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
        cb.set_label("Median price ($/MWh)", fontsize=8)
    fig.suptitle("Price 'grid clock': median price by month and hour (pre-seal data only)",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    save(fig, "prices_month_hour_heatmap.png")


def fig_spikes(stats: dict) -> None:
    keys = [("np15_rt", "CAISO NP15 real-time", C1), ("pace_rt", "PACE real-time", C2),
            ("ercot_north_rt", "ERCOT North real-time", C3)]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.2), sharey=False)
    for ax, (key, title, color) in zip(axes, keys):
        if key not in stats["series"]:
            continue
        sp = stats["series"][key]["spikes"]["gt_100"]
        ax.bar(range(24), sp["by_hour"], color=color, width=0.8)
        ax.set(title=f"{title}: {sp['hours']:,} hours > $100", xlabel="Hour of day (local)",
               xticks=range(0, 24, 3))
        ax.title.set_fontsize(9.5)
    axes[0].set_ylabel("Hours with mean price > $100/MWh")
    fig.suptitle("When price spikes happen: hourly means above $100/MWh, by local hour (pre-seal)",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    save(fig, "prices_spikes_by_hour.png")


def fig_alignment(stats: dict) -> None:
    keys = [("np15_da", "CAISO NP15 DA vs CISO load"), ("pace_rt", "PACE RT vs PACE load"),
            ("ercot_north_da", "ERCOT North DA vs ERCOT load")]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.3))
    for ax, (key, title) in zip(axes, keys):
        a = stats["series"][key].get("alignment")
        if not a:
            continue
        n = sum(a["hist_hour_max_price"])
        ax.plot(range(24), np.array(a["hist_hour_max_price"]) / n * 100, color=C1, marker="o", ms=2.5,
                label="daily price peak")
        ax.plot(range(24), np.array(a["hist_hour_max_demand"]) / n * 100, color=C2, marker="o", ms=2.5,
                label="daily demand peak")
        ax.plot(range(24), np.array(a["hist_hour_max_net_load"]) / n * 100, color=C3, marker="o",
                ms=2.5, label="daily net-load peak")
        ax.set(title=title, xlabel="Hour of day (local)", xticks=range(0, 24, 3))
        ax.title.set_fontsize(9.5)
    axes[0].set_ylabel("Share of days (%)")
    axes[0].legend(fontsize=7.5, loc="upper left")
    fig.suptitle("Which hour is the daily peak? Price follows net load (demand minus solar and wind) more than demand",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    save(fig, "prices_vs_demand_peak_hour.png")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", type=Path, default=None)
    ap.add_argument("--ercot-rtm-cache", type=Path, default=None)
    args = ap.parse_args()
    style()
    tables = load_all_hourly(args.ercot_rtm_cache)
    stats = {"completeness": completeness_table(tables), "edam_pace_dam": edam_pace_first_day(tables),
             "series": {}}
    for key, *_ in SERIES:
        df, meta = series_frame(tables, key)
        if df.is_empty():
            continue
        entry = {"meta": meta, "levels": level_stats(df), "shape": shape_stats(df),
                 "spikes": spike_stats(df)}
        if key in ("np15_da", "sp15_da", "np15_rt", "pace_rt", "ercot_north_da", "ercot_north_rt"):
            entry["alignment"] = alignment_stats(df, meta["ba"])
        stats["series"][key] = entry
    # cross-node: PACE RT vs CAISO hubs (same hours), pre-seal
    pace, _ = series_frame(tables, "pace_rt")
    np15, _ = series_frame(tables, "np15_rt")
    j = pace.select("ts_utc", pl.col("lmp").alias("pace")).join(
        np15.select("ts_utc", pl.col("lmp").alias("np15")), on="ts_utc")
    stats["pace_vs_np15_rt"] = {"hours": j.height,
                                "pearson": float(j.select(pl.corr("pace", "np15")).item()),
                                "mean_diff_pace_minus_np15": float((j["pace"] - j["np15"]).mean()),
                                "share_hours_pace_cheaper": float((j["pace"] < j["np15"]).mean())}
    fig_daily_shape(stats)
    fig_heatmaps(tables)
    fig_spikes(stats)
    fig_alignment(stats)
    text = json.dumps(stats, indent=1, default=str)
    if args.stats:
        args.stats.write_text(text)
    print(text[:3000])


if __name__ == "__main__":
    main()
