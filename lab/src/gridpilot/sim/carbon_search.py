"""Emissions-first carbon search: policies K, W, L and H (spec §8 "Core policy"; §15 F3,
F10, F11, F12.1–F12.3, F12.7, F13.1, F14.5–F14.7; Task 5 amendments).

At each arrival the policy enumerates the operational candidates (F13.1) — hourly
boundaries in [ready, deadline − duration] at each legal site, plus the earliest feasible
start at each site, plus the exact booking (F10, F12.3, F12.7) — scores each by predicted
kg CO₂, and returns the best one that fits the capacity it sees. Legality is the
engine's: candidates are filtered with `SimContext` (mobility, size, transfer, the F3
closure calendar, F12.1 transfer-hour support) and capacity views; nothing is
re-implemented here.

**Predicted kg.** The exact-overlap integral of hourly g/kWh over the whole execution
[s, s + d) at the facility power `gpus × 0.60 kW × PUE 1.20`, plus, for a remote move, the
transfer energy (5% of the job's IT energy, half at home and half at the destination,
PUE at each end) priced in the UTC hour containing the arrival (F7, F14.5). Integrals
use per-site prefix sums, so each is O(1).

**Signals.**
- K, W, L: Task 2's issued validation forecasts. At arrival t every hour uses the value
  of the latest issue with issue_ts ≤ t that covers it; issues after t are never used.
  Hours no such issue covers use the frozen K climatology tail (modeled). The as-of state
  is updated incrementally as t passes each issue (prefix sums rebuilt once per issue).
  L is fitted once upstream; this module never calls `forecast()`.
- H: realized truth, passed in (F14.6: the driver's filled scoring truth). A diagnostic
  hindsight policy with exactly K/W/L's candidates and reservations (F13.1).

**Ties** within 1e-9 kg go to the earlier completion, then PACE, then BA code, then start.

**Seal.** The signal grid ends at or before TEST_START; inputs reaching the seal raise,
and a candidate outside the grid raises rather than inventing values.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import polars as pl

from gridpilot.sim.capacity import CapacityView
from gridpilot.sim.engine import (
    HOME,
    HOUR_US,
    US,
    Action,
    Job,
    SimContext,
    _merge,
    closed_intervals,
    floor_hour,
)
from gridpilot.sim.power import GPU_KW, PUE, TRANSFER_FRACTION
from gridpilot.splits import TEST_START

if TYPE_CHECKING:
    from gridpilot.forecast import Climatology

TIE_KG = 1e-9  # absolute part of the tie / improvement tolerance
TIE_REL = 1e-12  # relative part: tolerance = 1e-9 + 1e-12·|kg|
SIGNALS = ("K", "W", "L", "H")
TARGET = "ci_consumed"
TRUTH_COL = "ci_consumed_g_kwh"
GRID_START = datetime(2024, 10, 29, tzinfo=UTC)  # = forecast.VAL_FIT_AT
GRID_END = TEST_START
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_SEAL_US = (TEST_START - _EPOCH) // timedelta(microseconds=1)


def job_energy_kwh(gpus: float, duration_s: float) -> float:
    """Facility execution energy: gpus × 0.60 kW × hours × PUE 1.20 (F7)."""
    return gpus * GPU_KW * duration_s / 3600 * PUE


def transfer_kwh(gpus: float, duration_s: float) -> float:
    """Transfer IT energy, 5% of the job's IT energy (F7). It is charged half at home and
    half at the destination, each half times PUE, in the arrival hour."""
    return TRANSFER_FRACTION * gpus * GPU_KW * duration_s / 3600


def kg_tol(kg: float) -> float:
    """Tie and F14.7 improvement tolerance at magnitude `kg`: 1e-9 + 1e-12·|kg| kg, so
    large jobs' float rounding in the prefix sums never decides a choice."""
    return TIE_KG + TIE_REL * abs(float(kg))


def _us(ts: datetime) -> int:
    if ts.tzinfo is None:
        raise ValueError(f"{ts} must be timezone-aware")
    return (ts - _EPOCH) // timedelta(microseconds=1)


# --------------------------------------------------------------------------- signal


class _Signal:
    """Per-site hourly g/kWh on the grid [g0, g0 + n h), with prefix sums.

    `base` (sites × n) is the value of an hour that no applied issue covers: the
    climatology tail for K/W/L, or the truth (NaN where missing) for H. Issues are
    applied in issue_ts order up to the current instant, each overwriting the hours it
    covers, so every hour carries the latest issue at or before that instant.
    """

    def __init__(self, sites: Sequence[str], g0: int, n: int, base: np.ndarray,
                 issues: tuple[np.ndarray, ...] | None = None):
        self.sites = tuple(sites)
        self.idx = {s: i for i, s in enumerate(self.sites)}
        self.g0, self.n = g0, n
        self.base = base
        empty = np.empty(0, dtype=np.int64)
        self.iss_t, self.ptr, self.i_site, self.i_hour, self.i_val = issues or (
            empty, np.zeros(1, dtype=np.int64), empty, empty, np.empty(0))
        self._reset()
        self._prefix()

    def _reset(self) -> None:
        s, n = len(self.sites), self.n
        self.cur = np.zeros((s, n + 1))  # the last column pads x == grid end
        self.cur[:, :n] = self.base
        self.cov = np.zeros((s, n + 1), dtype=bool)
        if not len(self.iss_t):  # no issues (H): truth hours count as covered
            self.cov[:, :n] = ~np.isnan(self.base)
        self.applied = -1

    def _prefix(self) -> None:
        nan = np.isnan(self.cur)
        self.has_nan = bool(nan.any())
        self.val = np.where(nan, 0.0, self.cur)
        self.P = np.zeros_like(self.val)
        np.cumsum(self.val[:, :-1], axis=1, out=self.P[:, 1:])
        if self.has_nan:
            self.Q = np.zeros(self.val.shape, dtype=np.int64)
            np.cumsum(nan[:, :-1], axis=1, out=self.Q[:, 1:])
        self._next_gap: dict[int, np.ndarray] = {}

    def update(self, now: int) -> None:
        """Make the state 'every issue with issue_ts ≤ now applied'."""
        j = int(np.searchsorted(self.iss_t, now, side="right")) - 1
        if j == self.applied:
            return
        if j < self.applied:  # time went back (a test or a new run): rebuild
            self._reset()
        for k in range(self.applied + 1, j + 1):
            sl = slice(int(self.ptr[k]), int(self.ptr[k + 1]))
            self.cur[self.i_site[sl], self.i_hour[sl]] = self.i_val[sl]
            self.cov[self.i_site[sl], self.i_hour[sl]] = True
        self.applied = j
        self._prefix()

    def _hours(self, t: np.ndarray, what: str) -> np.ndarray:
        off = t - self.g0
        if off.size and (off.min() < 0 or off.max() > self.n * HOUR_US):
            raise ValueError(f"{what} outside the signal grid [{self.g0}, "
                             f"{self.g0 + self.n * HOUR_US}) µs")
        return off

    def integral(self, si: np.ndarray, s: np.ndarray, e: np.ndarray) -> np.ndarray:
        """∫ g/kWh dt over [s, e) in (g/kWh)·h, exact overlap per hour."""
        os_, oe = self._hours(s, "a start"), self._hours(e, "an end")
        hs, he = os_ // HOUR_US, oe // HOUR_US
        rs = (os_ - hs * HOUR_US) / HOUR_US
        re = (oe - he * HOUR_US) / HOUR_US
        if self.has_nan:
            hce = -(-oe // HOUR_US)
            if (self.Q[si, hce] - self.Q[si, hs] > 0).any():
                raise ValueError("a candidate touches a missing signal hour (H truth: the "
                                 "mask or the F14.6 fill must cover it)")
        return (self.P[si, he] - self.P[si, hs]) + self.val[si, he] * re - self.val[si, hs] * rs

    def at(self, si: np.ndarray, t: int) -> np.ndarray:
        """g/kWh in the UTC hour containing instant t."""
        h = self._hours(np.array([floor_hour(t)]), "an arrival hour")[0] // HOUR_US
        if h >= self.n:
            raise ValueError("an arrival hour is outside the signal grid")
        v = self.cur[si, h]
        if np.isnan(v).any():
            raise ValueError("a transfer charge falls on a missing signal hour")
        return v

    def coverage_end(self, site: str, t: int) -> int:
        """End of the run of covered hours starting at the hour containing t."""
        i = self.idx[site]
        nxt = self._next_gap.get(i)
        if nxt is None:
            gap = np.where(~self.cov[i, :self.n], np.arange(self.n), self.n)
            nxt = np.minimum.accumulate(gap[::-1])[::-1]
            self._next_gap[i] = nxt
        h = (floor_hour(t) - self.g0) // HOUR_US
        return self.g0 + int(nxt[h] if 0 <= h < self.n else h) * HOUR_US


# --------------------------------------------------------------------------- policy


class CarbonSearch:
    """Emissions-first carbon search under one signal (implements `Policy`).

    `CarbonSearch(signal, forecasts, truth, mask, *, tail, sites, grid, truth_col)`:
    - `signal` ∈ {K, W, L, H}; it is also the policy's `name`.
    - `forecasts` (K/W/L): Task 2's `forecasts.parquet` frame (ba, target, model,
      issue_ts, target_ts, value); rows for this model and target ci_consumed are used.
    - `truth` (H): ba, ts_utc and `truth_col` (g/kWh, consumption basis); F14.6's filled
      scoring truth from the driver. Missing hours stay missing; touching one raises.
    - `mask` (optional): a `site_mask` frame. It is not used for legality (the engine's
      `closed` is); it is checked once per run to equal the engine's calendar on the
      mask's window, so the policy and the engine cannot disagree silently.
    - `tail` (K/W/L): {ba: Climatology} — Task 2's frozen K climatology (`tail_climatology`).
    - `grid`: the UTC hour range the signal covers; it must end at or before TEST_START.
    """

    def __init__(
        self,
        signal: str,
        forecasts: pl.DataFrame | None = None,
        truth: pl.DataFrame | None = None,
        mask: pl.DataFrame | None = None,
        *,
        tail: Mapping[str, Climatology] | None = None,
        sites: Sequence[str] | None = None,
        grid: tuple[datetime, datetime] = (GRID_START, GRID_END),
        truth_col: str = TRUTH_COL,
    ):
        if signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {signal!r}")
        self.name = self.signal = signal
        g0, g1 = _us(grid[0]), _us(grid[1])
        if g0 % HOUR_US or g1 % HOUR_US or g1 <= g0:
            raise ValueError("grid must be whole UTC hours with start < end")
        if g1 > _SEAL_US:
            raise ValueError(f"grid ends after the seal (TEST_START {TEST_START})")
        n = (g1 - g0) // HOUR_US
        if signal == "H":
            if truth is None:
                raise ValueError("H needs a truth frame")
            self._sig = self._truth_signal(truth, truth_col, sites, g0, n)
        else:
            if tail is None:
                raise ValueError(f"{signal} needs the climatology tail (K), see tail_climatology")
            if forecasts is None:
                raise ValueError(f"{signal} needs the issued forecast frame")
            self._sig = self._forecast_signal(forecasts, tail, sites, g0, g1, n)
        self._mask = mask
        self._ctx: SimContext | None = None
        self._home_i = 0

    # ------------------------------------------------------------------ construction

    def _forecast_signal(self, fc, tail, sites, g0, g1, n) -> _Signal:
        from gridpilot.forecast import predict_climatology

        sites = tuple(sites) if sites is not None else tuple(sorted(tail))
        if missing := [s for s in sites if s not in tail]:
            raise ValueError(f"no climatology tail for {missing}")
        for c in ("issue_ts", "target_ts"):
            if fc.height and fc[c].max() >= TEST_START:
                raise ValueError(f"forecast {c} reaches the seal (TEST_START)")
        if "target" in fc.columns:
            fc = fc.filter(pl.col("target") == TARGET)
        if "model" in fc.columns:
            fc = fc.filter(pl.col("model") == self.signal)
        f = (fc.filter(pl.col("ba").is_in(list(sites)) & pl.col("value").is_not_null()
                       & pl.col("value").is_not_nan())
             .select("ba", pl.col("issue_ts").dt.epoch("us").alias("i"),
                     pl.col("target_ts").dt.epoch("us").alias("t"),
                     pl.col("value").cast(pl.Float64).alias("v")))
        if f.select(pl.struct("i", "ba", "t").is_duplicated().any()).item():
            raise ValueError("duplicate (issue_ts, ba, target_ts) in the forecast frame")
        if (f["t"] % HOUR_US != 0).any():
            raise ValueError("forecast target_ts must be UTC hour starts")
        f = f.filter((pl.col("t") >= g0) & (pl.col("t") < g1)).sort("i", "ba", "t")
        i = f["i"].to_numpy()
        iss_t, first = np.unique(i, return_index=True)
        ptr = np.append(first, len(i)).astype(np.int64)
        idx = {s: k for k, s in enumerate(sites)}
        si = np.array([idx[b] for b in f["ba"].to_list()], dtype=np.int64)
        hi = (f["t"].to_numpy() - g0) // HOUR_US
        hours = pl.datetime_range(datetime.fromtimestamp(g0 / 1e6, UTC),
                                  datetime.fromtimestamp((g1 - HOUR_US) / 1e6, UTC),
                                  interval="1h", time_unit="us", time_zone="UTC", eager=True)
        base = np.vstack([predict_climatology(tail[s], hours) for s in sites])
        return _Signal(sites, g0, n, base, (iss_t.astype(np.int64), ptr, si, hi,
                                            f["v"].to_numpy()))

    @staticmethod
    def _truth_signal(truth, col, sites, g0, n) -> _Signal:
        if truth.height and truth["ts_utc"].max() >= TEST_START:
            raise ValueError("truth frame reaches the seal (TEST_START)")
        sites = tuple(sites) if sites is not None else tuple(sorted(truth["ba"].unique()))
        t = (truth.filter(pl.col("ba").is_in(list(sites)))
             .select("ba", pl.col("ts_utc").dt.epoch("us").alias("t"),
                     pl.col(col).cast(pl.Float64).alias("v")))
        if t.select(pl.struct("ba", "t").is_duplicated().any()).item():
            raise ValueError("duplicate (ba, ts_utc) in the truth frame")
        if (t["t"] % HOUR_US != 0).any():
            raise ValueError("truth ts_utc must be UTC hour starts")
        t = t.filter((pl.col("t") >= g0) & (pl.col("t") < g0 + n * HOUR_US)
                     & pl.col("v").is_not_null() & pl.col("v").is_not_nan())
        idx = {s: k for k, s in enumerate(sites)}
        base = np.full((len(sites), n), np.nan)
        base[np.array([idx[b] for b in t["ba"].to_list()], dtype=np.int64),
             (t["t"].to_numpy() - g0) // HOUR_US] = t["v"].to_numpy()
        return _Signal(sites, g0, n, base)

    def _check_ctx(self, ctx: SimContext) -> None:
        if ctx is self._ctx:
            return
        idx = self._sig.idx
        if missing := [s for s, n in ctx.sites.items() if n > 0 and s not in idx]:
            raise ValueError(f"{self.name}: no signal for sites {missing}")
        if ctx.home not in idx:
            raise ValueError(f"{self.name}: no signal for home {ctx.home}")
        if self._mask is not None:
            self._check_mask(ctx)
        self._ctx, self._home_i = ctx, idx[ctx.home]

    def _check_mask(self, ctx: SimContext) -> None:
        m = self._mask
        if m.height == 0:
            return
        lo = int(m["ts_utc"].min().timestamp()) * 1_000_000
        hi = int(m["ts_utc"].max().timestamp()) * 1_000_000 + HOUR_US
        want = closed_intervals(m)
        for site in ctx.sites:
            if site not in set(m["ba"].unique()):
                continue
            a, b = _merge(want.get(site, [])) if want.get(site) else (np.empty(0), np.empty(0))
            ea, eb = ctx.closed.get(site, (np.empty(0), np.empty(0)))
            keep = (eb > lo) & (ea < hi)
            got = (np.maximum(ea[keep], lo), np.minimum(eb[keep], hi))
            if not (np.array_equal(a, got[0]) and np.array_equal(b, got[1])):
                raise ValueError(f"{self.name}: the mask differs from the engine's closed "
                                 f"calendar at {site} (F3: one calendar for every policy)")

    # ------------------------------------------------------------------ search

    def _cands(self, job: Job, views: Mapping[str, CapacityView],
               ctx: SimContext) -> list[tuple[str, int]]:
        out: list[tuple[str, int]] = []
        latest, d = job.latest_start_us, job.duration_us
        for site in ctx.legal_sites(job):
            if not ctx.transfer_supported(job, site):
                continue
            ready = ctx.ready_at(job, site)
            if ready > latest:
                continue
            h = -(-ready // HOUR_US) * HOUR_US
            while h <= latest:
                if ctx.is_open(site, h, d):
                    out.append((site, h))
                h += HOUR_US
            e = ctx.earliest_start(job, site, views, latest=latest)
            if e is not None:
                out.append((site, e))
        if job.booking is not None:
            out.append((job.booking.site, job.booking.start_us))
        return list(dict.fromkeys(out))

    def _score(self, job: Job, cands: Sequence[tuple[str, int]], now: int,
               home: str) -> np.ndarray:
        sig = self._sig
        sig.update(now)
        si = np.array([sig.idx[s] for s, _ in cands], dtype=np.int64)
        st = np.array([t for _, t in cands], dtype=np.int64)
        kg = (job.gpus * GPU_KW * PUE / 1000) * sig.integral(si, st, st + job.duration_us)
        hi = sig.idx[home]
        remote = si != hi
        if remote.any():
            # The same rounded µs duration as the execution integral.
            half = 0.5 * transfer_kwh(job.gpus, job.duration_us / US) * PUE / 1000
            ci_home = sig.at(np.array([hi]), job.arrival_us)[0]
            kg[remote] += half * (ci_home + sig.at(si[remote], job.arrival_us))
        return kg

    def _best(self, job: Job, cands: Sequence[tuple[str, int]], kg: np.ndarray,
              views: Mapping[str, CapacityView], home: str) -> int | None:
        """Index of the best candidate that fits `views` (ties as in the module doc)."""
        d, g = job.duration_us, job.gpus
        m = None
        ties = []
        for i in np.argsort(kg, kind="stable"):
            if m is not None and kg[i] > m + kg_tol(m):
                break
            site, s = cands[i]
            if views[site].fits(s, s + d, g):
                m = kg[i] if m is None else m
                ties.append(int(i))
        if not ties:
            return None
        return min(ties, key=lambda i: (cands[i][1] + d, cands[i][0] != home, cands[i][0],
                                        cands[i][1]))

    # ------------------------------------------------------------------ Policy API

    def choose(self, job: Job, now: int, capacities: Mapping[str, CapacityView],
               ctx: SimContext) -> Action | None:
        """The best fitting candidate by predicted kg as of `now`; None for the booking
        (the engine then runs it there, exempt from the mask like every booking)."""
        self._check_ctx(ctx)
        cands = self._cands(job, capacities, ctx)
        kg = self._score(job, cands, now, ctx.home)
        i = self._best(job, cands, kg, capacities, ctx.home)
        if i is None:
            return None
        site, s = cands[i]
        b = job.booking
        if b is not None and (site, s) == (b.site, b.start_us):
            return None
        return Action(site, s)

    def blocked(self, job: Job, now: int, actual: Action,
                real: Mapping[str, CapacityView], cf: Mapping[str, CapacityView],
                ctx: SimContext) -> bool:
        """F14.7: over the union of both views' candidates, filtered against the
        counterfactual ledger `cf`, the best choice differs from `actual` and predicts
        more than `kg_tol(kg(actual))` = 1e-9 + 1e-12·|kg| less."""
        self._check_ctx(ctx)
        act = (actual.site, actual.start_us)
        cands = list(dict.fromkeys(self._cands(job, real, ctx) + self._cands(job, cf, ctx)
                                   + [act]))
        kg = self._score(job, cands, now, ctx.home)
        i = self._best(job, cands, kg, cf, ctx.home)
        if i is None or cands[i] == act:
            return False
        mine = kg[cands.index(act)]
        return bool(mine - kg[i] > kg_tol(mine))

    # ------------------------------------------------------------------ helpers

    def candidates(self, job: Job, views: Mapping[str, CapacityView],
                   ctx: SimContext) -> list[Action]:
        """The operational candidates (F13.1) before the capacity filter."""
        return [Action(s, t) for s, t in self._cands(job, views, ctx)]

    def predicted_kg(self, job: Job, actions: Sequence[Action], now: int,
                     home: str = HOME) -> np.ndarray:
        """Predicted kg CO₂ for each action as of `now` (execution plus transfer)."""
        return self._score(job, [(a.site, a.start_us) for a in actions], now, home)

    def coverage_end_us(self, now: int, site: str) -> int:
        """As of `now`, the end of the issued coverage that starts at the hour containing
        `now` (for H: of the available truth). Hours from here on are the modeled tail."""
        self._sig.update(now)
        return self._sig.coverage_end(site, now)


# --------------------------------------------------------------------------- inputs


def latest_forecast_run(root: Path | None = None) -> Path:
    """The newest `runs/forecast/<id>` directory holding a forecasts.parquet. A helper
    for choosing a run by hand; the loaders never call it, they take an explicit run."""
    from gridpilot.paths import REPO_ROOT

    root = root or REPO_ROOT / "runs" / "forecast"
    runs = sorted(root.glob("*/forecasts.parquet"))
    if not runs:
        raise FileNotFoundError(f"no forecast run under {root}; run "
                                f"`uv run python -m gridpilot.forecast`")
    return runs[-1].parent


def load_forecasts(run_dir: Path) -> pl.DataFrame:
    """The ci_consumed rows of the Task 2 validation run in `run_dir` (explicit, pinned)."""
    f = pl.read_parquet(Path(run_dir) / "forecasts.parquet").filter(pl.col("target") == TARGET)
    if f.height and (f["target_ts"].max() >= TEST_START or f["issue_ts"].max() >= TEST_START):
        raise ValueError(f"{run_dir}: forecasts reach the seal")
    return f


def tail_climatology(run_dir: Path, bas: Sequence[str] | None = None,
                     atol: float = 1e-9) -> dict[str, Climatology]:
    """The frozen K climatology per BA, loaded from `run_dir/climatology.parquet` (no
    refit): the modeled tail for hours beyond issued coverage.

    It is checked against the same run's K rows: predicting every K target hour must
    reproduce the issued K value within `atol`, or this raises. The rebuilt
    `Climatology.n` is 0 (the export does not carry the label count).
    """
    from gridpilot.forecast import Climatology as Clim
    from gridpilot.forecast import predict_climatology

    run_dir = Path(run_dir)
    table = pl.read_parquet(run_dir / "climatology.parquet").filter(pl.col("target") == TARGET)
    k_rows = load_forecasts(run_dir).filter(pl.col("model") == "K")
    out: dict[str, Clim] = {}
    for ba in (bas or sorted(table["ba"].unique())):
        t = table.filter(pl.col("ba") == ba)
        if t.height == 0:
            raise ValueError(f"{run_dir}: no climatology for {ba}")
        cells = tuple(t.filter(pl.col("level") == i)
                      .select(*keys, pl.col("value").alias(f"k{i}"))
                      for i, keys in enumerate(Clim.LEVELS))
        median = t.filter(pl.col("level") == 3)["value"]
        if median.len() != 1 or t["tz"].n_unique() != 1:
            raise ValueError(f"{run_dir}: malformed climatology for {ba}")
        clim = Clim(tz=t["tz"][0], cells=cells, ba_median=float(median[0]), n=0)
        k = k_rows.filter(pl.col("ba") == ba)
        if k.height == 0:
            raise ValueError(f"{run_dir}: no K rows for {ba} to check the climatology against")
        got = predict_climatology(clim, k["target_ts"])
        worst = float(np.max(np.abs(got - k["value"].to_numpy())))
        if not worst <= atol:
            raise ValueError(f"{run_dir}: the climatology does not reproduce the run's K "
                             f"rows for {ba} (max |diff| {worst:.3g})")
        out[ba] = clim
    return out
