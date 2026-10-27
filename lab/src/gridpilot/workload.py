"""Seren continuous replay cycle (spec section 7, "Replay calendar").

One 161-day cycle of the Acme Seren trace (submissions from 2023-03-06T00:00+08:00) is
mapped onto a synthetic US business clock and repeated forward:

    arrival = ANCHOR + phase + k * 161 d + (submit_ts - CYCLE_START)

`ANCHOR` is Monday 2024-01-01 00:00 at fixed UTC-07:00. Because the offset is taken from
elapsed time between instants, the source's UTC+8 wall clock disappears while the weekday,
burst structure and long durations are kept. Whole-cycle repetition and the clock mapping
are `simulated`; run times are `measured`.

Flexibility (assumed, spec section 7): Pretrain, SFT, MLLM and Eval are candidates and
sha256(f"{source_id}:42") parity picks half of them. The flag depends only on the source
ID, so every repeated instance (job_uid "{source_id}#c{cycle}") keeps it.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

import polars as pl

from gridpilot.data.traces import load_acme

log = logging.getLogger(__name__)

CYCLE_START = datetime(2023, 3, 6, tzinfo=ZoneInfo("Asia/Shanghai"))
CYCLE_DAYS = 161
ANCHOR = datetime(2024, 1, 1, tzinfo=timezone(timedelta(hours=-7)))  # fixed UTC-07:00

FLEX_SEED = 42
CANDIDATE_TYPES = ("Pretrain", "SFT", "MLLM", "Eval")
DELAY_S = {"Pretrain": 6 * 3600, "SFT": 6 * 3600, "MLLM": 6 * 3600, "Eval": 3600}

_CYCLE = timedelta(days=CYCLE_DAYS)
_CYCLE_START_UTC = CYCLE_START.astimezone(UTC)
_ANCHOR_UTC = ANCHOR.astimezone(UTC)


def is_flexible(source_id: str, job_type: str) -> bool:
    """Spec flexibility rule: candidate type and an even sha256(f"{id}:42") digest."""
    if job_type not in CANDIDATE_TYPES:
        return False
    return int(hashlib.sha256(f"{source_id}:{FLEX_SEED}".encode()).hexdigest(), 16) % 2 == 0


@lru_cache(maxsize=1)
def _cycle_jobs() -> pl.DataFrame:
    """Source attempts of one cycle with their cycle-relative submission offset."""
    t = load_acme("seren")
    n0 = t.height
    cycle_end = _CYCLE_START_UTC + _CYCLE
    in_cycle = (pl.col("submit_ts") >= _CYCLE_START_UTC) & (pl.col("submit_ts") < cycle_end)
    gpu_ok = pl.col("gpu_count").is_finite() & (pl.col("gpu_count") > 0)
    run_ok = pl.col("run_s").is_finite() & (pl.col("run_s") > 0)

    def drop(frame: pl.DataFrame, keep: pl.Expr, reason: str) -> pl.DataFrame:
        kept = frame.filter(keep.fill_null(False))
        log.info("workload exclusion: %d attempts dropped: %s", frame.height - kept.height, reason)
        return kept

    t = drop(t, in_cycle, f"submitted outside source cycle [{CYCLE_START}, +{CYCLE_DAYS} d)")
    t = drop(t, gpu_ok, "no GPU requested (CPU-only, or non-finite/non-positive gpu_count)")
    t = drop(t, run_ok, "non-positive or non-finite run_s")
    log.info("workload: %d of %d Seren attempts kept (any status)", t.height, n0)

    flex = {
        sid: is_flexible(sid, jt)
        for sid, jt in t.filter(pl.col("job_type").is_in(CANDIDATE_TYPES))
        .select("job_id", "job_type").iter_rows()
    }
    return t.select(
        pl.col("job_id").alias("source_id"),
        "submit_ts",
        (pl.col("submit_ts") - _CYCLE_START_UTC).alias("offset"),
        pl.col("run_s"),
        pl.col("run_s").alias("duration_s"),
        pl.col("gpu_count").round().cast(pl.Int64).alias("gpus"),
        "job_type",
        pl.col("job_id").replace_strict(flex, default=False, return_dtype=pl.Boolean).alias("flexible"),
    ).with_columns(
        pl.when(pl.col("flexible"))
        .then(pl.col("job_type").replace_strict(DELAY_S, default=0, return_dtype=pl.Int64))
        .otherwise(0)
        .alias("max_delay_s")
    )


def replay(start: datetime, end: datetime, phase_days: int = 0) -> pl.DataFrame:
    """Replayed Seren arrivals in [start, end), sorted by arrival.

    `phase_days` shifts the whole workload later against the calendar (pre-registered
    0, 49, 98). Cycle `k >= 0` spans [ANCHOR + phase + k*161 d, +161 d); nothing arrives
    before ANCHOR + phase.
    """
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware")
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    base = _cycle_jobs()
    origin = _ANCHOR_UTC + timedelta(days=phase_days)
    k_lo = max(0, (start - origin) // _CYCLE)
    k_hi = (end - origin) // _CYCLE  # inclusive; cycle k_hi may start before `end`
    parts = []
    for k in range(k_lo, k_hi + 1):
        c0 = origin + k * _CYCLE
        if c0 >= end or c0 + _CYCLE <= start:
            continue
        parts.append(
            base.with_columns(
                (pl.lit(c0) + pl.col("offset")).alias("arrival_ts"),
                (pl.col("source_id") + f"#c{k}").alias("job_uid"),
            ).filter((pl.col("arrival_ts") >= start) & (pl.col("arrival_ts") < end))
        )
    if not parts:
        parts = [base.head(0).with_columns(
            pl.lit(None, dtype=pl.Datetime("us", "UTC")).alias("arrival_ts"),
            pl.lit(None, dtype=pl.Utf8).alias("job_uid"),
        )]
    out = pl.concat(parts).sort("arrival_ts", "job_uid")
    return out.select(
        "job_uid",
        "source_id",
        pl.col("arrival_ts").dt.cast_time_unit("us").dt.convert_time_zone("UTC"),
        "duration_s",
        "gpus",
        "job_type",
        "flexible",
        "max_delay_s",
        pl.col("flexible").alias("mobile"),
        pl.lit("simulated").alias("evidence_arrival"),
        pl.lit("measured").alias("evidence_duration"),
    )


def cycle_stats(df: pl.DataFrame | None = None) -> dict:
    """Spec-required replay statistics: unique source attempts, repeated instances,
    GPU-hours, and the energy share of long (> 24 h) and large (> 512 GPU) attempts.

    Energy is proportional to gpus x duration (constant 0.60 kW per slot), so shares are
    shares of GPU-hours. With no `df`, the single source cycle is summarised."""
    d = df if df is not None else _cycle_jobs()
    gh = pl.col("gpus") * pl.col("duration_s") / 3600.0
    long_, large = pl.col("duration_s") > 24 * 3600, pl.col("gpus") > 512
    total = d.select(gh.sum()).item()
    share = lambda m: d.filter(m).select(gh.sum()).item() / total  # noqa: E731
    return {
        "unique_attempts": d["source_id"].n_unique(),
        "instances": d.height,
        "gpu_hours": total,
        "energy_share_gt_24h": share(long_),
        "energy_share_gt_512_gpus": share(large),
        "energy_share_either": share(long_ | large),
        "job_share_gt_24h": d.filter(long_).height / d.height,
        "job_share_gt_512_gpus": d.filter(large).height / d.height,
    }
