"""Frozen paired circular block bootstrap over weekly totals, and the H2 decision helper.

These are **conditional temporal block-resampling intervals** (F12.4): conditional on
this replay, its alignment and the models; they assume weekly totals depend on each
other only within blocks, and they do not cover alternative alignments (the replay
cycle recurs every 23 weeks), emissions-factor error or other clusters. An interval
that excludes zero is described as such, never as "confirmation".

**Frozen algorithm (F12.4, F13.4, F14.8).**
- Weeks: every Monday-00:00 America/Denver week intersecting the arrival interval,
  zero-job weeks included (`gridpilot.eval.weekly`). n = number of weeks.
- For each block length b, a fresh `numpy.random.Generator(PCG64(20261027))`. For each of
  2,000 replicates, in replicate order, one call `rng.integers(0, n, size=ceil(n/b))`
  (int64) gives the block starts; each start s expands to `(s + j) % n` for j < b; the
  blocks are concatenated and the first n indices kept. Source blocks may overlap.
- The same indices go to every policy (they depend only on n, b, reps and seed).
- Per replicate, totals A* (reference) and B* (candidate) are sums over the indices;
  diff = A* − B* (kg; positive = candidate emits less) and saving = diff / A*.
- 95% percentile intervals: `numpy.quantile(x, [0.025, 0.975], method="linear")`.
- Degenerate cases: empty input → null point values and intervals; a zero reference
  total → null saving; any replicate with a zero reference total → null saving
  interval (the kg interval is unaffected).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import polars as pl

BOOTSTRAP_LABEL = "conditional temporal block-resampling interval"
SEED = 20261027
REPS = 2000
BLOCKS = (2, 4, 8)
PRIMARY_BLOCK = 4
QUANTILES = (0.025, 0.975)


def block_indices(n: int, block: int, reps: int = REPS, seed: int = SEED) -> np.ndarray:
    """The frozen (reps, n) index matrix for n weeks and block length `block`."""
    if n < 0 or block < 1 or reps < 1:
        raise ValueError(f"need n >= 0, block >= 1, reps >= 1; got {n}, {block}, {reps}")
    out = np.empty((reps, n), dtype=np.int64)
    if n == 0:
        return out
    rng = np.random.Generator(np.random.PCG64(seed))
    m = math.ceil(n / block)
    offs = np.arange(block, dtype=np.int64)
    for r in range(reps):
        starts = rng.integers(0, n, size=m, dtype=np.int64)
        out[r] = ((starts[:, None] + offs) % n).ravel()[:n]
    return out


def _values(x, value: str) -> tuple[np.ndarray, pl.Series | None]:
    if isinstance(x, pl.DataFrame):
        if value not in x.columns:
            raise ValueError(f"weekly frame has no {value!r} column")
        weeks = x["week"] if "week" in x.columns else None
        return x[value].cast(pl.Float64).to_numpy(), weeks
    return np.asarray(x, dtype=float).ravel(), None


def _ci(x: np.ndarray) -> tuple[float, float]:
    lo, hi = np.quantile(x, QUANTILES, method="linear")
    return float(lo), float(hi)


def paired_block_bootstrap(
    a_weeks,
    b_weeks,
    block: int = PRIMARY_BLOCK,
    reps: int = REPS,
    seed: int = SEED,
    *,
    value: str = "co2_kg",
) -> dict:
    """Paired conditional temporal block-resampling intervals for reference `a` against
    candidate `b` (weekly frames from `weekly`, or aligned 1-D arrays).

    Returns the ratio-of-totals saving (a − b) / a and the paired absolute difference
    a − b in kg, each with a 95% percentile interval. A negative value means the
    candidate emits more than the reference; signs are never altered.
    """
    a, wa = _values(a_weeks, value)
    b, wb = _values(b_weeks, value)
    if a.shape != b.shape:
        raise ValueError(f"weekly series differ in length: {a.size} vs {b.size}")
    if wa is not None and wb is not None and not wa.equals(wb):
        raise ValueError("weekly frames cover different weeks")
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        raise ValueError("weekly totals must be finite")
    n = a.size
    out = {
        "method": BOOTSTRAP_LABEL,
        "block": block,
        "reps": reps,
        "seed": seed,
        "quantiles": QUANTILES,
        "n_weeks": n,
        "value": value,
        "diff_definition": "reference − candidate (positive = candidate emits less)",
        "reference_total": float(a.sum()),
        "candidate_total": float(b.sum()),
        "diff_kg": None,
        "diff_kg_ci": None,
        "saving": None,
        "saving_ci": None,
        "saving_ci_null_reason": None,
    }
    if n == 0:
        out["saving_ci_null_reason"] = "empty input"
        return out
    A0, B0 = a.sum(), b.sum()
    out["diff_kg"] = float(A0 - B0)
    out["saving"] = None if A0 == 0 else float((A0 - B0) / A0)
    idx = block_indices(n, block, reps, seed)
    A, B = a[idx].sum(axis=1), b[idx].sum(axis=1)
    out["diff_kg_ci"] = _ci(A - B)
    if (A == 0).any():
        out["saving_ci_null_reason"] = "a replicate has a zero reference total"
    else:
        out["saving_ci"] = _ci((A - B) / A)
    return out


def h2_decision(
    w_weeks,
    l_weeks,
    blocks: Sequence[int] = BLOCKS,
    reps: int = REPS,
    seed: int = SEED,
    *,
    value: str = "co2_kg",
) -> dict:
    """H2's decision rule on W − L kg (F4, F12.4, F13.4).

    The driver applies it to the full scored phase-0 cohort (F14.3); the coverage
    stratum is a secondary estimate with no decision rule, and the 91-day fallback makes
    no H2 decision statement (F14.4). Intervals are conditional temporal
    block-resampling intervals at b = 2, 4 and 8. `direction` is "favourable" only if
    all three lower endpoints of W − L are > 0 (L emits less), "adverse" only if all
    three upper endpoints are < 0, else "inconclusive"; `decided` is direction !=
    "inconclusive". The b = 4 interval is the primary statistic.
    """
    res = {int(b): paired_block_bootstrap(w_weeks, l_weeks, int(b), reps, seed, value=value)
           for b in blocks}
    cis = [r["diff_kg_ci"] for r in res.values()]
    if any(c is None for c in cis):
        direction = "inconclusive"
    elif all(c[0] > 0 for c in cis):
        direction = "favourable"
    elif all(c[1] < 0 for c in cis):
        direction = "adverse"
    else:
        direction = "inconclusive"
    return {
        "method": BOOTSTRAP_LABEL,
        "statistic": "W − L kg CO₂ (positive = L emits less)",
        "blocks": [int(b) for b in blocks],
        "primary_block": PRIMARY_BLOCK,
        "intervals": res,
        "direction": direction,
        "decided": direction != "inconclusive",
    }
