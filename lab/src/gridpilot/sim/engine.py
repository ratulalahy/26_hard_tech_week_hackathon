"""Event-driven simulator for non-preemptive gang jobs (spec §8; §15 F1, F2, F3, F5, F10, F11).

**Time** is integer microseconds since the Unix epoch (UTC) everywhere inside the engine,
`Capacity` and the `Policy` protocol. Datetimes are converted at the boundary: on input
(`arrival_ts`) and in the ledger (`datetime[us, UTC]`). Durations are rounded once to
the microsecond; the ledger also keeps the exact input `duration_s`.

**Bookings (F11).** One U run per scenario (`u_bookings`) gives every job a booking: its
U site and interval, and its F1 deadline `max(arrival + duration + max_delay, U end)`.
Every `simulate` run starts with all bookings reserved. At the arrival of job j the
policy sees the capacity with j's own booking released, still holding every other
booking and every earlier move. If it returns an on-time action that fits (re-checked
here), j runs there; otherwise j runs on its booking. Releasing only adds capacity, so
every job is on time by construction; a late job raises, because it would be a bug.

**Order.** Arrivals are processed by arrival, then declared deadline
(arrival + duration + max_delay), then `job_uid`. The declared deadline, not the F1 one,
keeps the order the same for every policy and for the U run that defines the bookings.

**Mask (F3).** `closed` gives per-site closed intervals. No policy action may execute
over a closed interval; the engine rejects one that does. Bookings are exempt: they sit
at PACE, which has no missing truth in validation.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np
import polars as pl

from gridpilot.sim.capacity import Capacity, CapacityView

log = logging.getLogger(__name__)

SITES: dict[str, int] = {"PACE": 2288, "CISO": 512, "BPAT": 512, "NEVP": 512}
HOME = "PACE"
TRANSFER_S = 1800.0  # remote staging before execution (assumed, §7)
US = 1_000_000

JOB_COLUMNS = ["job_uid", "arrival_ts", "duration_s", "gpus", "job_type", "flexible",
               "max_delay_s", "mobile"]
BOOKING_COLUMNS = ["job_uid", "site", "start_us", "end_us", "deadline_us"]
LEDGER_COLUMNS = [
    "job_uid", "site", "start_ts", "end_ts", "transfer", "late", "deadline_ts", "gpus",
    "arrival_ts", "duration_s", "moved", "booking_site",
]

Ledger = pl.DataFrame
"""One row per job, in processing order (LEDGER_COLUMNS).

start_ts/end_ts are execution (after any transfer), datetime[us, UTC]; end_ts − start_ts
is the duration rounded to the µs, and duration_s is the exact input value. `transfer`
is True when the job ran away from home; `moved` when it did not run on its booking;
`late` is always False under bookings (kept for the accounting contract).
"""


# --------------------------------------------------------------------------- types


@dataclass(frozen=True, slots=True)
class Action:
    """Run the job at `site`, executing from `start_us` (after any transfer)."""

    site: str
    start_us: int


@dataclass(frozen=True, slots=True)
class Job:
    """One request as a policy sees it. Times are integer µs."""

    job_uid: str
    arrival_us: int
    duration_us: int
    duration_s: float  # exact, for energy
    gpus: int
    job_type: str
    flexible: bool
    max_delay_us: int
    mobile: bool
    deadline_us: int  # F1 deadline (from the booking), or the declared one in the U run
    booking: Action | None  # the job's U slot (F11); None only inside the U run

    @property
    def latest_start_us(self) -> int:
        """The latest execution start that still meets the deadline."""
        return self.deadline_us - self.duration_us


def _merge(intervals: Sequence[tuple[int, int]]) -> tuple[np.ndarray, np.ndarray]:
    iv = sorted((int(a), int(b)) for a, b in intervals)
    out: list[list[int]] = []
    for a, b in iv:
        if b <= a:
            raise ValueError(f"empty closed interval [{a}, {b})")
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    arr = np.array(out, dtype=np.int64).reshape(-1, 2)
    return arr[:, 0].copy(), arr[:, 1].copy()


@dataclass(frozen=True)
class SimContext:
    """Static facts shared by every policy in a run, plus the legality helpers.

    `closed[site] = (starts, ends)`: sorted, merged closed intervals in µs (F3).
    """

    sites: Mapping[str, int]
    home: str = HOME
    transfer_us: int = int(TRANSFER_S * US)
    closed: Mapping[str, tuple[np.ndarray, np.ndarray]] = field(default_factory=dict)

    def legal_sites(self, job: Job) -> tuple[str, ...]:
        """Sites the job may run at: home first, then by BA code. Immobile jobs stay home."""
        if not job.mobile:
            order = [self.home]
        else:
            order = [self.home] + sorted(s for s in self.sites if s != self.home)
        return tuple(s for s in order if self.sites.get(s, 0) >= job.gpus)

    def ready_at(self, job: Job, site: str) -> int:
        """Earliest execution start at `site`: arrival, plus the transfer if remote."""
        return job.arrival_us + (0 if site == self.home else self.transfer_us)

    def closure(self, site: str, start: int, duration: int) -> int | None:
        """End of the first closed interval that [start, start+duration) touches, or None."""
        iv = self.closed.get(site)
        if iv is None:
            return None
        starts, ends = iv
        k = int(np.searchsorted(ends, start, side="right"))  # first interval ending after start
        if k < len(starts) and starts[k] < start + duration:
            return int(ends[k])
        return None

    def is_open(self, site: str, start: int, duration: int) -> bool:
        return self.closure(site, start, duration) is None

    def earliest_start(
        self,
        job: Job,
        site: str,
        capacities: Mapping[str, CapacityView],
        latest: int | None = None,
    ) -> int | None:
        """Earliest start at `site` that fits and avoids closed intervals, or None."""
        cap = capacities[site]
        s: int | None = self.ready_at(job, site)
        while s is not None:
            s = cap.earliest_start(s, job.duration_us, job.gpus, latest)
            if s is None:
                return None
            reopen = self.closure(site, s, job.duration_us)
            if reopen is None:
                return s
            s = reopen
            if latest is not None and s > latest:
                return None
        return None

    def earliest_action(
        self,
        job: Job,
        capacities: Mapping[str, CapacityView],
        sites: Sequence[str] | None = None,
    ) -> Action | None:
        """Earliest finish over `sites` (default: all legal), ties to home then BA code."""
        best: tuple[int, bool, str] | None = None
        for site in self.legal_sites(job) if sites is None else sites:
            s = self.earliest_start(job, site, capacities)
            if s is None:
                continue
            key = (s + job.duration_us, site != self.home, site)
            if best is None or key < best:
                best = key
        if best is None:
            return None
        return Action(best[2], best[0] - job.duration_us)

    def on_time(self, job: Job, start: int) -> bool:
        return start + job.duration_us <= job.deadline_us


@runtime_checkable
class Policy(Protocol):
    """A placement rule. It gets read-only capacity views; the engine reserves.

    Return an `Action`, or None to run on the booking. An action that is late or does
    not fit also runs on the booking. An illegal action (site not legal for the job,
    start before arrival or before the transfer, or touching a closed interval) raises.
    """

    name: str

    def choose(
        self,
        job: Job,
        now: int,
        capacities: Mapping[str, CapacityView],
        ctx: SimContext,
    ) -> Action | None: ...


# --------------------------------------------------------------------------- policies


class U:
    """Earliest feasible execution at home (PACE), in FIFO order; no carbon input."""

    name = "U"

    def choose(self, job, now, capacities, ctx):
        if ctx.home not in ctx.legal_sites(job):
            return None
        s = ctx.earliest_start(job, ctx.home, capacities)
        return None if s is None else Action(ctx.home, s)


class G:
    """Earliest finish across the legal core sites, then home, then BA code; no carbon."""

    name = "G"

    def choose(self, job, now, capacities, ctx):
        return ctx.earliest_action(job, capacities)


class S:
    """Fixed clean-region priority.

    Try the sites in `ranking` (the training-window mean consumed intensity order,
    cleanest first; Task 7 supplies it), then home: take the first whose earliest
    feasible completion meets the deadline. Otherwise the job runs on its booking.
    """

    name = "S"

    def __init__(self, ranking: Sequence[str]):
        self.ranking = tuple(ranking)

    def choose(self, job, now, capacities, ctx):
        legal = ctx.legal_sites(job)
        order = [s for s in self.ranking if s in legal]
        if ctx.home in legal and ctx.home not in order:
            order.append(ctx.home)
        for site in order:
            s = ctx.earliest_start(job, site, capacities, latest=job.latest_start_us)
            if s is not None:
                return Action(site, s)
        return None


# --------------------------------------------------------------------------- inputs


@dataclass(frozen=True)
class WarmupState:
    """Reservations left by a U warm-up run (F2), as intervals; reusable across runs.

    A run using it must not start before the warm-up's last arrival: a cohort job
    arriving strictly before `last_arrival_us` raises (arrival == last is allowed).
    The ≥ 15-day warm-up length (F2) is the driver's check.
    """

    intervals: pl.DataFrame  # site, start_us, end_us, gpus
    last_arrival_us: int
    ledger: Ledger = field(repr=False)


def _prepare(jobs: pl.DataFrame) -> pl.DataFrame:
    missing = [c for c in JOB_COLUMNS if c not in jobs.columns]
    if missing:
        raise ValueError(f"job frame is missing columns {missing}")
    dtype = jobs.schema["arrival_ts"]
    if not isinstance(dtype, pl.Datetime) or dtype.time_zone is None:
        raise ValueError(f"arrival_ts must be a time-zone-aware datetime, got {dtype}")
    nulls = jobs.select(JOB_COLUMNS).null_count().row(0)
    if any(nulls):
        raise ValueError(f"nulls in job columns: {dict(zip(JOB_COLUMNS, nulls, strict=True))}")
    if jobs["job_uid"].n_unique() != jobs.height:
        raise ValueError("job_uid is not unique")
    f = jobs.select(JOB_COLUMNS).with_columns(
        pl.col("duration_s").cast(pl.Float64),
        pl.col("max_delay_s").cast(pl.Float64),
        pl.col("gpus").cast(pl.Float64).alias("_g"),
    )
    bad = f.filter(~pl.col("duration_s").is_finite() | ~pl.col("max_delay_s").is_finite())
    if bad.height:
        raise ValueError(f"non-finite duration_s/max_delay_s: {bad['job_uid'][:5].to_list()}")
    bad = f.filter(~pl.col("_g").is_finite() | (pl.col("_g") != pl.col("_g").round()))
    if bad.height:
        raise ValueError(f"non-integral gpus: {bad['job_uid'][:5].to_list()}")
    f = f.with_columns(
        pl.col("_g").cast(pl.Int64).alias("gpus"),
        pl.col("arrival_ts").dt.epoch("us").alias("_arr"),
        (pl.col("duration_s") * US).round().cast(pl.Int64).alias("_dur"),
        (pl.col("max_delay_s") * US).round().cast(pl.Int64).alias("_delay"),
    ).drop("_g")
    bad = f.filter((pl.col("_dur") <= 0) | (pl.col("gpus") <= 0) | (pl.col("_delay") < 0))
    if bad.height:
        raise ValueError(
            f"non-positive duration/gpus or negative delay: {bad['job_uid'][:5].to_list()}"
        )
    n_odd = f.select((pl.col("mobile") & ~pl.col("flexible")).sum()).item()
    log.info("%d rows are mobile but not flexible", n_odd)
    f = f.with_columns((pl.col("_arr") + pl.col("_dur") + pl.col("_delay")).alias("_base"))
    return f.sort(["_arr", "_base", "job_uid"])


def _attach_bookings(frame: pl.DataFrame, bookings: pl.DataFrame,
                     sites: Mapping[str, int]) -> pl.DataFrame:
    missing = [c for c in BOOKING_COLUMNS if c not in bookings.columns]
    if missing:
        raise ValueError(f"bookings is missing columns {missing}")
    b = bookings.select(
        "job_uid",
        pl.col("site").alias("_bsite"),
        pl.col("start_us").cast(pl.Int64).alias("_bs"),
        pl.col("end_us").cast(pl.Int64).alias("_be"),
        pl.col("deadline_us").cast(pl.Int64).alias("_dl"),
    )
    if b["job_uid"].n_unique() != b.height:
        raise ValueError("bookings has duplicate job_uid")
    unknown = b.join(frame, on="job_uid", how="anti")
    if unknown.height:
        raise ValueError(f"bookings has {unknown.height} unknown job_uid, "
                         f"e.g. {unknown['job_uid'][:5].to_list()}")
    out = frame.join(b, on="job_uid", how="left", maintain_order="left")
    lost = out.filter(pl.col("_bs").is_null())
    if lost.height:
        raise ValueError(f"bookings missing for {lost.height} jobs, "
                         f"e.g. {lost['job_uid'][:5].to_list()}")
    bad = out.filter(
        ~pl.col("_bsite").is_in(list(sites))
        | (pl.col("_bs") < pl.col("_arr"))
        | (pl.col("_be") - pl.col("_bs") != pl.col("_dur"))
        | (pl.col("_be") > pl.col("_dl"))
    )
    if bad.height:
        raise ValueError(f"bookings inconsistent with jobs (site, start, duration or "
                         f"deadline): {bad['job_uid'][:5].to_list()}")
    return out


def _capacities(
    sites: Mapping[str, int],
    warm: WarmupState | None,
    extra: pl.DataFrame | None,
    t0: int | None,
) -> dict[str, Capacity]:
    """Bulk-build each site from warm-up intervals still live at t0, plus `extra`
    (site, start_us, end_us, gpus)."""
    parts = []
    if warm is not None:
        got = set(warm.intervals["site"].unique()) - set(sites)
        if got:
            raise ValueError(f"warm-up uses sites {got} not in this run")
        iv = warm.intervals
        if t0 is not None:
            iv = iv.filter(pl.col("end_us") > t0)
        parts.append(iv)
    if extra is not None:
        parts.append(extra)
    allv = pl.concat(parts) if parts else None
    caps = {}
    for site, slots in sites.items():
        if allv is None:
            caps[site] = Capacity(slots)
            continue
        d = allv.filter(pl.col("site") == site)
        try:
            caps[site] = Capacity.from_intervals(
                slots, d["start_us"].to_numpy(), d["end_us"].to_numpy(), d["gpus"].to_numpy()
            )
        except ValueError as e:
            raise ValueError(f"{site}: warm-up plus bookings do not fit: {e}") from e
    return caps


def closed_intervals(mask: pl.DataFrame) -> dict[str, list[tuple[int, int]]]:
    """F3: turn a `site_mask` frame (ba, ts_utc, truth_ok) into merged closed hours (µs)."""
    shut = (mask.filter(~pl.col("truth_ok"))
            .select("ba", pl.col("ts_utc").dt.epoch("us").alias("s"))
            .sort("ba", "s"))
    out: dict[str, list[tuple[int, int]]] = {}
    for ba, s in shut.iter_rows():
        iv = out.setdefault(ba, [])
        if iv and iv[-1][1] == s:
            iv[-1] = (iv[-1][0], s + 3600 * US)
        else:
            iv.append((s, s + 3600 * US))
    return out


# --------------------------------------------------------------------------- engine


@dataclass
class _Run:
    order: pl.DataFrame  # jobs in processing order, with _arr, _dur, _base (and bookings)
    site: list[str]
    start: np.ndarray
    late: np.ndarray
    moved: np.ndarray


def _run(
    jobs: pl.DataFrame,
    policy: Policy,
    *,
    sites: Mapping[str, int],
    bookings: pl.DataFrame | None,
    warm: WarmupState | None,
    transfer_s: float,
    closed: Mapping[str, Sequence[tuple[int, int]]] | None,
    home: str,
    on_commit: Callable[[Job, Action], None] | None = None,
) -> _Run:
    if home not in sites:
        raise ValueError(f"home site {home} is not in sites")
    if not math.isfinite(transfer_s) or transfer_s < 0:
        raise ValueError(f"transfer_s must be finite and >= 0, got {transfer_s}")
    unknown = set(closed or {}) - set(sites)
    if unknown:
        raise ValueError(f"closed names sites {unknown} not in this run")
    ctx = SimContext(
        sites=dict(sites), home=home, transfer_us=round(transfer_s * US),
        closed={s: _merge(iv) for s, iv in (closed or {}).items() if iv},
    )
    frame = _prepare(jobs)
    n = frame.height
    if n and warm is not None and frame["_arr"][0] < warm.last_arrival_us:
        raise ValueError("a job arrives before the warm-up's last arrival")
    t0 = int(frame["_arr"][0]) if n else None

    booked = bookings is not None
    if booked:
        frame = _attach_bookings(frame, bookings, sites)
        extra = frame.select(pl.col("_bsite").alias("site"), pl.col("_bs").alias("start_us"),
                             pl.col("_be").alias("end_us"), "gpus")
        dl = frame["_dl"].to_numpy()
        bsite = frame["_bsite"].to_list()
        bs = frame["_bs"].to_numpy()
    else:
        extra = None
        dl = frame["_base"].to_numpy()
    caps = _capacities(sites, warm, extra, t0)
    views = {s: c.view() for s, c in caps.items()}

    uid = frame["job_uid"].to_list()
    arr = frame["_arr"].to_numpy()
    dur = frame["_dur"].to_numpy()
    dur_s = frame["duration_s"].to_numpy()
    gpus = frame["gpus"].to_numpy()
    jtype = frame["job_type"].to_list()
    flex = frame["flexible"].to_numpy()
    delay = frame["_delay"].to_numpy()
    mobile = frame["mobile"].to_numpy()

    site_out: list[str] = [""] * n
    start_out = np.empty(n, dtype=np.int64)
    late_out = np.zeros(n, dtype=bool)
    moved_out = np.zeros(n, dtype=bool)
    cap_list = list(caps.values())

    for k in range(n):
        g = int(gpus[k])
        d = int(dur[k])
        booking = Action(bsite[k], int(bs[k])) if booked else None
        job = Job(uid[k], int(arr[k]), d, float(dur_s[k]), g, jtype[k], bool(flex[k]),
                  int(delay[k]), bool(mobile[k]), int(dl[k]), booking)
        now = job.arrival_us
        for c in cap_list:
            c.advance(now)
        if booked:  # the policy sees capacity without j's own booking
            caps[booking.site].release(booking.start_us, booking.start_us + d, g)
        action = policy.choose(job, now, views, ctx)
        if action is not None:
            _check_action(policy, job, action, ctx)
            a_end = action.start_us + d
            if booked and not (ctx.on_time(job, action.start_us)
                               and caps[action.site].fits(action.start_us, a_end, g)):
                action = None  # late or does not fit: run on the booking
        if action is None:
            if not booked:
                raise ValueError(f"job {job.job_uid} ({g} GPUs) fits no legal site "
                                 f"in {dict(sites)}")
            action = booking
        caps[action.site].reserve(action.start_us, action.start_us + d, g)
        if on_commit is not None:
            on_commit(job, action)
        site_out[k] = action.site
        start_out[k] = action.start_us
        late_out[k] = not ctx.on_time(job, action.start_us)
        moved_out[k] = booked and action != booking
        if booked and late_out[k]:
            raise AssertionError(f"{policy.name}: {job.job_uid} is late under bookings (F11)")

    return _Run(frame, site_out, start_out, late_out, moved_out)


def _check_action(policy: Policy, job: Job, action: Action, ctx: SimContext) -> None:
    if action.site not in ctx.legal_sites(job):
        raise ValueError(f"{policy.name}: {action.site} is not a legal site for {job.job_uid}")
    start = action.start_us
    if start != int(start):
        raise ValueError(f"{policy.name}: start must be integer µs, got {start!r}")
    if start < ctx.ready_at(job, action.site):
        what = "the transfer" if action.site != ctx.home else "arrival"
        raise ValueError(
            f"{policy.name}: {job.job_uid} starts at {action.site} before {what} allows "
            f"({start} < {ctx.ready_at(job, action.site)}; transfer {ctx.transfer_us} µs)"
        )
    if not ctx.is_open(action.site, start, job.duration_us):
        raise ValueError(f"{policy.name}: {job.job_uid} at {action.site} touches a closed "
                         f"interval (F3)")


def _ts(us: np.ndarray | pl.Series) -> pl.Series:
    return pl.Series(np.asarray(us, dtype=np.int64)).cast(pl.Datetime("us")) \
        .dt.replace_time_zone("UTC")


def _ledger(r: _Run, home: str) -> Ledger:
    o = r.order
    site = pl.Series("site", r.site, dtype=pl.Utf8)
    start = r.start
    end = start + o["_dur"].to_numpy()
    dl = o["_dl"] if "_dl" in o.columns else o["_base"]
    bsite = o["_bsite"] if "_bsite" in o.columns else site
    return pl.DataFrame({
        "job_uid": o["job_uid"],
        "site": site,
        "start_ts": _ts(start),
        "end_ts": _ts(end),
        "transfer": site != home,
        "late": pl.Series(r.late, dtype=pl.Boolean),
        "deadline_ts": _ts(dl.to_numpy()),
        "gpus": o["gpus"],
        "arrival_ts": _ts(o["_arr"].to_numpy()),
        "duration_s": o["duration_s"],
        "moved": pl.Series(r.moved, dtype=pl.Boolean),
        "booking_site": bsite,
    }).select(LEDGER_COLUMNS)


# --------------------------------------------------------------------------- API


def simulate(
    jobs: pl.DataFrame,
    policy: Policy,
    sites: Mapping[str, int] = SITES,
    *,
    bookings: pl.DataFrame,
    warm: WarmupState | None = None,
    transfer_s: float = TRANSFER_S,
    closed: Mapping[str, Sequence[tuple[int, int]]] | None = None,
    home: str = HOME,
    on_commit: Callable[[Job, Action], None] | None = None,
) -> Ledger:
    """Replay `jobs` (the replay() frame) under `policy` with F11 bookings.

    `bookings` comes from `u_bookings` for the same jobs, sites and warm-up; it is
    required and must cover exactly the jobs. `warm` seeds capacity with the warm-up's
    still-running reservations. `closed` maps a site to closed µs intervals (F3; build it
    with `closed_intervals(site_mask(...))`). `on_commit(job, action)` is an optional
    diagnostic hook called after each placement.
    """
    r = _run(jobs, policy, sites=sites, bookings=bookings, warm=warm, transfer_s=transfer_s,
             closed=closed, home=home, on_commit=on_commit)
    return _ledger(r, home)


def u_bookings(
    jobs: pl.DataFrame,
    sites: Mapping[str, int] = SITES,
    *,
    warm: WarmupState | None = None,
    transfer_s: float = TRANSFER_S,
    home: str = HOME,
) -> pl.DataFrame:
    """F1 + F11: one U run gives each job its booking and deadline.

    Columns job_uid, site, start_us, end_us, deadline_us (Int64 µs), where
    deadline_us = max(arrival + duration + max_delay, U end). Pass the same `sites` and
    `warm` as the policy runs. U uses no transfer; `transfer_s` is accepted for symmetry.
    """
    r = _run(jobs, U(), sites=sites, bookings=None, warm=warm, transfer_s=transfer_s,
             closed=None, home=home)
    end = r.start + r.order["_dur"].to_numpy()
    return pl.DataFrame({
        "job_uid": r.order["job_uid"],
        "site": pl.Series(r.site, dtype=pl.Utf8),
        "start_us": pl.Series(r.start, dtype=pl.Int64),
        "end_us": pl.Series(end, dtype=pl.Int64),
        "deadline_us": pl.Series(np.maximum(r.order["_base"].to_numpy(), end), dtype=pl.Int64),
    })


def warm_up(
    jobs: pl.DataFrame,
    sites: Mapping[str, int] = SITES,
    *,
    home: str = HOME,
) -> WarmupState:
    """Run the warm-up jobs under U (F2) and keep the reservations they leave behind."""
    r = _run(jobs, U(), sites=sites, bookings=None, warm=None, transfer_s=TRANSFER_S,
             closed=None, home=home)
    end = r.start + r.order["_dur"].to_numpy()
    intervals = pl.DataFrame({
        "site": pl.Series(r.site, dtype=pl.Utf8),
        "start_us": pl.Series(r.start, dtype=pl.Int64),
        "end_us": pl.Series(end, dtype=pl.Int64),
        "gpus": r.order["gpus"],
    })
    last = int(r.order["_arr"].max()) if r.order.height else -(2**62)
    return WarmupState(intervals=intervals, last_arrival_us=last, ledger=_ledger(r, home))
