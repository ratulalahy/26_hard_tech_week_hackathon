"""Carbon-intensity arithmetic shared by the evidence notebooks and, later, the router.

All functions take an hourly series on a contiguous grid (one value per hour, in time order).
They are perfect-foresight upper bounds: they see the whole series.
"""

from __future__ import annotations

import numpy as np


def wait_choice(ci: np.ndarray, max_wait_h: int) -> np.ndarray:
    """For each hour t, the offset k in [0, max_wait_h] of the lowest value in ci[t .. t+k].

    Ties go to the earliest hour, and the window is truncated at the end of the series.
    """
    ci = np.asarray(ci, dtype=float)
    if max_wait_h < 0:
        raise ValueError("max_wait_h must be >= 0")
    n = len(ci)
    best = ci.copy()
    offset = np.zeros(n, dtype=int)
    for k in range(1, max_wait_h + 1):
        if k >= n:
            break
        later = ci[k:]
        better = later < best[: n - k]
        best[: n - k] = np.where(better, later, best[: n - k])
        offset[: n - k] = np.where(better, k, offset[: n - k])
    return offset


def wait_cut(choose_on: np.ndarray, max_wait_h: int, evaluate_on: np.ndarray | None = None) -> float:
    """Share of emissions a 1-hour job avoids by starting at the cleanest hour within its wait.

    Each hour t is one job. It starts at t + wait_choice(choose_on)[t]. The cut is
    sum(e[t] - e[start]) / sum(e[t]) with e = ``evaluate_on`` (default: ``choose_on``).

    With ``evaluate_on`` = ``choose_on`` this is the profile's "wait <= W h cut" (grid.md, section
    8). Passing a marginal-intensity series as ``evaluate_on`` asks how much of an average-intensity
    schedule's saving survives on the margin.
    """
    choose_on = np.asarray(choose_on, dtype=float)
    e = choose_on if evaluate_on is None else np.asarray(evaluate_on, dtype=float)
    if e.shape != choose_on.shape:
        raise ValueError("choose_on and evaluate_on must have the same length")
    start = np.arange(len(e)) + wait_choice(choose_on, max_wait_h)
    return float((e - e[start]).sum() / e.sum())
