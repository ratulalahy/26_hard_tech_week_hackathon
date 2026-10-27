"""Results export contract (spec §11, F12.5, Task 7): envelopes, the seal, the claim frame."""

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from gridpilot.forecast import LIMITATION as FORECAST_LIMITATION
from gridpilot.paths import REPO_ROOT, RESULTS_DIR
from gridpilot.results import (
    CLAIM_FRAME,
    EVIDENCE_CLASSES,
    IMPORT_CONVENTION,
    LIMIT_BOOKINGS_UNSIGNED,
    LIMIT_VALIDATION_DEV,
    LIMIT_ZERO_MISSES,
    canonical_hash,
    check_claim_frame,
    env,
    sealed_timestamps,
    unenveloped_numbers,
    validate_artifact,
    write_json_atomic,
)

ARTIFACTS = ("manifest.json", "metrics.json", "forecast-replay.json", "job-replay.json",
             "grid-profile.json", "workload-profile.json", "extensions.json", "storage.json",
             "scenario-flows.json", "flexibility-budget.json", "case-days.json",
             "assumptions.json")


# --------------------------------------------------------------------------- env()


def test_env_shape_and_numpy():
    e = env(np.float64(1.5), "kg_CO2", "simulated", "run:U:co2_kg")
    assert e == {"value": 1.5, "unit": "kg_CO2", "evidence": "simulated",
                 "provenance_id": "run:U:co2_kg", "status": "ok", "reason": None}
    assert type(env(np.int64(3), "jobs", "simulated", "p")["value"]) is int
    s = env(np.array([1.0, 2.0]), "g/kWh", "forecast", "p")
    assert s["value"] == [1.0, 2.0]
    assert json.dumps(s)


def test_env_rejects_bad_evidence_and_unexplained_nulls():
    with pytest.raises(ValueError, match="evidence"):
        env(1.0, "kg", "guessed", "p")
    with pytest.raises(ValueError, match="reason"):
        env(None, "kg", "simulated", "p")
    with pytest.raises(ValueError, match="reason"):
        env([1.0, None], "kg", "simulated", "p")
    with pytest.raises(ValueError, match="reason"):
        env(1.0, "kg", "simulated", "p", status="not_run")
    with pytest.raises(ValueError, match="status"):
        env(1.0, "kg", "simulated", "p", status="great")
    # NaN is never a number in an artifact: it becomes null and needs a reason.
    with pytest.raises(ValueError, match="reason"):
        env(float("nan"), "kg", "simulated", "p")
    e = env(float("nan"), "kg", "simulated", "p", status="unavailable", reason="no data")
    assert e["value"] is None
    assert set(EVIDENCE_CLASSES) == {"observed", "measured", "forecast", "modeled", "assumed",
                                     "simulated"}


# --------------------------------------------------------------------------- validators


def test_unenveloped_numbers_found_with_paths():
    good = {"a": env(1.0, "kg", "simulated", "p"), "b": "text", "c": [env(2, "n", "measured", "q")],
            "flag": True}
    assert unenveloped_numbers(good) == []
    bad = {"a": 1.0, "b": {"c": [1, 2]}, "d": {"value": 3.0, "unit": "kg"},
           "e": {**env(1.0, "kg", "simulated", "p"), "evidence": "vibes"}}
    paths = unenveloped_numbers(bad)
    assert "$.a" in paths
    assert "$.b.c[0]" in paths and "$.b.c[1]" in paths
    assert any(p.startswith("$.d") for p in paths)
    assert any(p.startswith("$.e") for p in paths)


def test_sealed_timestamps_found_and_wallclock_exempt():
    ok = {"ts": "2025-10-31T23:00:00+00:00", "d": "2024-11-01", "s": "PACE",
          "wallclock_generated_at": "2026-10-27T09:00:00Z", "run_id": "20261027T090000Z",
          "path": "runs/slice/20261027T101902Z/forecast", "text": "window [2024-11-01, A)",
          "sealed_window": "test window [2025-11-01T00:00Z, 2026-11-01T00:00Z): never read",
          "evidence_scope": "the sealed window [2025-11-01, 2026-11-01) is never read",
          "note": "EIA's 2025-26 factors"}
    assert sealed_timestamps(ok) == []
    bad = {"x": ["2025-11-01T00:00:00+00:00"], "y": {"2026-01-01": 1},
           "z": "2025-10-31T18:00:00-07:00", "w": "2025-11-01",
           "sub": "arrivals until 2025-11-03T00:00Z were read",
           "wallclock_other": "2026-10-27T09:00:00Z"}
    found = sealed_timestamps(bad)
    assert "$.x[0]" in found
    assert any("2026-01-01" in p for p in found)
    assert "$.z" in found  # 2025-11-01T01:00Z
    assert "$.w" in found
    assert "$.sub" in found  # a date substring inside a longer string
    assert "$.wallclock_other" in found  # only the exact key wallclock_generated_at is exempt


def test_validate_artifact_and_claim_frame():
    req = [FORECAST_LIMITATION, IMPORT_CONVENTION, LIMIT_ZERO_MISSES, LIMIT_BOOKINGS_UNSIGNED,
           LIMIT_VALIDATION_DEV]
    m = {"claim_frame": CLAIM_FRAME, "limitations": req}
    assert validate_artifact(m) == []
    check_claim_frame(m)
    with pytest.raises(ValueError):
        check_claim_frame({"claim_frame": "something else", "limitations": req})
    with pytest.raises(ValueError):
        check_claim_frame({"claim_frame": CLAIM_FRAME, "limitations": [IMPORT_CONVENTION]})
    for drop in (LIMIT_ZERO_MISSES, LIMIT_BOOKINGS_UNSIGNED, LIMIT_VALIDATION_DEV):
        with pytest.raises(ValueError):
            check_claim_frame({"claim_frame": CLAIM_FRAME,
                               "limitations": [x for x in req if x != drop]})
    errs = validate_artifact({"n": 5, "t": "2025-12-01T00:00:00Z"})
    assert len(errs) == 2


def test_write_json_atomic_refuses_invalid(tmp_path: Path):
    p = tmp_path / "x.json"
    write_json_atomic(p, {"a": env(1.0, "kg", "simulated", "p")})
    assert json.loads(p.read_text())["a"]["value"] == 1.0
    with pytest.raises(ValueError):
        write_json_atomic(tmp_path / "y.json", {"a": 1.0})
    assert not (tmp_path / "y.json").exists()
    assert not list(tmp_path.glob(".*tmp*"))


def test_claim_frame_text_is_verbatim():
    assert CLAIM_FRAME == (
        "simulated advance-reservation scheduling scenario; baseline-relative deadlines; "
        "exact declared runtimes; runtime uncertainty untested; EIA-attributed "
        "(consumption-basis) emissions; conditional temporal block-resampling intervals")


# --------------------------------------------------------------------------- committed results


def test_canonical_hash_ignores_provenance_and_tiny_float_noise():
    a = {"run_id": "r1", "x": env(1.00000000001, "kg", "simulated", "r1:x"), "y": [0.0, -0.0]}
    b = {"run_id": "r2", "x": env(1.00000000004, "kg", "simulated", "r2:x"), "y": [-0.0, 0.0]}
    assert canonical_hash(a) == canonical_hash(b)  # 10 significant digits (T10)
    c = {"run_id": "r1", "x": env(1.000001, "kg", "simulated", "r1:x"), "y": [0.0, 0.0]}
    assert canonical_hash(a) != canonical_hash(c)


def _tracked_artifacts() -> list[str]:
    out = subprocess.run(["git", "ls-files", "results"], cwd=REPO_ROOT, capture_output=True,
                         text=True, check=False).stdout.split()
    return [Path(p).name for p in out if Path(p).name in ARTIFACTS]


def _committed():
    tracked = _tracked_artifacts()
    missing = [a for a in tracked if not (RESULTS_DIR / a).exists()]
    assert not missing, f"tracked results/ artifacts are missing on disk: {missing}"
    found = [RESULTS_DIR / a for a in ARTIFACTS if (RESULTS_DIR / a).exists()]
    if not tracked and not found:
        pytest.skip("no results/ artifacts tracked or exported yet (run `make slice`)")
    return found


def test_results_artifacts_all_present():
    found = _committed()
    assert {p.name for p in found} == set(ARTIFACTS)


def test_every_number_enveloped():
    for p in _committed():
        bad = unenveloped_numbers(json.loads(p.read_text()))
        assert bad == [], f"{p.name}: numbers outside a valid envelope at {bad[:10]}"


def test_no_sealed_dates():
    for p in _committed():
        bad = sealed_timestamps(json.loads(p.read_text()))
        assert bad == [], f"{p.name}: timestamps at or after TEST_START at {bad[:10]}"


def _envs(x, path="$"):
    if isinstance(x, dict):
        if "value" in x and "evidence" in x:
            yield path, x
            return
        for k, v in x.items():
            yield from _envs(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from _envs(v, f"{path}[{i}]")


def test_extensions_evidence_classes():
    """T10: repricing, common support and policy outcomes are simulated; scenario knobs are
    assumed; the D-058 cuts are not_run with the owner's reason; the seal holds."""
    _committed()
    ext = json.loads((RESULTS_DIR / "extensions.json").read_text())
    for path, e in _envs(ext):
        leaf = path.rsplit(".", 1)[-1]
        if ".scenario.knobs." in path:
            assert e["evidence"] == "assumed", path
        elif leaf in ("saving", "saving_ci95", "diff_kg", "diff_kg_ci95", "co2_kg"):
            assert e["evidence"] == "simulated", path
    for k, v in ext["not_run"].items():
        assert v["status"] == "not_run" and v["reason"].startswith("cut by owner (D-058)"), k
    assert ext["export_git_clean"] is True  # exported at a clean commit (fix r1 M-3)
    rep = ext["primary_reproduction"]
    assert rep["metrics_canonical_equal"] and all(rep["ledgers_equal"].values())
    blocks = {**ext["phases"], **ext["sensitivities"]}
    assert set(blocks) == {"phase_49", "phase_98", "dest_slots_0", "dest_slots_1024",
                           "transfer_120min", "batch_delay_24h", "mobility_le_8gpus"}
    for name, b in blocks.items():
        if b["status"] == "ok":
            assert b["all_on_time"], name  # late count stays 0 under bookings
            assert b["run_id"] and b["canonical_hashes"]["summary_canonical_sha256"], name
        else:
            assert b["status"] == "not_run" and b["reason"], name
    for b in (ext["repricing"], ext["common_support"]):
        assert b["canonical_hashes"]["run_id"] == ext["registered_run_id"]
        assert b["scenario"]["name"] == "primary"
    man = json.loads((RESULTS_DIR / "manifest.json").read_text())
    assert man["extensions"]["missing_runs"] == ext["missing_runs"]
    assert man["extensions"]["canonical_sha256"] == canonical_hash(ext)
    assert man["common_support_rerun"] == "see extensions.json#common_support"


def test_storage_evidence_classes():
    """T10b (D-061; Astra F12–F15, F29): the storage illustration is labelled illustrative;
    dispatch outcomes (energy, CO2, import, peak relief) are simulated, CI inputs modeled, eta,
    P/E, sizes and the schedule hours assumed; the schedule comes from the training years;
    strategy B is a hindsight heuristic, never a bound; the manifest points at it."""
    _committed()
    sto = json.loads((RESULTS_DIR / "storage.json").read_text())
    assert sto["kind"] == "illustrative"
    assert sto["note"] == ("not part of the registered experiment; validation-year profiles; "
                           "storage not simulated in the scheduler")
    assert "heuristic" in sto["strategy_labels"]["B"]
    assert "bound" not in sto["strategy_labels"]["B"] and "optim" not in sto["strategy_labels"]["B"]
    # fix round 1: the headline is the lead's illustrative 4 MWh / 1 MW selection (simulated
    # selection rule); counts are measured; the flat-marginal scenario is a loss at every size
    h = sto["headline"]
    assert h["e_mwh"]["value"] == 4 and h["e_mwh"]["evidence"] == "simulated"
    assert "illustrative" in h["rule"] and h["plateau_e_mwh"]["evidence"] == "simulated"
    for k in ("n_hours", "n_days", "n_train_hours", "by_local_hour"):
        assert sto["rush"][k]["evidence"] == "measured", k
    assert sto["window"]["n_hours"]["evidence"] == "measured"
    for c in sto["cases"].values():
        for by_eta in c["strategies"].values():
            for b in by_eta.values():
                assert all(x <= 0 for x in b["flat_marginal_cut_t"]["value"])
    assert [r["quantile"]["value"] for r in sto["rush"]["sensitivity"]] == [0.95, 0.98, 0.99]
    a = sto["assumptions"]
    for k in ("sizes_mwh", "p_over_e", "etas", "eta_default", "connection_mw"):
        assert a[k]["evidence"] == "assumed", k
    for k in ("charge_hours", "discharge_hours"):
        assert sto["schedule"][k]["evidence"] == "assumed", k
    assert sto["schedule"]["train_window"] == ["2022-01-01T00:00:00Z", "2024-10-29T00:00:00Z"]
    assert sto["schedule"]["train_profile_g_kwh"]["evidence"] == "modeled"
    assert sto["validation_profile_g_kwh"]["evidence"] == "modeled"
    for name, c in sto["cases"].items():
        for k in ("energy_mwh", "mean_load_mw", "load_hours", "base_co2_t"):
            assert c[k]["evidence"] == "simulated", (name, k)
        for s, by_eta in c["strategies"].items():
            assert set(by_eta) == {"0.75", "0.85", "0.90"}
            for eta, b in by_eta.items():
                for k, e in b.items():
                    assert e["evidence"] == "simulated", (name, s, eta, k)
                    assert len(e["value"]) == len(a["sizes_mwh"]["value"])
        for s, imp in c["import_at_headline"].items():
            assert all(e["evidence"] == "simulated" for e in imp.values()), (name, s)
    for p, sites in sto["peak_relief"]["policies"].items():
        for site, by in sites.items():
            assert all(e["evidence"] == "simulated" for e in by.values()), (p, site)
    assert sto["peak_relief"]["run_id"] == sto["registered_run_id"]
    assert sto["window"]["end"] <= "2025-11-01"
    man = json.loads((RESULTS_DIR / "manifest.json").read_text())
    assert sto["registered_run_id"] == man["run_id"]
    assert man["storage"]["artifact"] == "storage.json"
    assert man["storage"]["canonical_sha256"] == canonical_hash(sto)
    # the storage window is the registered cohort window: no-storage CO2 is U's CO2
    met = json.loads((RESULTS_DIR / "metrics.json").read_text())
    u = met["policies"]["U"]["metrics"]["co2_kg"]["value"] / 1000
    assert abs(sto["cases"]["U"]["base_co2_t"]["value"] - u) < 1e-6 * u
    assert abs(sto["combined"]["U_co2_t"]["value"] - u) < 1e-6 * u


def test_case_days_evidence_classes_and_rule():
    """T16 (D-066): the case study is illustrative and validation-only; the three days are the
    pre-registered top 3 by PACE daily maximum net load, in rank order; grid series observed,
    carbon modeled, policy outcomes simulated, weather forecast (descriptive); every context
    source is labelled context, and each day has one."""
    _committed()
    cd = json.loads((RESULTS_DIR / "case-days.json").read_text())
    man = json.loads((RESULTS_DIR / "manifest.json").read_text())
    assert cd["kind"] == "illustrative" and cd["window"] == "validation"
    assert cd["registered_run_id"] == man["run_id"]
    assert man["case_days"]["canonical_sha256"] == canonical_hash(cd)
    assert "D-066" in cd["rule"] and "earlier date" in cd["rule"]
    days = cd["days"]
    assert [d["rank"]["value"] for d in days] == [1, 2, 3]
    top = [(r["date"], r["max_net_load_mw"]["value"]) for r in cd["ranking_top10"]]
    assert top == sorted(top, key=lambda x: (-x[1], x[0]))
    assert [d["date"] for d in days] == [t[0] for t in top[:3]]
    assert all("2024-11-01" <= d["date"] < "2025-10-24" for d in days)
    assert "context, not evidence" in cd["context_note"]
    for d in days:
        assert d["peak"]["net_load_mw"]["value"] == max(d["pace"]["net_load_mw"]["value"])
        for k in ("demand_mw", "wind_mw", "solar_mw", "net_load_mw"):
            assert d["pace"][k]["evidence"] == "observed", k
        assert d["pace"]["ci_g_kwh"]["evidence"] == "modeled"
        for p in ("U", "S", "W"):
            pol = d["policies"][p]
            for k in ("utah_cluster_mw", "co2_t", "utah_cluster_at_peak_mw", "moved_energy_mwh"):
                assert pol[k]["evidence"] == "simulated", (p, k)
        for w in d["weather"].values():
            for k in ("tmax_f", "tmin_f", "cdd_65f", "hdd_65f"):
                assert w[k]["evidence"] == "forecast", k
        assert d["context"] and all("sentence" in c and "kind" in c for c in d["context"])
        assert all(c["kind"] == "none" or c["url"].startswith("https://") for c in d["context"])
    # execution and transfer each reconcile to the registered run; the total equals co2_kg
    met = json.loads((RESULTS_DIR / "metrics.json").read_text())
    for p in ("U", "S", "W"):
        c = cd["accounting_check"][p]
        for k in ("execution", "transfer", "total"):
            assert abs(c[k]["sliced_kg"]["value"] - c[k]["accounting_kg"]["value"]) < 1e-3, (p, k)
        tot = met["policies"][p]["metrics"]["co2_kg"]["value"]
        assert abs(c["total"]["accounting_kg"]["value"] - tot) < 1e-6 * tot, p
    assert cd["accounting_check"]["U"]["transfer"]["accounting_kg"]["value"] == 0
    assert cd["accounting_check"]["S"]["transfer"]["accounting_kg"]["value"] > 0


def test_manifest_carries_claim_frame():
    _committed()
    m = json.loads((RESULTS_DIR / "manifest.json").read_text())
    check_claim_frame(m)
    assert m["snapshot_id"] == "05efabe781cc"
