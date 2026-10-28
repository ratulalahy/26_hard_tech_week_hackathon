"""Stage 3 T20 (D-071): the pre-registered test-year extras.

The end-to-end synthetic test-window run of every item is in `test_seal_e2e.py` (opt-in,
GRIDPILOT_SEAL_E2E=1). Here: the validation path is unchanged (the registered canonical metrics
hash and the nine ledger hashes), the seal helpers T20 adds change no refusal, and the
pre-registered rules behave as written."""

from __future__ import annotations

import ast
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import polars as pl
import pytest
import sealkit

from gridpilot import seal
from gridpilot import test_extras as tx
from gridpilot.cohort import ledger_hash
from gridpilot.forecast import FEATURES
from gridpilot.paths import REPO_ROOT, RESULTS_DIR
from gridpilot.results import canonical_hash
from gridpilot.splits import TEST_START

LAB = Path(__file__).resolve().parents[1]
# The registered validation run (D-056/T12): its canonical metrics hash and its nine ledgers.
REGISTERED_RUN = "20261027T160656Z"
METRICS_CANONICAL = "e6ad2635699099775e414ddd073b5a7d9a81a57293d2ea3693ec309d9baeae35"
LEDGERS = {
    "U": "f2506967525706f960f90ce3e8bb923e9033e912a1bb88070047fe18bfe608e5",
    "G": "40ee000efc175d93877d4449878317513473f8ca7bfbb304a4b8f6f5b5dac7cd",
    "S": "2ca17acf18a76ef7b3e89df1a2c554ae3501647325c982a32dab0efc9f2c8b1e",
    "K": "2ac04f323a9448ce3b8eda833016ea8cd73a801c1cba1d5c322c3a1d0d3fff74",
    "W": "7d93538589284c7ac9d01bbf6fd5e0303490fac9bef1e7be3c8c7680154ae46a",
    "L": "8bd359c887b6b6770fd937dd59d323c4854325e4ce11bfdddc47c32d4a44cf89",
    "H": "8e327baf8a6d9163f466428c06bf28646d49e41b46d1943b60a34baedcd8deaa",
    "W_time": "5c13bf1c1c0d250321b91a628d6fac40603c1e9a478a59221b1f3e79551df841",
    "L_time": "91421a62a7325f0da60ef7e89df33e6721be4d12dbfc0364251c778afb6debcd",
}


# --------------------------------------------------------------------------- validation path


def test_the_registered_validation_results_are_unchanged():
    """The committed results are the registered run's: canonical metrics hash e6ad2635… and
    the nine ledger hashes (T20 changes no validation code path; the T12 rebuild re-checks it
    from scratch on the final lab/ tree)."""
    m = json.loads((RESULTS_DIR / "metrics.json").read_text())
    man = json.loads((RESULTS_DIR / "manifest.json").read_text())
    assert m["run_id"] == man["run_id"] == REGISTERED_RUN
    assert canonical_hash(m) == METRICS_CANONICAL
    assert man["reproducibility"]["ledger_canonical_sha256"] == LEDGERS
    assert seal.validation_reference(REPO_ROOT)["metrics_canonical_sha256"] == METRICS_CANONICAL


def _registered_dir() -> Path | None:
    for root in (REPO_ROOT, Path(os.environ.get("GRIDPILOT_DATA_DIR", REPO_ROOT / "data")).parent):
        d = root / "runs" / "slice" / REGISTERED_RUN
        if (d / "ledger_U.parquet").exists():
            return d
    return None


def test_the_registered_ledgers_on_disk_hash_as_registered():
    d = _registered_dir()
    if d is None:
        pytest.skip("the registered run directory is not on this machine")
    for p, want in LEDGERS.items():
        assert ledger_hash(pl.read_parquet(d / f"ledger_{p}.parquet")) == want, p


def test_the_validation_reproduction_matches_when_given():
    """GRIDPILOT_T20_REPRO=<run dir of `run_slice.py --no-export`> made by this code: its
    canonical metrics hash and ledgers equal the registered ones."""
    rd = os.environ.get("GRIDPILOT_T20_REPRO")
    if not rd:
        pytest.skip("set GRIDPILOT_T20_REPRO to a reproduction run directory")
    cfg = json.loads((Path(rd) / "config.json").read_text())
    assert cfg["metrics_canonical_sha256"] == METRICS_CANONICAL
    assert cfg["reproducibility"]["ledger_canonical_sha256"] == LEDGERS


# --------------------------------------------------------------------------- seal helpers


def test_outside_test_mode_the_read_bound_is_the_seal_and_scopes_refuse():
    assert seal.active() is None and seal.read_end() == TEST_START
    with pytest.raises(seal.SealError), seal.purpose_scope("D-071 item 1"):
        pass
    from gridpilot.storage import cohort_window, hourly_load_kwh

    led = pl.DataFrame({"site": ["PACE"], "start_ts": [TEST_START], "end_ts": [TEST_START],
                        "gpus": [1]}, schema={"site": pl.Utf8, "start_ts": pl.Datetime("us", "UTC"),
                                              "end_ts": pl.Datetime("us", "UTC"),
                                              "gpus": pl.Int64})
    with pytest.raises(ValueError, match="seal"):
        hourly_load_kwh(led, "PACE", tx._us(TEST_START), 1)
    with pytest.raises(ValueError, match="seal"):
        cohort_window(datetime(2025, 10, 1, tzinfo=UTC), datetime(2025, 11, 2, tzinfo=UTC))


def test_the_test_extension_runner_refuses_outside_test_mode():
    import importlib.util

    spec = importlib.util.spec_from_file_location("run_slice_t20", LAB / "scripts" / "run_slice.py")
    rs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rs)
    from gridpilot.scenario import EXTENSIONS, Window

    with pytest.raises(seal.SealError):
        rs.run_test_extension(Window.validation(), EXTENSIONS["phase_49"], None)
    with pytest.raises(seal.SealError):
        rs.run_test_extras(Window.validation(), None)
    # the CLI still refuses --scenario with --window test (unchanged)
    with pytest.raises(SystemExit):
        rs.main(["--window", "test", "--scenario", "phase_49"])


def test_optional_weather_inputs_are_checked_like_every_recorded_input(tmp_path):
    data = sealkit.make_data_dir(tmp_path)
    rels = sealkit.write_weather_slc(data, datetime(2025, 1, 1, tzinfo=UTC), sealkit.F_SYN)
    assert seal.extra_inputs(data) == tuple(rels)
    rec = {rel: seal.file_sha256(data / rel) for rel in (*seal.TEST_INPUTS, *rels)}
    repo = sealkit.make_repo(tmp_path, data, record_overrides={"input_sha256": rec})
    a = sealkit.authorize(repo, data)
    assert set(a.input_sha256) == set(rec)
    seal._ISSUED.clear()
    (data / rels[0]).write_text((data / rels[0]).read_text().replace("10.0", "10.1", 1) + " ")
    with pytest.raises(seal.SealError, match=r"\(c\)"):
        sealkit.authorize(repo, data)


def test_write_freeze_records_the_optional_inputs_present(tmp_path):
    data = tmp_path / "d"
    assert seal.extra_inputs(data) == ()
    rels = sealkit.write_weather_slc(data, datetime(2025, 1, 1, tzinfo=UTC),
                                     datetime(2026, 2, 1, tzinfo=UTC))
    assert len(rels) == 2 and all(r.startswith(seal.WEATHER_SLC_REL) for r in rels)
    src = (LAB / "scripts" / "write_freeze.py").read_text()
    assert "seal.extra_inputs(data)" in src


def test_every_purpose_scope_names_a_d071_item():
    tree = ast.parse((LAB / "scripts" / "run_slice.py").read_text())
    labels = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "purpose_scope":
            arg = node.args[0]
            text = arg.value if isinstance(arg, ast.Constant) else ast.unparse(arg)
            labels.append(text)
    assert len(labels) >= 6
    assert all("D-071 item" in t for t in labels), labels


# --------------------------------------------------------------------------- the rules


def test_feature_groups_partition_the_l_features():
    cols = [c for g in tx.FEATURE_GROUPS.values() for c in g]
    assert sorted(cols) == sorted(FEATURES) and len(cols) == len(set(cols))
    assert list(tx.FEATURE_GROUPS) == ["calendar", "weekly memory", "most recent",
                                       "recent level", "missing-data flags"]


def test_seasons_follow_the_monday_of_each_week():
    tz = tx.TZ
    assert tx._season(datetime(2025, 12, 1, tzinfo=tz)) == "DJF"
    assert tx._season(datetime(2026, 2, 23, tzinfo=tz)) == "DJF"
    assert tx._season(datetime(2026, 3, 2, tzinfo=tz)) == "MAM"
    assert tx._season(datetime(2026, 8, 31, tzinfo=tz)) == "JJA"
    assert tx._season(datetime(2025, 10, 27, tzinfo=tz)) == "SON"


def test_test_days_lie_wholly_inside_the_window():
    F = datetime(2025, 11, 8, tzinfo=UTC)
    days = tx.test_days(F)
    assert days[0] == date(2025, 11, 1) and days[-1] == date(2025, 11, 6)
    for d in days:
        a, b = tx.local_day(d)
        assert TEST_START <= a and b <= F


def test_the_day_rule_takes_the_top_three_ties_to_the_earlier_date():
    days = [date(2025, 11, d) for d in range(1, 6)]
    ts = [datetime(2025, 11, d, 18, tzinfo=UTC) for d in range(1, 6)]
    net = pl.DataFrame({"ts_utc": ts, "value": [5.0, 9.0, 9.0, 7.0, 1.0]},
                       schema={"ts_utc": pl.Datetime("us", "UTC"), "value": pl.Float64})
    top = tx.select_days(tx.daily_max(net, days))
    assert top["date"].to_list() == [date(2025, 11, 2), date(2025, 11, 3), date(2025, 11, 4)]
    assert top["rank"].to_list() == [1, 2, 3]


def test_a_drift_row_is_never_dropped():
    v = {"a": {"value": 0.2, "unit": "fraction", "evidence": "simulated", "provenance_id": "p",
               "status": "ok", "reason": None}, "l": {"value": [1.0, 2.0], "unit": "MW",
                                                        "evidence": "simulated",
                                                        "provenance_id": "q", "status": "ok",
                                                        "reason": None}}
    t = {"a": {"value": 0.15, "unit": "fraction", "evidence": "simulated", "provenance_id": "p",
               "status": "ok", "reason": None}}
    r = tx.drift_row("x", "m", v, "a", t, "a", "pid")
    assert r["difference"]["value"] == pytest.approx(-0.05)
    r = tx.drift_row("x", "m", v, "l/value/1", None, "a", "pid")
    assert r["validation"]["value"] == 2.0 and r["validation"]["unit"] == "MW"
    assert r["test"]["status"] == "unavailable" and r["difference"]["status"] == "unavailable"


def test_the_drift_table_lists_every_item_even_with_nothing_to_read():
    out = tx.drift_table(val={}, test={}, extension_names=["phase_49", "mobility_le_8gpus"])
    items = {r["item"] for r in out["rows"]}
    assert items == {"headline", "1 extensions", "2 storage", "2b storage schedules",
                     "3 toughest days", "4 water",
                     "5 seasonal", "6 forecast skill", "6 permutation importance"}
    assert all(r["validation"]["status"] == "unavailable" for r in out["rows"])


def test_residual_quantiles_and_coverage():
    t = [datetime(2025, 1, 1, h, tzinfo=UTC) for h in range(10)]
    truth = pl.DataFrame({"ba": ["PACE"] * 10, "ts_utc": t, "value": np.arange(10.0)},
                         schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"),
                                 "value": pl.Float64})
    fc = pl.DataFrame({"ba": ["PACE"] * 10, "target_ts": t, "value": np.zeros(10)},
                      schema={"ba": pl.Utf8, "target_ts": pl.Datetime("us", "UTC"),
                              "value": pl.Float64})
    lo, hi, n = tx.residual_quantiles(fc, truth)
    assert n == 10 and lo == pytest.approx(0.9) and hi == pytest.approx(8.1)
    cov, _ = tx._coverage(fc, truth, lo, hi)
    assert cov == pytest.approx(0.8)


def test_the_committed_validation_counterparts_are_the_registered_runs():
    p = RESULTS_DIR / "extras-validation.json"
    d = json.loads(p.read_text())
    assert d["window"] == "validation" and d["run_id"] == REGISTERED_RUN
    for ba, by in d["forecast_skill"]["series"].items():
        for t, r in by.items():
            assert r["permutation_importance"]["reproduces_frozen_forecasts"], (ba, t)
            assert set(r["models"]) == {"K", "W", "L"}
    fi = d["forecast_skill"]["frozen_intervals"]
    assert set(fi) == {"PACE", "CISO", "BPAT", "NEVP"} and len(fi["PACE"]) == 4
    assert set(d["seasonal"]["seasons"]) == set(tx.SEASONS)


# --------------------------------------------------------------------------- method unchanged


def _validation_as_active(monkeypatch):
    from gridpilot.window import Window

    monkeypatch.setattr(tx, "_active_window", Window.validation)


def _ext_mobility_dir() -> Path | None:
    ext = json.loads((RESULTS_DIR / "extensions.json").read_text())
    rid = ext["sensitivities"]["mobility_le_8gpus"]["run_id"]
    d = _registered_dir()
    if d is None:
        return None
    m = d.parents[1] / "ext" / "mobility_le_8gpus" / rid
    return m if (m / "ledger_W.parquet").exists() else None


def test_item2_on_the_validation_ledgers_reproduces_the_committed_storage(monkeypatch):
    """The test-year storage code, applied to the registered validation run, gives
    results/storage.json's numbers exactly: the D-061/D-067 method is unchanged."""
    from gridpilot import storage as st
    from gridpilot.splits import drop_sealed

    d, mob = _registered_dir(), _ext_mobility_dir()
    if d is None or mob is None:
        pytest.skip("the registered and mobility runs are not on this machine")
    _validation_as_active(monkeypatch)
    cfg = json.loads((d / "config.json").read_text())
    led = {p: pl.read_parquet(d / f"ledger_{p}.parquet") for p in ("U", "S", "W")}
    committed = json.loads((RESULTS_DIR / "storage.json").read_text())
    out = tx.storage_section(ledgers=led, mob_w=pl.read_parquet(mob / "ledger_W.parquet"),
                             filled=drop_sealed(pl.read_parquet(d / "truth_fill.parquet")),
                             eval_start=datetime.fromisoformat(cfg["eval_start"]),
                             net=st.net_load(), committed=committed, pid="t")
    a = committed["cases"]
    for case in ("U", "mobility_le_8gpus_W"):
        for strat in ("A", "B"):
            for e, i in (("4", 3), ("8", 4)):
                got = out["cases"][case][strat][e]
                want = a[case]["strategies"][strat]["0.85"]
                assert got["cut_frac"]["value"] == pytest.approx(want["cut_frac"]["value"][i],
                                                                 rel=1e-12)
                assert got["flat_marginal_cut_t"]["value"] == pytest.approx(
                    want["flat_marginal_cut_t"]["value"][i], rel=1e-12)
    for e, i in (("4", 3), ("8", 4)):
        assert out["combined"]["move_and_store_cut_frac"]["A"][e]["value"] == pytest.approx(
            committed["combined"]["move_and_store_cut_frac"]["A"]["value"][i], rel=1e-12)
    assert out["rush"]["n_hours"]["value"] == committed["rush"]["n_hours"]["value"]
    for p in ("S", "W"):
        assert out["peak_relief"][p]["PACE"]["rush_change_vs_U_mw"]["value"] == pytest.approx(
            committed["peak_relief"]["policies"][p]["PACE"]["rush_change_vs_U_mw"]["value"])


def test_item4_on_the_validation_ledgers_reproduces_the_committed_water(monkeypatch):
    from gridpilot import water as wa
    from gridpilot.storage import cohort_window

    d = _registered_dir()
    if d is None:
        pytest.skip("the registered run is not on this machine")
    _validation_as_active(monkeypatch)
    cfg = json.loads((d / "config.json").read_text())
    led = {p: pl.read_parquet(d / f"ledger_{p}.parquet") for p in tx.WATER_POLICIES}
    win = cohort_window(datetime.fromisoformat(cfg["eval_start"]),
                        max(x["end_ts"].max() for x in led.values()))
    raw = wa.load_balance(win[0] - wa.MARGIN, win[1])  # through drop_sealed
    bal = raw.with_columns(pl.lit(None, pl.Float64).alias("gen_hydro_adj_mw"))
    out = tx.water_section(ledgers=led, balance=bal, win=win, pid="t")
    committed = json.loads((RESULTS_DIR / "water.json").read_text())
    for p in ("S", "W", "L"):
        for k in ("ex_hydro_frac", "with_hydro_frac", "ex_hydro_gal", "with_hydro_gal"):
            assert out["policies"][p]["change_vs_U"][k]["value"] == pytest.approx(
                committed["policies"][p]["change_vs_U"][k]["value"], rel=1e-9), (p, k)
