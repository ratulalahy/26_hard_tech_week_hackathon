"""Carbon truth table: EIA consumption-based CO2 intensity (lb/kWh in the workbook -> g/kWh)."""

from datetime import UTC, datetime
from pathlib import Path

import openpyxl
import polars as pl
import pytest

from gridpilot.data import eia_co2
from gridpilot.data.eia_co2 import load_carbon, parse_ba_workbook, site_mask
from gridpilot.splits import TEST_START

SHEET = "Published Hourly Data"
CONS = "CO2 Emissions Intensity for Consumed Electricity"
GEN = "CO2 Emissions Intensity for Generated Electricity"


def _workbook(path: Path, rows: list[tuple]) -> Path:
    """rows: (utc_time, generated lb/kWh, consumed lb/kWh); values may be str or None."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SHEET
    ws.append(["BA", "UTC time", "Demand", GEN, CONS])
    for t, g, c in rows:
        ws.append(["TEST", t, 100.0, g, c])
    wb.save(path)
    return path


def test_units(tmp_path):
    p = _workbook(tmp_path / "a.xlsx", [(datetime(2024, 7, 1, 1), 0.5, 1.25)])
    df = parse_ba_workbook(p, "TEST")
    assert df.columns == ["ba", "ts_utc", "ci_consumed_g_kwh", "ci_generated_g_kwh", "null_reason"]
    assert round(df["ci_consumed_g_kwh"][0], 2) == 566.99
    assert round(df["ci_generated_g_kwh"][0], 2) == 226.80
    assert df["null_reason"][0] is None


def test_hour_start(tmp_path):
    p = _workbook(tmp_path / "a.xlsx", [(datetime(2024, 7, 1, 1), 0.5, 1.25)])
    df = parse_ba_workbook(p, "TEST")
    assert df["ts_utc"][0] == datetime(2024, 7, 1, 0, tzinfo=UTC)
    assert df.schema["ts_utc"] == pl.Datetime("us", "UTC")


def test_negative_is_null(tmp_path):
    p = _workbook(tmp_path / "a.xlsx", [(datetime(2024, 7, 1, 1), 0.5, -5)])
    df = parse_ba_workbook(p, "TEST")
    assert df["ci_consumed_g_kwh"][0] is None
    assert df["null_reason"][0] == "negative"


def test_missing_values_and_missing_rows_are_explicit(tmp_path):
    # hour-ending 02 empty, 03 text, 04 absent from the file, 05 and 06 fine
    p = _workbook(tmp_path / "a.xlsx", [
        (datetime(2024, 7, 1, 1), 0.5, 1.0),
        (datetime(2024, 7, 1, 2), 0.5, None),
        (datetime(2024, 7, 1, 3), 0.5, "n/a"),
        (datetime(2024, 7, 1, 5), 0.5, 1.0),
        (datetime(2024, 7, 1, 6), 0.5, 1.0),
    ])
    df = parse_ba_workbook(p, "TEST")
    assert df.height == 6  # contiguous hourly grid, hour-start 00..05
    assert df["null_reason"].to_list() == [None, "missing", "non_numeric", "missing_row", None, None]
    assert df["ci_consumed_g_kwh"].null_count() == 3


def test_site_mask(tmp_path):
    p = _workbook(tmp_path / "a.xlsx", [
        (datetime(2024, 7, 1, 1), 0.5, 1.0),
        (datetime(2024, 7, 1, 2), 0.5, None),
        (datetime(2024, 7, 1, 3), 0.5, -1.0),
        (datetime(2024, 7, 1, 4), 0.5, 1.0),
    ])
    m = site_mask(parse_ba_workbook(p, "TEST"))
    assert m.columns == ["ba", "ts_utc", "truth_ok"]
    assert m["truth_ok"].to_list() == [True, False, False, True]
    assert m.schema["truth_ok"] == pl.Boolean


def _stored(path: Path) -> Path:
    ts = [datetime(2025, 10, 31, 22, tzinfo=UTC), datetime(2025, 10, 31, 23, tzinfo=UTC),
          datetime(2025, 11, 1, 0, tzinfo=UTC), datetime(2025, 11, 1, 1, tzinfo=UTC)]
    pl.DataFrame({"ba": ["X"] * 4, "ts_utc": ts, "ci_consumed_g_kwh": [1.0] * 4,
                  "ci_generated_g_kwh": [1.0] * 4, "null_reason": [None] * 4}).with_columns(
        pl.col("ts_utc").dt.cast_time_unit("us")).write_parquet(path)
    return path


def test_load_carbon_is_sealed_synthetic(tmp_path):
    df = load_carbon(_stored(tmp_path / "c.parquet"))
    assert df.height == 2
    assert df["ts_utc"].max() < TEST_START


def test_load_carbon_is_sealed():
    if not eia_co2.CARBON_PATH.exists():
        pytest.skip("carbon_hourly.parquet not built")
    assert load_carbon()["ts_utc"].max() < TEST_START


def test_build_carbon_is_atomic_and_leaves_no_temp(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    _workbook(raw / "AAA.xlsx", [(datetime(2024, 7, 1, 1), 0.5, 1.0)])
    monkeypatch.setattr(eia_co2, "WORKBOOK_DIR", raw)
    monkeypatch.setattr(eia_co2, "CARBON_PATH", tmp_path / "out" / "carbon_hourly.parquet")
    out = eia_co2.build_carbon(bas=("AAA",))
    assert out == tmp_path / "out" / "carbon_hourly.parquet"
    assert [p.name for p in out.parent.iterdir()] == ["carbon_hourly.parquet"]
    assert pl.read_parquet(out)["ba"].to_list() == ["AAA"]
