"""Stage 3 T14 (D-063): the transcribed water factors. Every value is pinned here against the
source PDF as read on 2026-10-27 (NREL/TP-6A20-50900 Tables 1 and 2; LBNL-2001637 pp. 47-48), so a
typo in the transcription, or an edit that drifts from the source, fails."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gridpilot.data import water_factors as wf

REPO = Path(__file__).resolve().parents[2]


# NREL/TP-6A20-50900 (Macknick et al. 2011), median operational water CONSUMPTION, gal/MWh:
# (table, printed page, fuel type, cooling, technology) -> (median, min, max, n)
PINNED = {
    ("Table 2", 13, "Coal", "Tower", "Generic"): (687, 480, 1100, 5),
    ("Table 2", 13, "Natural Gas", "Tower", "Combined Cycle"): (198, 130, 300, 5),
    ("Table 2", 13, "Natural Gas", "Tower", "Steam"): (826, 662, 1170, 4),
    ("Table 2", 13, "Nuclear", "Tower", "Generic"): (672, 581, 845, 6),
    ("Table 1", 12, "Hydropower", "N/A", "Aggregated in-stream and reservoir"): (4491, 1425, 18000, 3),
    ("Table 1", 12, "PV", "N/A", "Utility Scale PV"): (26, 0, 33, 3),
    ("Table 1", 12, "Wind", "N/A", "Wind Turbine"): (0, 0, 1, 2),
    ("Table 1", 12, "Geothermal", "Dry", "Binary"): (135, 0, 270, 2),
}


def test_every_transcribed_nrel_factor_matches_the_pinned_source_values():
    got = {(f.table, f.page, f.fuel_type, f.cooling, f.technology): (f.median, f.min, f.max, f.n)
           for f in wf.NREL_FACTORS.values()}
    assert got == PINNED


def test_every_factor_names_its_table_page_and_units():
    for key, f in wf.NREL_FACTORS.items():
        assert f.unit == "gal/MWh", key
        assert f.metric == "consumption", key
        assert f.table in ("Table 1", "Table 2"), key
        assert f.page == (12 if f.table == "Table 1" else 13), key
        assert f.min <= f.median <= f.max, key


def test_fuel_mapping_covers_every_eia930_fuel_and_hydro_is_the_only_hydro():
    from gridpilot.data.eia930 import TIDY_FUELS

    mapped = set(wf.FUEL_MAP)
    # hydro is split into conventional (evaporation, shown separately) and pumped storage
    want = (set(TIDY_FUELS) - {"hydro"}) | {"hydro_conv", "pumped_storage"}
    assert mapped == want
    for fuel, m in wf.FUEL_MAP.items():
        assert m.role in ("factor", "zero", "mix_average", "hydro"), fuel
        assert m.evidence == "assumed", fuel
        assert len(m.reason) > 20, fuel
        if m.role in ("factor", "hydro"):
            assert m.factor in wf.NREL_FACTORS, fuel
        else:
            assert m.factor is None, fuel
    assert [f for f, m in wf.FUEL_MAP.items() if m.role == "hydro"] == ["hydro_conv"]
    assert wf.FUEL_MAP["coal"].factor == "coal_tower_generic"
    assert wf.FUEL_MAP["gas"].factor == "gas_tower_cc"
    assert wf.FUEL_MAP["nuclear"].factor == "nuclear_tower"
    assert wf.FUEL_MAP["wind"].factor == "wind"


def test_factor_per_fuel_gal_per_mwh():
    g = wf.fuel_factors_gal_mwh()
    assert g["coal"] == 687 and g["gas"] == 198 and g["nuclear"] == 672
    assert g["hydro_conv"] == 4491 and g["solar"] == 26 and g["wind"] == 0
    assert g["battery"] == 0 and g["pumped_storage"] == 0
    assert "other" not in g and "unknown" not in g  # mix-average: left out of the shares


def test_wue_range_is_lbnl_text_and_ordered():
    lo, hi = wf.WUE_L_PER_KWH["low"], wf.WUE_L_PER_KWH["high"]
    assert (lo.value, hi.value) == (0.36, 0.48)
    assert lo.page == 48 and hi.page == 48
    assert "just over 0.36" in lo.quote and "0.45 and 0.48" in hi.quote
    assert wf.LBNL_US_GRID_L_PER_KWH.value == 4.35 and wf.LBNL_US_GRID_L_PER_KWH.page == 57


def test_unit_conversions():
    assert wf.L_PER_GAL == pytest.approx(3.785411784)
    assert wf.GAL_PER_ACRE_FOOT == pytest.approx(325851.43, rel=1e-6)


def test_sources_match_the_committed_manifest():
    man = json.loads((REPO / "data" / "manifests" / "water.json").read_text())
    by_path = {f["path"]: f for f in man["files"]}
    for src in wf.SOURCES.values():
        rec = by_path[src.path]
        assert rec["sha256"] == src.sha256
        assert rec["url"] == src.url
        assert rec["license"] and rec["retrieved_at"]
