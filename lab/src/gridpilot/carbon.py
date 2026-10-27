"""Carbon-intensity arithmetic shared by the evidence notebooks, the recon scripts and the
scoring truth fill.

`wait_choice` and `wait_cut` take an hourly series on a contiguous grid (one value per hour,
in time order). They are perfect-foresight upper bounds: they see the whole series.

`fuel_mix_ci` is our EIA-930 production-basis intensity: the grid-profile formula over
adjusted generation by fuel (moved here from `scripts/recon_grid.py`, which reuses it; F14.6
tier 3). It is `modeled`.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from gridpilot.data.eia930 import PARTITION_FUELS

# Direct (combustion) CO2 factors, EIA FAQ "How much carbon dioxide is produced per kilowatthour
# of U.S. electricity generation?" (https://www.eia.gov/tools/faqs/faq.php?id=74&t=11), data
# year 2023, utility-scale incl. CHP: coal 2.31, natural gas 0.96, petroleum 2.46, all sources
# 0.81 lb CO2/kWh. 1 lb = 453.592 g. Non-fossil sources are 0 (EIA treats biomass, hydro,
# solar and wind as carbon neutral). "Unknown" takes the all-source US average (assumed);
# "Other" (biomass, waste, geothermal and, before 2024-07, storage) is 0 in the primary case and
# the all-source average in the sensitivity case.
LB_TO_G = 453.592
EF_G_KWH = {"coal": 2.31 * LB_TO_G, "gas": 0.96 * LB_TO_G, "oil": 2.46 * LB_TO_G,
            "unknown": 0.81 * LB_TO_G}
EF_OTHER_SENS_G_KWH = 0.81 * LB_TO_G


def _adj(fuel: str) -> pl.Expr:
    return pl.col(f"gen_{fuel}_adj_mw")


def fuel_gen_total() -> pl.Expr:
    """Generation by fuel (MW): the sum of the partition fuels; null if every fuel is null."""
    any_fuel = pl.any_horizontal([_adj(f).is_not_null() for f in PARTITION_FUELS])
    total = pl.sum_horizontal([_adj(f).fill_null(0) for f in PARTITION_FUELS])
    return pl.when(any_fuel).then(total).otherwise(None)


def fuel_co2_kg(other_sens: bool = False) -> pl.Expr:
    """Hourly CO2 (kg; MW × kg/MWh): negative generation never emits. Null if every fuel is
    null. `other_sens` prices "Other" at the all-source average (the sensitivity case)."""
    any_fuel = pl.any_horizontal([_adj(f).is_not_null() for f in PARTITION_FUELS])
    emis = pl.sum_horizontal([_adj(f).fill_null(0).clip(lower_bound=0) * ef
                              for f, ef in EF_G_KWH.items()])
    if other_sens:
        emis = emis + _adj("other").fill_null(0).clip(lower_bound=0) * EF_OTHER_SENS_G_KWH
    return pl.when(any_fuel).then(emis).otherwise(None)


def fuel_mix_ci(other_sens: bool = False) -> pl.Expr:
    """Production-basis g/kWh from adjusted generation by fuel; null unless generation > 0."""
    total = fuel_gen_total()
    return pl.when(total > 0).then(fuel_co2_kg(other_sens) / total).otherwise(None)


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
