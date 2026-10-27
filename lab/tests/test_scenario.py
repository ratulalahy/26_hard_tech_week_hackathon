"""Stage 3 T10 Part A: the Window and Scenario dataclasses and the scenario knobs (spec §7,
F14.1). Every knob is `assumed`; the primary scenario must reproduce the registered run."""

import dataclasses
import json
from datetime import UTC, datetime

import polars as pl
import pytest

from gridpilot.paths import RESULTS_DIR
from gridpilot.scenario import EXTENSIONS, Scenario, Window
from gridpilot.sim import HOME, SITES, TRANSFER_S
from gridpilot.splits import TEST_START

# --------------------------------------------------------------------------- Window


def test_window_validation_and_fallback_match_the_registered_bounds():
    v = Window.validation()
    assert (v.name, v.init, v.eval_start, v.F) == (
        "validation", datetime(2024, 10, 17, tzinfo=UTC), datetime(2024, 11, 1, tzinfo=UTC),
        datetime(2025, 10, 24, tzinfo=UTC))
    f = Window.fallback()
    assert (f.name, f.init, f.eval_start, f.F) == (
        "fallback", datetime(2025, 7, 10, tzinfo=UTC), datetime(2025, 7, 25, tzinfo=UTC),
        datetime(2025, 10, 24, tzinfo=UTC))
    assert Window.named("validation") == v and Window.named("fallback") == f


def test_window_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        Window.validation().F = TEST_START


def test_window_test_needs_the_test_mode_context():
    # T11: the test window exists only inside gridpilot.seal.test_mode (see test_seal.py).
    from gridpilot.seal import SealError

    with pytest.raises(SealError, match="test-mode context"):
        Window.test()
    with pytest.raises(SealError, match="test-mode context"):
        Window.named("test")
    assert Window.validation().read_end == Window.fallback().read_end == TEST_START
    assert not Window.validation().is_test


def test_window_refuses_the_seal_and_other_names():
    with pytest.raises(ValueError, match="seal"):
        Window("validation", datetime(2025, 10, 1, tzinfo=UTC), datetime(2025, 10, 20, tzinfo=UTC),
               datetime(2025, 11, 2, tzinfo=UTC))
    with pytest.raises(ValueError):
        Window("test", datetime(2025, 10, 17, tzinfo=UTC), datetime(2025, 11, 1, tzinfo=UTC),
               datetime(2025, 10, 24, tzinfo=UTC))
    with pytest.raises(ValueError, match="warm-up"):
        Window("validation", datetime(2024, 10, 20, tzinfo=UTC),
               datetime(2024, 11, 1, tzinfo=UTC), datetime(2025, 10, 24, tzinfo=UTC))
    with pytest.raises(ValueError, match="aware"):
        Window("validation", datetime(2024, 10, 17), datetime(2024, 11, 1),
               datetime(2025, 10, 24))


# --------------------------------------------------------------------------- Scenario


def test_primary_defaults():
    p = Scenario.primary()
    assert p == Scenario()
    assert p.is_primary
    assert (p.dest_slots, p.transfer_s, p.batch_delay_s, p.mobility_max_gpus, p.phase_days) == (
        512, 1800.0, 21600, None, 0)
    assert p.sites() == SITES
    assert list(p.sites()) == list(SITES)  # same site order as the registered run
    assert p.time_only_sites() == {s: (n if s == HOME else 0) for s, n in SITES.items()}
    assert p.transfer_s == TRANSFER_S


def test_primary_reproduces_the_registered_config_fields():
    """The committed manifest is the registered run's record (run dirs are gitignored)."""
    m = json.loads((RESULTS_DIR / "manifest.json").read_text())
    a = m["assumptions"]
    p = Scenario.primary()
    assert a["home_slots"]["value"] == p.sites()[HOME]
    assert {s: e["value"] for s, e in a["destination_slots"].items()} == {
        s: n for s, n in p.sites().items() if s != HOME}
    assert a["transfer_time_s"]["value"] == p.transfer_s
    delays = {k: v["value"] for k, v in a["allowed_delay_s"].items()}
    assert delays["Pretrain"] == delays["SFT"] == delays["MLLM"] == p.batch_delay_s
    assert delays["Eval"] == 3600
    assert m["split"]["phase_days"]["value"] == p.phase_days
    assert m["cohort_record"]["phase_days"]["value"] == p.phase_days
    cfg = p.config()
    assert cfg["sites"] == SITES and cfg["phase_days"] == 0
    assert cfg["mobility_max_gpus"] is None


def test_primary_transform_is_the_identity():
    j = _jobs()
    assert Scenario.primary().transform(j).equals(j)


def test_batch_delay_changes_only_flexible_batch_types():
    j = _jobs()
    out = Scenario(name="b24", batch_delay_s=86400).transform(j)
    d = dict(zip(out["job_uid"], out["max_delay_s"], strict=True))
    assert d["pre_flex"] == 86400 and d["sft_flex"] == 86400 and d["mllm_flex"] == 86400
    assert d["eval_flex"] == 3600  # Eval stays bounded at 1 h
    assert d["pre_rigid"] == 0  # inflexible jobs have no discretionary delay
    assert out.drop("max_delay_s").equals(j.drop("max_delay_s"))


def test_mobility_limit_keeps_flexibility_and_drops_mobility_above_the_cap():
    j = _jobs()
    out = Scenario(name="m8", mobility_max_gpus=8).transform(j)
    mob = dict(zip(out["job_uid"], out["mobile"], strict=True))
    assert mob["pre_flex"] is True  # 8 GPUs
    assert mob["sft_flex"] is False  # 16 GPUs
    assert out["flexible"].equals(j["flexible"])
    assert out["max_delay_s"].equals(j["max_delay_s"])


def test_destination_capacity_and_transfer_knobs():
    z = Scenario(name="d0", dest_slots=0)
    assert z.sites() == {HOME: SITES[HOME], "CISO": 0, "BPAT": 0, "NEVP": 0}
    assert not z.has_destinations
    assert z.policies() == ("U", "S", "K", "W", "L")
    big = Scenario(name="d1024", dest_slots=1024)
    assert big.sites()["BPAT"] == 1024 and big.sites()[HOME] == SITES[HOME]
    assert big.policies() == ("U", "S", "K", "W", "L", "W_time", "L_time")
    assert Scenario(name="t", transfer_s=7200.0).transfer_s == 7200.0


def test_primary_policies_are_the_registered_set():
    assert Scenario.primary().policies() == (
        "U", "G", "S", "K", "W", "L", "H", "W_time", "L_time")


def test_knob_validation():
    with pytest.raises(ValueError):
        Scenario(name="x", phase_days=7)  # pre-registered phases only
    with pytest.raises(ValueError):
        Scenario(name="x", dest_slots=-1)
    with pytest.raises(ValueError):
        Scenario(name="x", transfer_s=-1.0)
    with pytest.raises(ValueError):
        Scenario(name="x", mobility_max_gpus=0)
    with pytest.raises(ValueError):
        Scenario(name="x", batch_delay_s=5400)  # whole hours only (cohort._batch_delay)
    with pytest.raises(ValueError):
        Scenario(name="primary", dest_slots=0)  # the name is reserved for the defaults


def test_u_changing_knobs_follow_f14_1():
    """F14.1: batch delay changes deadlines; phase changes the stream (own A). Capacity,
    transfer and mobility leave U and its deadlines unchanged."""
    assert Scenario(name="b", batch_delay_s=86400).changes_deadlines
    assert not Scenario(name="d", dest_slots=0).changes_deadlines
    assert not Scenario(name="t", transfer_s=7200.0).changes_deadlines
    assert not Scenario(name="m", mobility_max_gpus=8).changes_deadlines
    assert Scenario(name="p", phase_days=49).own_cohort
    assert not Scenario(name="b", batch_delay_s=86400).own_cohort


def test_d058_extension_registry():
    assert set(EXTENSIONS) == {"phase_49", "phase_98", "dest_slots_0", "dest_slots_1024",
                               "transfer_120min", "batch_delay_24h", "mobility_le_8gpus"}
    e = EXTENSIONS
    assert e["phase_49"].phase_days == 49 and e["phase_98"].phase_days == 98
    assert e["dest_slots_0"].dest_slots == 0 and e["dest_slots_1024"].dest_slots == 1024
    assert e["transfer_120min"].transfer_s == 7200.0
    assert e["batch_delay_24h"].batch_delay_s == 86400
    assert e["mobility_le_8gpus"].mobility_max_gpus == 8
    for name, s in e.items():
        assert s.name == name and not s.is_primary
        # one-axis endpoints: exactly one knob differs from primary
        diff = [k for k in ("dest_slots", "transfer_s", "batch_delay_s", "mobility_max_gpus",
                            "phase_days") if getattr(s, k) != getattr(Scenario.primary(), k)]
        assert len(diff) == 1, (name, diff)
    assert Scenario.named("primary") == Scenario.primary()
    assert Scenario.named("phase_98") == e["phase_98"]


# --------------------------------------------------------------------------- helpers


def _jobs() -> pl.DataFrame:
    rows = [  # uid, type, gpus, flexible, delay
        ("pre_flex", "Pretrain", 8, True, 21600),
        ("sft_flex", "SFT", 16, True, 21600),
        ("mllm_flex", "MLLM", 4, True, 21600),
        ("eval_flex", "Eval", 1, True, 3600),
        ("pre_rigid", "Pretrain", 64, False, 0),
        ("other", "Debug", 2, False, 0),
    ]
    return pl.DataFrame({
        "job_uid": [r[0] for r in rows], "job_type": [r[1] for r in rows],
        "gpus": [r[2] for r in rows], "flexible": [r[3] for r in rows],
        "max_delay_s": pl.Series([r[4] for r in rows], dtype=pl.Int64),
        "mobile": [r[3] for r in rows],
    })
