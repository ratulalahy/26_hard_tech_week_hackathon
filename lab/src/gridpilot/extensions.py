"""Stage 3 T10 Part B (D-058): re-scoring fixed ledgers. No re-simulation happens here.

- `reprice`: the same ledgers priced on another truth (production-basis CI, filled by the
  F14.6 tiers with production as tier 1), each policy against U on every basis.
- `common_support_cohort`: the F14.6 sensitivity. Every policy keeps only the jobs whose
  charged hours touch tier-1 truth only, under every policy (`common_support`); the savings
  and intervals are recomputed on that cohort, with its size and energy share.

Totals are `math.fsum` (order-free); intervals are the frozen paired block bootstrap. All
outputs are validation results (simulated).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

import polars as pl

from gridpilot.eval import (
    BLOCKS,
    TruthTable,
    common_support,
    fsum_by,
    job_accounting,
    paired_block_bootstrap,
    weekly,
)


def policy_contrasts(ledgers: Mapping[str, pl.DataFrame], jobs: pl.DataFrame, tt: TruthTable,
                     window: tuple[datetime, datetime], *, reference: str = "U",
                     blocks: Sequence[int] = BLOCKS) -> dict:
    """Totals, weekly series and the paired bootstrap of every policy against `reference`
    (diff = reference − candidate; saving = ratio of totals)."""
    if reference not in ledgers:
        raise ValueError(f"reference {reference!r} not in ledgers")
    acc = {p: job_accounting(led, jobs, tt) for p, led in ledgers.items()}
    weeks = {p: weekly(led, jobs, tt, window=window) for p, led in ledgers.items()}
    totals = {p: fsum_by(a, "co2_kg") for p, a in acc.items()}
    energy = {p: fsum_by(a, "energy_kwh") for p, a in acc.items()}
    tier = {p: (fsum_by(a, "kwh_tier_ge2") / energy[p]) if energy[p] else None
            for p, a in acc.items()}
    contrasts = {p: {int(b): paired_block_bootstrap(weeks[reference], weeks[p], block=int(b))
                     for b in blocks}
                 for p in ledgers if p != reference}
    return {"reference": reference, "totals": totals, "energy_kwh": energy,
            "tier_ge2_kwh_share": tier, "contrasts": contrasts,
            "n_weeks": weeks[reference].height}


def reprice(ledgers: Mapping[str, pl.DataFrame], jobs: pl.DataFrame,
            truths: Mapping[str, TruthTable], window: tuple[datetime, datetime],
            **kw) -> dict:
    """`policy_contrasts` on each named truth basis; the ledgers are never changed."""
    return {basis: policy_contrasts(ledgers, jobs, tt, window, **kw)
            for basis, tt in truths.items()}


def common_support_cohort(ledgers: Mapping[str, pl.DataFrame], jobs: pl.DataFrame,
                          tt: TruthTable, window: tuple[datetime, datetime], **kw) -> dict:
    """F14.6 common support: drop, from every policy, each job whose charged hours touch
    tier ≥ 2 under any policy; recompute the contrasts on the jobs left."""
    dropped = common_support(ledgers, tt)
    drop = list(dropped)
    keep = jobs.filter(~pl.col("job_uid").is_in(drop))
    kept = {p: led.filter(~pl.col("job_uid").is_in(drop)) for p, led in ledgers.items()}
    share_e = {}
    for p, led in ledgers.items():
        a = job_accounting(led, jobs, tt)
        tot = fsum_by(a, "energy_kwh")
        share_e[p] = (fsum_by(a.filter(~pl.col("job_uid").is_in(drop)), "energy_kwh") / tot
                      if tot else None)
    return {"dropped": dropped, "n_cohort": jobs.height, "n_jobs": keep.height,
            "share_jobs": keep.height / jobs.height if jobs.height else None,
            "energy_share": share_e,
            "contrasts": policy_contrasts(kept, keep, tt, window, **kw)}


__all__ = ["common_support_cohort", "policy_contrasts", "reprice"]
