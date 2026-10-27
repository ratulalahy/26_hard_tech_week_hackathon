"""Work and carbon accounting over simulator ledgers, and the relaxed lower bound.

Spec §8 "Relaxed hindsight bound", §9; §15 F3, F5, F7, F11, F12.1, F12.3, F12.4, F13.1,
F14.5, F14.6; the Task 6 amendment.

**Energy (modeled; F7, amendment 1).**
- Execution: `gpus × 0.60 kW × hours × PUE 1.20`, charged at the execution site's hourly
  intensity as an exact-overlap integral over the half-open interval [start, end).
- Transfer, for remote runs only: IT energy `0.05 × gpus × 0.60 kW × duration_h`. Half is
  charged at home and half at the destination, both at the UTC hour containing the
  arrival (F14.5), with PUE 1.20 on each half. `transfer_kwh` includes PUE;
  `transfer_it_kwh` does not.
- Durations are the engine's: the input `duration_s` rounded once to the microsecond, so
  ledger `end_ts − start_ts` equals the requested duration exactly (≤ 0.5 µs from input).

**Truth.** `truth` is either Task 1's `load_carbon()` frame (`ci_consumed_g_kwh`; every
non-null row is tier 1) or the F14.6 scoring frame (`ba, ts_utc, ci_g_kwh, tier`), whose
tiers 2–4 are modeled fills. An hour is *missing* if it has no value, no row, or a
`site_mask` row with `truth_ok = False`. Accounting never fills: a ledger interval that
touches a missing hour raises. Rows at or after TEST_START are dropped, and any request
for an hour at or after TEST_START raises (seal, F8). `TruthTable(..., window=)` and
`support_check(..., window=)` take the evaluation window (default validation); with the test
window (test mode only, Stage 3 T11) the bound is F_test instead of TEST_START.

**Evidence.** Energy is `modeled`; CO₂ outputs and schedule quantities are `simulated` (the
policy outcomes of a simulated run; T9 C5).

**Determinism (Stage 3 T10).** Every float total that feeds an export is `math.fsum` over
the values sorted by job_uid (`fsum_by`), never a parallel `group_by(...).sum()`, so a total
does not depend on row order or thread scheduling.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl

from gridpilot.sim import HOME, SITES, TRANSFER_S, WarmupState
from gridpilot.sim.power import GPU_KW as KW_PER_GPU  # one source of the constants (A14)
from gridpilot.sim.power import PUE, TRANSFER_FRACTION
from gridpilot.splits import TEST_START
from gridpilot.window import Window, resolve

BOUND_TOL_KG = 1e-6  # "feasible ≥ bound" tolerance on the scored cohort (F14.5)
WEEK_TZ = "America/Denver"

US = 1_000_000
HOUR_US = 3600 * US
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def fsum_by(frame: pl.DataFrame, col: str, key: str = "job_uid") -> float:
    """Exactly rounded total of `frame[col]` (math.fsum over values sorted by `key`): the
    same float for any row order (Stage 3 T10 determinism). 0.0 for an empty frame."""
    if frame.height == 0:
        return 0.0
    return math.fsum(frame.sort(key)[col].to_list())


def _aware(dt: datetime, what: str) -> datetime:
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{what} must be a timezone-aware datetime, got {dt!r}")
    return dt


def _dt_us(dt: datetime, what: str) -> int:
    """Exact µs since the Unix epoch for a tz-aware datetime."""
    return (_aware(dt, what) - EPOCH) // timedelta(microseconds=1)


TEST_START_US = _dt_us(TEST_START, "TEST_START")
_RATE = KW_PER_GPU * PUE  # facility kW per GPU
_CHUNK = 4_000_000  # bound candidates evaluated per numpy batch

EVIDENCE = {
    "completed_gpu_s": "simulated", "requested_gpu_s": "simulated",
    "late_jobs": "simulated", "late_gpu_h": "simulated",
    "wait_p50_s": "simulated", "wait_p95_s": "simulated", "wait_max_s": "simulated",
    "wait_mean_s": "simulated", "moved_share_jobs": "simulated",
    "moved_share_energy": "modeled", "blocked_jobs": "simulated", "blocked_kwh": "modeled",
    "fit_rejected_jobs": "simulated", "fit_rejected_kwh": "modeled",
    "execution_kwh": "modeled", "transfer_kwh": "modeled", "transfer_it_kwh": "modeled",
    "energy_kwh": "modeled", "co2_kg": "simulated", "execution_co2_kg": "simulated",
    "transfer_co2_kg": "simulated", "co2_kg_per_1000_gpu_h": "simulated",
    "kwh_share_tier_ge2": "modeled", "remote_energy_share": "modeled",
}


def _us(col: str) -> pl.Expr:
    return pl.col(col).dt.epoch("us")


def _ts(us: np.ndarray) -> pl.Series:
    return pl.Series(np.asarray(us, dtype=np.int64)).cast(pl.Datetime("us")) \
        .dt.replace_time_zone("UTC")


def _seal(t_us: np.ndarray, what: str, bound_us: int = TEST_START_US) -> None:
    if t_us.size and int(t_us.max()) > bound_us:
        raise ValueError(f"{what} reaches past the read bound {_us_dt_iso(bound_us)} "
                         f"(TEST_START outside test mode): the sealed window is never read "
                         f"here (F8)")


def _us_dt_iso(us: int) -> str:
    return (EPOCH + timedelta(microseconds=int(us))).isoformat()


# --------------------------------------------------------------------------- truth


class TruthTable:
    """Hourly intensity per site on one UTC hour grid, with prefix sums for exact-overlap
    integrals. Build it once and pass it to every call to reuse it across policies.

    Arrays per site: `ci` (g/kWh, 0 where missing), `missing`, `filled` (tier ≥ 2).

    `tier` must be an integer 1–4 wherever the value is finite (F14.6); a null or
    out-of-range tier raises. Without a `tier` column every finite value is tier 1.

    **Mask.** The mask must be built from the same (filled) truth, e.g.
    `site_mask(filled_truth, ...)`, so it closes only hours that have no value. A mask
    that closes an hour holding a finite value raises: it would silently make accounting
    and the bound disagree with the engine's closure calendar. A null `truth_ok` means
    closed.
    """

    def __init__(self, truth: pl.DataFrame, mask: pl.DataFrame | None = None, *,
                 window: Window | None = None):
        self.window = resolve(window, "TruthTable")
        bound = self.window.read_end
        self.read_end_us = _dt_us(bound, "read_end")
        if "ci_g_kwh" in truth.columns:
            ci_col = "ci_g_kwh"
            tier = pl.col("tier").cast(pl.Int64) if "tier" in truth.columns else pl.lit(1)
        elif "ci_consumed_g_kwh" in truth.columns:
            ci_col, tier = "ci_consumed_g_kwh", pl.lit(1)
        else:
            raise ValueError("truth needs ci_g_kwh (F14.6) or ci_consumed_g_kwh (Task 1)")
        if truth.height and truth["ts_utc"].max() >= bound:
            # I6: a frame past the read bound is refused, not silently trimmed
            raise ValueError(f"truth holds rows at or after the read bound {bound.isoformat()} "
                             f"(TEST_START outside test mode): sealed values are read only "
                             f"inside the test-mode context (F8)")
        t = truth.select(
            "ba", _us("ts_utc").alias("t"), pl.col(ci_col).cast(pl.Float64).alias("ci"),
            tier.alias("tier"),
        )
        bad = t.filter(pl.col("ci").is_finite().fill_null(False)
                       & (pl.col("tier").is_null() | ~pl.col("tier").is_between(1, 4)))
        if bad.height:
            raise ValueError(f"{bad.height} truth rows with a finite value have a null or "
                             f"out-of-range tier (must be 1–4; F14.6), e.g. "
                             f"{bad.head(3).to_dicts()}")
        if t.select((pl.col("t") % HOUR_US != 0).any()).item():
            raise ValueError("truth ts_utc must be UTC hour starts")
        if t.select(pl.struct("ba", "t").is_duplicated().any()).item():
            raise ValueError("truth has duplicate (ba, ts_utc) rows")
        if t.height:
            self.start_us = int(t["t"].min())
            self.end_us = int(t["t"].max()) + HOUR_US
        else:
            self.start_us = self.end_us = 0
        self.n = (self.end_us - self.start_us) // HOUR_US
        n = self.n
        self._arrays: dict[str, tuple[np.ndarray, ...]] = {}
        closed: dict[str, np.ndarray] = {}
        if mask is not None:
            m = mask.filter(~pl.col("truth_ok").fill_null(False)
                            & (pl.col("ts_utc") < bound)).select(
                "ba", ((_us("ts_utc") - self.start_us) // HOUR_US).alias("h"))
            m = m.filter((pl.col("h") >= 0) & (pl.col("h") < n))
            for ba, g in m.group_by("ba"):
                closed[ba[0]] = g["h"].to_numpy()
        for ba, g in t.group_by("ba"):
            ba = ba[0]
            h = ((g["t"].to_numpy() - self.start_us) // HOUR_US).astype(np.int64)
            ci = np.zeros(n + 1)
            miss = np.ones(n, dtype=bool)
            fill = np.zeros(n + 1)
            v = g["ci"].to_numpy()
            ok = np.isfinite(v)
            ci[h[ok]] = v[ok]
            miss[h[ok]] = False
            fill[h[ok]] = (g["tier"].to_numpy()[ok] >= 2).astype(float)
            if ba in closed:
                clash = closed[ba][~miss[closed[ba]]]
                if clash.size:
                    ts = [self.start_us + int(x) * HOUR_US for x in clash[:3]]
                    raise ValueError(
                        f"mask closes {clash.size} {ba} hours that have a finite truth value "
                        f"(e.g. µs {ts}); build the mask from the same filled truth")
                miss[closed[ba]] = True
            ci[:n][miss] = 0.0
            fill[:n][miss] = 0.0
            self._arrays[ba] = self._pack(ci, miss, fill)
        self._empty = self._pack(np.zeros(n + 1), np.ones(n, dtype=bool), np.zeros(n + 1))

    @staticmethod
    def _pack(ci, miss, fill):
        P = np.concatenate([[0.0], np.cumsum(ci[:-1])])  # ∫ ci over whole hours < h
        Q = np.concatenate([[0.0], np.cumsum(fill[:-1])])
        M = np.concatenate([[0], np.cumsum(miss)]).astype(np.int64)
        return ci, P, fill, Q, M

    def _site(self, site: str):
        return self._arrays.get(site, self._empty)

    def _cum(self, arr, pref, r):
        h = r // HOUR_US
        return pref[h] + (r - h * HOUR_US) / HOUR_US * arr[h]

    def _span(self, s, e):
        s = np.asarray(s, dtype=np.int64)
        e = np.asarray(e, dtype=np.int64)
        _seal(e, "a truth request", self.read_end_us)
        span = self.n * HOUR_US
        out = (s < self.start_us) | (e > self.end_us) | (e < s)
        rs = np.clip(s - self.start_us, 0, span)
        re = np.clip(e - self.start_us, 0, span)
        return s, e, rs, re, out

    def integral(self, site: str, s, e) -> tuple[np.ndarray, np.ndarray]:
        """(∫ ci dt over [s, e) in g/kWh·h, touches-missing) for µs arrays s, e."""
        ci, P, _, _, M = self._site(site)
        s, e, rs, re, out = self._span(s, e)
        val = self._cum(ci, P, re) - self._cum(ci, P, rs)
        hc = -((-re) // HOUR_US)
        miss = out | ((e > s) & (M[hc] - M[rs // HOUR_US] > 0))
        return val, miss

    def filled_hours(self, site: str, s, e) -> np.ndarray:
        """Hours of [s, e) priced on tier ≥ 2 (F14.6)."""
        _, _, fill, Q, _ = self._site(site)
        s, e, rs, re, out = self._span(s, e)
        return np.where(out, 0.0, self._cum(fill, Q, re) - self._cum(fill, Q, rs))

    def _hour(self, t):
        t = np.asarray(t, dtype=np.int64)
        if t.size and int(t.max()) >= self.read_end_us:
            raise ValueError(f"a truth request at or after the read bound "
                             f"{_us_dt_iso(self.read_end_us)} (TEST_START outside test mode; F8)")
        h = (t - self.start_us) // HOUR_US
        out = (h < 0) | (h >= self.n)
        return np.clip(h, 0, max(self.n - 1, 0)), out

    def point(self, site: str, t) -> tuple[np.ndarray, np.ndarray]:
        """(ci, missing) at the UTC hour containing each µs instant t."""
        ci, _, _, _, M = self._site(site)
        h, out = self._hour(t)
        if self.n == 0:
            return np.zeros(h.shape), np.ones(h.shape, dtype=bool)
        miss = out | (M[h + 1] - M[h] > 0)
        return np.where(miss, 0.0, ci[h]), miss

    def filled_at(self, site: str, t) -> np.ndarray:
        _, _, fill, _, _ = self._site(site)
        h, out = self._hour(t)
        if self.n == 0:
            return np.zeros(h.shape, dtype=bool)
        return ~out & (fill[h] > 0)


def _truth(truth, mask, window: Window | None = None) -> TruthTable:
    if isinstance(truth, TruthTable):
        if mask is not None:
            raise ValueError("pass the mask when building the TruthTable, not with it")
        if window is not None and truth.window != window:
            raise ValueError(f"TruthTable window {truth.window.name} != {window.name}")
        return truth
    return TruthTable(truth, mask, window=window)


# --------------------------------------------------------------------------- per job


def _source_col(jobs: pl.DataFrame) -> str:
    for c in ("source_job_id", "source_id"):
        if c in jobs.columns:
            return c
    raise ValueError("jobs needs source_job_id or source_id")


def _joined(ledger: pl.DataFrame, jobs: pl.DataFrame) -> pl.DataFrame:
    need = ["job_uid", "site", "start_ts", "end_ts", "arrival_ts", "deadline_ts", "moved",
            "blocked", "fit_rejected"]
    missing = [c for c in need if c not in ledger.columns]
    if missing:
        raise ValueError(f"ledger is missing columns {missing}")
    if ledger["job_uid"].n_unique() != ledger.height:
        raise ValueError("ledger has duplicate job_uid")
    if jobs["job_uid"].n_unique() != jobs.height:
        raise ValueError("jobs has duplicate job_uid")
    src = _source_col(jobs) if ("source_id" in jobs.columns
                                or "source_job_id" in jobs.columns) else None
    j = jobs.select(
        "job_uid",
        (pl.col(src) if src else pl.col("job_uid")).alias("source_id"),
        _us("arrival_ts").alias("_jarr"),
        pl.col("gpus").cast(pl.Int64).alias("_jg"),
        (pl.col("duration_s").cast(pl.Float64) * US).round().cast(pl.Int64).alias("req_us"),
    )
    lcols = [
        "job_uid", "site", _us("start_ts").alias("s"), _us("end_ts").alias("e"),
        _us("arrival_ts").alias("arr"), _us("deadline_ts").alias("dl"), "moved", "blocked",
        "fit_rejected",
        (pl.col("booking_site") if "booking_site" in ledger.columns
         else pl.lit(None, dtype=pl.Utf8)).alias("booking_site"),
        (pl.col("gpus").cast(pl.Int64) if "gpus" in ledger.columns
         else pl.lit(None, dtype=pl.Int64)).alias("_lg"),
    ]
    out = ledger.select(lcols).join(j, on="job_uid", how="full", coalesce=True)
    lost = out.filter(pl.col("s").is_null())
    if lost.height:
        raise ValueError(f"ledger is missing {lost.height} jobs, e.g. "
                         f"{lost['job_uid'][:5].to_list()}")
    unknown = out.filter(pl.col("req_us").is_null())
    if unknown.height:
        raise ValueError(f"ledger has {unknown.height} jobs not in jobs, e.g. "
                         f"{unknown['job_uid'][:5].to_list()}")
    bad = out.filter(pl.col("_lg").is_not_null() & (pl.col("_lg") != pl.col("_jg")))
    if bad.height:
        raise ValueError(f"ledger gpus differ from jobs for {bad['job_uid'][:5].to_list()}")
    bad = out.filter(pl.col("arr") != pl.col("_jarr"))
    if bad.height:
        raise ValueError(f"ledger arrival_ts differs from jobs for "
                         f"{bad['job_uid'][:5].to_list()}")
    bad = out.filter(pl.col("e") < pl.col("s"))
    if bad.height:
        raise ValueError(f"ledger end before start for {bad['job_uid'][:5].to_list()}")
    return out.rename({"_jg": "gpus"}).drop("_lg", "_jarr")


def job_accounting(
    ledger: pl.DataFrame,
    jobs: pl.DataFrame,
    truth: pl.DataFrame | TruthTable,
    *,
    mask: pl.DataFrame | None = None,
    home: str = HOME,
) -> pl.DataFrame:
    """One row per job: work, wait, lateness, energy and CO₂ (see the module docstring).

    The ledger must hold exactly the jobs in `jobs` (missing, unknown or duplicate rows
    raise), and its gpus and arrivals must match. Columns: job_uid, source_id, site,
    booking_site, arrival_ts, start_ts, end_ts, deadline_ts, gpus, wait_s, late, moved,
    blocked, fit_rejected, remote, requested_gpu_s, completed_gpu_s, execution_kwh,
    transfer_it_kwh,
    transfer_kwh, energy_kwh, kwh_tier_ge2, execution_co2_kg, transfer_co2_kg, co2_kg.
    """
    tt = _truth(truth, mask)
    f = _joined(ledger, jobs)
    n = f.height
    site = f["site"].to_numpy().astype(str) if n else np.array([], dtype=str)
    s, e, arr = (f[c].to_numpy().astype(np.int64) for c in ("s", "e", "arr"))
    gpus = f["gpus"].to_numpy().astype(np.int64)
    req = f["req_us"].to_numpy().astype(np.int64)
    rate = gpus * _RATE
    remote = site != home

    exec_int = np.zeros(n)
    exec_fill_h = np.zeros(n)
    miss = np.zeros(n, dtype=bool)
    ci_home = np.zeros(n)
    ci_dest = np.zeros(n)
    fill_home = np.zeros(n)
    fill_dest = np.zeros(n)
    if remote.any():
        ci_home[remote], m = tt.point(home, arr[remote])
        miss[remote] |= m
        fill_home[remote] = tt.filled_at(home, arr[remote])
    for st in np.unique(site):
        k = site == st
        exec_int[k], m = tt.integral(st, s[k], e[k])
        miss[k] |= m
        exec_fill_h[k] = tt.filled_hours(st, s[k], e[k])
        kr = k & remote
        if kr.any():
            ci_dest[kr], m = tt.point(st, arr[kr])
            miss[kr] |= m
            fill_dest[kr] = tt.filled_at(st, arr[kr])
    if miss.any():
        bad = f["job_uid"].filter(pl.Series(miss)).to_list()
        raise ValueError(f"{len(bad)} ledger rows touch missing truth (accounting never "
                         f"fills; F3, F12.1, F14.6), e.g. {bad[:5]}")

    t_kwh = np.where(remote, TRANSFER_FRACTION * gpus * KW_PER_GPU * req / HOUR_US, 0.0)
    t_fac = t_kwh * PUE
    exec_kwh = rate * (e - s) / HOUR_US
    exec_co2 = rate * exec_int / 1000
    t_co2 = 0.5 * t_fac * (ci_home + ci_dest) / 1000
    tier2 = rate * exec_fill_h + 0.5 * t_fac * (fill_home + fill_dest)
    wait = (s - arr) / US
    late = e > f["dl"].to_numpy().astype(np.int64)

    return pl.DataFrame({
        "job_uid": f["job_uid"],
        "source_id": f["source_id"],
        "site": f["site"],
        "booking_site": f["booking_site"],
        "arrival_ts": _ts(arr),
        "start_ts": _ts(s),
        "end_ts": _ts(e),
        "deadline_ts": _ts(f["dl"].to_numpy()),
        "gpus": f["gpus"],
        "wait_s": wait,
        "late": pl.Series(late, dtype=pl.Boolean),
        "moved": f["moved"],
        "blocked": f["blocked"],
        "fit_rejected": f["fit_rejected"],
        "remote": pl.Series(remote, dtype=pl.Boolean),
        "requested_gpu_us": pl.Series(gpus * req, dtype=pl.Int64),
        "completed_gpu_us": pl.Series(gpus * (e - s), dtype=pl.Int64),
        "requested_gpu_s": gpus * req / US,
        "completed_gpu_s": gpus * (e - s) / US,
        "execution_kwh": exec_kwh,
        "transfer_it_kwh": t_kwh,
        "transfer_kwh": t_fac,
        "energy_kwh": exec_kwh + t_fac,
        "kwh_tier_ge2": tier2,
        "execution_co2_kg": exec_co2,
        "transfer_co2_kg": t_co2,
        "co2_kg": exec_co2 + t_co2,
    })


def _occupancy(warm: pl.DataFrame | WarmupState) -> pl.DataFrame:
    """(site, start_us, end_us, gpus) from a warm-up ledger or a WarmupState."""
    if isinstance(warm, WarmupState):
        warm = warm.ledger
    need = ["site", "start_ts", "end_ts", "gpus"]
    missing = [c for c in need if c not in warm.columns]
    if missing:
        raise ValueError(f"warm-up ledger is missing columns {missing}")
    return warm.select("site", _us("start_ts").alias("start_us"),
                       _us("end_ts").alias("end_us"), pl.col("gpus").cast(pl.Int64))


def _peak(starts: np.ndarray, ends: np.ndarray, gpus: np.ndarray) -> int:
    """Peak simultaneous GPUs over half-open intervals (ends release before starts)."""
    if starts.size == 0:
        return 0
    t = np.concatenate([ends, starts])
    d = np.concatenate([-gpus, gpus])
    order = np.lexsort((d, t))  # at equal t, releases (negative) first
    return int(np.cumsum(d[order]).max())


def score(
    ledger: pl.DataFrame,
    jobs: pl.DataFrame,
    truth: pl.DataFrame | TruthTable,
    *,
    mask: pl.DataFrame | None = None,
    sites: Mapping[str, int] = SITES,
    home: str = HOME,
    warm: pl.DataFrame | WarmupState | None = None,
) -> dict:
    """Policy metrics over one ledger (spec §9; amendment 7; F14.6).

    - Work: `requested_gpu_s` (declared) and `completed_gpu_s` (ledger); `conserved` is
      exact equality in integer GPU-µs.
    - Lateness: `late_jobs`, `late_gpu_h` (declared GPU-hours of jobs ending after their
      deadline). Under F11 bookings both are 0 by construction.
    - `feasible` = no late job, work conserved, and `capacity_violations == 0`: the
      number of sites whose peak simultaneous GPUs (`peak_gpus`) exceed their slots,
      over the cohort ledger plus `warm` (the warm-up ledger or `WarmupState`) when
      given. Without `warm` the check covers the cohort only. All other metrics are
      cohort-only; warm-up work and energy are never added.
    - Wait = execution start − arrival (transfer time included for remote runs).
    - Energy: `execution_kwh`, `transfer_kwh` (with PUE), `transfer_it_kwh`, and
      `energy_kwh` = execution + transfer. `kwh_share_tier_ge2` is the share of charged
      kWh priced on fill tiers 2–4 (F14.6).
    - CO₂ (kg, attributed operational, simulated): `co2_kg` = execution + transfer.
    - F11/F12.7/F14.7 diagnostics: moved counts and energy; `blocked` (F14.7, only
      non-zero for a `diagnose_blocked=True` ledger) counts and energy; and
      `fit_rejected` (the engine's F12.7 bug signal: a returned action that did not
      fit) counts and energy, which should be 0 for every registered policy.
    """
    a = job_accounting(ledger, jobs, truth, mask=mask, home=home).sort("job_uid")
    n = a.height

    def tot(c):
        return math.fsum(a[c].to_list()) if n else 0.0

    req_us = int(a["requested_gpu_us"].sum()) if n else 0
    done_us = int(a["completed_gpu_us"].sum()) if n else 0
    late = a.filter(pl.col("late"))
    exec_kwh, energy = tot("execution_kwh"), tot("energy_kwh")
    co2 = tot("co2_kg")
    gpu_h = done_us / US / 3600
    wait = a["wait_s"].to_numpy()
    if n:
        p50, p95 = (float(x) for x in np.percentile(wait, [50, 95], method="linear"))
        wmax, wmean = float(wait.max()), float(wait.mean())
    else:
        p50 = p95 = wmax = wmean = None

    occ = a.select("site", _us("start_ts").alias("start_us"), _us("end_ts").alias("end_us"),
                   pl.col("gpus").cast(pl.Int64))
    if warm is not None:
        occ = pl.concat([occ, _occupancy(warm)])
    unknown = set(occ["site"].unique().to_list()) - set(sites)
    if unknown:
        raise ValueError(f"ledger or warm-up uses sites {unknown} not in {list(sites)}")
    peaks = {}
    for st in sites:
        d = occ.filter(pl.col("site") == st)
        peaks[st] = _peak(d["start_us"].to_numpy().astype(np.int64),
                          d["end_us"].to_numpy().astype(np.int64),
                          d["gpus"].to_numpy().astype(np.int64))
    violations = sum(peaks[st] > slots for st, slots in sites.items())

    def share(num, den):
        return None if den == 0 else num / den

    moved = a.filter(pl.col("moved"))
    blocked = a.filter(pl.col("blocked"))
    rejected = a.filter(pl.col("fit_rejected"))
    remote = a.filter(pl.col("remote"))
    late_jobs = late.height
    conserved = req_us == done_us
    return {
        "n_jobs": n,
        "requested_gpu_s": req_us / US,
        "completed_gpu_s": done_us / US,
        "conserved": conserved,
        "late_jobs": late_jobs,
        "late_gpu_h": fsum_by(late, "requested_gpu_s") / 3600 if late_jobs else 0.0,
        "capacity_violations": int(violations),
        "peak_gpus": peaks,
        "feasible": bool(late_jobs == 0 and conserved and violations == 0),
        "wait_p50_s": p50,
        "wait_p95_s": p95,
        "wait_max_s": wmax,
        "wait_mean_s": wmean,
        "execution_kwh": exec_kwh,
        "transfer_kwh": tot("transfer_kwh"),
        "transfer_it_kwh": tot("transfer_it_kwh"),
        "energy_kwh": energy,
        "kwh_share_tier_ge2": share(tot("kwh_tier_ge2"), energy),
        "execution_co2_kg": tot("execution_co2_kg"),
        "transfer_co2_kg": tot("transfer_co2_kg"),
        "co2_kg": co2,
        "co2_kg_per_1000_gpu_h": None if gpu_h == 0 else co2 / (gpu_h / 1000),
        "moved_jobs": moved.height,
        "moved_share_jobs": share(moved.height, n),
        "moved_share_energy": share(fsum_by(moved, "execution_kwh"), exec_kwh),
        "remote_jobs": remote.height,
        "remote_energy_share": share(fsum_by(remote, "energy_kwh"), energy),
        "blocked_jobs": blocked.height,
        "blocked_kwh": fsum_by(blocked, "execution_kwh"),
        "fit_rejected_jobs": rejected.height,
        "fit_rejected_kwh": fsum_by(rejected, "execution_kwh"),
        "evidence": dict(EVIDENCE),
    }


def _us_np(s: pl.Series) -> np.ndarray:
    return s.dt.epoch("us").to_numpy().astype(np.int64)


def bound_ok(co2_kg: float, bound_kg: float, tol: float = BOUND_TOL_KG) -> bool:
    """The project's ordering check: a feasible policy's CO₂ ≥ C_relaxed − tol (F14.5).
    Apply it to the scored cohort only (warm-up excluded)."""
    return co2_kg >= bound_kg - tol


def common_support(
    ledgers: Mapping[str, pl.DataFrame],
    truth: pl.DataFrame | TruthTable,
    *,
    mask: pl.DataFrame | None = None,
    home: str = HOME,
) -> list[str]:
    """F14.6 sensitivity: sorted job_uids whose charged hours touch tier ≥ 2 under any
    policy (execution [start, end) with positive overlap, or, for a remote run, the
    arrival hour at home or at the destination). Drop them from every policy."""
    tt = _truth(truth, mask)
    hit: set[str] = set()
    for led in ledgers.values():
        uid = led["job_uid"].to_numpy()
        site = led["site"].to_numpy().astype(str)
        s, e, arr = (_us_np(led[c]) for c in ("start_ts", "end_ts", "arrival_ts"))
        touch = np.zeros(led.height, dtype=bool)
        remote = site != home
        if remote.any():
            touch[remote] |= tt.filled_at(home, arr[remote])
        for st in np.unique(site):
            k = site == st
            touch[k] |= tt.filled_hours(st, s[k], e[k]) > 0
            kr = k & remote
            if kr.any():
                touch[kr] |= tt.filled_at(st, arr[kr])
        hit.update(uid[touch].tolist())
    return sorted(hit)


# --------------------------------------------------------------------------- bound


def _deadlines(jobs: pl.DataFrame, bookings: pl.DataFrame | None) -> pl.DataFrame:
    if bookings is not None:
        b = bookings.select("job_uid", pl.col("deadline_us").cast(pl.Int64).alias("dl"))
        out = jobs.join(b, on="job_uid", how="left")
    elif "deadline_us" in jobs.columns:
        out = jobs.with_columns(pl.col("deadline_us").cast(pl.Int64).alias("dl"))
    elif "deadline_ts" in jobs.columns:
        out = jobs.with_columns(_us("deadline_ts").alias("dl"))
    else:
        raise ValueError("relaxed_bound needs deadlines: pass bookings (u_bookings) or a "
                         "jobs frame with deadline_ts or deadline_us")
    lost = out.filter(pl.col("dl").is_null())
    if lost.height:
        raise ValueError(f"no deadline for {lost.height} jobs, e.g. "
                         f"{lost['job_uid'][:5].to_list()}")
    return out


def _ceil_h(x: np.ndarray) -> np.ndarray:
    return -((-x) // HOUR_US) * HOUR_US


def _min_integral(tt: TruthTable, site: str, lo: np.ndarray, hi: np.ndarray,
                  d: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per job, min over s ∈ [lo, hi] of ∫ ci over [s, s+d) avoiding missing hours, and
    the earliest start attaining it. The integral is piecewise linear in s with kinks
    where s or s+d crosses an hour boundary, and the supported set's endpoints are such
    kinks too, so the breakpoint set {lo, hi, hour boundaries, hour boundaries − d} in
    [lo, hi] is exact (spec §8, F14.5). inf where no candidate is supported."""
    m = lo.size
    best = np.full(m, np.inf)
    arg = np.zeros(m, dtype=np.int64)
    if m == 0:
        return best, arg
    a0, a1 = _ceil_h(lo), (hi // HOUR_US) * HOUR_US
    b0, b1 = _ceil_h(lo + d), ((hi + d) // HOUR_US) * HOUR_US
    ca = np.where(a1 >= a0, (a1 - a0) // HOUR_US + 1, 0)
    cb = np.where(b1 >= b0, (b1 - b0) // HOUR_US + 1, 0)
    c = 2 + ca + cb
    cum = np.cumsum(c)
    i = 0
    while i < m:
        base = cum[i] - c[i]
        j = int(np.searchsorted(cum, base + _CHUNK, side="right"))
        j = max(j, i + 1)
        sl = slice(i, j)
        cc = c[sl]
        off = np.cumsum(cc) - cc
        grp = np.repeat(np.arange(j - i), cc)
        pos = np.arange(int(cc.sum())) - off[grp]
        k = pos - 2
        lo_g, hi_g, a0_g, b0_g, d_g, ca_g = (x[sl][grp] for x in (lo, hi, a0, b0, d, ca))
        cand = np.where(
            pos == 0, lo_g,
            np.where(pos == 1, hi_g,
                     np.where(k < ca_g, a0_g + k * HOUR_US,
                              b0_g + (k - ca_g) * HOUR_US - d_g)))
        val, miss = tt.integral(site, cand, cand + d_g)
        val = np.where(miss, np.inf, val)
        order = np.lexsort((cand, val, grp))
        first = order[off]
        best[sl] = val[first]
        arg[sl] = cand[first]
        i = j
    return best, arg


def relaxed_bound_jobs(
    jobs: pl.DataFrame,
    truth: pl.DataFrame | TruthTable,
    mask: pl.DataFrame | None = None,
    sites: Mapping[str, int] = SITES,
    *,
    bookings: pl.DataFrame | None = None,
    home: str = HOME,
    transfer_s: float = TRANSFER_S,
) -> pl.DataFrame:
    """C_relaxed per job (F5, F12.3, F13.1 "C_relaxed"; F14.5).

    Each job's minimum realized CO₂ over its continuous envelope: start s ∈ [arrival
    (+ `transfer_s` when remote), deadline − duration] at every legal site (home; other
    sites only for mobile jobs; gang ≤ site slots), with execution and, for a remote run,
    both arrival-hour transfer charges on supported truth (F12.1). Every other job's
    occupancy, every booking and warm-up occupancy are dropped. The booking lies inside
    this envelope, so it is covered. Deadlines come from `bookings.deadline_us`, else the
    jobs' `deadline_ts`/`deadline_us`. `sites`, `transfer_s` and `home` are the
    scenario's own (F14.5).

    Columns: job_uid, site, start_ts, execution_co2_kg, transfer_co2_kg, co2_kg; site,
    start and CO₂ are null where the job has no legal action. Ties go to home, then BA
    code, then the earliest start.
    """
    tt = _truth(truth, mask)
    f = _deadlines(jobs, bookings)
    uid = f["job_uid"]
    arr = _us_np(f["arrival_ts"])
    d = (f["duration_s"].cast(pl.Float64) * US).round().cast(pl.Int64).to_numpy()
    gpus = f["gpus"].cast(pl.Int64).to_numpy()
    mobile = f["mobile"].to_numpy().astype(bool)
    dl = f["dl"].to_numpy().astype(np.int64)
    tr_us = round(transfer_s * US)
    n = f.height
    if home not in sites:
        raise ValueError(f"home site {home} is not in sites")

    best = np.full(n, np.inf)
    best_exec = np.zeros(n)
    best_tr = np.zeros(n)
    best_site = np.full(n, None, dtype=object)
    best_start = np.zeros(n, dtype=np.int64)
    ci_home, miss_home = tt.point(home, arr) if n else (np.zeros(0), np.zeros(0, bool))
    for site in [home] + sorted(s for s in sites if s != home):
        remote = site != home
        lo = arr + (tr_us if remote else 0)
        hi = dl - d
        ok = (gpus <= sites[site]) & (hi >= lo)
        tco2 = np.zeros(n)
        if remote:
            ok &= mobile
            ci_d, miss_d = tt.point(site, arr) if n else (np.zeros(0), np.zeros(0, bool))
            ok &= ~miss_home & ~miss_d
            t_fac = TRANSFER_FRACTION * gpus * KW_PER_GPU * d / HOUR_US * PUE
            tco2 = 0.5 * t_fac * (ci_home + ci_d) / 1000
        idx = np.flatnonzero(ok)
        val, start = _min_integral(tt, site, lo[idx], hi[idx], d[idx])
        exec_kg = gpus[idx] * _RATE * val / 1000
        total = exec_kg + tco2[idx]
        better = total < best[idx]
        w = idx[better]
        best[w] = total[better]
        best_exec[w] = exec_kg[better]
        best_tr[w] = tco2[idx][better]
        best_site[w] = site
        best_start[w] = start[better]

    found = np.isfinite(best)
    return pl.DataFrame({
        "job_uid": uid,
        "site": pl.Series(np.where(found, best_site, None).tolist(), dtype=pl.Utf8),
        "start_ts": _ts(best_start).set(pl.Series(~found), None),
        "execution_co2_kg": pl.Series(np.where(found, best_exec, np.nan)).fill_nan(None),
        "transfer_co2_kg": pl.Series(np.where(found, best_tr, np.nan)).fill_nan(None),
        "co2_kg": pl.Series(np.where(found, best, np.nan)).fill_nan(None),
    })


def relaxed_bound(
    jobs: pl.DataFrame,
    truth: pl.DataFrame | TruthTable,
    mask: pl.DataFrame | None = None,
    sites: Mapping[str, int] = SITES,
    *,
    bookings: pl.DataFrame | None = None,
    home: str = HOME,
    transfer_s: float = TRANSFER_S,
) -> float:
    """C_relaxed in kg: the sum of `relaxed_bound_jobs`. A lower bound on every feasible
    policy's cohort CO₂ (a bound, never a ceiling; F7). Raises if any job has no legal
    action, since its booking would then be unsupported too (F12.3)."""
    per = relaxed_bound_jobs(jobs, truth, mask, sites, bookings=bookings, home=home,
                             transfer_s=transfer_s)
    lost = per.filter(pl.col("co2_kg").is_null())
    if lost.height:
        raise ValueError(f"{lost.height} jobs have no legal action in the relaxed envelope "
                         f"(unsupported truth?), e.g. {lost['job_uid'][:5].to_list()}")
    return fsum_by(per, "co2_kg")


# --------------------------------------------------------------------------- weekly


def denver_weeks(start: datetime, end: datetime) -> pl.Series:
    """Every Monday-00:00 America/Denver week that intersects [start, end) (F13.4).
    Both bounds must be timezone-aware."""
    start, end = _aware(start, "start"), _aware(end, "end")
    if not end > start:
        raise ValueError(f"empty window [{start}, {end})")
    s = pl.Series([start.astimezone(UTC), (end - timedelta(microseconds=1)).astimezone(UTC)]) \
        .dt.cast_time_unit("us").dt.convert_time_zone(WEEK_TZ).dt.truncate("1w")
    return pl.datetime_range(s[0], s[1], "1w", time_unit="us", time_zone=WEEK_TZ,
                             eager=True).alias("week")


def weekly(
    ledger: pl.DataFrame,
    jobs: pl.DataFrame,
    truth: pl.DataFrame | TruthTable,
    *,
    window: tuple[datetime, datetime],
    mask: pl.DataFrame | None = None,
    home: str = HOME,
) -> pl.DataFrame:
    """Weekly totals by arrival week (F12.4, F13.4; amendment 2).

    Each job's full totals land in the Monday-00:00 America/Denver week of its arrival,
    whatever weeks its execution spans. Rows are every week intersecting the arrival
    interval `window` = [eval_start, A) (required; tz-aware), zero-job weeks included,
    partial edge weeks as they are. Arrivals outside the window raise. Columns: week
    (datetime[us, America/Denver]), co2_kg, energy_kwh, n_jobs, gpu_h, execution_kwh,
    transfer_kwh.
    """
    start, end = window
    start, end = _aware(start, "window start"), _aware(end, "window end")
    a = job_accounting(ledger, jobs, truth, mask=mask, home=home)
    if not end > start:
        raise ValueError(f"empty arrival window {window}")
    out = a.filter((pl.col("arrival_ts") < start) | (pl.col("arrival_ts") >= end))
    if out.height:
        raise ValueError(f"{out.height} arrivals fall outside the window {window}, e.g. "
                         f"{out['job_uid'][:5].to_list()}")
    a = a.with_columns(pl.col("arrival_ts").dt.convert_time_zone(WEEK_TZ).dt.truncate("1w")
                       .alias("week")).sort("job_uid")
    cols = ("co2_kg", "energy_kwh", "execution_kwh", "transfer_kwh")
    rows = []
    for (wk,), g in a.partition_by("week", as_dict=True, maintain_order=True).items():
        r = {"week": wk, "n_jobs": g.height,
             "gpu_h": math.fsum(g["completed_gpu_s"].to_list()) / 3600}
        r.update({c: math.fsum(g[c].to_list()) for c in cols})
        rows.append(r)
    agg = pl.DataFrame(rows, schema={"week": a.schema["week"], "n_jobs": pl.Int64,
                                     "gpu_h": pl.Float64, **{c: pl.Float64 for c in cols}})
    weeks = denver_weeks(start, end).to_frame()
    return (
        weeks.join(agg, on="week", how="left")
        .with_columns(pl.col("n_jobs").fill_null(0).cast(pl.Int64),
                      pl.col("co2_kg", "energy_kwh", "gpu_h", "execution_kwh",
                             "transfer_kwh").fill_null(0.0))
        .select("week", "co2_kg", "energy_kwh", "n_jobs", "gpu_h", "execution_kwh",
                "transfer_kwh")
        .sort("week")
    )


# --------------------------------------------------------------------------- diagnostics


def influence(
    ledgers: Mapping[str, pl.DataFrame],
    jobs: pl.DataFrame,
    truth: pl.DataFrame | TruthTable,
    k_list: Sequence[int] = (1, 5, 10),
    *,
    reference: str = "U",
    mask: pl.DataFrame | None = None,
    home: str = HOME,
) -> dict:
    """Leave-top-k-sources-out (F6, F12.4 D4; amendments 5, 11).

    Unique source attempts are ranked by declared GPU-hours (gpus × duration_s / 3600,
    one attempt; independent of policy), ties to the smaller `source_job_id`. For each k
    (0 included) every instance of the top k is removed from every policy's totals, and
    each policy is compared with `reference`: diff_kg = reference − policy (positive =
    policy emits less), saving = diff_kg / reference (None if the reference is 0).
    """
    if reference not in ledgers:
        raise ValueError(f"reference policy {reference!r} not in ledgers")
    src = _source_col(jobs)
    tt = _truth(truth, mask)
    varied = (jobs.group_by(src)
              .agg(pl.col("duration_s").n_unique().alias("nd"), pl.col("gpus").n_unique()
                   .alias("ng"))
              .filter((pl.col("nd") > 1) | (pl.col("ng") > 1)))
    if varied.height:
        raise ValueError(f"{varied.height} sources have instances with different durations "
                         f"or gpus (one declared attempt each), e.g. "
                         f"{varied[src][:5].to_list()}")
    rank = (
        jobs.group_by(src)
        .agg((pl.col("gpus") * pl.col("duration_s") / 3600).max().alias("declared_gpu_h"))
        .sort(["declared_gpu_h", src], descending=[True, False])
    )
    acc = {p: job_accounting(led, jobs, tt, home=home).select("job_uid", "source_id",
                                                              "co2_kg")
           for p, led in ledgers.items()}
    ks = sorted({0, *(int(k) for k in k_list)})
    by_k = {}
    for k in ks:
        top = rank[src][:k].to_list()
        totals = {p: fsum_by(a.filter(~pl.col("source_id").is_in(top)), "co2_kg")
                  for p, a in acc.items()}
        ref = totals[reference]
        removed = jobs.filter(pl.col(src).is_in(top)).height
        by_k[k] = {
            "removed_sources": top,
            "removed_jobs": removed,
            "totals": totals,
            "vs_reference": {p: {"diff_kg": ref - v,
                                 "saving": None if ref == 0 else (ref - v) / ref}
                             for p, v in totals.items()},
        }
    top_rows = rank[: max(ks)].rename({src: "source_id"}).to_dicts()
    return {"reference": reference, "rank_by": "declared_gpu_h", "ranking": top_rows,
            "by_k": by_k, "evidence": "simulated"}


def support_check(
    bookings: pl.DataFrame,
    truth: pl.DataFrame | TruthTable,
    F: datetime,
    *,
    mask: pl.DataFrame | None = None,
    window: Window | None = None,
) -> dict:
    """Accounting-support pre-check of U bookings (F12.3, F13.3; amendment 6).

    Reports every booking that ends after F (`ends_after_f`) or whose [start, end)
    touches an hour with no truth at its site (`missing_truth`). Pass the F14.6 filled
    truth (the pre-check uses it); `n_filled_truth` counts bookings priced partly on
    tiers 2–4 (informational). Hours at or after TEST_START (with the test `window`:
    F_test) are never read: a booking reaching them counts as `missing_truth`. Accepts `u_bookings` frames (start_us,
    end_us) or ledgers (start_ts, end_ts), e.g. the warm-up ledger, which F13.2 checks
    through its actual completion. `ok` is False on any failure, which the driver must
    report as an accounting-support failure.
    """
    f_us = _dt_us(F, "F")
    tt = _truth(truth, mask, window)
    if "start_us" in bookings.columns:
        s = bookings["start_us"].to_numpy().astype(np.int64)
        e = bookings["end_us"].to_numpy().astype(np.int64)
    else:
        s, e = _us_np(bookings["start_ts"]), _us_np(bookings["end_ts"])
    uid = bookings["job_uid"].to_list()
    site = bookings["site"].to_numpy().astype(str)
    after = e > f_us
    sealed = e > tt.read_end_us
    e_read = np.minimum(e, tt.read_end_us)
    s_read = np.minimum(s, e_read)
    miss = sealed.copy()
    filled = np.zeros(len(uid), dtype=bool)
    for st in np.unique(site):
        k = site == st
        _, m = tt.integral(st, s_read[k], e_read[k])
        miss[k] |= m
        filled[k] = tt.filled_hours(st, s_read[k], e_read[k]) > 0
    failures = []
    for i in np.flatnonzero(after | miss):
        reasons = (["ends_after_f"] if after[i] else []) + \
                  (["missing_truth"] if miss[i] else [])
        failures.append({"job_uid": uid[i], "site": site[i],
                         "start_us": int(s[i]), "end_us": int(e[i]), "reasons": reasons})
    return {
        "ok": not failures,
        "n_checked": len(uid),
        "n_after_f": int(after.sum()),
        "n_missing_truth": int(miss.sum()),
        "n_filled_truth": int(filled.sum()),
        "F": F.isoformat(),
        "failures": failures,
    }
