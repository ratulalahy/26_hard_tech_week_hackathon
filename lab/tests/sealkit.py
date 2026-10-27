"""Synthetic seal fixtures (Stage 3 T11): a fake data directory with sealed rows, a temporary
git repository with a fake freeze record and its annotated tag. Nothing here touches the real
data directory or the real sealed window.

Sentinel values make the sealed rows recognisable: pre-seal hours carry consumed 0.5 lb/kWh
(226.796 g/kWh) and sealed hours 0.9 lb/kWh (408.2328 g/kWh).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from gridpilot import seal
from gridpilot.data.eia930 import PARTITION_FUELS
from gridpilot.data.eia_co2 import CONSUMED_COL, GENERATED_COL, SHEET, TIME_COL
from gridpilot.splits import TEST_START

FIXTURE = Path(__file__).parent / "fixtures" / "freeze.json"
H = timedelta(hours=1)
PRE_LB, SEALED_LB = 0.5, 0.9
PRE_GEN_LB, SEALED_GEN_LB = 0.4, 0.8
F_SYN = datetime(2025, 11, 8, tzinfo=UTC)  # a short synthetic test cutoff
DATA_START = datetime(2025, 10, 1, tzinfo=UTC)
BALANCE_BAS = ("PACE", "CISO", "BPAT", "NEVP", "AVA")


def _hours(start, end):
    out, t = [], start
    while t < end:
        out.append(t)
        t += H
    return out


def write_workbook(path: Path, start: datetime, end: datetime) -> None:
    """A BA workbook with the parser's sheet and columns; 'UTC time' is hour-ending."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    ws.append([TIME_COL, GENERATED_COL, CONSUMED_COL])
    for t in _hours(start, end):
        sealed = t >= TEST_START
        ws.append([(t + H).replace(tzinfo=None), SEALED_GEN_LB if sealed else PRE_GEN_LB,
                   SEALED_LB if sealed else PRE_LB])
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def balance_frame(start: datetime, end: datetime, bas=BALANCE_BAS) -> pl.DataFrame:
    hours = _hours(start, end)
    rows = {"ba": [], "ts_utc": [], "demand_adj_mw": []}
    gen = {f"gen_{f}_adj_mw": [] for f in PARTITION_FUELS}
    for ba in bas:
        for t in hours:
            sealed = t >= TEST_START
            rows["ba"].append(ba)
            rows["ts_utc"].append(t)
            rows["demand_adj_mw"].append(9000.0 if sealed else 5000.0)
            for k in gen:
                gen[k].append({"gen_coal_adj_mw": 300.0 if sealed else 100.0,
                               "gen_solar_adj_mw": 50.0, "gen_wind_adj_mw": 20.0,
                               "gen_hydro_adj_mw": 200.0}.get(k, 0.0))
    df = pl.DataFrame({**rows, **gen}).with_columns(
        pl.col("ts_utc").cast(pl.Datetime("us", "UTC")), pl.col("ba").cast(pl.Categorical))
    return df


def make_data_dir(root: Path, start: datetime = DATA_START, end: datetime = F_SYN) -> Path:
    data = root / "data"
    for ba in seal.CORE_BAS:
        write_workbook(data / seal.WORKBOOK_REL.format(ba=ba), start, end)
    bal = data / seal.BALANCE_REL
    bal.parent.mkdir(parents=True, exist_ok=True)
    balance_frame(start, end).write_parquet(bal)
    trace = data / seal.TRACE_REL
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text("synthetic trace placeholder (not read by the seal tests)\n")
    return data


def git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), "-c", "user.name=seal-test",
                        "-c", "user.email=seal-test@example.invalid", "-c", "commit.gpgsign=false",
                        "-c", "tag.gpgsign=false", *args],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


def _manifests(repo: Path) -> str:
    """Two committed manifests and their snapshot; returns the snapshot id."""
    man = repo / "data" / "manifests"
    man.mkdir(parents=True, exist_ok=True)
    (man / "eia930.json").write_text(json.dumps({"source": "synthetic", "files": []}) + "\n")
    (man / "traces_acme.json").write_text(json.dumps({"source": "synthetic", "files": []}) + "\n")
    sources = {p.stem: {"manifest_sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "files": 0,
                        "bytes": 0, "status": "frozen"}
               for p in sorted(man.glob("*.json")) if p.name != "snapshot.json"}
    sid = seal.snapshot_id_of(sources)
    (man / "snapshot.json").write_text(json.dumps({"snapshot_id": sid, "sources": sources},
                                                  indent=2) + "\n")
    return sid


def freeze_record(*, commit: str, snapshot_id: str, data_dir: Path, F: datetime = F_SYN,
                  **overrides) -> dict:
    d = json.loads(FIXTURE.read_text())
    d["freeze_commit"] = commit
    d["snapshot_id"] = snapshot_id
    d["test_F"] = seal.iso(F)
    d["input_sha256"] = {rel: seal.file_sha256(data_dir / rel) for rel in seal.TEST_INPUTS}
    d.update(overrides)
    return d


def make_repo(root: Path, data_dir: Path, *, F: datetime = F_SYN, tag: str = "annotated",
              record_overrides: dict | None = None, tag_sha: str | None = None) -> Path:
    """A git repo at `root/repo`: commit 1 (code + manifests) is the freeze commit; commit 2
    adds config/freeze.json; `config-freeze` tags commit 2 (annotated by default)."""
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / ".gitignore").write_text("runs/\n")
    (repo / "code.py").write_text("FROZEN = True\n")
    sid = _manifests(repo)
    (repo / "config").mkdir()
    shutil.copy(Path(__file__).parents[2] / seal.FREEZE_SCHEMA_REL, repo / seal.FREEZE_SCHEMA_REL)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "code at the freeze")
    commit = git(repo, "rev-parse", "HEAD")
    rec = freeze_record(commit=commit, snapshot_id=sid, data_dir=data_dir, F=F)
    rec.update(record_overrides or {})
    p = repo / seal.FREEZE_REL
    p.write_text(json.dumps(rec, indent=2) + "\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "freeze record")
    sha = tag_sha or seal.file_sha256(p)
    if tag == "annotated":
        git(repo, "tag", "-a", seal.FREEZE_TAG, "-m", seal.freeze_tag_message(sha))
    elif tag == "lightweight":
        git(repo, "tag", seal.FREEZE_TAG)
    return repo


def setup(tmp_path: Path, **kw) -> tuple[Path, Path, Path]:
    """(repo, data_dir, results_dir) for a synthetic, authorizable test run."""
    data = make_data_dir(tmp_path)
    repo = make_repo(tmp_path, data, **kw)
    return repo, data, repo / "results"


def authorize(repo: Path, data: Path, results: Path | None = None, **kw) -> seal.Authorization:
    return seal.authorize(repo_root=repo, data_dir=data, results_dir=results or repo / "results",
                          **kw)


def read_log(results: Path) -> list[dict]:
    p = results / "test_reads.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
