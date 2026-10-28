"""Stage 3 T22: the price lens (wholesale scenario, validation only). Hand-checked toy costs, the
coverage rule, the exact level/timing split, the seal on price reads, and the artifact contract."""

from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from gridpilot import price_lens as lens
from gridpilot.results import validate_artifact
from gridpilot.sim import SITES
from gridpilot.sim.power import GPU_KW, PUE, TRANSFER_FRACTION
from gridpilot.splits import TEST_START

T0 = datetime(2025, 3, 3, 7, tzinfo=UTC)  # a Monday, 00:00 America/Denver
RATE = GPU_KW * PUE
REPO = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- fixtures


def _ledger(rows):
    """rows: (job_uid, site, start, end, gpus, arrival)."""
    return pl.DataFrame({
        "job_uid": [r[0] for r in rows], "site": [r[1] for r in rows],
        "start_ts": [r[2] for r in rows], "end_ts": [r[3] for r in rows],
        "gpus": [r[4] for r in rows], "arrival_ts": [r[5] for r in rows],
        "deadline_ts": [r[3] + timedelta(days=2) for r in rows],
        "duration_s": [(r[3] - r[2]).total_seconds() for r in rows],
        "moved": [r[1] != "PACE" for r in rows], "blocked": [False] * len(rows),
        "fit_rejected": [False] * len(rows), "transfer": [r[1] != "PACE" for r in rows],
    }, schema_overrides={"start_ts": pl.Datetime("us", "UTC"), "end_ts": pl.Datetime("us", "UTC"),
                         "arrival_ts": pl.Datetime("us", "UTC"),
                         "deadline_ts": pl.Datetime("us", "UTC"), "gpus": pl.Int64})


def _grid(n):
    return pl.DataFrame({"ts_utc": pl.datetime_range(
        T0, T0 + timedelta(hours=n - 1), "1h", time_unit="us", time_zone="UTC", eager=True)})


def _tables(grid, price, ok=None):
    ok = np.ones(grid.height, dtype=bool) if ok is None else ok
    mean = {s: float(np.mean(price[s][ok])) for s in SITES}
    one = np.ones(grid.height)
    return {"usd": lens.site_table(grid, price),
            "level": lens.site_table(grid, {s: np.where(ok, mean[s], 0.0) for s in SITES}),
            "mwh": lens.site_table(grid, {s: ok.astype(float) for s in SITES}),
            "mwh_all": lens.site_table(grid, {s: one for s in SITES}),
            "co2": lens.site_table(grid, {s: np.where(ok, 400.0, 0.0) for s in SITES}),
            "co2_all": lens.site_table(grid, {s: one * 400.0 for s in SITES})}, mean


def _jobs(led):
    return led.select("job_uid", pl.col("job_uid").alias("source_id"), "arrival_ts", "gpus",
                      "duration_s")


# --------------------------------------------------------------------------- cost accounting


def test_execution_cost_is_the_exact_overlap_of_energy_and_hourly_price():
    grid = _grid(4)
    price = {s: np.array([10.0, 50.0, -5.0, 0.0]) for s in SITES}
    led = _ledger([("a", "PACE", T0 + timedelta(minutes=30), T0 + timedelta(hours=2, minutes=15),
                    8, T0)])
    tables, _ = _tables(grid, price)
    t = lens.policy_totals(led, _jobs(led), tables)
    kw = 8 * RATE
    want = kw * (0.5 * 10 + 1.0 * 50 + 0.25 * -5) / 1000  # kWh × $/MWh / 1000
    assert t["usd"] == pytest.approx(want, rel=1e-12)
    assert t["mwh"] == pytest.approx(kw * 1.75 / 1000, rel=1e-12)


def test_transfer_energy_is_priced_half_home_half_destination_at_arrival():
    grid = _grid(6)
    price = {"PACE": np.full(6, 20.0), "CISO": np.full(6, 60.0), "BPAT": np.zeros(6),
             "NEVP": np.zeros(6)}
    price["PACE"][1] = 100.0  # the arrival hour at home
    arr = T0 + timedelta(hours=1, minutes=10)
    s = arr + timedelta(minutes=30)
    led = _ledger([("a", "CISO", s, s + timedelta(hours=2), 4, arr)])
    tables, _ = _tables(grid, price)
    t = lens.policy_totals(led, _jobs(led), tables)
    exec_usd = 4 * RATE * 2 * 60.0 / 1000
    tr_kwh = TRANSFER_FRACTION * 4 * GPU_KW * 2 * PUE
    tr_usd = 0.5 * tr_kwh * (100.0 + 60.0) / 1000
    assert t["usd_transfer"] == pytest.approx(tr_usd, rel=1e-12)
    assert t["usd"] == pytest.approx(exec_usd + tr_usd, rel=1e-12)
    assert t["site"]["usd"]["CISO"] == pytest.approx(exec_usd, rel=1e-12)


# --------------------------------------------------------------------------- coverage


def _intervals(rows):
    return pl.DataFrame({"ts_utc": [r[0] for r in rows], "node": [r[1] for r in rows],
                         "lmp": [r[2] for r in rows]},
                        schema_overrides={"ts_utc": pl.Datetime("us", "UTC")})


def test_an_hour_missing_one_interval_at_any_site_is_excluded_for_every_site():
    grid = _grid(2)
    rows = []
    for site, node in lens.NODES.items():
        for h in range(2):
            for q in range(4):
                if site == "BPAT" and h == 1 and q == 3:
                    continue  # BPAT's second hour has 3 of 4 intervals
                rows.append((T0 + timedelta(hours=h, minutes=15 * q), node, 10.0 + q))
    cov = lens.coverage(grid, lens.hourly_prices(_intervals(rows)), lens.NODES)
    assert cov["covered"].tolist() == [True, False]
    assert cov["sites"]["BPAT"] == {"node": lens.NODES["BPAT"], "complete": 1, "partial": 1,
                                    "missing": 0}
    assert cov["sites"]["PACE"]["complete"] == 2
    for s in SITES:  # excluded for every policy: the hour prices at zero everywhere
        assert cov["price"][s].tolist() == [pytest.approx(11.5), 0.0]


def test_unpriced_hours_count_zero_energy_cost_and_co2_for_every_policy():
    grid = _grid(3)
    price = {s: np.array([10.0, 99.0, 30.0]) for s in SITES}
    ok = np.array([True, False, True])
    price = {s: np.where(ok, v, 0.0) for s, v in price.items()}
    led = _ledger([("a", "PACE", T0, T0 + timedelta(hours=3), 1, T0)])
    tables, _ = _tables(grid, price, ok)
    t = lens.policy_totals(led, _jobs(led), tables)
    assert t["usd"] == pytest.approx(RATE * 40 / 1000)
    assert t["mwh"] == pytest.approx(RATE * 2 / 1000)
    assert t["mwh_all"] == pytest.approx(RATE * 3 / 1000)
    assert t["co2"] == pytest.approx(RATE * 2 * 400 / 1000)


# --------------------------------------------------------------------------- decomposition


def test_level_timing_split_is_exact_and_waiting_has_no_level_effect():
    grid = _grid(8)
    rng = np.random.default_rng(5)
    price = {s: rng.uniform(-10, 90, 8) for s in SITES}
    tables, mean = _tables(grid, price)
    u = _ledger([("a", "PACE", T0, T0 + timedelta(hours=2), 8, T0),
                 ("b", "PACE", T0 + timedelta(hours=1), T0 + timedelta(hours=4), 4,
                  T0 + timedelta(hours=1))])
    wait = _ledger([("a", "PACE", T0 + timedelta(hours=3), T0 + timedelta(hours=5), 8, T0),
                    ("b", "PACE", T0 + timedelta(hours=1), T0 + timedelta(hours=4), 4,
                     T0 + timedelta(hours=1))])
    move = _ledger([("a", "BPAT", T0 + timedelta(minutes=30),
                     T0 + timedelta(hours=2, minutes=30), 8, T0),
                    ("b", "PACE", T0 + timedelta(hours=1), T0 + timedelta(hours=4), 4,
                     T0 + timedelta(hours=1))])
    jobs = _jobs(u)
    tu = lens.policy_totals(u, jobs, tables)
    for led in (wait, move):
        tp = lens.policy_totals(led, jobs, tables)
        d = lens.decompose(tp, tu, mean)
        assert d["delta_usd"] == pytest.approx(tp["usd"] - tu["usd"], abs=1e-12)
        assert d["level_usd"] + d["timing_usd"] == pytest.approx(d["delta_usd"], abs=1e-12)
        assert d["extra_energy_usd"] + d["location_usd"] == pytest.approx(d["level_usd"],
                                                                          abs=1e-12)
    dw = lens.decompose(lens.policy_totals(wait, jobs, tables), tu, mean)
    assert dw["level_usd"] == pytest.approx(0.0, abs=1e-12)
    assert dw["extra_energy_usd"] == pytest.approx(0.0, abs=1e-12)


def test_ratio_interval_is_null_when_a_replicate_cuts_no_co2():
    u_w, p_w = np.array([10.0, 10.0, 10.0]), np.array([12.0, 12.0, 12.0])
    u_c, p_c = np.array([1000.0, 1000.0, 1000.0]), np.array([1000.0, 900.0, 1000.0])
    ci, why = lens.ratio_interval(u_w, p_w, u_c, p_c, block=1)
    assert ci is None and "no attributed" in why
    ci, why = lens.ratio_interval(u_w, p_w, u_c, u_c - 500.0, block=1)
    assert why is None and ci == pytest.approx([2 / 0.5, 2 / 0.5])


# --------------------------------------------------------------------------- the seal


def _oasis_zip(path: Path, rows):
    buf = io.StringIO()
    buf.write("INTERVALSTARTTIME_GMT,NODE,LMP_TYPE,PRC\n")
    for t, node, typ, v in rows:
        buf.write(f"{t.strftime('%Y-%m-%dT%H:%M:%S')}-00:00,{node},{typ},{v}\n")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("x.csv", buf.getvalue())


def _price_dir(tmp_path, files):
    """files: (name, start, end, rows). Writes the zips and a manifest; returns data_dir."""
    d = tmp_path / "data"
    entries = []
    for name, s, e, rows in files:
        rel = f"raw/prices/caiso/rtpd/core/{name}"
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        _oasis_zip(p, rows)
        entries.append({"path": rel, "status": "ok", "sha256": hashlib.sha256(
            p.read_bytes()).hexdigest(), "start_utc": s.isoformat(), "end_utc": e.isoformat()})
    (d / "manifests").mkdir(parents=True)
    (d / lens.MANIFEST).write_text(json.dumps({"files": entries}))
    return d


def test_price_reads_skip_sealed_files_and_drop_sealed_rows(tmp_path):
    node = lens.NODES["PACE"]
    edge = TEST_START - timedelta(hours=1)
    straddle = [(edge + timedelta(minutes=15 * q), node, "LMP", 5.0) for q in range(8)]
    sealed = [(TEST_START + timedelta(days=2), node, "LMP", 999.0)]
    d = _price_dir(tmp_path, [
        ("a.zip", TEST_START - timedelta(days=5), TEST_START + timedelta(days=25), straddle),
        ("b.zip", TEST_START + timedelta(days=1), TEST_START + timedelta(days=30), sealed)])
    win = (edge - timedelta(hours=1), TEST_START)
    assert [f["path"].rsplit("/", 1)[1] for f in lens.price_files(win, d)] == ["a.zip"]
    iv, files = lens.load_rt_intervals([node], win, d)
    assert iv["ts_utc"].max() < TEST_START
    assert iv.height == 4 and (iv["lmp"] == 5.0).all()
    assert [f["path"].rsplit("/", 1)[1] for f in files] == ["a.zip"]


def test_price_reads_refuse_a_window_past_the_seal_and_a_changed_file(tmp_path):
    node = lens.NODES["PACE"]
    d = _price_dir(tmp_path, [("a.zip", T0, T0 + timedelta(days=1),
                               [(T0, node, "LMP", 1.0)])])
    with pytest.raises(ValueError, match="seal"):
        lens.load_rt_intervals([node], (T0, TEST_START + timedelta(hours=1)), d)
    (d / "raw/prices/caiso/rtpd/core/a.zip").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="sha256"):
        lens.load_rt_intervals([node], (T0, T0 + timedelta(days=1)), d)


# --------------------------------------------------------------------------- end to end


def _run_dir(tmp_path, data_dir):
    run = tmp_path / "runs" / "slice" / "20250101T000000Z"
    run.mkdir(parents=True)
    a_end = T0 + timedelta(days=13)
    (run / "config.json").write_text(json.dumps({
        "window": "validation", "eval_start": T0.isoformat(), "A": a_end.isoformat()}))
    jobs_u, jobs_w = [], []
    for k in range(12):
        arr = T0 + timedelta(days=k, hours=3)
        jobs_u.append((f"j{k}#0", "PACE", arr, arr + timedelta(hours=5), 8, arr))
        if k % 2:
            s = arr + timedelta(minutes=30)
            jobs_w.append((f"j{k}#0", "BPAT", s, s + timedelta(hours=5), 8, arr))
        else:
            s = arr + timedelta(hours=6)
            jobs_w.append((f"j{k}#0", "PACE", s, s + timedelta(hours=5), 8, arr))
    u, w = _ledger(jobs_u), _ledger(jobs_w)
    for p in lens.POLICIES:
        (w if p in ("S", "W", "L") else u).write_parquet(run / f"ledger_{p}.parquet")
    hours = pl.datetime_range(T0, T0 + timedelta(days=15), "1h", time_unit="us",
                              time_zone="UTC", eager=True, closed="left")
    truth = pl.concat([pl.DataFrame({"ba": [s] * len(hours), "ts_utc": hours,
                                     "ci_g_kwh": [700.0 if s == "PACE" else 100.0] * len(hours),
                                     "tier": [1] * len(hours)}) for s in SITES])
    truth.write_parquet(run / "truth_fill.parquet")
    rows = []
    for i, t in enumerate(pl.datetime_range(T0, T0 + timedelta(days=15), "15m",
                                            time_unit="us", time_zone="UTC", eager=True,
                                            closed="left")):
        for s, node in [*lens.NODES.items(), ("CISO", lens.CISO_SENS_NODE)]:
            rows.append((t, node, "LMP", 20.0 + (i % 96) / 4 if s == "PACE" else 45.0))
    d = _price_dir(tmp_path, [("a.zip", T0, T0 + timedelta(days=15), rows)])
    return run, d


def test_end_to_end_artifact_is_enveloped_and_honest(tmp_path):
    run, d = _run_dir(tmp_path, None)
    main = lens.compute(run, None, data_dir=d)
    sens = lens.compute(run, None, data_dir=d, with_bootstrap=False,
                        nodes={**lens.NODES, "CISO": lens.CISO_SENS_NODE})
    art = lens.build_artifact(main, sens)
    assert validate_artifact(art) == []
    assert art["scenario"] == lens.SCENARIO and "retail" in art["caveat"]
    w = art["policies"]["W"]
    assert w["scenario"] == lens.SCENARIO
    # moving half the jobs to a dearer site costs more: the sign is reported as it is
    assert w["delta_vs_U_usd"]["value"] > 0
    assert w["attributed_co2_cut_vs_U_t"]["value"] > 0
    per_t = w["delta_vs_U_usd"]["value"] / w["attributed_co2_cut_vs_U_t"]["value"]
    assert w["cost_per_attributed_tonne_usd_t"]["value"] == pytest.approx(per_t)
    dec = {k: v["value"] for k, v in w["decomposition_vs_U_usd"].items()}
    assert dec["level_usd"] + dec["timing_usd"] == pytest.approx(w["delta_vs_U_usd"]["value"])
    # U has no CO₂ cut against itself: the ratio is null with a reason
    pu = art["policies"]["U"]["cost_per_attributed_tonne_usd_t"]
    assert pu["value"] is None and pu["reason"]
    assert set(art["policies"]["W"]["interval"]["blocks"]) == {"2", "4", "8"}
    assert art["coverage"]["priced_share"]["value"] == 1.0
    assert math.isclose(art["policies"]["U"]["excluded_energy_share"]["value"], 0.0,
                        abs_tol=1e-12)


def test_wording_never_claims_abatement_or_avoided():
    text = Path(lens.__file__).read_text() + (REPO / "lab/scripts/export_prices.py").read_text()
    out = REPO / "results" / "prices.json"
    if out.exists():
        text += out.read_text()
        art = json.loads(out.read_text())
        assert "retail" in art["caveat"]
        assert all(p["scenario"] == lens.SCENARIO for p in art["policies"].values())
    low = text.lower()
    assert "avoided" not in low
    assert "abatement cost" not in low.replace("not a marginal abatement cost", "")
