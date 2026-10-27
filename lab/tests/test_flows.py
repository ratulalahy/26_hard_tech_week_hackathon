"""Stage 3 T15 (D-064): the scenario flows and the flexibility budget, both re-read from
already-computed validation ledgers (no new simulation). Synthetic frames only here."""

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from gridpilot import flows
from gridpilot.results import sealed_timestamps, unenveloped_numbers

T0 = datetime(2024, 11, 4, 7, tzinfo=UTC)
H = timedelta(hours=1)


def _acct(rows):
    """job_accounting-shaped rows: (uid, site, start_h, exec_kwh, co2_kg, moved, blocked, gpus)."""
    return pl.DataFrame(
        [{"job_uid": u, "site": s, "booking_site": "PACE", "start_ts": T0 + h * H,
          "execution_kwh": k, "co2_kg": c, "moved": mv, "blocked": b, "gpus": g,
          "remote": s != "PACE"}
         for u, s, h, k, c, mv, b, g in rows])


def _flags(rows):
    return pl.DataFrame([{"job_uid": u, "flexible": f, "mobile": m} for u, f, m in rows])


def _case():
    # U: everything on its booking in Utah.
    u = _acct([("a", "PACE", 0, 100.0, 50.0, False, False, 8),
               ("b", "PACE", 0, 40.0, 20.0, False, False, 8),
               ("c", "PACE", 0, 30.0, 15.0, False, False, 1024),
               ("d", "PACE", 0, 20.0, 10.0, False, False, 8),
               ("e", "PACE", 0, 10.0, 5.0, False, False, 8),
               ("f", "PACE", 0, 5.0, 2.0, False, False, 8)])
    # policy: a ran remote; b waited in Utah (later); c flexible but stayed on its booking
    # (too big for a destination); d is not flexible (and started early: still must-stay);
    # e was capacity-blocked (F14.7); f flexible but immobile.
    p = _acct([("a", "BPAT", 1, 100.0, 10.0, True, False, 8),
               ("b", "PACE", 3, 40.0, 18.0, True, False, 8),
               ("c", "PACE", 0, 30.0, 15.0, False, False, 1024),
               ("d", "PACE", -1, 20.0, 11.0, True, False, 8),
               ("e", "PACE", 0, 10.0, 5.0, False, True, 8),
               ("f", "PACE", 0, 5.0, 2.0, False, False, 8)])
    fl = _flags([("a", True, True), ("b", True, True), ("c", True, True), ("d", False, False),
                 ("e", True, True), ("f", True, False)])
    return u, p, fl


def test_budget_buckets_partition_energy_and_saving():
    u, p, fl = _case()
    b = flows.budget(u, p, fl, dest_slots=512)
    k = b["buckets"]
    assert [x["id"] for x in k] == list(flows.BUCKETS)
    by = {x["id"]: x for x in k}
    assert by["moved_remote"]["mwh"] == pytest.approx(0.100)
    assert by["retimed_home"]["mwh"] == pytest.approx(0.040)
    assert by["stayed_booking"]["mwh"] == pytest.approx(0.030)
    assert by["must_stay"]["mwh"] == pytest.approx(0.025)  # d (not flexible) + f (immobile)
    assert by["capacity_blocked"]["mwh"] == pytest.approx(0.010)
    assert sum(x["mwh"] for x in k) == pytest.approx(b["total_mwh"])
    assert sum(x["share"] for x in k) == pytest.approx(1.0)
    assert by["must_stay"]["n_jobs"] == 2 and by["moved_remote"]["n_jobs"] == 1
    # saving vs U = 40 + 2 + 0 - 1 + 0 + 0 = 41 kg; shares carry the sign
    assert b["saving_kg"] == pytest.approx(41.0)
    assert by["moved_remote"]["saving_share"] == pytest.approx(40 / 41)
    assert by["must_stay"]["saving_share"] == pytest.approx(-1 / 41)
    assert sum(x["saving_share"] for x in k) == pytest.approx(1.0)
    # retiming direction, and the jobs too large for any destination
    assert by["retimed_home"]["n_later"] == 1 and by["retimed_home"]["n_earlier"] == 0
    assert by["stayed_booking"]["larger_than_destination_mwh"] == pytest.approx(0.030)
    assert b["blocked_total_mwh"] == pytest.approx(0.010)


def test_budget_blocked_not_run_without_diagnosis():
    u, p, fl = _case()
    p = p.with_columns(pl.lit(False).alias("blocked"))
    b = flows.budget(u, p, fl, dest_slots=512, diagnosed=False)
    by = {x["id"]: x for x in b["buckets"]}
    assert by["capacity_blocked"]["status"] == "not_run"
    assert by["capacity_blocked"]["mwh"] is None
    # e falls into the bucket its flags and placement give it (stayed on its booking)
    assert by["stayed_booking"]["mwh"] == pytest.approx(0.040)


def test_budget_rejects_mismatched_jobs():
    u, p, fl = _case()
    with pytest.raises(ValueError, match="same jobs"):
        flows.budget(u, p.filter(pl.col("job_uid") != "a"), fl, dest_slots=512)
    with pytest.raises(ValueError, match="flags"):
        flows.budget(u, p, fl.filter(pl.col("job_uid") != "a"), dest_slots=512)


def _ledger(rows):
    """(uid, site, arrival_h, start_h, end_h, gpus, duration_s, moved)."""
    return pl.DataFrame([{"job_uid": u, "site": s, "arrival_ts": T0 + a * H,
                          "start_ts": T0 + st * H, "end_ts": T0 + en * H, "gpus": g,
                          "duration_s": d, "moved": mv}
                         for u, s, a, st, en, g, d, mv in rows])


def test_week_arcs_count_remote_arrivals_in_the_week():
    led = _ledger([("a", "BPAT", 0, 1, 3, 8, 7200.0, True),
                   ("b", "BPAT", 1, 2, 3, 4, 3600.0, True),
                   ("c", "CISO", 200, 201, 202, 8, 3600.0, True),  # outside the week
                   ("d", "PACE", 2, 2, 3, 8, 3600.0, False)])
    arcs = flows.week_arcs(led, T0, T0 + 168 * H)
    by = {a["to"]: a for a in arcs}
    assert [a["to"] for a in arcs] == list(flows.DESTS)
    assert by["BPAT"]["jobs"] == 2 and by["BPAT"]["gpu_h"] == pytest.approx(16 + 4)
    assert by["CISO"]["jobs"] == 0 and by["CISO"]["gpu_h"] == 0.0


def test_execution_split_separates_remote_from_retimed():
    led = _ledger([("a", "BPAT", 0, 1, 3, 10, 7200.0, True),
                   ("b", "PACE", 0, 2, 3, 10, 3600.0, True),
                   ("c", "PACE", 0, 0, 1, 10, 3600.0, False)])
    s = flows.execution_split(led)
    rate = 10 * flows.KW_PER_GPU * flows.PUE
    assert s["remote_kwh"] == pytest.approx(2 * rate)
    assert s["retimed_home_kwh"] == pytest.approx(rate)
    assert s["total_kwh"] == pytest.approx(4 * rate)
    assert s["remote_jobs"] == 1 and s["retimed_home_jobs"] == 1
    assert s["by_site_kwh"]["BPAT"] == pytest.approx(2 * rate)


def _vs_u(saving=0.2):
    e = lambda v, u: {"value": v, "unit": u, "evidence": "simulated", "provenance_id": "x",
                      "status": "ok", "reason": None}
    return {"saving": e(saving, "fraction"), "saving_ci95": e([saving - 0.05, saving + 0.05], "fraction"),
            "diff_kg": e(1000.0, "kg_CO2"), "diff_kg_ci95": e([900.0, 1100.0], "kg_CO2"),
            "n_weeks": {**e(51, "weeks"), "evidence": "measured"}}


def test_flows_artifact_is_enveloped_and_pre_seal():
    led = _ledger([("a", "BPAT", 0, 1, 3, 8, 7200.0, True)])
    pol = flows.policy_flow("r:S", _vs_u(), led, T0, T0 + 168 * H,
                            remote_energy_share=_vs_u()["saving"],
                            moved_share_energy=_vs_u()["saving"],
                            by_site_kwh={"PACE": 0.0, "BPAT": 2 * 8 * 0.72, "CISO": 0.0, "NEVP": 0.0},
                            late_jobs={**_vs_u()["saving"], "value": 0, "unit": "jobs"})
    art = flows.flows_artifact(
        scenarios=[{"id": "registered", "label": "x", "registered": True, "run_id": "r",
                    "run_dir": "runs/slice/r", "knobs": {}, "policies": {"S": pol}}],
        week=(T0, T0 + 168 * H), registered_run_id="r")
    assert unenveloped_numbers(art) == []
    assert sealed_timestamps(art) == []
    s = art["scenarios"][0]["policies"]["S"]
    assert s["remote_execution_mwh"]["BPAT"]["evidence"] == "simulated"
    assert s["saving_vs_U"]["saving"]["value"] == 0.2  # copied, not recomputed
    assert "remote" in art["definitions"]["remote_execution"]
    assert "retim" in art["definitions"]["moved"]


def test_budget_artifact_is_enveloped():
    u, p, fl = _case()
    art = flows.budget_artifact({"S": flows.budget(u, p, fl, dest_slots=512)},
                                run_id="r", registered_run_id="r0", default="S")
    assert unenveloped_numbers(art) == []
    assert sealed_timestamps(art) == []
    b = art["policies"]["S"]["buckets"][0]
    assert b["mwh"]["evidence"] == "simulated"
    assert art["flags_evidence"] == "assumed"
    assert art["default_policy"] == "S"
