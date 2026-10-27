"""Carbon truth table: EIA consumption-based CO2 intensity (lb/kWh in the workbook -> g/kWh)."""

import hashlib
import json
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
    assert df.columns == ["ba", "ts_utc", "ci_consumed_g_kwh", "ci_generated_g_kwh", "null_reason",
                          "null_reason_generated"]
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
                  "ci_generated_g_kwh": [1.0] * 4, "null_reason": [None] * 4,
                  "null_reason_generated": [None] * 4}).with_columns(
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


def test_built_parquet_on_disk_has_no_sealed_row():
    if not eia_co2.CARBON_PATH.exists():
        pytest.skip("carbon_hourly.parquet not built")
    assert pl.read_parquet(eia_co2.CARBON_PATH)["ts_utc"].max() < TEST_START


@pytest.fixture
def out_paths(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    monkeypatch.setattr(eia_co2, "WORKBOOK_DIR", raw)
    monkeypatch.setattr(eia_co2, "CARBON_PATH", tmp_path / "out" / "carbon_hourly.parquet")
    return raw, tmp_path / "out"


def test_build_carbon_truncates_at_seal_and_writes_lineage(out_paths):
    raw, out_dir = out_paths
    # workbook hours-ending 2025-10-31 23:00, 2025-11-01 00:00 (= hour 2025-10-31 23Z), 01:00, 02:00
    _workbook(raw / "AAA.xlsx", [(datetime(2025, 10, 31, 23), 0.5, 1.0),
                                 (datetime(2025, 11, 1, 0), 0.5, 1.0),
                                 (datetime(2025, 11, 1, 1), 0.5, 1.0),
                                 (datetime(2025, 11, 1, 2), 0.5, 1.0)])
    out = eia_co2.build_carbon(bas=("AAA",))
    df = pl.read_parquet(out)  # directly, not via load_carbon
    assert df["ts_utc"].max() < TEST_START
    assert df["ts_utc"].to_list() == [datetime(2025, 10, 31, 22, tzinfo=UTC),
                                      datetime(2025, 10, 31, 23, tzinfo=UTC)]
    meta = json.loads((out_dir / "carbon_hourly.meta.json").read_text())
    assert meta["evidence"] == "observed"
    assert meta["unit"] == "lb/kWh" and meta["g_per_lb_factor"] == 453.592
    assert meta["cutoff_test_start"].startswith("2025-11-01T00:00:00")
    assert meta["source_workbooks_sha256"]["AAA.xlsx"] == hashlib.sha256(
        (raw / "AAA.xlsx").read_bytes()).hexdigest()
    assert meta["output_sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    assert "UTC end" in meta["time_shift"] and meta["built_at"]
    assert sorted(p.name for p in out_dir.iterdir()) == ["carbon_hourly.meta.json",
                                                         "carbon_hourly.parquet"]


@pytest.mark.parametrize("failing", ["write_parquet", "replace"])
def test_build_carbon_failure_keeps_old_file_and_leaves_no_temp(out_paths, monkeypatch, failing):
    raw, out_dir = out_paths
    _workbook(raw / "AAA.xlsx", [(datetime(2024, 7, 1, 1), 0.5, 1.0)])
    out_dir.mkdir()
    old = out_dir / "carbon_hourly.parquet"
    old.write_bytes(b"previous good file")
    before = old.read_bytes()

    def boom(*a, **k):
        raise OSError("disk full")

    if failing == "replace":
        monkeypatch.setattr(eia_co2.os, "replace", boom)
    else:
        monkeypatch.setattr(pl.DataFrame, "write_parquet", boom)
    with pytest.raises(OSError):
        eia_co2.build_carbon(bas=("AAA",))
    assert old.read_bytes() == before
    assert [p.name for p in out_dir.iterdir()] == ["carbon_hourly.parquet"]


def test_build_two_bas_sorted_by_ba_then_time(out_paths):
    raw, _ = out_paths
    _workbook(raw / "BBB.xlsx", [(datetime(2024, 7, 1, 1), 0.5, 1.0), (datetime(2024, 7, 1, 2), 0.5, 1.0)])
    _workbook(raw / "AAA.xlsx", [(datetime(2024, 7, 1, 1), 0.5, 1.0)])
    df = pl.read_parquet(eia_co2.build_carbon(bas=("BBB", "AAA")))
    assert df.select("ba", "ts_utc").rows() == sorted(df.select("ba", "ts_utc").rows())
    assert df["ba"].to_list() == ["AAA", "BBB", "BBB"]


def test_generated_basis_has_its_own_reason(tmp_path):
    p = _workbook(tmp_path / "a.xlsx", [(datetime(2024, 7, 1, 1), -0.5, 1.0),
                                        (datetime(2024, 7, 1, 2), 0.5, 1.0)])
    df = parse_ba_workbook(p, "TEST")
    assert df["ci_generated_g_kwh"][0] is None
    assert df["null_reason_generated"].to_list() == ["negative", None]
    assert df["null_reason"].to_list() == [None, None]
    assert df["ci_consumed_g_kwh"].null_count() == 0


def test_zero_is_a_valid_value(tmp_path):
    p = _workbook(tmp_path / "a.xlsx", [(datetime(2024, 7, 1, 1), 0, 0)])
    df = parse_ba_workbook(p, "TEST")
    assert df["ci_consumed_g_kwh"][0] == 0.0
    assert df["null_reason"][0] is None
    assert site_mask(df)["truth_ok"].to_list() == [True]


@pytest.mark.parametrize("text", ["nan", "inf", "-inf"])
def test_nan_and_inf_are_non_numeric(tmp_path, text):
    p = _workbook(tmp_path / "a.xlsx", [(datetime(2024, 7, 1, 1), text, text)])
    df = parse_ba_workbook(p, "TEST")
    assert df["ci_consumed_g_kwh"][0] is None
    assert df["null_reason"][0] == "non_numeric"
    assert df["null_reason_generated"][0] == "non_numeric"


def test_duplicate_hour_raises(tmp_path):
    p = _workbook(tmp_path / "a.xlsx", [(datetime(2024, 7, 1, 1), 0.5, 1.0),
                                        (datetime(2024, 7, 1, 1), 0.5, 2.0)])
    with pytest.raises(ValueError, match="duplicate"):
        parse_ba_workbook(p, "TEST")


def test_null_or_unparseable_time_raises(tmp_path):
    p = _workbook(tmp_path / "a.xlsx", [(datetime(2024, 7, 1, 1), 0.5, 1.0), (None, 0.5, 1.0)])
    with pytest.raises(ValueError, match="UTC time"):
        parse_ba_workbook(p, "TEST")
    q = _workbook(tmp_path / "b.xlsx", [(datetime(2024, 7, 1, 1), 0.5, 1.0), ("not a time", 0.5, 1.0)])
    with pytest.raises(ValueError, match="UTC time"):
        parse_ba_workbook(q, "TEST")


def _carbon(rows: list[tuple]) -> pl.DataFrame:
    return pl.DataFrame(
        {"ba": [r[0] for r in rows], "ts_utc": [r[1] for r in rows],
         "ci_consumed_g_kwh": [r[2] for r in rows]},
        schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"), "ci_consumed_g_kwh": pl.Float64},
    )


def test_site_mask_is_closed_outside_stored_range_and_for_unknown_ba():
    h = lambda n: datetime(2024, 7, 1, n, tzinfo=UTC)
    c = _carbon([("A", h(0), 1.0), ("A", h(1), 2.0), ("B", h(1), 3.0)])
    m = site_mask(c, start=h(0), end=h(4), bas=("A", "B", "C"))
    got = {(r["ba"], r["ts_utc"].hour): r["truth_ok"] for r in m.to_dicts()}
    assert len(m) == 3 * 4 and m.columns == ["ba", "ts_utc", "truth_ok"]
    assert got[("A", 0)] and got[("A", 1)] and not got[("A", 2)] and not got[("A", 3)]
    assert not got[("B", 0)] and got[("B", 1)]  # B has no row at hour 0
    assert not any(got[("C", n)] for n in range(4))  # C has no rows at all


def test_site_mask_defaults_come_from_data_range():
    h = lambda n: datetime(2024, 7, 1, n, tzinfo=UTC)
    c = _carbon([("A", h(0), 1.0), ("B", h(2), 1.0)])
    m = site_mask(c)
    assert len(m) == 2 * 3
    assert m.filter(pl.col("truth_ok")).select("ba", "ts_utc").rows() == [("A", h(0)), ("B", h(2))]


def test_site_mask_refuses_sealed_window():
    c = _carbon([("A", datetime(2025, 10, 31, 23, tzinfo=UTC), 1.0)])
    with pytest.raises(ValueError, match="TEST_START"):
        site_mask(c, end=datetime(2025, 11, 1, 1, tzinfo=UTC))
