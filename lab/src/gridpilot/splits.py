"""Time splits, including the sealed test window (AGENTS.md, "Data rules").

Boundaries are UTC and half-open: [start, end). The train start is set by the
spec from the data profile; only the validation and test boundaries are fixed.
"""

from datetime import UTC, datetime

import polars as pl

VALIDATION_START = datetime(2024, 11, 1, tzinfo=UTC)
TEST_START = datetime(2025, 11, 1, tzinfo=UTC)
TEST_END = datetime(2026, 11, 1, tzinfo=UTC)


def drop_sealed(frame: pl.DataFrame | pl.LazyFrame, ts_col: str = "ts_utc"):
    """Keep only rows before the sealed test window.

    Call this before any summary, plot or model fit during design. Completeness
    checks on the test window (row counts, missing hours) are the only exception.
    """
    return frame.filter(pl.col(ts_col) < TEST_START)
