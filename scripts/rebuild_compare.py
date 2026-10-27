"""Stage 3 T12 step 2 (F12.6): compare an independent clean rebuild with the registered run, and
write the rebuild evidence `docs/evidence/rebuild-<date>.json`.

    cd lab && uv run python ../scripts/rebuild_compare.py \
        --clone <clone dir> --rebuild-data <fresh data dir> --rebuild-run <rebuild run dir> \
        --registered-run <registered run dir> --main-data <shared data dir> \
        [--also-run <other reproduction run dir>] --timing <timing.json> --out <evidence.json>

Compared (a mismatch in any required item sets `match: false`, which `write_freeze.py` refuses):
- the canonical metrics hash of each side's serialized `results/metrics.json` (current rule,
  `gridpilot.results.canonical_hash`);
- the 9 canonical ledger hashes, as each run recorded them and recomputed from the ledger files;
- the cohort ids hash and the booking hash (cohort.json), and `bookings.parquet` by frame;
- the L configuration (max_leaf_nodes per series) of both forecast runs;
- `balance.parquet` and `carbon_hourly.parquet` (rebuilt data dir vs the shared one) by frame
  equality (`polars.testing.assert_frame_equal`). The seal (F8): frames are compared on
  `drop_sealed` rows only; for balance.parquet, which also holds the sealed window, the
  sealed rows are covered by the file sha256 (equal bytes ⇒ equal frames) and never read.

It lives outside `lab/` so that it can change without changing the frozen `lab/` tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
from polars.testing import assert_frame_equal

from gridpilot import seal
from gridpilot.cohort import ledger_hash
from gridpilot.results import canonical_hash
from gridpilot.splits import TEST_START, drop_sealed

LEDGERS = ("U", "G", "S", "K", "W", "L", "H", "W_time", "L_time")
BALANCE_REL = "interim/eia930/balance.parquet"
CARBON_REL = "processed/carbon/carbon_hourly.parquet"


def sha(p: Path) -> str:
    return seal.file_sha256(p)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          check=True).stdout.strip()


def frames_equal(a: pl.DataFrame, b: pl.DataFrame) -> tuple[bool, str | None]:
    try:
        assert_frame_equal(a, b, check_exact=True)
        return True, None
    except AssertionError as e:
        return False, str(e)[:500]


def side(a, b, **extra) -> dict:
    return {"registered": a, "rebuild": b, "match": a == b, **extra}


def metrics_canonical(run: Path) -> str:
    return canonical_hash(json.loads((run / "results" / "metrics.json").read_text()))


def forecast_dir(run: Path) -> Path:
    cfg = json.loads((run / "config.json").read_text())
    return run / "forecast" / Path(cfg["reproducibility"]["forecast_run"]["path"]).name


def leaves(fc: Path) -> dict[str, int]:
    m = json.loads((fc / "metrics.json").read_text())["series"]
    return {k: m[k]["L_max_leaf_nodes"] for k in seal.SERIES}


def table(name: str, main: Path, rebuilt: Path, sealed_rows_in_file: bool) -> dict:
    sa, sb = sha(main), sha(rebuilt)
    la, lb = pl.scan_parquet(main), pl.scan_parquet(rebuilt)
    schema_ok = la.collect_schema() == lb.collect_schema()
    # The seal: only pre-seal rows are materialized here.
    eq, err = frames_equal(drop_sealed(la).collect(), drop_sealed(lb).collect())
    n_sealed = {k: drop_sealed_complement_count(p) for k, p in (("main", main),
                                                                  ("rebuild", rebuilt))}
    if not sealed_rows_in_file and any(n_sealed.values()):
        raise SystemExit(f"{name}: a validation table holds sealed rows {n_sealed}")
    bytes_eq = sa == sb
    out = {"sha256": {"main": sa, "rebuild": sb}, "bytes_equal": bytes_eq,
           "schema_equal": schema_ok, "pre_seal_frame_equal": eq,
           "rows_at_or_after_TEST_START": n_sealed}
    if err:
        out["pre_seal_frame_difference"] = err
    if sealed_rows_in_file:
        out["sealed_rows"] = ("equal bytes, so equal frames (never read)" if bytes_eq else
                              "NOT COMPARED: the bytes differ, and comparing the frames would "
                              "read sealed values")
        out["frame_equal"] = schema_ok and eq and bytes_eq
    else:
        out["frame_equal"] = schema_ok and eq
    out["method"] = ("polars.testing.assert_frame_equal(check_exact=True) on drop_sealed rows, "
                     "schema equality, and sha256 of the files")
    return out


def drop_sealed_complement_count(p: Path) -> int:
    """How many rows sit at or after TEST_START (a count, never a value)."""
    return pl.scan_parquet(p).filter(pl.col("ts_utc") >= TEST_START).select(pl.len()).collect().item()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for k in ("clone", "rebuild-data", "rebuild-run", "registered-run", "main-data", "timing",
              "out"):
        ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--also-run", action="append", default=[],
                    help="another reproduction of the registered run, reported alongside")
    ap.add_argument("--clone-source", default=None)
    ap.add_argument("--derivation-out", default=None,
                    help="write seal.balance_derivation of the rebuilt table here (only when "
                         "it is byte-identical to the shared one)")
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    clone, rdata = Path(a.clone), Path(a.rebuild_data)
    rrun, reg, mdata = Path(a.rebuild_run), Path(a.registered_run), Path(a.main_data)
    timing = json.loads(Path(a.timing).read_text())
    rcfg = json.loads((rrun / "config.json").read_text())
    gcfg = json.loads((reg / "config.json").read_text())
    rrep, grep_ = rcfg["reproducibility"], gcfg["reproducibility"]

    ev: dict = {"schema": "gridpilot.rebuild.v1", "generated_at": seal.iso(datetime.now(UTC)),
                "what": ("F12.6 independent clean rebuild: a fresh clone of the freeze-candidate "
                         "commit, a fresh data dir rebuilt from raw by `make data`, and "
                         "`run_slice --no-export` on the validation window, compared with the "
                         "registered run")}
    commit = git(clone, "rev-parse", "HEAD")
    ev["clone"] = {"path": str(clone), "source": a.clone_source, "commit": commit,
                   "lab_tree": git(clone, "rev-parse", "HEAD:lab"),
                   "status_porcelain": git(clone, "status", "--porcelain", "--untracked-files=all")}
    raw = rdata / "raw"
    ev["data_dir"] = {
        "path": str(rdata), "raw": {"symlink": raw.is_symlink(), "target": str(raw.resolve())},
        "manifests_from_git": {p.name: sha(p) for p in sorted((rdata / "manifests").glob("*.json"))},
        "manifests_equal_clone_git": all(
            sha(p) == hashlib.sha256(subprocess.run(
                ["git", "-C", str(clone), "show", f"HEAD:data/manifests/{p.name}"],
                capture_output=True, check=True).stdout).hexdigest()
            for p in (rdata / "manifests").glob("*.json")),
        "built_by_make_data": [BALANCE_REL, CARBON_REL, CARBON_REL.replace(".parquet",
                                                                            ".meta.json")]}
    ev["registered_run"] = {"run_id": gcfg["run_id"], "path": str(reg),
                            "git_sha": gcfg["git_sha"], "snapshot_id": grep_["snapshot_id"]}
    ev["rebuild_run"] = {"run_id": rcfg["run_id"], "path": str(rrun), "git_sha": rcfg["git_sha"],
                         "git_clean": rcfg["git_clean"], "snapshot_id": rrep["snapshot_id"],
                         "window": rcfg["window"]}
    cmp: dict = {}
    req: dict[str, bool] = {}

    # Metrics, canonical hash of the serialized artifact (current rule).
    mc = side(metrics_canonical(reg), metrics_canonical(rrun),
              rule="gridpilot.results.canonical_hash of the serialized results/metrics.json")
    mc["committed_results_metrics_json"] = canonical_hash(json.loads(subprocess.run(
        ["git", "-C", str(clone), "show", "HEAD:results/metrics.json"], capture_output=True,
        check=True).stdout))
    for o in a.also_run:
        mc.setdefault("also", {})[Path(o).name] = metrics_canonical(Path(o))
    cmp["metrics_canonical_sha256"] = mc
    req["metrics_canonical_sha256"] = mc["match"]

    # Ledgers: as recorded, and recomputed from the files.
    led = {}
    for n in LEDGERS:
        recorded = side(grep_["ledger_canonical_sha256"][n], rrep["ledger_canonical_sha256"][n])
        recomputed = side(ledger_hash(pl.read_parquet(reg / f"ledger_{n}.parquet")),
                          ledger_hash(pl.read_parquet(rrun / f"ledger_{n}.parquet")))
        led[n] = {"recorded": recorded, "recomputed_from_files": recomputed,
                  "file_sha256": side(grep_["file_sha256"][f"ledger_{n}.parquet"],
                                      rrep["file_sha256"][f"ledger_{n}.parquet"],
                                      required=False)}
        req[f"ledger_{n}"] = recorded["match"] and recomputed["match"] and (
            recorded["registered"] == recomputed["registered"])
    for o in a.also_run:
        oc = json.loads((Path(o) / "config.json").read_text())["reproducibility"]
        for n in LEDGERS:
            led[n].setdefault("also", {})[Path(o).name] = oc["ledger_canonical_sha256"][n]
    cmp["ledger_canonical_sha256"] = led

    # Cohort and bookings.
    gco = json.loads((reg / "cohort.json").read_text())
    rco = json.loads((rrun / "cohort.json").read_text())
    strip = {"wallclock_written_at"}
    beq, berr = frames_equal(pl.read_parquet(reg / "bookings.parquet"),
                             pl.read_parquet(rrun / "bookings.parquet"))
    cmp["cohort"] = {
        "cohort_ids_sha256": side(gco["cohort_ids_sha256"], rco["cohort_ids_sha256"]),
        "booking_sha256": side(gco["booking_sha256"], rco["booking_sha256"]),
        "cohort_record_equal_without_wallclock": (
            {k: v for k, v in gco.items() if k not in strip}
            == {k: v for k, v in rco.items() if k not in strip}),
        "bookings_parquet": {"frame_equal": beq, "difference": berr,
                             "file_sha256": side(sha(reg / "bookings.parquet"),
                                                 sha(rrun / "bookings.parquet"),
                                                 required=False)},
    }
    req["cohort_ids_sha256"] = cmp["cohort"]["cohort_ids_sha256"]["match"]
    req["booking_sha256"] = cmp["cohort"]["booking_sha256"]["match"]
    req["bookings_parquet_frame"] = beq

    # Forecasts and the L configuration.
    gfc, rfc = forecast_dir(reg), forecast_dir(rrun)
    cmp["forecast"] = {
        "forecasts_sha256": side(sha(gfc / "forecasts.parquet"), sha(rfc / "forecasts.parquet"),
                                 required=False),
        "climatology_sha256": side(sha(gfc / "climatology.parquet"),
                                   sha(rfc / "climatology.parquet"), required=False),
        "L_max_leaf_nodes": side(leaves(gfc), leaves(rfc)),
        "registered_metrics_path": str(gfc / "metrics.json"),
        "registered_metrics_sha256": sha(gfc / "metrics.json"),
    }
    req["L_max_leaf_nodes"] = cmp["forecast"]["L_max_leaf_nodes"]["match"]

    # Derived tables: the rebuilt data dir vs the shared one.
    tabs = {"balance.parquet": table("balance.parquet", mdata / BALANCE_REL,
                                     rdata / BALANCE_REL, sealed_rows_in_file=True),
            "carbon_hourly.parquet": table("carbon_hourly.parquet", mdata / CARBON_REL,
                                           rdata / CARBON_REL, sealed_rows_in_file=False)}
    tabs["truth_fill.parquet (run)"] = {
        "frame_equal": frames_equal(drop_sealed(pl.read_parquet(reg / "truth_fill.parquet")),
                                    drop_sealed(pl.read_parquet(rrun / "truth_fill.parquet")))[0],
        "required": False}
    tabs["inputs_recorded_by_the_runs"] = {
        k: side(grep_["file_sha256"][k], rrep["file_sha256"][k], required=False)
        for k in ("balance.parquet", "carbon_hourly.parquet", "trace_seren.csv")}
    cmp["tables"] = tabs
    ev["tables"] = {k: tabs[k] for k in ("balance.parquet", "carbon_hourly.parquet")}
    req["balance_frame_equal"] = tabs["balance.parquet"]["frame_equal"]
    req["carbon_frame_equal"] = tabs["carbon_hourly.parquet"]["frame_equal"]

    ev["comparisons"] = cmp
    ev["required"] = req
    ev["match"] = all(req.values())
    ev["forecast"] = {"registered_metrics_sha256": cmp["forecast"]["registered_metrics_sha256"],
                      "L_max_leaf_nodes": cmp["forecast"]["L_max_leaf_nodes"]}
    ev["validation_reference"] = seal.validation_reference(clone)
    ev["commands"] = timing.get("commands", [])
    ev["wall_time_s"] = timing.get("wall_time_s", {}) | {
        "compare": round(time.perf_counter() - t0, 1)}
    ev["started_at"], ev["finished_at"] = timing.get("started_at"), seal.iso(datetime.now(UTC))

    if a.derivation_out:
        if tabs["balance.parquet"]["bytes_equal"]:
            der = seal.balance_derivation(rdata, clone)
            der["rebuild"] = {"evidence": "docs/evidence/rebuild-20261027.json",
                              "clone_commit": commit, "data_dir": str(rdata)}
            Path(a.derivation_out).parent.mkdir(parents=True, exist_ok=True)
            Path(a.derivation_out).write_text(json.dumps(der, indent=2) + "\n")
            ev["balance_derivation"] = {"written": a.derivation_out,
                                        "output_sha256": der["output_sha256"]}
        else:
            ev["balance_derivation"] = {"written": None,
                                        "reason": "the rebuilt balance.parquet is not "
                                                  "byte-identical to the shared one"}
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ev, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"match": ev["match"], "required": req}, indent=1))
    return 0 if ev["match"] else 1


if __name__ == "__main__":
    sys.exit(main())
