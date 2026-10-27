from datetime import UTC, datetime

import polars as pl
import pytest

from gridpilot.data.eia930 import (
    PARTITION_FUELS,
    TIDY_FUELS,
    column_name,
    file_name,
    normalize_header,
    parse_balance_csv,
)
from gridpilot.splits import TEST_START, drop_sealed

OLD_FUELS = ["Coal", "Natural Gas", "Nuclear", "All Petroleum Products",
             "Hydropower and Pumped Storage", "Solar", "Wind", "Other Fuel Sources",
             "Unknown Fuel Sources"]
NEW_FUELS = ["Coal", "Natural Gas", "Nuclear", "All Petroleum Products",
             "Hydropower Excluding Pumped Storage", "Pumped Storage",
             "Solar without Integrated Battery Storage", "Solar with Integrated Battery Storage",
             "Wind without Integrated Battery Storage", "Wind with Integrated Battery Storage",
             "Battery Storage", "Other Energy Storage", "Unknown Energy Storage", "Geothermal",
             "Other Fuel Sources", "Unknown Fuel Sources"]
TOTALS = ["Demand (MW)", "Net Generation (MW)", "Total Interchange (MW)"]


def _header(fuels: list[str], typos: bool = False) -> list[str]:
    cols = ["Balancing Authority", "Data Date", "Hour Number", "Local Time at End of Hour",
            "UTC Time at End of Hour", "Demand Forecast (MW)", *TOTALS, "Sum(Valid DIBAs) (MW)"]
    cols += [f"{t} (Imputed)" for t in TOTALS] + [f"{t} (Adjusted)" for t in TOTALS]
    gen = [f"Net Generation (MW) from {f}" for f in fuels]
    adj = [f"{g} (Adjusted)" for g in gen]
    if typos:  # exactly as in EIA's 2024 Jul_Dec+ files
        adj = [a.replace("Pumped Storage (Adjusted)", "Pumped Storage  (Adjusted)")
               .replace("Solar with Integrated", "Solar witho Integrated") for a in adj]
    return cols + gen + [f"{g} (Imputed)" for g in gen] + adj + ["Region"]


def _write(path, header, rows):
    lines = [",".join(f'"{h}"' for h in header)]
    lines += [",".join(r) for r in rows]
    path.write_text("\n".join(lines) + "\n")


def _row(header, values: dict[str, str]) -> list[str]:
    return [values.get(h, "") for h in header]


def test_file_names():
    assert file_name("BALANCE", 2019, "Jan_Jun") == "EIA930_BALANCE_2019_Jan_Jun.csv"
    with pytest.raises(ValueError):
        file_name("BALANCE", 2019, "H1")


def test_header_typos_are_normalized():
    assert normalize_header("Net Generation (MW) from Pumped Storage  (Adjusted)") == (
        "Net Generation (MW) from Pumped Storage (Adjusted)")
    assert column_name("Net Generation (MW) from Solar witho Integrated Battery Storage (Adjusted)") \
        == "fuel__solar_batt__adj"
    with pytest.raises(ValueError):
        column_name("Net Generation (MW) from Unobtainium")


def test_old_taxonomy_timestamps_and_adjusted(tmp_path):
    header = _header(OLD_FUELS)
    base = {"Balancing Authority": "PACE", "Region": "NW", "Data Date": "01/01/2019"}
    rows = [
        # Hour ending 1 AM MST = 08:00 UTC -> hour-beginning ts_utc 07:00 UTC; offset -7.
        _row(header, {**base, "Hour Number": "1", "Local Time at End of Hour": "01/01/2019 1:00:00 AM",
                      "UTC Time at End of Hour": "01/01/2019 8:00:00 AM",
                      "Demand Forecast (MW)": "\"5,100\"", "Demand (MW)": "5000",
                      "Demand (MW) (Adjusted)": "5000", "Net Generation (MW)": "6000",
                      "Net Generation (MW) (Adjusted)": "6000",
                      "Net Generation (MW) from Coal": "3000",
                      "Net Generation (MW) from Coal (Adjusted)": "3000",
                      "Net Generation (MW) from Solar": "0",
                      "Net Generation (MW) from Solar (Adjusted)": "0"}),
        # Missing raw demand that EIA imputed.
        _row(header, {**base, "Hour Number": "2", "Local Time at End of Hour": "01/01/2019 2:00:00 AM",
                      "UTC Time at End of Hour": "01/01/2019 9:00:00 AM",
                      "Demand (MW) (Imputed)": "4900", "Demand (MW) (Adjusted)": "4900"}),
    ]
    p = tmp_path / "EIA930_BALANCE_2019_Jan_Jun.csv"
    _write(p, header, rows)
    df = parse_balance_csv(p)
    assert df.height == 2
    assert df["ts_utc"].to_list() == [datetime(2019, 1, 1, 7, tzinfo=UTC),
                                      datetime(2019, 1, 1, 8, tzinfo=UTC)]
    assert df["utc_offset_h"].to_list() == [-7, -7]
    assert df["demand_forecast_mw"][0] == 5100  # thousands separator stripped
    assert df["demand_mw"].to_list() == [5000, None]
    assert df["demand_adj_mw"].to_list() == [5000, 4900]
    assert df["demand_imputed"].to_list() == [False, True]
    assert df["gen_coal_mw"][0] == 3000 and df["gen_solar_mw"][0] == 0
    assert df["gen_battery_mw"].is_null().all()  # not in the old taxonomy
    assert df["source_file"][0] == "2019_Jan_Jun"
    assert {f"gen_{f}_mw" for f in TIDY_FUELS} <= set(df.columns)


def test_new_taxonomy_harmonizes_hydro_solar_wind(tmp_path):
    header = _header(NEW_FUELS, typos=True)
    v = {"Balancing Authority": "CISO", "Region": "CAL", "Data Date": "07/01/2024", "Hour Number": "13",
         "Local Time at End of Hour": "07/01/2024 1:00:00 PM",
         "UTC Time at End of Hour": "07/01/2024 8:00:00 PM",
         "Net Generation (MW) from Hydropower Excluding Pumped Storage": "2000",
         "Net Generation (MW) from Pumped Storage": "-300",
         "Net Generation (MW) from Solar without Integrated Battery Storage": "15000",
         "Net Generation (MW) from Solar with Integrated Battery Storage": "500",
         "Net Generation (MW) from Wind without Integrated Battery Storage": "1000",
         "Net Generation (MW) from Battery Storage": "-4000",
         "Net Generation (MW) from Solar witho Integrated Battery Storage (Adjusted)": "600",
         "Net Generation (MW) from Solar without Integrated Battery Storage (Adjusted)": "15000",
         "Net Generation (MW) from Pumped Storage  (Adjusted)": "-300"}
    p = tmp_path / "EIA930_BALANCE_2024_Jul_Dec.csv"
    _write(p, header, [_row(header, v)])
    r = parse_balance_csv(p).row(0, named=True)
    assert r["ts_utc"] == datetime(2024, 7, 1, 19, tzinfo=UTC)
    assert r["utc_offset_h"] == -7  # PDT
    assert r["gen_hydro_mw"] == 1700  # WAT + PS keeps the old combined meaning
    assert r["gen_solar_mw"] == 15500 and r["gen_solar_batt_mw"] == 500
    assert r["gen_wind_mw"] == 1000  # WNB missing counts as absent, not as null total
    assert r["gen_battery_mw"] == -4000
    assert r["gen_solar_adj_mw"] == 15600 and r["gen_solar_batt_adj_mw"] == 600  # typo header
    assert r["gen_pumped_storage_adj_mw"] == -300  # double-space header
    assert r["gen_coal_mw"] is None and r["gen_geothermal_mw"] is None
    assert len(PARTITION_FUELS) == 13 and "solar_batt" not in PARTITION_FUELS


def test_hour_beginning_timestamps_respect_the_seal(tmp_path):
    header = _header(OLD_FUELS)
    base = {"Balancing Authority": "PACE", "Region": "NW", "Demand (MW)": "1"}
    rows = [_row(header, {**base, "UTC Time at End of Hour": t, "Local Time at End of Hour": t})
            for t in ("11/01/2025 12:00:00 AM", "11/01/2025 1:00:00 AM")]
    p = tmp_path / "x.csv"
    _write(p, header, rows)
    df = parse_balance_csv(p)
    # The hour ending 00:00Z on Nov 1 is Oct 31 23:00-24:00Z: before the test window.
    kept = drop_sealed(df)
    assert kept["ts_utc"].to_list() == [datetime(2025, 10, 31, 23, tzinfo=UTC)]
    assert df.filter(pl.col("ts_utc") >= TEST_START).height == 1
