from datetime import UTC, datetime

import polars as pl

from gridpilot.splits import TEST_START, drop_sealed


def test_drop_sealed_keeps_only_rows_before_the_test_window():
    frame = pl.DataFrame(
        {
            "ts_utc": [datetime(2025, 10, 31, 23, tzinfo=UTC), TEST_START, datetime(2026, 5, 1, tzinfo=UTC)],
            "value": [1, 2, 3],
        }
    )
    assert drop_sealed(frame)["value"].to_list() == [1]
