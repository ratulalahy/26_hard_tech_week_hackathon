"""The seal on the test window (AGENTS.md "Data rules"; spec §5, §12, F8; Stage 3 T11; D-059:
the sealed test year is opened **exactly once**, and any rerun carries a logged reason).

The sealed test window [2025-11-01T00Z, 2026-11-01T00Z) opens only through one logged entry
point, after a recorded configuration freeze:

1. **The freeze record** `config/freeze.json` (schema `config/freeze.schema.json`, written by
   T12) holds the freeze commit, the deployed policy and its §8 rule trace, the frozen L
   `max_leaf_nodes` per series, the test cutoff `test_F`, the test fit time and history start,
   the S ranking with its means and window, the scenario catalog, the snapshot id, every input
   file's sha256, and the validation run id and canonical hash. It is read from git at HEAD and
   validated with the JSON schema plus the cross-field rules (`load_freeze`, `freeze_errors`).
2. **`authorize`** runs the refusal checks and returns the only object `test_mode` accepts:
   - (a) HEAD is the freeze commit, or descends from it through commits that only **add or
     modify** `config/freeze.json` and the test outputs (no rename, no deletion); the tree is
     clean, with no skip-worktree / assume-unchanged file, no file hidden by `.git/info/exclude`
     and no stray ignored file under `lab/`; the read log at HEAD extends, byte for byte, the
     log at every commit since the freeze.
   - (b) the annotated tag `config-freeze` carries the record's sha256, targets the last commit
     that touched the record, whose parent is the freeze commit; it equals the tag on `origin`
     (an unreachable remote refuses unless an override reason is given, which is logged); no
     earlier invocation in the log used a different record.
   - B7 / I5: the snapshot and manifests are read from git at HEAD, and every test input that a
     committed manifest lists has the manifest's sha256 (balance.parquet: its committed
     derivation record, or a logged exception until T12 writes one).
   - (c) every input file's sha256 matches the record.
   - (d) a prior opening — any `invocation` or `read` line in the working-tree or committed log,
     any commit that ever touched the test outputs, a completed `results/test/`, the test carbon
     table or any `runs/test/*` — requires a rerun reason, which is logged.
   - the validation reference matches `results/manifest.json` and `results/metrics.json` at
     HEAD (canonical hash of the serialized artifact).
   - In real use the roots are the repository's, the results dir is `results/` and the data dir
     is `gridpilot.paths.DATA_DIR`. Other roots need `synthetic=True` and a data dir holding a
     `SYNTHETIC` marker that is not the repository's data dir (tests only).
   Every failure raises `SealError` with the reason.
3. **`test_mode(auth)`** is the active context. An authorization is single-use. The session lives
   in a `ContextVar`, is bound to its process and thread, and holds an `O_EXCL` lock file. Only
   `run_slice --window test` (the entry point) enters it; a static test checks that.
4. **`sealed_read(path, *, purpose, columns, time_range)`** is the only function that returns
   rows at or after TEST_START. It refuses outside the context. It reads the file's bytes once,
   checks their sha256 against the freeze record (or the session's own built files), appends one
   fsynced JSONL line to `results/test_reads.jsonl`, and only then parses the same bytes.

Inside the context, `gridpilot.window.Window.test()` is constructible; outside it raises.

**Shared state in the git common dir** (fix round 2, N1/N2): every invocation is also appended
(fsynced) to `<git-common-dir>/gridpilot/test_openings.jsonl`, the witness that all worktrees and
the main checkout share, so an opening in one worktree is a prior opening in every other. The
session lock is `<git-common-dir>/gridpilot/test_mode.lock`, holding the session's pid.

**Recovery from a crashed session** (a stale lock, whose pid is no longer alive): check (a) names
the stale lock. Then (1) delete the lock file; (2) commit **only** the read log
(`results/test_reads.jsonl`), never edited; (3) rerun with `--rerun-reason "<what crashed, and
the fix>"`. A code fix needs a new freeze record: a bug-fix rerun accepts it when the decision
fields are identical, the new `freeze_commit` descends from the old one, and only
`freeze_commit`, `frozen_at` and `validation_run` differ (lead ruling N3); both record hashes and
the field diff are logged.
"""

from __future__ import annotations

import contextvars
import hashlib
import io
import json
import math
import os
import re
import stat
import subprocess
import sys
import threading
import uuid
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

import polars as pl

from gridpilot import paths
from gridpilot.splits import TEST_END, TEST_START

SCHEMA_ID = "gridpilot.freeze.v1"
TEST_INIT = datetime(2025, 10, 17, tzinfo=UTC)  # F14.4: eval_start − 15 d
TEST_FIT_AT = datetime(2025, 10, 29, tzinfo=UTC)  # spec §5
TEST_HISTORY_START = datetime(2023, 1, 1, tzinfo=UTC)  # spec §5
FREEZE_REL = "config/freeze.json"
FREEZE_SCHEMA_REL = "config/freeze.schema.json"
FREEZE_TAG = "config-freeze"
READ_LOG_REL = "results/test_reads.jsonl"
TEST_RESULTS_REL = "results/test"
TEST_HISTORY_DIR = "history"  # results/test/history/<run_id>/: earlier runs' artifacts (M9)
TEST_RUNS_REL = "runs/test"
# Shared across worktrees, under `git rev-parse --git-common-dir` (N1, N2).
WITNESS_REL = "gridpilot/test_openings.jsonl"
LOCK_REL = "gridpilot/test_mode.lock"
GITHUB_ORIGIN = "https://github.com/ratulalahy/26_hard_tech_week_hackathon.git"  # N5
# N3 (lead ruling): a bug-fix rerun may change only these record fields ...
RERUN_MUTABLE = frozenset({"freeze_commit", "frozen_at", "validation_run"})
# ... and must keep these identical.
DECISION_FIELDS = ("deployed_policy", "L_max_leaf_nodes", "s_ranking", "test_F",
                   "test_F_basis", "scenario_catalog", "input_sha256", "snapshot_id")
COMPLETED_MARKER = "manifest.json"  # results/test/manifest.json = a completed test run
# Paths that later commits may add or modify (never rename or delete) without reopening (a).
POST_FREEZE_PATHS = (FREEZE_REL, f"{TEST_RESULTS_REL}/", READ_LOG_REL)
MANIFESTS_REL = "data/manifests"
SNAPSHOT_REL = f"{MANIFESTS_REL}/snapshot.json"
# The committed derivation record of the interim balance table (I5; T12's rebuild writes it).
BALANCE_DERIVATION_REL = f"{MANIFESTS_REL}/derived/balance.json"
SYNTHETIC_MARKER = "SYNTHETIC"  # a synthetic (test-only) data dir holds this file (I4)
# Input files the test run reads (paths relative to the data directory). Each must be in the
# freeze record with its sha256.
CORE_BAS = ("PACE", "CISO", "BPAT", "NEVP")
WORKBOOK_REL = "raw/eia930/ba_workbooks/{ba}.xlsx"
BALANCE_REL = "interim/eia930/balance.parquet"
TRACE_REL = "raw/traces/acme/trace_seren.csv"
TEST_INPUTS = tuple(WORKBOOK_REL.format(ba=ba) for ba in CORE_BAS) + (BALANCE_REL, TRACE_REL)
# D-071 item 3 (T20): the Salt Lake City forecast-archive files whose span reaches the test year,
# read on test only for the toughest days' temperature context. Optional inputs: write_freeze
# records those present in the data dir, (c) then checks them like every recorded input, I5
# checks them against the committed openmeteo manifest, and `sealed_read` accepts nothing else.
WEATHER_SLC_REL = "raw/openmeteo/historical-forecast/best_match/PACE_SLC"
# Where an earlier version wrote the test carbon table (shared, unguarded); its existence is a
# prior opening (I1). The table now lives in the test run directory (I6).
LEGACY_CARBON_TEST_REL = "processed/carbon/carbon_hourly_test.parquet"
CARBON_TEST_NAME = "carbon_hourly_test.parquet"
SERIES = ("PACE/ci_consumed", "CISO/ci_consumed", "BPAT/ci_consumed", "NEVP/ci_consumed",
          "PACE/demand", "PACE/wind", "PACE/solar")  # = forecast.RUN_SERIES
LEAF_NODES = (15, 31)  # = forecast.MAX_LEAF_NODES
SITES = ("PACE", "BPAT", "CISO", "NEVP")
SELECTION_POLICIES = ("U", "G", "S", "K", "W", "L")  # spec §8 deployment candidates
TAG_LINE = re.compile(r"config/freeze\.json sha256: ([0-9a-f]{64})")
# Ignored files under lab/ that the clean check tolerates (caches and the environment).
LAB_IGNORED_OK = re.compile(r"(^|/)(\.venv|__pycache__|\.pytest_cache|\.ruff_cache|\.hypothesis|"
                            r"\.ipynb_checkpoints|[^/]*\.egg-info)(/|$)|\.py[cod]$")
OPENING_EVENTS = ("invocation", "read")

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX12 = re.compile(r"^[0-9a-f]{12}$")
_RUN_ID = re.compile(r"^\d{8}T\d{6}Z$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_KEYS = ("schema", "freeze_commit", "frozen_at", "deployed_policy", "L_max_leaf_nodes", "test_F",
         "test_fit_at", "test_history_start", "s_ranking", "scenario_catalog", "snapshot_id",
         "input_sha256", "validation_run")
# Optional keys (T12): how test_F was derived from the completeness counts (final review B4).
_OPTIONAL_KEYS = ("test_F_basis",)
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class SealError(PermissionError):
    """A refusal to open the sealed window, or a sealed read outside the logged context."""


def iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(s: str, what: str) -> datetime:
    if not isinstance(s, str) or not _UTC.match(s):
        raise SealError(f"freeze record: {what} must be UTC 'YYYY-MM-DDTHH:MM:SSZ', got {s!r}")
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def freeze_tag_message(freeze_sha256: str) -> str:
    """The annotated-tag message T12 writes for `config-freeze` (check (b) parses it)."""
    return f"GridPilot configuration freeze\n\nconfig/freeze.json sha256: {freeze_sha256}\n"


# --------------------------------------------------------------------------- freeze record


@dataclass(frozen=True)
class Freeze:
    """A validated `config/freeze.json`. `raw` is the parsed JSON; `sha256` the file's."""

    raw: dict
    sha256: str
    path: Path

    @property
    def freeze_commit(self) -> str:
        return self.raw["freeze_commit"]

    @property
    def test_F(self) -> datetime:
        return parse_utc(self.raw["test_F"], "test_F")

    @property
    def test_fit_at(self) -> datetime:
        return parse_utc(self.raw["test_fit_at"], "test_fit_at")

    @property
    def test_history_start(self) -> datetime:
        return parse_utc(self.raw["test_history_start"], "test_history_start")

    @property
    def l_max_leaf_nodes(self) -> dict[str, int]:
        return dict(self.raw["L_max_leaf_nodes"])

    @property
    def s_order(self) -> list[str]:
        return list(self.raw["s_ranking"]["order"])

    @property
    def s_means(self) -> dict[str, float]:
        return {b: float(v) for b, v in self.raw["s_ranking"]["mean_consumed_ci_g_kwh"].items()}

    @property
    def s_window(self) -> tuple[datetime, datetime]:
        a, b = self.raw["s_ranking"]["window"]
        return parse_utc(a, "s_ranking.window[0]"), parse_utc(b, "s_ranking.window[1]")

    @property
    def deployed_policy(self) -> str:
        return self.raw["deployed_policy"]["name"]

    @property
    def snapshot_id(self) -> str:
        return self.raw["snapshot_id"]

    @property
    def input_sha256(self) -> dict[str, str]:
        return dict(self.raw["input_sha256"])

    @property
    def scenario_catalog(self) -> dict[str, dict]:
        return dict(self.raw["scenario_catalog"])


def _schema_errors(d: Any) -> list[str]:
    """JSON-schema errors (config/freeze.schema.json, draft 2020-12)."""
    import jsonschema

    schema = json.loads((paths.REPO_ROOT / FREEZE_SCHEMA_REL).read_text())
    v = jsonschema.Draft202012Validator(schema)
    return [f"schema: {'/'.join(map(str, e.path)) or '$'}: {e.message}"
            for e in sorted(v.iter_errors(d), key=lambda e: list(map(str, e.path)))]


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def freeze_errors(d: Any) -> list[str]:
    """Every way `d` fails the freeze-record contract: the JSON schema, plus the cross-field
    rules a schema cannot state."""
    if not isinstance(d, dict):
        return ["the record is not a JSON object"]
    errs = _schema_errors(d)
    errs += [f"missing key {k!r}" for k in _KEYS if k not in d]
    errs += [f"unknown key {k!r}" for k in d if k not in _KEYS + _OPTIONAL_KEYS]
    if any(k not in d for k in _KEYS):
        return errs

    def t(key):
        try:
            return parse_utc(d[key], key)
        except SealError as e:
            errs.append(str(e))
            return None

    if d["schema"] != SCHEMA_ID:
        errs.append(f"schema must be {SCHEMA_ID!r}")
    if not isinstance(d["freeze_commit"], str) or not _HEX40.match(d["freeze_commit"]):
        errs.append("freeze_commit must be a 40-hex commit sha")
    fz = t("frozen_at")
    if fz is not None and fz > datetime.now(UTC) + timedelta(hours=1):
        errs.append("frozen_at is in the future")
    dp = d["deployed_policy"]
    if not isinstance(dp, dict) or dp.get("name") not in SELECTION_POLICIES:
        errs.append(f"deployed_policy.name must be one of {SELECTION_POLICIES} (spec §8)")
    elif (not isinstance(dp.get("rule_trace"), list) or not dp["rule_trace"]
          or not all(isinstance(r, dict) and isinstance(r.get("rule"), str) and r["rule"]
                     and isinstance(r.get("result"), str) and r["result"]
                     for r in dp["rule_trace"])):
        errs.append("deployed_policy.rule_trace must be a non-empty list of {rule, result}")
    leaf = d["L_max_leaf_nodes"]
    if not isinstance(leaf, dict) or set(leaf) != set(SERIES):
        errs.append(f"L_max_leaf_nodes must have exactly the series {SERIES}")
    elif any(type(v) is not int or v not in LEAF_NODES for v in leaf.values()):
        errs.append(f"L_max_leaf_nodes values must be the integers {LEAF_NODES}")
    F = t("test_F")
    if F is not None:
        if not TEST_START < F <= TEST_END:
            errs.append(f"test_F {d['test_F']} must lie in ({iso(TEST_START)}, {iso(TEST_END)}]")
        if F.hour or F.minute or F.second:
            errs.append("test_F must be a UTC midnight (the last complete day ends there)")
        basis = d.get("test_F_basis")
        if basis is not None:
            D = basis.get("D") if isinstance(basis, dict) else None
            if not isinstance(D, str) or not _DATE.match(D):
                errs.append("test_F_basis.D must be a UTC day 'YYYY-MM-DD'")
            else:
                Dt = datetime.strptime(D, "%Y-%m-%d").replace(tzinfo=UTC)
                if F != min(Dt + timedelta(days=1), TEST_END):
                    errs.append(f"test_F {d['test_F']} must be min(D + 1 day, TEST_END) for "
                                f"test_F_basis.D {D}")
    fit = t("test_fit_at")
    if fit is not None and fit != TEST_FIT_AT:
        errs.append(f"test_fit_at must be {iso(TEST_FIT_AT)} (spec §5)")
    hs = t("test_history_start")
    if hs is not None and hs != TEST_HISTORY_START:
        errs.append(f"test_history_start must be {iso(TEST_HISTORY_START)} (spec §5)")
    sr = d["s_ranking"]
    order = sr.get("order") if isinstance(sr, dict) else None
    if not isinstance(order, list) or sorted(order) != sorted(SITES):
        errs.append(f"s_ranking.order must be a permutation of {SITES}")
    else:
        means = sr.get("mean_consumed_ci_g_kwh")
        if not isinstance(means, dict) or set(means) != set(SITES):
            errs.append(f"s_ranking.mean_consumed_ci_g_kwh must hold exactly {SITES}")
        elif not all(_num(v) and v > 0 for v in means.values()):
            errs.append("s_ranking.mean_consumed_ci_g_kwh values must be finite positive numbers")
        elif order != sorted(SITES, key=lambda b: (means[b], b)):
            errs.append("s_ranking.order must be the sites sorted by their means (then BA code)")
        win = sr.get("window")
        if not isinstance(win, list) or len(win) != 2:
            errs.append("s_ranking.window must be [start, end]")
        else:
            try:
                a, b = (parse_utc(x, "s_ranking.window") for x in win)
                if not a < b <= TEST_START:
                    errs.append("s_ranking.window must be a pre-seal range (end <= TEST_START)")
                elif (a, b) != (TEST_HISTORY_START, TEST_FIT_AT):
                    errs.append(f"s_ranking.window must be [{iso(TEST_HISTORY_START)}, "
                                f"{iso(TEST_FIT_AT)}] (N11)")
            except SealError as e:
                errs.append(str(e))
    sc = d["scenario_catalog"]
    if not isinstance(sc, dict) or not isinstance(sc.get("primary"), dict):
        errs.append("scenario_catalog must hold the 'primary' scenario's config")
    if not isinstance(d["snapshot_id"], str) or not _HEX12.match(d["snapshot_id"]):
        errs.append("snapshot_id must be 12 hex characters")
    ins = d["input_sha256"]
    if not isinstance(ins, dict) or not ins:
        errs.append("input_sha256 must be a non-empty {path: sha256} map")
    else:
        for k, v in ins.items():
            if not isinstance(v, str) or not _HEX64.match(v):
                errs.append(f"input_sha256[{k!r}] is not a sha256")
            pp = PurePosixPath(k)
            if (pp.is_absolute() or any(p in ("..", ".", "") for p in k.split("/"))
                    or pp.as_posix() != k or "\\" in k):
                errs.append(f"input_sha256 key {k!r} must be a normalized path relative to the "
                            f"data directory")
    vr = d["validation_run"]
    if (not isinstance(vr, dict) or set(vr) != {"run_id", "metrics_canonical_sha256"}
            or not isinstance(vr.get("run_id"), str) or not _RUN_ID.match(vr["run_id"])
            or not _HEX64.match(str(vr.get("metrics_canonical_sha256")))):
        errs.append("validation_run must be {run_id, metrics_canonical_sha256}")
    return errs


def parse_freeze(raw: bytes, path: Path) -> Freeze:
    """Validate the bytes of a freeze record (hashed and parsed from the same buffer)."""
    try:
        d = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise SealError(f"freeze record {path} is not valid JSON: {e}") from e
    errs = freeze_errors(d)
    if errs:
        raise SealError(f"freeze record {path} is invalid: {'; '.join(errs)}")
    return Freeze(raw=d, sha256=hashlib.sha256(raw).hexdigest(), path=path)


def load_freeze(path: Path | str | None = None) -> Freeze:
    """Read and validate a freeze-record file (default: the repository's working copy).
    `authorize` reads the record from git at HEAD instead."""
    path = Path(path) if path else paths.REPO_ROOT / FREEZE_REL
    if not path.exists():
        raise SealError(f"no freeze record at {path}: the configuration is not frozen")
    return parse_freeze(path.read_bytes(), path)


# --------------------------------------------------------------------------- git


def _git(root: Path, *args: str, timeout: float | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}  # never wait on a credential prompt
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          check=False, timeout=timeout, env=env)


def git_common_dir(root: Path) -> Path:
    """The git directory every worktree of `root` shares (N1, N2)."""
    d = Path(_git_out(root, "rev-parse", "--git-common-dir"))
    return (d if d.is_absolute() else Path(root) / d).resolve()


def _git_out(root: Path, *args: str) -> str:
    r = _git(root, *args)
    if r.returncode:
        raise SealError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def extra_inputs(data_dir: Path) -> tuple[str, ...]:
    """The optional test inputs present in `data_dir` (data-dir-relative paths): the Salt Lake
    City archive files from 2025 on (D-071 item 3)."""
    d = Path(data_dir) / WEATHER_SLC_REL
    if not d.is_dir():
        return ()
    return tuple(sorted(f"{WEATHER_SLC_REL}/{p.name}" for p in d.glob("*.json")
                        if p.name[:4].isdigit() and int(p.name[:4]) >= TEST_START.year))


def committed_bytes(root: Path, rel: str, rev: str = "HEAD") -> bytes | None:
    """The file `rel` as committed at `rev`, or None (B7: read from git, not the data dir)."""
    r = subprocess.run(["git", "-C", str(root), "show", f"{rev}:{rel}"], capture_output=True,
                       check=False)
    return r.stdout if r.returncode == 0 else None


def committed_manifests(root: Path, rev: str = "HEAD") -> dict[str, str]:
    """sha256 of every committed `data/manifests/*.json` at `rev`, by file name."""
    names = _git_out(root, "ls-tree", "--name-only", f"{rev}:{MANIFESTS_REL}").splitlines()
    out = {}
    for n in sorted(names):
        if n.endswith(".json"):
            out[n] = hashlib.sha256(committed_bytes(root, f"{MANIFESTS_REL}/{n}", rev)
                                    or b"").hexdigest()
    return out


def manifest_entries(root: Path, rev: str = "HEAD") -> dict[str, tuple[str, str]]:
    """{data-dir-relative path: (manifest name, sha256)} from every committed manifest's file
    records (`path`, or `raw/<source>/<file>`)."""
    out: dict[str, tuple[str, str]] = {}
    for name in committed_manifests(root, rev):
        if name == "snapshot.json":
            continue
        d = json.loads(committed_bytes(root, f"{MANIFESTS_REL}/{name}", rev) or b"{}")
        recs = next((d[k] for k in ("files", "entries", "downloads", "outputs")
                     if isinstance(d.get(k), list)), [])
        stem = name[:-5]
        for r in recs:
            if not isinstance(r, dict) or not r.get("sha256"):
                continue
            rel = r.get("path") or (f"raw/{stem}/{r['file']}" if r.get("file") else None)
            if rel:
                out[rel] = (name, r["sha256"])
    return out


def snapshot_id_of(sources: dict[str, dict]) -> str:
    """The snapshot id rule of scripts/snapshot_manifests.py."""
    return hashlib.sha256(json.dumps({k: v["manifest_sha256"] for k, v in sources.items()},
                                     sort_keys=True).encode()).hexdigest()[:12]


def balance_derivation(data_dir: Path, repo_root: Path,
                       raw_files: Sequence[Path] | None = None) -> dict:
    """The derivation record of interim/eia930/balance.parquet (I5): the hash of the table, the
    hashes of the raw BALANCE files it is built from, and the git tree hash of `lab/` that built
    it. T12's rebuild writes it to `data/manifests/derived/balance.json` and commits it."""
    raw = sorted(raw_files or (data_dir / "raw" / "eia930").glob("EIA930_BALANCE_*.csv"))
    return {"output": BALANCE_REL, "output_sha256": file_sha256(data_dir / BALANCE_REL),
            "inputs_sha256": {p.relative_to(data_dir).as_posix(): file_sha256(p) for p in raw},
            "code": "gridpilot.data.eia930.build_balance",
            "lab_tree": _git_out(repo_root, "rev-parse", "HEAD:lab")}


def validation_reference(root: Path, rev: str = "HEAD") -> dict:
    """What T12 records in `validation_run`: the registered run id from results/manifest.json,
    and the canonical hash of the serialized results/metrics.json, both as committed at `rev`
    (M3, M15)."""
    from gridpilot.results import canonical_hash

    man = committed_bytes(root, "results/manifest.json", rev)
    met = committed_bytes(root, "results/metrics.json", rev)
    if man is None or met is None:
        raise SealError("results/manifest.json and results/metrics.json must be committed")
    return {"run_id": json.loads(man)["run_id"],
            "metrics_canonical_sha256": canonical_hash(json.loads(met))}


def read_log_events(raw: bytes | str | None) -> list[dict]:
    """The JSON lines of a read log (an unparsable line counts as an opening event)."""
    if not raw:
        return []
    text = raw.decode() if isinstance(raw, bytes) else raw
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            rec = {"event": "invocation", "unparsable": line[:200]}
        out.append(rec if isinstance(rec, dict) else {"event": "invocation"})
    return out


# --------------------------------------------------------------------------- authorize


@dataclass(frozen=True)
class Authorization:
    """Proof that every refusal check passed. Only `authorize` makes one; `test_mode` accepts
    it once (M5): a copy, or a second entry, is refused."""

    freeze: Freeze
    repo_root: Path
    data_dir: Path
    results_dir: Path
    code_commit: str
    rerun_reason: str | None
    manifests_sha256: dict[str, str]
    input_sha256: dict[str, str]
    prior_openings: tuple[str, ...] = ()
    exceptions: tuple[str, ...] = ()
    remote_tag: str | None = None
    synthetic: bool = False
    common_dir: Path | None = None
    origin_url: str | None = None
    record_changes: tuple = ()  # N3: accepted bug-fix record changes (dicts)

    @property
    def F(self) -> datetime:
        return self.freeze.test_F

    @property
    def witness_path(self) -> Path:
        return Path(self.common_dir) / WITNESS_REL

    @property
    def lock_path(self) -> Path:
        return Path(self.common_dir) / LOCK_REL

    @property
    def log_path(self) -> Path:
        return self.results_dir / Path(READ_LOG_REL).name

    @property
    def test_results_dir(self) -> Path:
        return self.results_dir / Path(TEST_RESULTS_REL).name

    @property
    def runs_root(self) -> Path:
        return self.repo_root / TEST_RUNS_REL


_ISSUED: dict[int, Authorization] = {}  # issued, not yet used (single use; M5)
_ISSUED_LOCK = threading.Lock()


def _same(a: Path, b: Path) -> bool:
    return Path(a).resolve() == Path(b).resolve()


def _check_roots(root: Path, data: Path, results: Path, synthetic: bool) -> None:
    """I4: real use runs on the repository itself; anything else is a marked synthetic run."""
    if not synthetic:
        problems = []
        if not _same(root, paths.REPO_ROOT):
            problems.append(f"repo_root {root} is not the repository {paths.REPO_ROOT}")
        if not (Path(root) / "lab" / "scripts" / "run_slice.py").exists():
            problems.append("run_slice.py is not under repo_root")
        if not _same(results, paths.REPO_ROOT / "results"):
            problems.append(f"results_dir {results} is not {paths.REPO_ROOT / 'results'}")
        if not _same(data, paths.DATA_DIR):
            problems.append(f"data_dir {data} is not GRIDPILOT_DATA_DIR {paths.DATA_DIR}")
        if problems:
            raise SealError("(I4) " + "; ".join(problems))
        return
    if not (Path(data) / SYNTHETIC_MARKER).exists():
        raise SealError(f"(I4) synthetic=True needs a data dir holding a {SYNTHETIC_MARKER} "
                        f"marker; {data} has none")
    if _same(data, paths.REPO_ROOT / "data") or _same(root, paths.REPO_ROOT):
        raise SealError("(I4) synthetic=True may not use the repository or its data dir")
    if Path(results).resolve().is_relative_to(paths.REPO_ROOT.resolve()):
        raise SealError(f"(N8) synthetic=True may not write into the repository: results_dir "
                        f"{results} is under {paths.REPO_ROOT}")


def _lock_state(path: Path) -> tuple[int | None, bool] | None:
    """None without a lock; else (pid, alive)."""
    if not path.exists():
        return None
    try:
        pid = int(path.read_text().split()[1])
    except (IndexError, ValueError, OSError):
        return None, False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return pid, False
    except PermissionError:
        return pid, True
    return pid, True


def _lock_message(path: Path, pid: int | None, alive: bool) -> str:
    if alive:
        return (f"another test-mode session is open (pid {pid}; lock {path}): wait for it to "
                f"finish")
    return (f"a stale lock {path} from pid {pid}, a session that crashed. Recovery: delete the "
            f"lock, commit only the read log (results/test_reads.jsonl), then rerun with "
            f"--rerun-reason \"<what crashed, and the fix>\"")


def _check_lock(path: Path) -> None:
    st = _lock_state(path)
    if st is not None:
        raise SealError("(a) " + _lock_message(path, *st))


def _load_committed_freeze(root: Path) -> Freeze:
    """M2: the record as committed at HEAD (the clean check guarantees the working copy is the
    same)."""
    raw = committed_bytes(root, FREEZE_REL)
    if raw is None:
        where = "is not committed" if (root / FREEZE_REL).exists() else "does not exist"
        raise SealError(f"no freeze record committed at HEAD ({FREEZE_REL} {where}): the "
                        f"configuration is not frozen")
    return parse_freeze(raw, root / FREEZE_REL)


def _allowed(path: str) -> bool:
    return any(path == a or (a.endswith("/") and path.startswith(a)) for a in POST_FREEZE_PATHS)


def _bad_changes(name_status: str) -> list[str]:
    """Changes other than an addition or a modification of an allowed path (I2)."""
    bad = []
    for line in name_status.splitlines():
        if not line.strip():
            continue
        status, *ps = line.split("\t")
        if status[:1] not in ("A", "M") or not all(_allowed(p) for p in ps):
            bad.append(f"{status} {' '.join(ps)}")
    return bad


def _check_tree(root: Path, freeze: Freeze) -> str:
    """(a) and M2: a clean tree; HEAD is the freeze commit, or descends from it through commits
    that only add or modify the allowed paths; the read log only grows."""
    status = _git_out(root, "status", "--porcelain", "--untracked-files=all")
    if status:
        n = len(status.splitlines())
        raise SealError(f"(a) the working tree is not clean ({n} changed or untracked path(s), "
                        f"e.g. {status.splitlines()[0].strip()!r}): commit or remove them")
    flagged = [ln for ln in _git_out(root, "ls-files", "-v").splitlines()
               if ln[:1].islower() or ln[:1] == "S"]
    if flagged:
        raise SealError(f"(a) files carry skip-worktree or assume-unchanged flags, which hide "
                        f"changes from git: {flagged[:5]}")
    exclude = Path(_git_out(root, "rev-parse", "--git-path", "info/exclude"))
    exclude = exclude if exclude.is_absolute() else root / exclude
    if exclude.exists() and exclude.read_text().strip():
        hidden = _git_out(root, "ls-files", "--others", "--ignored",
                          f"--exclude-from={exclude}").splitlines()
        if hidden:
            raise SealError(f"(a) files hidden by .git/info/exclude: {hidden[:5]}")
    ign = [p for p in _git_out(root, "ls-files", "--others", "--ignored", "--exclude-standard",
                               "--directory", "--", "lab").splitlines()
           if not LAB_IGNORED_OK.search(p)]
    if ign:
        raise SealError(f"(a) ignored files under lab/ (code that git does not see): {ign[:5]}")
    head = _git_out(root, "rev-parse", "HEAD")
    fc = freeze.freeze_commit
    if head != fc:
        if _git(root, "merge-base", "--is-ancestor", fc, head).returncode:
            raise SealError(f"(a) HEAD {head[:12]} is not the freeze commit {fc[:12]} "
                            f"(nor a descendant of it)")
        bad = _bad_changes(_git_out(root, "diff", "--no-renames", "--name-status", fc, head))
        commits = _git_out(root, "rev-list", "--reverse", f"{fc}..{head}").splitlines()
        for c in commits:
            bad += [f"{c[:12]}: {b}" for b in _bad_changes(_git_out(
                root, "diff-tree", "--no-commit-id", "--no-renames", "--name-status", "-r",
                "-m", c))]
        if bad:
            raise SealError(f"(a) HEAD {head[:12]} differs from the freeze commit {fc[:12]} by "
                            f"more than additions/modifications of the freeze record and the "
                            f"test outputs: {sorted(set(bad))[:6]}")
        log_head = committed_bytes(root, READ_LOG_REL) or b""
        for c in commits:
            prev = committed_bytes(root, READ_LOG_REL, c) or b""
            if not log_head.startswith(prev):
                raise SealError(f"(a) the read log at HEAD is not an append-only extension of "
                                f"the log at {c[:12]}: lines were removed or rewritten")
    if _git(root, "ls-files", "--error-unmatch", FREEZE_REL).returncode:
        raise SealError(f"(a) {FREEZE_REL} is not committed")
    return head


def _check_tag(root: Path, freeze: Freeze, head: str, remote_override: str | None,
               synthetic: bool = False) -> tuple[str | None, str | None]:
    """(b) and I3: the annotated tag binds the record to the freeze commit, locally and on
    origin. Returns the remote tag object (or None without an origin)."""
    ref = f"refs/tags/{FREEZE_TAG}"
    kind = _git(root, "cat-file", "-t", ref)
    if kind.returncode:
        raise SealError(f"(b) no tag {FREEZE_TAG!r}: the freeze is not recorded")
    if kind.stdout.strip() != "tag":
        raise SealError(f"(b) {FREEZE_TAG!r} is a lightweight tag; the freeze needs an "
                        f"annotated tag whose message carries the freeze record's sha256")
    msg = _git_out(root, "for-each-ref", ref, "--format=%(contents)")
    m = TAG_LINE.search(msg)
    if not m:
        raise SealError(f"(b) the {FREEZE_TAG!r} tag message has no "
                        f"'config/freeze.json sha256: <hex>' line")
    if m.group(1) != freeze.sha256:
        raise SealError(f"(b) config/freeze.json sha256 {freeze.sha256[:12]} does not match the "
                        f"{FREEZE_TAG!r} tag ({m.group(1)[:12]})")
    tagged = _git_out(root, "rev-parse", f"{ref}^{{commit}}")
    rec_commit = _git_out(root, "log", "-1", "--format=%H", "--", FREEZE_REL)
    if tagged != rec_commit:
        raise SealError(f"(b) the {FREEZE_TAG!r} tag targets {tagged[:12]}, not the last commit "
                        f"that touched {FREEZE_REL} ({rec_commit[:12]})")
    parents = _git_out(root, "rev-list", "--parents", "-n", "1", rec_commit).split()[1:]
    if parents != [freeze.freeze_commit]:
        raise SealError(f"(b) the freeze-record commit {rec_commit[:12]} must have exactly one "
                        f"parent, the freeze commit {freeze.freeze_commit[:12]}; it has "
                        f"{[p[:12] for p in parents]}")
    only = _git_out(root, "diff-tree", "--no-commit-id", "--no-renames", "--name-status", "-r",
                    rec_commit).splitlines()
    if [ln.split("\t", 1)[-1] for ln in only] != [FREEZE_REL]:
        raise SealError(f"(b) the freeze-record commit {rec_commit[:12]} must change only "
                        f"{FREEZE_REL}: {only[:5]}")
    if _git(root, "merge-base", "--is-ancestor", tagged, head).returncode:
        raise SealError(f"(b) the {FREEZE_TAG!r} tag ({tagged[:12]}) is not HEAD or an ancestor")
    url = _git(root, "remote", "get-url", "origin")
    if url.returncode:
        if synthetic:
            return None, None
        raise SealError(f"(b) the repository has no origin; it must be {GITHUB_ORIGIN} (N5)")
    origin = url.stdout.strip()
    if not synthetic and origin != GITHUB_ORIGIN:
        raise SealError(f"(b) origin is {origin}, not {GITHUB_ORIGIN} (N5)")
    local_obj = _git_out(root, "rev-parse", ref)
    failed, out = True, ""
    for _ in range(2):  # N5: retry once
        try:
            r = _git(root, "ls-remote", "origin", ref, timeout=60)
            failed, out = r.returncode != 0, r.stdout
        except subprocess.TimeoutExpired:
            failed, out = True, ""
        if not failed:
            break
    if failed:
        if remote_override:
            return f"unverified: {remote_override}", origin
        raise SealError(f"(b) cannot reach origin to verify the {FREEZE_TAG!r} tag; fix the "
                        f"network, or pass --remote-tag-override \"<reason>\" (logged)")
    # N5: the exact refname line, never a decoy ref ending in the same path
    exact = [ln.split("\t") for ln in out.splitlines() if ln.split("\t")[-1:] == [ref]]
    remote_obj = exact[0][0] if exact else None
    if remote_obj != local_obj:
        raise SealError(f"(b) the {FREEZE_TAG!r} tag on origin ({str(remote_obj)[:12]}) differs "
                        f"from the local tag ({local_obj[:12]}): push it, or the local tag was "
                        f"moved")
    return remote_obj, origin


def _check_manifests(root: Path, freeze: Freeze) -> dict[str, str]:
    """B7: the committed snapshot and manifests (git at HEAD) agree with the freeze record."""
    raw = committed_bytes(root, SNAPSHOT_REL)
    if raw is None:
        raise SealError(f"(B7) {SNAPSHOT_REL} is not committed at HEAD")
    snap = json.loads(raw)
    if snap.get("snapshot_id") != freeze.snapshot_id:
        raise SealError(f"(B7) committed snapshot {snap.get('snapshot_id')} != the freeze "
                        f"record's {freeze.snapshot_id}")
    sources = snap.get("sources") or {}
    if snapshot_id_of(sources) != snap["snapshot_id"]:
        raise SealError("(B7) the committed snapshot's id does not match its own manifest hashes")
    growing = [k for k, v in sources.items() if v.get("status") != "frozen"]
    if growing:
        raise SealError(f"(B7) the snapshot has non-frozen manifests {growing}: refresh it")
    man = committed_manifests(root)
    for name, rec in sources.items():
        got = man.get(f"{name}.json")
        if got != rec["manifest_sha256"]:
            raise SealError(f"(B7) committed data/manifests/{name}.json ({str(got)[:12]}) does "
                            f"not match the snapshot ({rec['manifest_sha256'][:12]})")
    return man


def _check_manifest_inputs(root: Path, freeze: Freeze) -> tuple[str, ...]:
    """I5: each test input a committed manifest lists has that manifest's sha256; the balance
    table matches its committed derivation record. Returns the logged exceptions."""
    entries = manifest_entries(root)
    rec = freeze.input_sha256
    extra = [r for r in rec if r.startswith(WEATHER_SLC_REL + "/")]
    for rel in (*TEST_INPUTS, *extra):
        if rel in entries and rec.get(rel) != entries[rel][1]:
            raise SealError(f"(I5) the freeze record's sha256 for {rel} differs from the "
                            f"committed manifest {entries[rel][0]} ({entries[rel][1][:12]})")
    raw = committed_bytes(root, BALANCE_DERIVATION_REL)
    if raw is None:
        msg = (f"{BALANCE_REL}: no committed derivation record ({BALANCE_DERIVATION_REL}); "
               f"its hash is checked against the freeze record only, until T12's rebuild "
               f"commits one (documented exception, I5)")
        return (msg,)
    der = json.loads(raw)
    if der.get("output") != BALANCE_REL or der.get("output_sha256") != rec.get(BALANCE_REL):
        raise SealError(f"(I5) the balance derivation record's output hash differs from the "
                        f"freeze record's {BALANCE_REL}")
    for r, h in (der.get("inputs_sha256") or {}).items():
        if r in entries and entries[r][1] != h:
            raise SealError(f"(I5) the balance derivation input {r} differs from the committed "
                            f"manifest {entries[r][0]}")
    if not der.get("inputs_sha256"):
        raise SealError("(I5) the balance derivation record lists no raw inputs")
    return ()


def _check_scenario(freeze: Freeze) -> None:
    from gridpilot.scenario import Scenario  # deferred: scenario imports the simulator

    code = json.loads(json.dumps(Scenario.primary().config()))
    if freeze.scenario_catalog["primary"] != code:
        raise SealError("the code's primary scenario differs from the frozen scenario catalog")


def _check_validation_ref(root: Path, freeze: Freeze) -> None:
    """M3: the validation reference is the committed registered run and its serialized
    metrics' canonical hash."""
    want = validation_reference(root)
    if freeze.raw["validation_run"] != want:
        raise SealError(f"(M3) validation_run {freeze.raw['validation_run']} does not match the "
                        f"committed results at HEAD {want}")


def _check_inputs(freeze: Freeze, data_dir: Path, synthetic: bool = False) -> dict[str, str]:
    """(c) Every input file's sha256 matches the freeze record. N8: a synthetic run's inputs
    must really live in its marked data dir (no symlink into a real one)."""
    rec = freeze.input_sha256
    if synthetic:
        real = Path(paths.DATA_DIR).resolve()
        real_marked = (real / SYNTHETIC_MARKER).exists()
        for rel in rec:
            rp = (data_dir / rel).resolve()
            if not rp.is_relative_to(Path(data_dir).resolve()):
                raise SealError(f"(N8) synthetic input {rel} resolves outside the synthetic data "
                                f"dir: {rp}")
            if not real_marked and rp.is_relative_to(real):
                raise SealError(f"(N8) synthetic input {rel} resolves into GRIDPILOT_DATA_DIR "
                                f"{real}")
    missing = [r for r in TEST_INPUTS if r not in rec]
    if missing:
        raise SealError(f"(c) the freeze record has no hash for the test inputs {missing}")
    for rel, want in sorted(rec.items()):
        p = data_dir / rel
        if not p.exists():
            raise SealError(f"(c) input {rel} is missing from {data_dir}")
        got = file_sha256(p)
        if got != want:
            raise SealError(f"(c) input {rel} changed since the freeze: sha256 {got[:12]} != "
                            f"{want[:12]}")
    return rec


def _witness_events(root: Path) -> list[dict]:
    w = git_common_dir(root) / WITNESS_REL
    return read_log_events(w.read_bytes() if w.exists() else None)


def prior_openings(root: Path, data_dir: Path, results_dir: Path) -> list[str]:
    """I1, N1, N4: every trace of an earlier opening of the sealed window, including the
    witness in the git common dir that every worktree shares."""
    out = []
    n_w = sum(r.get("event") in OPENING_EVENTS for r in _witness_events(root))
    if n_w:
        out.append(f"the shared witness ({WITNESS_REL} in the git common dir) holds {n_w} "
                   f"invocation(s)")
    log = results_dir / Path(READ_LOG_REL).name
    for where, raw in (("working-tree read log", log.read_bytes() if log.exists() else None),
                       ("committed read log", committed_bytes(root, READ_LOG_REL))):
        ev = [r.get("event") for r in read_log_events(raw)]
        n = sum(e in OPENING_EVENTS for e in ev)
        if n:
            out.append(f"{where} holds {n} invocation/read line(s)")
    hist = _git_out(root, "log", "--all", "--reflog", "--full-history", "--format=%h", "--",
                    f"{TEST_RESULTS_REL}/{COMPLETED_MARKER}", READ_LOG_REL).split()
    if hist:
        out.append(f"git history touches the test outputs ({len(hist)} commit(s), "
                   f"e.g. {hist[0]})")
    if (results_dir / Path(TEST_RESULTS_REL).name / COMPLETED_MARKER).exists():
        out.append(f"{TEST_RESULTS_REL}/{COMPLETED_MARKER} exists")
    if (data_dir / LEGACY_CARBON_TEST_REL).exists():
        out.append(f"the test carbon table {LEGACY_CARBON_TEST_REL} exists in the data dir")
    runs = root / TEST_RUNS_REL
    if runs.is_dir() and any(runs.iterdir()):
        out.append(f"{TEST_RUNS_REL}/ holds {len(list(runs.iterdir()))} entr(ies)")
    return out


def _earlier_record(root: Path, sha: str, events: list[dict]) -> dict | None:
    """The earlier freeze record with this sha256: logged with its invocation, or any version
    of config/freeze.json in git history (reflog included)."""
    for r in events:
        if r.get("config_sha256") == sha and isinstance(r.get("freeze_record"), dict):
            return r["freeze_record"]
    revs = _git_out(root, "log", "--all", "--reflog", "--format=%H", "--", FREEZE_REL).split()
    for c in revs:
        raw = committed_bytes(root, FREEZE_REL, c)
        if raw is not None and hashlib.sha256(raw).hexdigest() == sha:
            return json.loads(raw)
    return None


def _check_configs(root: Path, results_dir: Path, freeze: Freeze,
                   reason: str | None) -> tuple[dict, ...]:
    """I3 and N3: an earlier invocation used a different freeze record only as a bug-fix rerun
    (lead ruling): with a rerun reason, identical decision fields, a new freeze commit that
    descends from the old one, and only freeze_commit / frozen_at / validation_run changed.
    Returns the accepted changes (logged)."""
    log = results_dir / Path(READ_LOG_REL).name
    events = (read_log_events(log.read_bytes() if log.exists() else None)
              + read_log_events(committed_bytes(root, READ_LOG_REL)) + _witness_events(root))
    other = sorted({r.get("config_sha256") for r in events
                    if r.get("event") in OPENING_EVENTS and r.get("config_sha256")}
                   - {freeze.sha256})
    changes = []
    for sha in other:
        old = _earlier_record(root, sha, events)
        if old is None:
            raise SealError(f"(b) an earlier invocation used freeze record {sha[:12]}, which is "
                            f"neither logged nor in git history: it cannot be compared")
        new = freeze.raw
        diff = {k: [old.get(k), new.get(k)] for k in sorted(set(old) | set(new))
                if old.get(k) != new.get(k)}
        if not reason:
            raise SealError(f"(b) an earlier invocation used a different freeze record "
                            f"({sha[:12]}; changed: {sorted(diff)}); a bug-fix rerun needs "
                            f"--rerun-reason")
        bad = [k for k in diff if k not in RERUN_MUTABLE]
        if bad:
            raise SealError(f"(b) the freeze record changed {bad} since an earlier opening "
                            f"({sha[:12]}); a bug-fix rerun may change only "
                            f"{sorted(RERUN_MUTABLE)} (N3)")
        oc, nc = old.get("freeze_commit"), new.get("freeze_commit")
        if oc != nc and _git(root, "merge-base", "--is-ancestor", str(oc), nc).returncode:
            raise SealError(f"(b) the new freeze commit {nc[:12]} does not descend from the "
                            f"earlier one {str(oc)[:12]} (N3)")
        changes.append({"old_sha256": sha, "new_sha256": freeze.sha256, "changed": diff})
    return tuple(changes)


def _check_outputs(prior: list[str], rerun_reason: str | None) -> str | None:
    """(d) A prior opening requires a rerun reason (D-059)."""
    reason = rerun_reason.strip() if rerun_reason else None
    if rerun_reason is not None and not reason:
        raise SealError("(d) --rerun-reason must not be empty")
    if prior and not reason:
        raise SealError(f"(d) the sealed window was already opened ({'; '.join(prior)}); it is "
                        f"evaluated once. Pass --rerun-reason \"<text>\" to rerun, and the reason "
                        f"is logged")
    return reason


def authorize(*, repo_root: Path | None = None, data_dir: Path | None = None,
              results_dir: Path | None = None, rerun_reason: str | None = None,
              remote_tag_override: str | None = None, synthetic: bool = False) -> Authorization:
    """Run every refusal check (roots, freeze record, a, b, B7/I5, scenario, validation
    reference, c, prior openings and d) and return the single-use authorization `test_mode`
    needs. Raises SealError with the reason on the first failure; any unexpected error is
    wrapped as a SealError too (M11). Nothing here reads a sealed value: it hashes files and
    reads git."""
    try:
        return _authorize(repo_root, data_dir, results_dir, rerun_reason, remote_tag_override,
                          synthetic)
    except SealError:
        raise
    except Exception as e:  # M11: every failure is a refusal with a reason
        raise SealError(f"authorize failed: {type(e).__name__}: {e}") from e


def _authorize(repo_root, data_dir, results_dir, rerun_reason, remote_override, synthetic):
    root = Path(repo_root or paths.REPO_ROOT)
    data = Path(data_dir or paths.DATA_DIR)
    results = Path(results_dir or root / "results")
    _check_roots(root, data, results, synthetic)
    freeze = _load_committed_freeze(root)
    common = git_common_dir(root)
    _check_lock(common / LOCK_REL)
    head = _check_tree(root, freeze)
    remote, origin = _check_tag(root, freeze, head, remote_override, synthetic)
    manifests = _check_manifests(root, freeze)
    exceptions = _check_manifest_inputs(root, freeze)
    _check_scenario(freeze)
    _check_validation_ref(root, freeze)
    inputs = _check_inputs(freeze, data, synthetic)
    prior = prior_openings(root, data, results)
    reason = _check_outputs(prior, rerun_reason)
    changes = _check_configs(root, results, freeze, reason)
    auth = Authorization(freeze=freeze, repo_root=root, data_dir=data, results_dir=results,
                         code_commit=head, rerun_reason=reason, manifests_sha256=manifests,
                         input_sha256=inputs, prior_openings=tuple(prior),
                         exceptions=exceptions, remote_tag=remote, synthetic=synthetic,
                         common_dir=common, origin_url=origin, record_changes=changes)
    with _ISSUED_LOCK:
        _ISSUED[id(auth)] = auth
    return auth


# --------------------------------------------------------------------------- test mode


@dataclass
class Session:
    """The active test-mode context (one per entry-point invocation)."""

    auth: Authorization
    session_id: str
    pid: int
    thread: int
    run_id: str | None = None
    work_dir: Path | None = None  # the test run directory being written (holds the test table)
    run_dirs: list[Path] = field(default_factory=list)
    rc: int | None = None
    exported: bool = False
    n_reads: int = 0
    built: dict[str, str] = field(default_factory=dict)
    closed: bool = False  # N6: a captured context cannot revive a closed session
    scopes: list[str] = field(default_factory=list)  # purpose labels (`purpose_scope`, T20)

    @property
    def F(self) -> datetime:
        return self.auth.F

    @property
    def freeze(self) -> Freeze:
        return self.auth.freeze

    @property
    def data_dir(self) -> Path:
        return self.auth.data_dir

    @property
    def log_path(self) -> Path:
        return self.auth.log_path

    @property
    def carbon_test_path(self) -> Path:
        """The test carbon table, inside the test run directory (I6), never the shared data
        dir."""
        if self.work_dir is None:
            raise SealError("the session has no test run directory for the test carbon table")
        return Path(self.work_dir) / CARBON_TEST_NAME

    def data_path(self, rel: str) -> Path:
        return self.auth.data_dir / rel

    def register_built(self, path: Path) -> str:
        """Record a file this session built (e.g. the test carbon table) so that
        `sealed_read` may read it back; returns its sha256."""
        sha = file_sha256(path)
        self.built[str(Path(path).resolve())] = sha
        return sha

    def _check_input(self, path: Path, sha: str) -> None:
        resolved = str(path.resolve())
        if resolved in self.built:
            if self.built[resolved] != sha:
                raise SealError(f"{path} changed after this session built it")
            return
        try:
            rel = path.resolve().relative_to(self.data_dir.resolve()).as_posix()
        except ValueError:
            rel = None
        want = self.auth.input_sha256.get(rel) if rel else None
        if want is None:
            raise SealError(f"{path} is neither a frozen input nor built in this session")
        if want != sha:
            raise SealError(f"{path} changed since the freeze (sha256 {sha[:12]} != "
                            f"{want[:12]})")


_SESSION: contextvars.ContextVar[Session | None] = contextvars.ContextVar("gridpilot_seal",
                                                                         default=None)


def active() -> Session | None:
    """The active test-mode session of this process and thread, or None (M6)."""
    s = _SESSION.get()
    if (s is None or s.closed or s.pid != os.getpid()
            or s.thread != threading.get_ident()):
        return None
    return s


def require_active(what: str) -> Session:
    s = active()
    if s is None:
        raise SealError(f"{what}: the sealed test window opens only inside the logged test-mode "
                        f"context, which only `run_slice --window test` enters (same process "
                        f"and thread)")
    return s


def _fsync_dir(d: Path) -> None:
    fd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _append(path: Path, record: dict) -> None:
    """Append one JSONL line ("a" mode) and fsync it before returning; fsync the directory
    when the log is created (M7)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    line = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())
    if new:
        _fsync_dir(path.parent)


def _base_record(s: Session, event: str) -> dict:
    return {"event": event, "utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "session": s.session_id, "code_commit": s.auth.code_commit,
            "config_sha256": s.freeze.sha256, "freeze_commit": s.freeze.freeze_commit}


def log_event(event: str, **fields: Any) -> None:
    """Append a non-read event (e.g. the run id, an export) to the active session's log."""
    s = require_active(f"log_event({event})")
    _append(s.log_path, _base_record(s, event) | fields)


def _lock(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as e:
        st = _lock_state(path) or (None, False)
        raise SealError(_lock_message(path, *st)) from e
    with os.fdopen(fd, "w") as f:
        f.write(f"pid {os.getpid()} {datetime.now(UTC).isoformat()}\n")


def _read_only(dirs: Sequence[Path]) -> None:
    """I6: the test run directory's files become read-only (0444) when the context closes."""
    for d in dirs:
        if not Path(d).is_dir():
            continue
        for p in Path(d).rglob("*"):
            if p.is_file() and not p.is_symlink():
                p.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


@contextmanager
def test_mode(auth: Authorization) -> Iterator[Session]:
    """The active test-mode context. Logs the invocation (with any rerun reason, prior
    openings and exceptions) on entry and the outcome on exit (M1: `rc`, `exported`)."""
    with _ISSUED_LOCK:
        ok = isinstance(auth, Authorization) and _ISSUED.get(id(auth)) is auth
        if ok:
            del _ISSUED[id(auth)]  # single use (M5)
    if not ok:
        raise SealError("test_mode needs an unused Authorization that `authorize` returned "
                        "(a copy, or a second entry, is refused)")
    if active() is not None or _SESSION.get() is not None:
        raise SealError("test mode is already active")
    lock = auth.lock_path
    _lock(lock)
    s = Session(auth=auth, session_id=uuid.uuid4().hex[:16], pid=os.getpid(),
                thread=threading.get_ident())
    try:
        # N7: re-check, under the lock, that nothing was opened since the authorization
        now = prior_openings(auth.repo_root, auth.data_dir, auth.results_dir)
        new = [p for p in now if p not in auth.prior_openings]
        if new:
            raise SealError(f"(d) the sealed window was opened after this authorization "
                            f"({'; '.join(new)}): authorize again")
        inv = _base_record(s, "invocation") | {
            "test_F": iso(auth.F), "rerun_reason": auth.rerun_reason,
            "prior_openings": list(auth.prior_openings), "exceptions": list(auth.exceptions),
            "remote_tag": auth.remote_tag, "origin_url": auth.origin_url,
            "synthetic": auth.synthetic, "record_changes": list(auth.record_changes),
            "freeze_record": auth.freeze.raw, "repo_root": str(auth.repo_root),
            "results_dir": str(auth.results_dir),
            "inputs_sha256": auth.input_sha256, "manifests_sha256": auth.manifests_sha256,
            "argv": list(sys.argv)}
        _append(auth.witness_path, inv)  # N1: the shared witness first, before any read
        _append(s.log_path, inv)
    except BaseException:
        lock.unlink(missing_ok=True)
        raise
    token = _SESSION.set(s)
    outcome = "error"
    try:
        yield s
        outcome = "ok" if s.rc in (None, 0) else f"rc={s.rc}"
    except BaseException as e:
        outcome = f"error: {type(e).__name__}: {e}"[:500]
        raise
    finally:
        s.closed = True
        _SESSION.reset(token)
        try:
            _read_only(s.run_dirs)
            close = _base_record(s, "close") | {
                "outcome": outcome, "rc": s.rc, "exported": s.exported, "n_reads": s.n_reads,
                "run_id": s.run_id, "run_dirs": [str(d) for d in s.run_dirs]}
            _append(s.log_path, close)
            _append(auth.witness_path, close)
        finally:
            lock.unlink(missing_ok=True)


@contextmanager
def purpose_scope(label: str) -> Iterator[None]:
    """Label every sealed read inside the block with `label` (T20: the pre-registered D-071
    item it serves). The logged purpose becomes '<label>: <purpose>' and the line carries
    `scope`. Needs the active session; it changes no check and no refusal."""
    s = require_active("purpose_scope")
    if not isinstance(label, str) or not label.strip():
        raise SealError("purpose_scope needs a label")
    s.scopes.append(label.strip())
    try:
        yield
    finally:
        s.scopes.pop()


def read_end() -> datetime:
    """The exclusive bound a value may reach: F_test inside the active test-mode session (where
    sealed rows arrive only through `sealed_read`), TEST_START otherwise (T20)."""
    s = active()
    return s.F if s is not None else TEST_START


def _caller() -> str:
    """module:function:line of the first frame outside this module."""
    f = sys._getframe(1)
    here = __file__
    while f is not None and f.f_code.co_filename == here:
        f = f.f_back
    if f is None:
        return "unknown"
    return f"{f.f_globals.get('__name__', '?')}:{f.f_code.co_name}:{f.f_lineno}"


def _aware(t: datetime, what: str) -> datetime:
    if not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None:
        raise SealError(f"{what} must be a timezone-aware datetime, got {t!r}")
    return t.astimezone(UTC)


def sealed_read(path: Path | str, *, purpose: str, columns: Sequence[str],
                time_range: tuple[datetime, datetime], ts_col: str = "ts_utc",
                where: pl.Expr | None = None,
                reader: Callable[[io.BytesIO], pl.DataFrame] | None = None) -> pl.DataFrame:
    """Rows of `path` with `ts_col` in [time_range) (and `where`), as `columns`.

    The only function allowed to return rows at or after TEST_START. Refuses outside the
    active test-mode context, past F, and on any file that is not a frozen input (or built in
    this session) with its recorded sha256. It reads the bytes once, hashes them, appends one
    fsynced JSONL line to `results/test_reads.jsonl`, and parses the same bytes (M7). Parquet
    is scanned; any other format needs a `reader(buffer) -> DataFrame` (e.g. the BA-workbook
    parser)."""
    s = require_active("sealed_read")
    if not isinstance(purpose, str) or not purpose.strip():
        raise SealError("sealed_read needs a purpose")
    cols = list(columns)
    if not cols:
        raise SealError("sealed_read needs the columns it reads")
    start, end = (_aware(t, "time_range") for t in time_range)
    if not start < end:
        raise SealError(f"empty time range [{start}, {end})")
    if end > s.F:
        raise SealError(f"time range ends {iso(end)}, after the test cutoff F {iso(s.F)}")
    path = Path(path)
    if reader is None and path.suffix != ".parquet":
        raise SealError(f"{path.name}: sealed_read needs a reader for {path.suffix} files")
    buf = path.read_bytes()
    sha = hashlib.sha256(buf).hexdigest()
    s._check_input(path, sha)
    scope = " · ".join(s.scopes) or None
    _append(s.log_path, _base_record(s, "read") | {
        "purpose": f"{scope}: {purpose.strip()}" if scope else purpose.strip(), "scope": scope,
        "path": str(path), "sha256": sha, "columns": cols,
        "ts_col": ts_col, "time_range": [iso(start), iso(end)],
        "filter": None if where is None else str(where), "caller": _caller(),
        "run_id": s.run_id})
    s.n_reads += 1
    lazy = (reader(io.BytesIO(buf)).lazy() if reader is not None
            else pl.scan_parquet(io.BytesIO(buf)))
    lazy = lazy.filter((pl.col(ts_col) >= start) & (pl.col(ts_col) < end))
    if where is not None:
        lazy = lazy.filter(where)
    return lazy.select(cols).collect()


def data_path(rel: str) -> Path:
    """`rel` under the active session's data directory (test mode), else gridpilot.paths."""
    s = active()
    return (s.data_dir if s else paths.DATA_DIR) / rel


def last_export(results_dir: Path) -> dict | None:
    """The last `export` line of the read log (M8), or None."""
    log = Path(results_dir) / Path(READ_LOG_REL).name
    ex = [r for r in read_log_events(log.read_bytes() if log.exists() else None)
          if r.get("event") == "export"]
    return ex[-1] if ex else None


def verify_exports(results_dir: Path) -> list[str]:
    """M8: problems between results/test/*.json and the sha256 the last export line logged
    (empty = verified)."""
    ex = last_export(results_dir)
    if ex is None:
        return ["the read log has no export line"]
    out = Path(results_dir) / Path(TEST_RESULTS_REL).name
    want = ex.get("artifacts_sha256") or {}
    probs = []
    for name, h in want.items():
        p = out / name
        if not p.exists():
            probs.append(f"{name} is missing")
        elif file_sha256(p) != h:
            probs.append(f"{name} differs from the logged export")
    extra = sorted(p.name for p in out.glob("*.json") if p.name not in want)
    probs += [f"{n} was not in the logged export" for n in extra]
    return probs


__all__ = [
    "TEST_FIT_AT",
    "TEST_HISTORY_START",
    "TEST_INIT",
    "TEST_INPUTS",
    "Authorization",
    "Freeze",
    "SealError",
    "Session",
    "active",
    "authorize",
    "balance_derivation",
    "freeze_errors",
    "freeze_tag_message",
    "load_freeze",
    "log_event",
    "prior_openings",
    "purpose_scope",
    "read_end",
    "require_active",
    "sealed_read",
    "test_mode",
    "validation_reference",
    "verify_exports",
]
