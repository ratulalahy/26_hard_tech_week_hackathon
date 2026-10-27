"""The common scored cohort: F13.2 prefix rule over the F14.1 U-changing scenarios.

1. For each registered scenario, run workload-only U (`warm_up` on the warm-up arrivals,
   then `u_bookings` on the stream [eval_start, F)) and find its first failure: the first
   arrival at which any request's F1 deadline exceeds F.
2. A = the minimum of those first failures (the horizon end F if none fails). The whole
   simultaneous-arrival group at A and every later arrival are excluded.
3. The primary scenario's bookings are recomputed on the truncated stream. U is causal, so
   they must equal the full run's prefix; this is asserted.

Everything here is workload-only (no grid value is read), so it is recorded before any
grid scoring. The sensitivity scenarios contribute only to A (Task 7 amendment step 3).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import polars as pl

from gridpilot.sim import HOME, SITES, WarmupState, u_bookings, warm_up
from gridpilot.workload import CANDIDATE_TYPES, DELAY_S

US = 1_000_000
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
BATCH_TYPES = ("Pretrain", "SFT", "MLLM")
HOME_CAPACITY_FACTOR = 1.25
NODE_GPUS = 8

Scenario = Callable[[pl.DataFrame, Mapping[str, int]], tuple[pl.DataFrame, Mapping[str, int]]]


def _us(t: datetime) -> int:
    if t.tzinfo is None:
        raise ValueError(f"{t!r} must be timezone-aware")
    return (t - _EPOCH) // timedelta(microseconds=1)


def _dt(us: int) -> datetime:
    return _EPOCH + timedelta(microseconds=int(us))


# --------------------------------------------------------------------------- scenarios


def _batch_delay(hours: int) -> Callable[[pl.DataFrame], pl.DataFrame]:
    def f(jobs: pl.DataFrame) -> pl.DataFrame:
        return jobs.with_columns(
            pl.when(pl.col("flexible") & pl.col("job_type").is_in(list(BATCH_TYPES)))
            .then(pl.lit(hours * 3600, dtype=pl.Int64))
            .otherwise(pl.col("max_delay_s")).alias("max_delay_s"))
    return f


def _no_flexible(jobs: pl.DataFrame) -> pl.DataFrame:
    return jobs.with_columns(pl.lit(False).alias("flexible"), pl.lit(False).alias("mobile"),
                             pl.lit(0, dtype=pl.Int64).alias("max_delay_s"))


def _all_candidates(jobs: pl.DataFrame) -> pl.DataFrame:
    cand = pl.col("job_type").is_in(list(CANDIDATE_TYPES))
    return jobs.with_columns(
        cand.alias("flexible"), cand.alias("mobile"),
        pl.when(cand).then(pl.col("job_type").replace_strict(DELAY_S, default=0,
                                                             return_dtype=pl.Int64))
        .otherwise(0).cast(pl.Int64).alias("max_delay_s"))


def home_capacity_125(slots: int = SITES[HOME]) -> int:
    """1.25× home capacity, rounded half up to an 8-GPU node: 2,288 × 1.25 = 2,860 GPUs =
    357.5 nodes → 358 nodes = 2,864 slots. Integer arithmetic, so no float tie-breaking:
    nodes = floor(slots × 5/32 + 1/2) = (10·slots + 32) // 64."""
    if HOME_CAPACITY_FACTOR != 1.25 or NODE_GPUS != 8:
        raise AssertionError("the integer rounding below encodes 1.25x and 8-GPU nodes")
    return (10 * slots + 32) // 64 * NODE_GPUS


_JOB_TRANSFORMS: dict[str, Callable[[pl.DataFrame], pl.DataFrame]] = {
    "primary": lambda j: j,
    "batch_delay_0h": _batch_delay(0),
    "batch_delay_24h": _batch_delay(24),
    "no_flexible": _no_flexible,
    "all_candidates_flexible": _all_candidates,
    "home_capacity_1.25x": lambda j: j,
}
SCENARIO_NOTES = {
    "primary": "flexible = candidate type and sha256 parity; delays 6 h (Pretrain/SFT/MLLM), "
               "1 h (Eval); home 2,288 slots",
    "batch_delay_0h": "flexible Pretrain/SFT/MLLM allowed delay 0 h; Eval stays 1 h",
    "batch_delay_24h": "flexible Pretrain/SFT/MLLM allowed delay 24 h; Eval stays 1 h",
    "no_flexible": "no job is flexible or mobile; every allowed delay is 0 h",
    "all_candidates_flexible": "every Pretrain/SFT/MLLM/Eval job is flexible and mobile",
    "home_capacity_1.25x": "home capacity 1.25x rounded to an 8-GPU node (2,864 slots)",
}


def scenario_jobs(name: str, jobs: pl.DataFrame) -> pl.DataFrame:
    """The jobs frame under a registered F14.1 scenario (flags and delays are assumed)."""
    return _JOB_TRANSFORMS[name](jobs)


def scenario_sites(name: str, sites: Mapping[str, int] = SITES) -> dict[str, int]:
    out = dict(sites)
    if name == "home_capacity_1.25x":
        out[HOME] = home_capacity_125(out[HOME])
    return out


def _registered(name: str) -> Scenario:
    def f(jobs, sites):
        return scenario_jobs(name, jobs), scenario_sites(name, sites)
    return f


SCENARIOS: dict[str, Scenario] = {n: _registered(n) for n in _JOB_TRANSFORMS}


# --------------------------------------------------------------------------- cohort


def first_failure(bookings: pl.DataFrame, jobs: pl.DataFrame, F: datetime) -> datetime | None:
    """The first arrival whose F1 deadline (`bookings.deadline_us`) exceeds F, or None."""
    f_us = _us(F)
    j = jobs.select("job_uid", pl.col("arrival_ts").dt.epoch("us").alias("arr"))
    bad = bookings.join(j, on="job_uid", how="inner").filter(pl.col("deadline_us") > f_us)
    if bad.height == 0:
        return None
    return _dt(int(bad["arr"].min()))


def _hash_lines(lines) -> str:
    h = hashlib.sha256()
    for line in lines:
        h.update(line.encode())
        h.update(b"\n")
    return h.hexdigest()


def ids_hash(job_uids) -> str:
    return _hash_lines(sorted(job_uids))


def booking_hash(bookings: pl.DataFrame) -> str:
    b = bookings.sort("job_uid")
    return _hash_lines(f"{u},{s},{a},{e},{d}" for u, s, a, e, d in b.select(
        "job_uid", "site", "start_us", "end_us", "deadline_us").iter_rows())


def ledger_hash(ledger: pl.DataFrame) -> str:
    """Canonical policy-ledger hash (F12.6): rows sorted by job_uid, over site, start_us and
    end_us (integer µs)."""
    b = ledger.sort("job_uid").select(
        "job_uid", "site", pl.col("start_ts").dt.epoch("us").alias("s"),
        pl.col("end_ts").dt.epoch("us").alias("e"))
    return _hash_lines(f"{u},{s},{a},{e}" for u, s, a, e in b.iter_rows())


@dataclass(frozen=True)
class Cohort:
    A: datetime
    F: datetime
    first_failure: dict[str, datetime | None]
    jobs: pl.DataFrame  # primary-scenario cohort, arrivals in [eval_start, A)
    bookings: pl.DataFrame  # primary U bookings of the cohort
    warm: WarmupState  # primary U warm-up state
    n_stream: int
    n_excluded: int
    excluded_gpu_h: float
    prefix_unchanged: bool
    ids_hash: str
    booking_hash: str
    max_booking_end: datetime | None
    max_deadline: datetime | None


def prefix_cohort(
    warm_jobs: pl.DataFrame,
    stream: pl.DataFrame,
    F: datetime,
    *,
    scenarios: Mapping[str, Scenario] = SCENARIOS,
    sites: Mapping[str, int] = SITES,
    primary: str = "primary",
) -> Cohort:
    """F13.2 + F14.1: the common A and the primary cohort with its unchanged bookings.

    `warm_jobs` are the warm-up arrivals [init, eval_start) and `stream` the arrivals
    [eval_start, F); both get each scenario's transform (a scenario is a complete
    scenario, warm-up included).
    """
    if primary not in scenarios:
        raise ValueError(f"the primary scenario {primary!r} must be registered")
    fails: dict[str, datetime | None] = {}
    full_primary = None
    for name, fn in scenarios.items():
        wj, ws = fn(warm_jobs, sites)
        sj, ss = fn(stream, sites)
        warm = warm_up(wj, ws)
        b = u_bookings(sj, ss, warm=warm)
        fails[name] = first_failure(b, sj, F)
        if name == primary:
            full_primary = (b, warm, sj, ss, wj)
    hits = [t for t in fails.values() if t is not None]
    A = min(hits) if hits else F
    b_full, _, sj, ss, wj = full_primary
    cohort = sj.filter(pl.col("arrival_ts") < A)
    warm = warm_up(wj, ss)
    bookings = u_bookings(cohort, ss, warm=warm)
    uids = cohort["job_uid"].to_list()
    prefix = b_full.filter(pl.col("job_uid").is_in(uids)).sort("job_uid")
    unchanged = bookings.sort("job_uid").equals(prefix)
    if not unchanged:
        raise AssertionError("prefix bookings changed after truncation: U is not causal")
    if bookings.height and int(bookings["deadline_us"].max()) > _us(F):
        raise AssertionError("a cohort deadline exceeds F after truncation")
    excl = sj.filter(pl.col("arrival_ts") >= A)
    return Cohort(
        A=A, F=F, first_failure=fails, jobs=cohort, bookings=bookings, warm=warm,
        n_stream=sj.height, n_excluded=excl.height,
        excluded_gpu_h=float((excl["gpus"] * excl["duration_s"]).sum() / 3600)
        if excl.height else 0.0,
        prefix_unchanged=unchanged, ids_hash=ids_hash(uids), booking_hash=booking_hash(bookings),
        max_booking_end=_dt(int(bookings["end_us"].max())) if bookings.height else None,
        max_deadline=_dt(int(bookings["deadline_us"].max())) if bookings.height else None,
    )


__all__ = ["SCENARIOS", "SCENARIO_NOTES", "Cohort", "booking_hash", "first_failure",
           "home_capacity_125", "ids_hash", "ledger_hash", "prefix_cohort", "scenario_jobs",
           "scenario_sites"]
