"""Profile the GPU job traces for docs/data-profile/workloads-prices.md.

Prints every statistic the doc cites (also written as JSON to --stats) and draws the
figures into docs/data-profile/figures/workloads-prices/. Traces are 2020-2023 (2026
release for the supplementary spot trace) and are never joined to grid data here.

    cd lab && uv run python scripts/recon_traces_profile.py --stats /tmp/traces_stats.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from gridpilot.data import traces as T
from gridpilot.paths import REPO_ROOT

FIG_DIR = REPO_ROOT / "docs" / "data-profile" / "figures" / "workloads-prices"
SERIES = {"acme_seren": "#2a78d6", "acme_kalos": "#eb6834", "pai2020": "#1baf7a"}
LABEL = {
    "acme_seren": "Acme Seren (2023, LLM)",
    "acme_kalos": "Acme Kalos (2023, LLM)",
    "pai2020": "Alibaba PAI (2020, MLaaS)",
    "spot2026": "Alibaba spot (2026 release)",
}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def style() -> None:
    plt.rcParams.update({
        "figure.dpi": 130, "savefig.dpi": 160, "font.size": 9.5,
        "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
        "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
        "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "lines.linewidth": 1.8,
    })


def save(fig, name: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / name, bbox_inches="tight")
    plt.close(fig)
    print(f"figure -> {FIG_DIR / name}")


def q(s: pl.Series, ps=(0.1, 0.25, 0.5, 0.75, 0.9, 0.99)) -> dict:
    s = s.drop_nulls()
    return {f"p{int(p * 100)}": float(s.quantile(p, "linear")) for p in ps} | {
        "max": float(s.max()), "mean": float(s.mean())}


def busy_gpus_hourly(g: pl.DataFrame) -> pl.DataFrame:
    """Hourly mean busy GPUs from job [start, end) spans (minute difference array)."""
    g = g.filter(pl.col("start_ts").is_not_null() & pl.col("end_ts").is_not_null())
    t0 = g["start_ts"].min()
    s = ((g["start_ts"] - t0).dt.total_seconds() // 60).to_numpy().astype(np.int64)
    e = ((g["end_ts"] - t0).dt.total_seconds() // 60).to_numpy().astype(np.int64)
    w = g["gpu_count"].to_numpy()
    n = int(e.max()) + 2
    diff = np.zeros(n)
    np.add.at(diff, s, w)
    np.add.at(diff, e, -w)
    busy = np.cumsum(diff)[: n - 1]
    hours = len(busy) // 60
    hourly = busy[: hours * 60].reshape(hours, 60).mean(axis=1)
    ts = pl.datetime_range(t0, t0 + pl.duration(hours=hours - 1), "1h", eager=True)
    return pl.DataFrame({"ts_utc": ts, "busy_gpus": hourly})


def profile_trace(df: pl.DataFrame, name: str) -> dict:
    allj = df.filter(pl.col("trace") == name)
    g = allj.filter(pl.col("gpu_count") > 0)
    known = g.filter(pl.col("run_s").is_not_null())
    span_h = (g["submit_ts"].max() - g["submit_ts"].min()).total_seconds() / 3600  # nulls ignored
    gh = known["gpu_hours"].sum()
    out = {
        "jobs_total": allj.height, "gpu_jobs": g.height, "gpu_jobs_with_run": known.height,
        "span_days": span_h / 24, "gpu_hours": gh, "mean_gpus_busy": gh / span_h,
        "run_s": q(known["run_s"]), "gpu_count": q(g["gpu_count"]),
        "gpu_hours_per_job": q(known["gpu_hours"]),
        "share_jobs_single_gpu_or_less": float((g["gpu_count"] <= 1).mean()),
    }
    for h in (1, 6, 24):
        long = known["run_s"] > h * 3600
        out[f"share_jobs_gt_{h}h"] = float(long.mean())
        out[f"share_gpuh_gt_{h}h"] = float(known.filter(long)["gpu_hours"].sum() / gh)
    for k in (8, 64, 256):
        out[f"share_gpuh_ge_{k}gpus"] = float(
            known.filter(pl.col("gpu_count") >= k)["gpu_hours"].sum() / gh)
    st = g.group_by("status").agg(pl.len().alias("jobs"), pl.col("gpu_hours").sum())
    out["status_share_jobs"] = {r["status"]: r["jobs"] / g.height for r in st.iter_rows(named=True)}
    out["status_share_gpuh"] = {
        r["status"]: (r["gpu_hours"] or 0) / gh for r in st.iter_rows(named=True)}
    if g["queue_s"].null_count() < g.height:
        out["queue_s"] = q(g["queue_s"])
        out["share_queued_gt_1h"] = float((g["queue_s"].drop_nulls() > 3600).mean())
        out["share_queued_gt_10min"] = float((g["queue_s"].drop_nulls() > 600).mean())
    if g["submit_local"].null_count() < g.height:
        gl = g.filter(pl.col("submit_local").is_not_null())
        out["jobs_without_submit_time"] = g.height - gl.height
        hod = gl.group_by(pl.col("submit_local").dt.hour().alias("h")).len().sort("h")
        share = (hod["len"] / hod["len"].sum()).to_list()
        out["arrival_share_by_local_hour"] = share
        out["arrival_peak_to_trough"] = max(share) / min(share)
        out["arrival_share_16_21_local"] = float(sum(share[16:21]))
        dow = gl.group_by(pl.col("submit_local").dt.weekday().alias("d")).len().sort("d")
        ds = (dow["len"] / dow["len"].sum()).to_list()
        out["arrival_share_by_dow"] = ds
        out["weekend_vs_weekday_daily_arrivals"] = (sum(ds[5:]) / 2) / (sum(ds[:5]) / 5)
    if g["gpu_util"].null_count() < g.height:
        u = known.filter(pl.col("gpu_util").is_not_null())
        out["gpu_util"] = q(u["gpu_util"]) | {
            "gpuh_weighted_mean": float((u["gpu_util"] * u["gpu_hours"]).sum() / u["gpu_hours"].sum()),
            "coverage_jobs": float(g["gpu_util"].is_not_null().mean())}
    by_type = known.group_by("job_type").agg(
        pl.len().alias("jobs"), pl.col("gpu_hours").sum().alias("gpuh"),
        pl.col("run_s").median().alias("med_run_s"), pl.col("gpu_count").median().alias("med_gpus"),
    ).with_columns((pl.col("gpuh") / gh).alias("gpuh_share")).sort("gpuh", descending=True)
    st_type = g.group_by("job_type").agg(
        (pl.col("status") == "failed").mean().alias("fail_rate"),
        (pl.col("status") == "cancelled").mean().alias("cancel_rate"),
        (pl.col("status") == "preempted").mean().alias("preempt_rate"),
        pl.col("queue_s").median().alias("med_queue_s"),
    )
    out["by_type"] = by_type.join(st_type, on="job_type", how="left").head(15).to_dicts()
    return out


def fig_arrivals(df: pl.DataFrame, stats: dict) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.4), gridspec_kw={"width_ratios": [2.2, 1]})
    for name, color in SERIES.items():
        s = np.array(stats[name]["arrival_share_by_local_hour"]) * 100
        a1.plot(range(24), s, color=color, label=LABEL[name], marker="o", ms=3)
        d = np.array(stats[name]["arrival_share_by_dow"]) * 100
        a2.plot(range(7), d, color=color, marker="o", ms=3)
    a1.axvspan(16, 21, color="#e34948", alpha=0.07, lw=0)
    a1.text(18.5, a1.get_ylim()[1] * 0.97, "16-21 h\n(typical grid\nevening peak)", ha="center",
            va="top", fontsize=8, color=INK2)
    a1.set(xlabel="Hour of day, cluster local time (UTC+8)", ylabel="Share of GPU-job submissions (%)",
           xticks=range(0, 24, 3), xlim=(-0.5, 23.5))
    a1.legend(loc="upper left", fontsize=8)
    a2.set(xlabel="Day of week, cluster local time", ylabel="Share of submissions (%)",
           xticks=range(7), xticklabels=DOW)
    fig.suptitle("When GPU jobs arrive: a strong working-hours pattern", x=0.01, ha="left",
                 fontsize=11, color=INK)
    save(fig, "traces_arrivals_hour_dow.png")


def fig_durations(df: pl.DataFrame) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.6))
    for name, color in SERIES.items():
        k = df.filter((pl.col("trace") == name) & (pl.col("gpu_count") > 0)
                      & pl.col("run_s").is_not_null() & (pl.col("run_s") > 0))
        r = np.sort(k["run_s"].to_numpy()) / 3600
        ccdf = 1 - np.arange(len(r)) / len(r)
        a1.loglog(r, ccdf * 100, color=color, label=LABEL[name])
        order = np.argsort(k["run_s"].to_numpy())
        rs = k["run_s"].to_numpy()[order] / 3600
        cum = np.cumsum(k["gpu_hours"].to_numpy()[order])
        a2.semilogx(rs, cum / cum[-1] * 100, color=color, label=LABEL[name])
    for a in (a1, a2):
        for h, lab in ((1, "1 h"), (6, "6 h"), (24, "24 h")):
            a.axvline(h, color=INK2, lw=0.7, ls=":")
            a.text(h, 1.02, lab, transform=a.get_xaxis_transform(), ha="center", fontsize=7.5,
                   color=INK2)
    a1.set(xlabel="Job run time (hours, log scale)", ylabel="Jobs running longer than x (%, log)",
           xlim=(1 / 360, 2000))
    a1.legend(fontsize=8, loc="lower left")
    a2.set(xlabel="Job run time (hours, log scale)",
           ylabel="Cumulative share of GPU-hours (%)", xlim=(1 / 360, 2000), ylim=(0, 100))
    fig.suptitle("Most jobs are short, but most GPU-hours come from long jobs", x=0.01,
                 ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    save(fig, "traces_duration_and_gpuhours.png")


def fig_gpu_count(df: pl.DataFrame) -> None:
    bins = [0, 1, 2, 8, 64, 256, 1e9]
    labels = ["<=1", "2", "3-8", "9-64", "65-256", ">256"]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.2), sharey=True)
    for ax, (name, color) in zip(axes, SERIES.items()):
        k = df.filter((pl.col("trace") == name) & (pl.col("gpu_count") > 0)
                      & pl.col("run_s").is_not_null())
        idx = np.digitize(k["gpu_count"].to_numpy(), bins[1:-1], right=True)
        jobs = np.bincount(idx, minlength=len(labels)) / k.height * 100
        gh = np.bincount(idx, weights=k["gpu_hours"].to_numpy(), minlength=len(labels))
        gh = gh / gh.sum() * 100
        x = np.arange(len(labels))
        ax.bar(x - 0.2, jobs, 0.38, color=color, alpha=0.45, label="share of jobs")
        ax.bar(x + 0.2, gh, 0.38, color=color, label="share of GPU-hours")
        ax.set(title=LABEL[name], xticks=x, xticklabels=labels, xlabel="GPUs per job")
        ax.title.set_fontsize(9)
    axes[0].set_ylabel("Share (%)")
    axes[0].legend(fontsize=8)
    fig.suptitle("Single-GPU jobs dominate counts; multi-node jobs dominate GPU-hours (Acme)",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    save(fig, "traces_gpu_count.png")


def fig_types(stats: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.3))
    for ax, name in zip(axes, ("acme_seren", "acme_kalos")):
        rows = [r for r in stats[name]["by_type"] if r["job_type"] != "CPU"]
        rows.sort(key=lambda r: r["gpuh_share"])
        y = np.arange(len(rows))
        ax.barh(y, [r["gpuh_share"] * 100 for r in rows], color=SERIES[name], height=0.6)
        for i, r in enumerate(rows):
            ax.text(r["gpuh_share"] * 100 + 1, i,
                    f"{r['jobs']:,} jobs; median {r['med_run_s'] / 60:.0f} min on "
                    f"{r['med_gpus']:.0f} GPU(s)", va="center", fontsize=7.5, color=INK2)
        ax.set(yticks=y, yticklabels=[r["job_type"] for r in rows], xlim=(0, 150),
               xticks=range(0, 101, 20), xlabel="Share of the trace's GPU-hours (%)",
               title=LABEL[name])
        ax.title.set_fontsize(9)
    fig.suptitle("Acme labels every job: pre-training is a few jobs and most of the GPU-hours",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    save(fig, "traces_acme_job_types.png")


def fig_busy(df: pl.DataFrame) -> dict:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 3.4), gridspec_kw={"width_ratios": [2, 1]})
    out = {}
    for name, color in (("acme_seren", SERIES["acme_seren"]),):
        g = df.filter((pl.col("trace") == name) & (pl.col("gpu_count") > 0))
        b = busy_gpus_hourly(g)
        daily = b.group_by_dynamic("ts_utc", every="1d").agg(pl.col("busy_gpus").mean())
        a1.plot(daily["ts_utc"].to_numpy(), daily["busy_gpus"].to_numpy(), color=color)
        loc = b.with_columns(pl.col("ts_utc").dt.convert_time_zone(T.CLUSTER_TZ).dt.hour().alias("h"))
        prof = loc.group_by("h").agg(pl.col("busy_gpus").mean()).sort("h")
        a2.plot(prof["h"].to_numpy(), prof["busy_gpus"].to_numpy(), color=color, marker="o", ms=3)
        steady = b.filter(pl.col("ts_utc") > b["ts_utc"].min() + pl.duration(days=7))
        out[name] = {
            "busy_gpus_mean": float(steady["busy_gpus"].mean()),
            "busy_gpus_p05": float(steady["busy_gpus"].quantile(0.05)),
            "busy_gpus_p95": float(steady["busy_gpus"].quantile(0.95)),
            "hour_of_day_profile_max_over_min": float(prof["busy_gpus"].max() / prof["busy_gpus"].min()),
        }
    a1.set(xlabel="Date (2023, UTC)", ylabel="Busy GPUs (daily mean)")
    a2.set(xlabel="Hour of day, cluster local time", ylabel="Busy GPUs (mean)", xticks=range(0, 24, 6))
    a2.set_ylim(0, None)
    fig.suptitle("Acme Seren: the cluster runs near-flat day and night; campaigns move the level",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.autofmt_xdate()
    fig.tight_layout()
    save(fig, "traces_seren_busy_gpus.png")
    return out


def fig_power() -> dict:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.3))
    out = {}
    for name, color, ax in (("gpu_power_seren_w", SERIES["acme_seren"], a1),
                            ("gpu_power_kalos_w", SERIES["acme_kalos"], a1),
                            ("gpu_server_power_w", SERIES["acme_seren"], a2)):
        c = T.load_acme_power_cdf(name)
        ax.plot(c["watts"].to_numpy(), c["cdf"].to_numpy() * 100, color=color,
                label=T.ACME_POWER_CDFS[name][2])
        out[name] = {"p10": T.cdf_quantile(c, 0.10), "p25": T.cdf_quantile(c, 0.25),
                     "p50": T.cdf_quantile(c, 0.5), "p75": T.cdf_quantile(c, 0.75),
                     "p90": T.cdf_quantile(c, 0.9), "max": float(c["watts"].max()),
                     "mean": T.cdf_mean(c)}
    a1.axvline(400, color=INK2, ls=":", lw=0.8)
    a1.text(405, 8, "A100 SXM TDP 400 W", fontsize=7.5, color=INK2)
    a1.set(xlabel="GPU board power (W)", ylabel="Share of samples at or below x (%)")
    a1.legend(fontsize=7.5, loc="lower right")
    a2.axvline(6500, color=INK2, ls=":", lw=0.8)
    a2.text(6450, 8, "DGX A100 max 6.5 kW", fontsize=7.5, color=INK2, ha="right")
    a2.set(xlabel="8-GPU server power (W)", ylabel="Share of samples at or below x (%)")
    a2.legend(fontsize=7.5, loc="lower right")
    fig.suptitle("Measured power (Acme, 2023): bimodal, idle near 60 W per GPU, busy near TDP",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    save(fig, "traces_acme_power_cdf.png")
    return out


def spot_stats(df: pl.DataFrame) -> dict:
    s = df.filter(pl.col("trace") == "spot2026")
    gh = s["gpu_hours"].sum()
    rows = s.group_by("job_type").agg(
        pl.len().alias("jobs"), pl.col("gpu_hours").sum().alias("gpuh"),
        pl.col("run_s").median().alias("med_run_s"), pl.col("gpu_count").median().alias("med_gpus"),
        (pl.col("run_s") > 86400).mean().alias("share_gt_24h"),
    ).with_columns((pl.col("gpuh") / gh).alias("gpuh_share"), (pl.col("jobs") / s.height).alias("job_share"))
    started_in_trace = s.filter(pl.col("submit_ts") > s["submit_ts"].min())
    gh2 = started_in_trace["gpu_hours"].sum()
    rows2 = started_in_trace.group_by("job_type").agg(pl.col("gpu_hours").sum() / gh2)
    by_gpu = s.group_by("gpu_type", "job_type").agg(pl.col("gpu_hours").sum()).sort("gpu_hours", descending=True)
    return {"jobs": s.height, "span_days": (s["submit_ts"].max() - s["submit_ts"].min()).total_seconds() / 86400,
            "by_type": rows.to_dicts(), "gpuh_share_excl_t0": rows2.to_dicts(), "by_gpu": by_gpu.to_dicts()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", type=Path, default=None)
    args = ap.parse_args()
    style()
    df = T.load_all()
    stats = {name: profile_trace(df, name) for name in ("acme_seren", "acme_kalos", "pai2020")}
    stats["spot2026"] = spot_stats(df)
    pai = df.filter(pl.col("trace") == "pai2020")
    groups = T.pai_groups().group_by("group").len()
    stats["pai2020"]["recurring_groups"] = {
        "instances_tagged": int(groups["len"].sum()), "groups": groups.height,
        "share_instances_in_groups_ge_5": float(groups.filter(pl.col("len") >= 5)["len"].sum() / groups["len"].sum()),
    }
    stats["pai2020"]["share_jobs_fractional_gpu"] = float(
        ((pai["gpu_count"] > 0) & (pai["gpu_count"] < 1)).sum() / (pai["gpu_count"] > 0).sum())
    fig_arrivals(df, stats)
    fig_durations(df)
    fig_gpu_count(df)
    fig_types(stats)
    stats["busy"] = fig_busy(df)
    stats["power"] = fig_power()
    text = json.dumps(stats, indent=1, default=str)
    if args.stats:
        args.stats.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
