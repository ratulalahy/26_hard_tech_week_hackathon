"""Event-driven simulator for non-preemptive gang jobs (spec §8, §15 F1, F2, F5, F10).

Events are job arrivals, processed in a fixed order: arrival time, then declared
deadline, then `job_uid`. At each arrival the policy sees only that job, the
reservations already committed, and the static context; it returns an `Action`
(site, execution start). The engine checks the action and reserves it at once.
Reservations are immutable: no preemption, no rescheduling, no release.

A job that cannot finish by its deadline is never dropped. It goes to the late-work
queue: it runs its full budget at its earliest legal finish (home first, then BA
code on ties) and is marked `late=True`.

Time inside the engine and the `Policy` protocol is float Unix seconds (UTC).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np
import polars as pl

from gridpilot.sim.capacity import Capacity

SITES: dict[str, int] = {"PACE": 2288, "CISO": 512, "BPAT": 512, "NEVP": 512}
HOME = "PACE"
TRANSFER_S = 1800.0  # remote staging before execution (assumed, §7)
LATE_TOL_S = 1e-6  # finish times within a microsecond of the deadline are on time

JOB_COLUMNS = {
    "job_uid": pl.Utf8,
    "arrival_ts": pl.Datetime,
    "duration_s": pl.Float64,
    "gpus": pl.Int64,
    "job_type": pl.Utf8,
    "flexible": pl.Boolean,
    "max_delay_s": pl.Float64,
    "mobile": pl.Boolean,
}
LEDGER_COLUMNS = [
    "job_uid", "site", "start_ts", "end_ts", "transfer", "late", "deadline_ts", "gpus",
]

Ledger = pl.DataFrame
"""One row per job: job_uid, site, start_ts, end_ts, transfer, late, deadline_ts, gpus.

start_ts/end_ts are execution (after any transfer), datetime[us, UTC], rounded to the
microsecond; `transfer` is True when the job ran away from home.
"""


# --------------------------------------------------------------------------- types


@dataclass(frozen=True, slots=True)
class Job:
    """One request as a policy sees it. Times are Unix seconds."""

    job_uid: str
    arrival: float
    duration_s: float
    gpus: int
    job_type: str
    flexible: bool
    max_delay_s: float
    mobile: bool
    deadline: float  # F1 deadline if given, else arrival + duration + max_delay

    @property
    def latest_start(self) -> float:
        """The latest execution start that still meets the deadline."""
        return self.deadline - self.duration_s


@dataclass(frozen=True, slots=True)
class Action:
    """Run the job at `site`, executing from `start` (Unix seconds, after any transfer)."""

    site: str
    start: float


@dataclass(frozen=True)
class SimContext:
    """Static facts shared by every policy in a run, plus the legality helpers."""

    sites: Mapping[str, int]
    home: str = HOME
    transfer_s: float = TRANSFER_S

    def legal_sites(self, job: Job) -> tuple[str, ...]:
        """Sites the job may run at: home first, then by BA code. Immobile jobs stay home."""
        order = [self.home] + sorted(s for s in self.sites if s != self.home)
        if not job.mobile:
            order = [self.home]
        return tuple(s for s in order if self.sites.get(s, 0) >= job.gpus)

    def ready_at(self, job: Job, site: str) -> float:
        """Earliest execution start at `site`: arrival, plus the transfer if remote."""
        return job.arrival + (0.0 if site == self.home else self.transfer_s)

    def earliest_start(
        self,
        job: Job,
        site: str,
        capacities: Mapping[str, Capacity],
        latest: float = math.inf,
    ) -> float | None:
        """Earliest feasible execution start at `site`, or None (too big, or past `latest`)."""
        return capacities[site].earliest_start(
            self.ready_at(job, site), job.duration_s, job.gpus, latest
        )

    def earliest_action(
        self,
        job: Job,
        capacities: Mapping[str, Capacity],
        sites: Sequence[str] | None = None,
    ) -> Action | None:
        """Earliest finish over `sites` (default: all legal), ties to home then BA code."""
        best: tuple[float, bool, str] | None = None
        for site in self.legal_sites(job) if sites is None else sites:
            s = self.earliest_start(job, site, capacities)
            if s is None:
                continue
            key = (s + job.duration_s, site != self.home, site)
            if best is None or key < best:
                best = key
        if best is None:
            return None
        return Action(best[2], best[0] - job.duration_s)

    def on_time(self, job: Job, start: float) -> bool:
        return start + job.duration_s <= job.deadline + LATE_TOL_S


@runtime_checkable
class Policy(Protocol):
    """A placement rule. It must not mutate `capacities`; the engine reserves.

    Return an `Action` to commit, or None to send the job to the late-work queue
    (the engine then schedules its earliest legal finish and marks it late). An action
    that finishes after the deadline is accepted and also marked late.
    """

    name: str

    def choose(
        self,
        job: Job,
        now: float,
        capacities: Mapping[str, Capacity],
        ctx: SimContext,
    ) -> Action | None: ...


# --------------------------------------------------------------------------- policies


class U:
    """Earliest feasible execution at home (PACE), in FIFO order; no carbon input."""

    name = "U"

    def choose(self, job, now, capacities, ctx):
        if ctx.home not in ctx.legal_sites(job):
            return None
        return Action(ctx.home, ctx.earliest_start(job, ctx.home, capacities))


class G:
    """Earliest finish across the legal core sites, then home, then BA code; no carbon."""

    name = "G"

    def choose(self, job, now, capacities, ctx):
        return ctx.earliest_action(job, capacities)


class S:
    """Fixed clean-region priority.

    Try the sites in `ranking` (the training-window mean consumed intensity order,
    cleanest first), then home: take the first whose earliest feasible completion meets
    the deadline. If none does, the job goes to the late-work queue.
    """

    name = "S"

    def __init__(self, ranking: Sequence[str] = ("BPAT", "CISO", "NEVP")):
        self.ranking = tuple(ranking)

    def choose(self, job, now, capacities, ctx):
        legal = ctx.legal_sites(job)
        order = [s for s in self.ranking if s in legal]
        if ctx.home in legal and ctx.home not in order:
            order.append(ctx.home)
        for site in order:
            s = ctx.earliest_start(job, site, capacities, latest=job.latest_start + LATE_TOL_S)
            if s is not None and ctx.on_time(job, s):
                return Action(site, s)
        return None


# --------------------------------------------------------------------------- engine


@dataclass(frozen=True)
class WarmupState:
    """Capacity after a U warm-up run (F2). `simulate` copies it, so it is reusable."""

    capacities: Mapping[str, Capacity]
    last_arrival: float
    ledger: Ledger = field(repr=False)


@dataclass
class _Run:
    order: pl.DataFrame  # the jobs in processing order, with _arr_s, _base_s, _dl_s
    site: list[str]
    start: np.ndarray
    end: np.ndarray
    late: np.ndarray
    capacities: dict[str, Capacity]


def _to_s(col: str) -> pl.Expr:
    return pl.col(col).dt.epoch("us").cast(pl.Float64) / 1e6


def _ts(seconds: np.ndarray) -> pl.Series:
    us = np.rint(np.asarray(seconds, dtype=np.float64) * 1e6).astype(np.int64)
    return pl.Series(us).cast(pl.Datetime("us")).dt.replace_time_zone("UTC")


def _prepare(jobs: pl.DataFrame, deadlines: pl.DataFrame | None) -> pl.DataFrame:
    missing = [c for c in JOB_COLUMNS if c not in jobs.columns]
    if missing:
        raise ValueError(f"job frame is missing columns {missing}")
    dtype = jobs.schema["arrival_ts"]
    if not isinstance(dtype, pl.Datetime) or dtype.time_zone is None:
        raise ValueError(f"arrival_ts must be a time-zone-aware datetime, got {dtype}")
    cols = list(JOB_COLUMNS)
    nulls = jobs.select(cols).null_count().row(0)
    if any(nulls):
        raise ValueError(f"nulls in job columns: {dict(zip(cols, nulls, strict=True))}")
    if jobs["job_uid"].n_unique() != jobs.height:
        raise ValueError("job_uid is not unique")
    bad = jobs.filter((pl.col("duration_s") <= 0) | (pl.col("gpus") <= 0)
                      | (pl.col("max_delay_s") < 0))
    if bad.height:
        raise ValueError(f"non-positive duration/gpus or negative delay: {bad['job_uid'][:5]}")

    frame = jobs.select(cols).with_columns(
        pl.col("duration_s").cast(pl.Float64),
        pl.col("gpus").cast(pl.Int64),
        pl.col("max_delay_s").cast(pl.Float64),
        _to_s("arrival_ts").alias("_arr_s"),
    ).with_columns(
        (pl.col("_arr_s") + pl.col("duration_s") + pl.col("max_delay_s")).alias("_base_s"),
    )
    if deadlines is None:
        frame = frame.with_columns(pl.col("_base_s").alias("_dl_s"))
    else:
        dl = deadlines.select("job_uid", _to_s("deadline_ts").alias("_dl_s"))
        if dl["job_uid"].n_unique() != dl.height:
            raise ValueError("deadlines has duplicate job_uid")
        frame = frame.join(dl, on="job_uid", how="left")
        lost = frame.filter(pl.col("_dl_s").is_null())
        if lost.height:
            raise ValueError(f"no deadline for {lost.height} jobs, e.g. {lost['job_uid'][:5]}")
    # §8: simultaneous arrivals by deadline, then stable ID. The declared deadline is used,
    # not the F1 one, so the order is the same for every policy and for the F1 U run.
    return frame.sort(["_arr_s", "_base_s", "job_uid"])


def _fresh(sites: Mapping[str, int], warmup_state: WarmupState | None) -> dict[str, Capacity]:
    if warmup_state is None:
        return {s: Capacity(n) for s, n in sites.items()}
    got = {s: c.slots for s, c in warmup_state.capacities.items()}
    if got != dict(sites):
        raise ValueError(f"warm-up sites {got} differ from run sites {dict(sites)}")
    return {s: c.copy() for s, c in warmup_state.capacities.items()}


def _run(
    jobs: pl.DataFrame,
    policy: Policy,
    *,
    sites: Mapping[str, int],
    deadlines: pl.DataFrame | None,
    warmup_state: WarmupState | None,
    transfer_s: float,
    home: str,
) -> _Run:
    if home not in sites:
        raise ValueError(f"home site {home} is not in sites")
    ctx = SimContext(sites=dict(sites), home=home, transfer_s=float(transfer_s))
    caps = _fresh(sites, warmup_state)
    frame = _prepare(jobs, deadlines)
    n = frame.height
    if n and warmup_state is not None and frame["_arr_s"][0] < warmup_state.last_arrival:
        raise ValueError("the run starts before the end of its warm-up")

    uid = frame["job_uid"].to_list()
    arr = frame["_arr_s"].to_numpy()
    dur = frame["duration_s"].to_numpy()
    gpus = frame["gpus"].to_numpy()
    jtype = frame["job_type"].to_list()
    flex = frame["flexible"].to_numpy()
    delay = frame["max_delay_s"].to_numpy()
    mobile = frame["mobile"].to_numpy()
    dl = frame["_dl_s"].to_numpy()

    site_out: list[str] = [""] * n
    start_out = np.empty(n)
    end_out = np.empty(n)
    late_out = np.zeros(n, dtype=bool)
    cap_list = list(caps.values())

    for k in range(n):
        job = Job(uid[k], float(arr[k]), float(dur[k]), int(gpus[k]), jtype[k],
                  bool(flex[k]), float(delay[k]), bool(mobile[k]), float(dl[k]))
        now = job.arrival
        for c in cap_list:
            c.advance(now)
        action = policy.choose(job, now, caps, ctx)
        if action is None:  # late-work queue: earliest legal finish, never dropped
            action = ctx.earliest_action(job, caps)
            if action is None:
                raise ValueError(
                    f"job {job.job_uid} ({job.gpus} GPUs) fits no legal site in {dict(sites)}"
                )
        start = _check_action(policy, job, action, ctx)
        end = start + job.duration_s
        caps[action.site].reserve(start, end, job.gpus)
        site_out[k] = action.site
        start_out[k] = start
        end_out[k] = end
        late_out[k] = not ctx.on_time(job, start)

    return _Run(frame, site_out, start_out, end_out, late_out, caps)


def _check_action(policy: Policy, job: Job, action: Action, ctx: SimContext) -> float:
    if action.site not in ctx.legal_sites(job):
        raise ValueError(f"{policy.name}: {action.site} is not a legal site for {job.job_uid}")
    start = float(action.start)
    if start < ctx.ready_at(job, action.site):
        what = "the transfer" if action.site != ctx.home else "arrival"
        raise ValueError(
            f"{policy.name}: {job.job_uid} starts at {action.site} before {what} allows "
            f"({start} < {ctx.ready_at(job, action.site)}; transfer {ctx.transfer_s} s)"
        )
    return start


def simulate(
    jobs: pl.DataFrame,
    policy: Policy,
    *,
    sites: Mapping[str, int] = SITES,
    deadlines: pl.DataFrame | None = None,
    warmup_state: WarmupState | None = None,
    transfer_s: float = TRANSFER_S,
    home: str = HOME,
) -> Ledger:
    """Replay `jobs` (the replay() frame) under `policy` and return the ledger.

    `deadlines` (job_uid, deadline_ts), e.g. from `u_finish_deadlines`, overrides the
    declared deadline arrival + duration + max_delay. `warmup_state` (from `warm_up`)
    seeds capacity with the warm-up reservations; it is copied, never changed.
    """
    r = _run(jobs, policy, sites=sites, deadlines=deadlines, warmup_state=warmup_state,
             transfer_s=transfer_s, home=home)
    return _ledger(r, home)


def _ledger(r: _Run, home: str) -> Ledger:
    site = pl.Series("site", r.site, dtype=pl.Utf8)
    return pl.DataFrame({
        "job_uid": r.order["job_uid"],
        "site": site,
        "start_ts": _ts(r.start),
        "end_ts": _ts(r.end),
        "transfer": site != home,
        "late": pl.Series(r.late, dtype=pl.Boolean),
        "deadline_ts": _ts(r.order["_dl_s"].to_numpy()),
        "gpus": r.order["gpus"],
    }).select(LEDGER_COLUMNS)


def warm_up(
    jobs: pl.DataFrame,
    *,
    sites: Mapping[str, int] = SITES,
    home: str = HOME,
) -> WarmupState:
    """Run the warm-up jobs under U (F2) and return the capacity they leave behind."""
    r = _run(jobs, U(), sites=sites, deadlines=None, warmup_state=None,
             transfer_s=TRANSFER_S, home=home)
    last = float(r.order["_arr_s"].max()) if r.order.height else -math.inf
    return WarmupState(capacities=r.capacities, last_arrival=last, ledger=_ledger(r, home))


def u_finish_deadlines(
    jobs: pl.DataFrame,
    *,
    sites: Mapping[str, int] = SITES,
    warmup_state: WarmupState | None = None,
    home: str = HOME,
) -> pl.DataFrame:
    """F1 deadlines: max(arrival + duration + allowed delay, finish under U).

    Pass the same `sites` and `warmup_state` as the policy runs, so U is feasible by
    construction. Deadlines are rounded like the ledger's end_ts (to the microsecond).
    """
    r = _run(jobs, U(), sites=sites, deadlines=None, warmup_state=warmup_state,
             transfer_s=TRANSFER_S, home=home)
    base_us = np.rint(r.order["_base_s"].to_numpy() * 1e6).astype(np.int64)
    end_us = np.rint(r.end * 1e6).astype(np.int64)
    deadline = pl.Series(np.maximum(base_us, end_us)).cast(pl.Datetime("us"))
    return pl.DataFrame({
        "job_uid": r.order["job_uid"],
        "deadline_ts": deadline.dt.replace_time_zone("UTC"),
    })
