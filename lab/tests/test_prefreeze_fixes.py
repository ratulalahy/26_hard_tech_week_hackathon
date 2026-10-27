"""Stage 3 T9: pre-freeze copy, label and export fixes. None of them may move a number."""

import importlib.util
import json
from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from gridpilot import workload_profile as wp
from gridpilot.data import eia_co2
from gridpilot.paths import REPO_ROOT, RESULTS_DIR
from gridpilot.results import LIMIT_VALIDATION_DEV, check_claim_frame
from gridpilot.sim import carbon_search, power

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_slice.py"
WEB_RESULTS = REPO_ROOT / "web" / "public" / "data" / "results"


@pytest.fixture(scope="module")
def rs():
    spec = importlib.util.spec_from_file_location("run_slice", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _acct(k_vs_s, w_vs_s, l_vs_s):
    def c(d, lo, hi, sav=0.0):
        return {4: {"diff_kg": d, "diff_kg_ci": (lo, hi), "saving": sav}}

    sites = {"PACE": 10.0, "BPAT": 70.0, "CISO": 20.0, "NEVP": 10.0}
    return {"contrasts": {"K_vs_S": c(*k_vs_s), "W_vs_S": c(*w_vs_s), "L_vs_S": c(*l_vs_s),
                          "W_time_vs_U": c(1, 0, 2, 0.0072), "L_time_vs_U": c(1, 0, 2, 0.0075),
                          "L_vs_U": c(1, 0, 2, 0.2251)},
            "scores": {"L": {"execution_kwh_by_site": sites}}}


# --------------------------------------------------------------------------- C4, A11


def test_framing_states_the_worse_policy_as_candidate_minus_s(rs):
    """C4: "K − S = +10.0 t", never "S − K = -10.0 t"; the interval flips with the sign."""
    txt = rs.framing_text(_acct((-10007, -19330, -1522), (-4940, -14832, 3642),
                                (-5104, -15294, 4152)))
    assert "K − S = +10.0 t, b = 4 95% interval [+1.5 t, +19.3 t]" in txt
    assert "W − S = +4.9 t [-3.6 t, +14.8 t]" in txt
    assert "S − K" not in txt and "S − W" not in txt and "= -10.0" not in txt


def test_headline_wording_names_the_modeled_basis(rs):
    txt = rs.headline_wording({"transfer_kwh": 126_800.0})
    assert txt.startswith("attributed operational CO₂ (EIA consumption basis, modeled), "
                          "including 126.8 MWh of simulated transfer energy;")


# --------------------------------------------------------------------------- A9


def test_top_n_is_ceil_not_round():
    jobs = pl.DataFrame({"job_uid": [f"j{i:03d}" for i in range(250)], "gpu_h": [1.0] * 250})
    t = wp.top_share(jobs, 0.01)  # 2.5 -> 3 (round() gives 2)
    assert t["n_jobs"] == 3 and t["top"].height == 3
    assert t["share"] == pytest.approx(3 / 250)
    assert t["top"]["job_uid"].to_list() == ["j000", "j001", "j002"]  # ties to job_uid


def test_run_slice_and_workload_profile_share_one_top_share(rs):
    n = 917_901  # 0.01 n = 9,179.01: ceil gives 9,180, round gives 9,179
    cj = pl.DataFrame({"job_uid": [f"j{i:07d}" for i in range(n)], "gpus": [1] * n,
                       "duration_s": [3600.0] * n})
    got = rs.top_share(cj)
    ref = wp.top_share(cj.select("job_uid", (pl.col("gpus") * pl.col("duration_s") / 3600)
                                 .alias("gpu_h")))
    assert got["n_jobs"] == ref["n_jobs"] == 9180
    assert got["share"] == pytest.approx(ref["share"])
    # the concentration table counts the same way
    acct = pl.DataFrame({"job_uid": cj["job_uid"], "requested_gpu_s": [3600.0] * n,
                         "energy_kwh": [1.0] * n, "co2_kg": [1.0] * n})
    top = wp.concentration(acct, acct.with_columns(pl.col("co2_kg") * 0.9))["top"]
    assert [t["n_jobs"] for t in top] == [918, 9180, 91_791]


# --------------------------------------------------------------------------- A13, A6


def test_not_run_lists_the_d058_cuts_with_reasons(rs):
    assert rs.NOT_RUN and all(set(x) == {"item", "reason"} for x in rs.NOT_RUN)
    assert {x["reason"] for x in rs.NOT_RUN} == {"cut by owner (D-058)"}


def test_claim_frame_requires_the_development_evidence_limitation():
    from gridpilot.forecast import LIMITATION
    from gridpilot.results import (
        CLAIM_FRAME,
        IMPORT_CONVENTION,
        LIMIT_BOOKINGS_UNSIGNED,
        LIMIT_ZERO_MISSES,
    )

    full = [LIMITATION, IMPORT_CONVENTION, LIMIT_ZERO_MISSES, LIMIT_BOOKINGS_UNSIGNED,
            LIMIT_VALIDATION_DEV]
    check_claim_frame({"claim_frame": CLAIM_FRAME, "limitations": full})
    with pytest.raises(ValueError, match="development"):
        check_claim_frame({"claim_frame": CLAIM_FRAME, "limitations": full[:-1]})
    assert LIMIT_VALIDATION_DEV == (
        "Validation results are development evidence: the validation year was profiled before "
        "the design, and the same period selected the learned model's settings. The sealed "
        "test year is the confirmatory evaluation.")


# --------------------------------------------------------------------------- A8


def test_build_carbon_sidecar_is_modeled_and_the_parquet_unchanged(tmp_path, monkeypatch):
    import openpyxl

    wb_dir = tmp_path / "wb"
    wb_dir.mkdir()
    from datetime import datetime

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = eia_co2.SHEET
    ws.append(["BA", eia_co2.TIME_COL, "Demand", eia_co2.GENERATED_COL, eia_co2.CONSUMED_COL])
    for h in range(1, 6):
        ws.append(["PACE", datetime(2024, 7, 1, h), 100.0, 0.5, 1.0 + h / 10])
    wb.save(wb_dir / "PACE.xlsx")
    out = tmp_path / "carbon" / "carbon_hourly.parquet"
    monkeypatch.setattr(eia_co2, "WORKBOOK_DIR", wb_dir)
    monkeypatch.setattr(eia_co2, "CARBON_PATH", out)
    eia_co2.build_carbon(("PACE",))
    first = pl.read_parquet(out)
    meta = json.loads(out.with_name(eia_co2.META_NAME).read_text())
    assert meta["evidence"] == "modeled"
    eia_co2.build_carbon(("PACE",))  # a rebuild of the sidecar leaves the frame identical
    assert_frame_equal(pl.read_parquet(out), first)
    assert "modeled" in eia_co2.__doc__ and "`observed`" not in eia_co2.__doc__


# --------------------------------------------------------------------------- A14


def test_power_constants_have_one_source():
    from gridpilot.eval import accounting

    assert (power.GPU_KW, power.PUE, power.TRANSFER_FRACTION) == (0.60, 1.20, 0.05)
    assert carbon_search.GPU_KW is power.GPU_KW and carbon_search.PUE is power.PUE
    assert accounting.KW_PER_GPU is power.GPU_KW and accounting.PUE is power.PUE
    assert accounting.TRANSFER_FRACTION is power.TRANSFER_FRACTION
    assert carbon_search.transfer_kwh(8, 3600) == pytest.approx(
        power.TRANSFER_FRACTION * 8 * power.GPU_KW)


def test_power_constants_match_the_committed_manifest():
    a = json.loads((RESULTS_DIR / "manifest.json").read_text())["assumptions"]
    assert a["kw_per_gpu"]["value"] == power.GPU_KW
    assert a["pue"]["value"] == power.PUE
    assert a["transfer_energy_fraction"]["value"] == power.TRANSFER_FRACTION


# --------------------------------------------------------------------------- A7, A13, A16


def test_forecast_replay_has_no_observed_alias():
    fr = json.loads((RESULTS_DIR / "forecast-replay.json").read_text())
    assert "observed" not in fr and "truth" in fr
    assert "observed" not in fr["history_to_first_cutoff"]
    assert "truth" in fr["history_to_first_cutoff"]


def test_committed_manifest_has_not_run_and_no_stale_keys():
    m = json.loads((RESULTS_DIR / "manifest.json").read_text())
    assert "not_before_18" not in m and "task5_status" not in m
    assert m["not_run"] and all(x["item"] and x["reason"] for x in m["not_run"])


def test_web_results_are_byte_identical_to_results():
    """A16: what the dashboard ships is what the lab exported (run `make web` after `make
    slice` or `make profile`)."""
    both = [p.name for p in sorted(RESULTS_DIR.glob("*.json")) if (WEB_RESULTS / p.name).exists()]
    assert both, "no results file is mirrored in web/public/data/results"
    stale = [n for n in both if (RESULTS_DIR / n).read_bytes() != (WEB_RESULTS / n).read_bytes()]
    assert not stale, f"web/public/data/results differs from results/ for {stale}; run `make web`"
