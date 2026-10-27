"""The seal on the test window (AGENTS.md "Data rules"; spec §5, §12, F8; Stage 3 T11).

The sealed test window [2025-11-01T00Z, 2026-11-01T00Z) opens only through one logged entry
point, after a recorded configuration freeze:

1. **The freeze record** `config/freeze.json` (schema `config/freeze.schema.json`, written by
   T12) holds the freeze commit, the deployed policy and its §8 rule trace, the frozen L
   `max_leaf_nodes` per series, the test cutoff `test_F`, the test fit time and history start,
   the S ranking and its window, the scenario catalog, the snapshot id, every input file's
   sha256, and the validation run id and canonical hash. `load_freeze` validates it.
2. **`authorize`** runs the refusal checks and returns the only object `test_mode` accepts:
   (a) HEAD is the freeze commit (or differs from it only in `config/freeze.json` and the test
   outputs) and the tree is clean; (b) the sha256 of `config/freeze.json` matches the
   annotated tag `config-freeze`; (c) every input file's sha256 matches the record; (d)
   `results/test/` holds no completed run unless a rerun reason is given. B7: the snapshot and
   the data manifests are read from git at HEAD, never from the data directory, and must agree
   with the record. Any failure raises `SealError` with the reason.
3. **`test_mode(auth)`** is the active test-mode context. Only `run_slice --window test` (the
   entry point) enters it; a static test checks that no other module calls it.
4. **`sealed_read(path, *, purpose, columns, time_range)`** is the only function that returns
   rows at or after TEST_START. It refuses outside the context. Before returning anything it
   appends one JSONL line to `results/test_reads.jsonl` (UTC time, purpose, path, the file's
   sha256, columns, time range, code commit, config hash and caller), opened with "a" and
   fsynced after each write. It reads only frozen inputs (or files built in this session) whose
   sha256 still matches.

Inside the context, `gridpilot.window.Window.test()` is constructible; outside it raises.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
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
TEST_RUNS_REL = "runs/test"
COMPLETED_MARKER = "manifest.json"  # results/test/manifest.json = a completed test run
# Paths that may be committed after the freeze commit without reopening (a): the freeze record
# itself and the test outputs.
POST_FREEZE_PATHS = (FREEZE_REL, f"{TEST_RESULTS_REL}/", READ_LOG_REL)
MANIFESTS_REL = "data/manifests"
SNAPSHOT_REL = f"{MANIFESTS_REL}/snapshot.json"
# Input files the test run reads (paths relative to the data directory). Each must be in the
# freeze record with its sha256.
CORE_BAS = ("PACE", "CISO", "BPAT", "NEVP")
WORKBOOK_REL = "raw/eia930/ba_workbooks/{ba}.xlsx"
BALANCE_REL = "interim/eia930/balance.parquet"
TRACE_REL = "raw/traces/acme/trace_seren.csv"
TEST_INPUTS = tuple(WORKBOOK_REL.format(ba=ba) for ba in CORE_BAS) + (BALANCE_REL, TRACE_REL)
SERIES = ("PACE/ci_consumed", "CISO/ci_consumed", "BPAT/ci_consumed", "NEVP/ci_consumed",
          "PACE/demand", "PACE/wind", "PACE/solar")  # = forecast.RUN_SERIES
LEAF_NODES = (15, 31)  # = forecast.MAX_LEAF_NODES
SITES = ("PACE", "BPAT", "CISO", "NEVP")
SELECTION_POLICIES = ("U", "G", "S", "K", "W", "L")  # spec §8 deployment candidates
TAG_LINE = re.compile(r"config/freeze\.json sha256: ([0-9a-f]{64})")

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX12 = re.compile(r"^[0-9a-f]{12}$")
_RUN_ID = re.compile(r"^\d{8}T\d{6}Z$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_KEYS = ("schema", "freeze_commit", "frozen_at", "deployed_policy", "L_max_leaf_nodes", "test_F",
         "test_fit_at", "test_history_start", "s_ranking", "scenario_catalog", "snapshot_id",
         "input_sha256", "validation_run")


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


def freeze_errors(d: Any) -> list[str]:
    """Every way `d` fails the freeze-record contract (config/freeze.schema.json, plus the
    cross-field rules a JSON schema cannot state)."""
    if not isinstance(d, dict):
        return ["the record is not a JSON object"]
    errs = [f"missing key {k!r}" for k in _KEYS if k not in d]
    errs += [f"unknown key {k!r}" for k in d if k not in _KEYS]
    if errs:
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
    t("frozen_at")
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
    elif any(v not in LEAF_NODES or isinstance(v, bool) for v in leaf.values()):
        errs.append(f"L_max_leaf_nodes values must be one of {LEAF_NODES}")
    F = t("test_F")
    if F is not None:
        if not TEST_START < F <= TEST_END:
            errs.append(f"test_F {d['test_F']} must lie in ({iso(TEST_START)}, {iso(TEST_END)}]")
        if F.hour or F.minute or F.second:
            errs.append("test_F must be a UTC midnight (the last complete day ends there)")
    fit = t("test_fit_at")
    if fit is not None and fit != TEST_FIT_AT:
        errs.append(f"test_fit_at must be {iso(TEST_FIT_AT)} (spec §5)")
    hs = t("test_history_start")
    if hs is not None and hs != TEST_HISTORY_START:
        errs.append(f"test_history_start must be {iso(TEST_HISTORY_START)} (spec §5)")
    sr = d["s_ranking"]
    if not isinstance(sr, dict) or sorted(sr.get("order") or []) != sorted(SITES):
        errs.append(f"s_ranking.order must be a permutation of {SITES}")
    elif not isinstance(sr.get("window"), list) or len(sr["window"]) != 2:
        errs.append("s_ranking.window must be [start, end]")
    else:
        try:
            a, b = (parse_utc(x, "s_ranking.window") for x in sr["window"])
            if not a < b <= TEST_START:
                errs.append("s_ranking.window must be a pre-seal range (end <= TEST_START)")
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
            if Path(k).is_absolute() or ".." in Path(k).parts:
                errs.append(f"input_sha256 key {k!r} must be relative to the data directory")
    vr = d["validation_run"]
    if (not isinstance(vr, dict) or set(vr) != {"run_id", "metrics_canonical_sha256"}
            or not _RUN_ID.match(str(vr.get("run_id")))
            or not _HEX64.match(str(vr.get("metrics_canonical_sha256")))):
        errs.append("validation_run must be {run_id, metrics_canonical_sha256}")
    return errs


def load_freeze(path: Path | str | None = None) -> Freeze:
    """Read and validate `config/freeze.json` (default: the repository's). Raises SealError."""
    path = Path(path) if path else paths.REPO_ROOT / FREEZE_REL
    if not path.exists():
        raise SealError(f"no freeze record at {path}: the configuration is not frozen")
    raw = path.read_bytes()
    try:
        d = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SealError(f"freeze record {path} is not valid JSON: {e}") from e
    errs = freeze_errors(d)
    if errs:
        raise SealError(f"freeze record {path} is invalid: {'; '.join(errs)}")
    return Freeze(raw=d, sha256=hashlib.sha256(raw).hexdigest(), path=path)


# --------------------------------------------------------------------------- git


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          check=False)


def _git_out(root: Path, *args: str) -> str:
    r = _git(root, *args)
    if r.returncode:
        raise SealError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


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


def snapshot_id_of(sources: dict[str, dict]) -> str:
    """The snapshot id rule of scripts/snapshot_manifests.py."""
    return hashlib.sha256(json.dumps({k: v["manifest_sha256"] for k, v in sources.items()},
                                     sort_keys=True).encode()).hexdigest()[:12]


# --------------------------------------------------------------------------- authorize


@dataclass(frozen=True)
class Authorization:
    """Proof that every refusal check passed. Only `authorize` makes one, and `test_mode`
    accepts nothing else."""

    freeze: Freeze
    repo_root: Path
    data_dir: Path
    results_dir: Path
    code_commit: str
    rerun_reason: str | None
    manifests_sha256: dict[str, str]
    input_sha256: dict[str, str]
    _token: object = field(repr=False, compare=False, default=None)

    @property
    def F(self) -> datetime:
        return self.freeze.test_F

    @property
    def log_path(self) -> Path:
        return self.results_dir / Path(READ_LOG_REL).name

    @property
    def test_results_dir(self) -> Path:
        return self.results_dir / Path(TEST_RESULTS_REL).name


_TOKEN = object()


def _check_tree(root: Path, freeze: Freeze) -> str:
    """(a) HEAD is the freeze commit, or differs from it only in POST_FREEZE_PATHS; the tree
    is clean (untracked files count)."""
    status = _git_out(root, "status", "--porcelain")
    if status:
        n = len(status.splitlines())
        raise SealError(f"(a) the working tree is not clean ({n} changed or untracked path(s), "
                        f"e.g. {status.splitlines()[0].strip()!r}): commit or remove them")
    head = _git_out(root, "rev-parse", "HEAD")
    fc = freeze.freeze_commit
    if head != fc:
        if _git(root, "merge-base", "--is-ancestor", fc, head).returncode:
            raise SealError(f"(a) HEAD {head[:12]} is not the freeze commit {fc[:12]} "
                            f"(nor a descendant of it)")
        changed = _git_out(root, "diff", "--name-only", fc, head).splitlines()
        bad = [p for p in changed if not any(p == a or (a.endswith("/") and p.startswith(a))
                                             for a in POST_FREEZE_PATHS)]
        if bad:
            raise SealError(f"(a) HEAD {head[:12]} differs from the freeze commit {fc[:12]} "
                            f"outside the freeze record and the test outputs: {bad[:5]}")
    if _git(root, "ls-files", "--error-unmatch", FREEZE_REL).returncode:
        raise SealError(f"(a) {FREEZE_REL} is not committed")
    return head


def _check_tag(root: Path, freeze: Freeze, head: str) -> None:
    """(b) The annotated tag `config-freeze` carries the sha256 of config/freeze.json."""
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
    if _git(root, "merge-base", "--is-ancestor", tagged, head).returncode:
        raise SealError(f"(b) the {FREEZE_TAG!r} tag ({tagged[:12]}) is not HEAD or an ancestor")


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


def _check_scenario(freeze: Freeze) -> None:
    from gridpilot.scenario import Scenario  # deferred: scenario imports the simulator

    code = json.loads(json.dumps(Scenario.primary().config()))
    if freeze.scenario_catalog["primary"] != code:
        raise SealError("the code's primary scenario differs from the frozen scenario catalog")


def _check_inputs(freeze: Freeze, data_dir: Path) -> dict[str, str]:
    """(c) Every input file's sha256 matches the freeze record."""
    rec = freeze.input_sha256
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


def _check_outputs(results_dir: Path, rerun_reason: str | None) -> str | None:
    """(d) No completed test run unless a rerun reason is given."""
    reason = rerun_reason.strip() if rerun_reason else None
    if rerun_reason is not None and not reason:
        raise SealError("(d) --rerun-reason must not be empty")
    done = results_dir / Path(TEST_RESULTS_REL).name / COMPLETED_MARKER
    if done.exists() and not reason:
        raise SealError(f"(d) {done} holds a completed test run; the window is evaluated once. "
                        f"Pass --rerun-reason \"<text>\" to rerun, and the reason is logged")
    return reason


def authorize(*, repo_root: Path | None = None, freeze_path: Path | None = None,
              data_dir: Path | None = None, results_dir: Path | None = None,
              rerun_reason: str | None = None) -> Authorization:
    """Run every refusal check, in order (freeze record, a, b, B7, scenario, c, d), and return
    the authorization `test_mode` needs. Raises SealError with the reason on the first failure.
    Nothing here reads a sealed value: it hashes files and reads git."""
    root = Path(repo_root or paths.REPO_ROOT)
    freeze = load_freeze(freeze_path or root / FREEZE_REL)
    head = _check_tree(root, freeze)
    _check_tag(root, freeze, head)
    manifests = _check_manifests(root, freeze)
    _check_scenario(freeze)
    data = Path(data_dir or paths.DATA_DIR)
    inputs = _check_inputs(freeze, data)
    results = Path(results_dir or root / "results")
    reason = _check_outputs(results, rerun_reason)
    return Authorization(freeze=freeze, repo_root=root, data_dir=data, results_dir=results,
                         code_commit=head, rerun_reason=reason, manifests_sha256=manifests,
                         input_sha256=inputs, _token=_TOKEN)


# --------------------------------------------------------------------------- test mode


@dataclass
class Session:
    """The active test-mode context (one per entry-point invocation)."""

    auth: Authorization
    session_id: str
    run_id: str | None = None
    n_reads: int = 0
    built: dict[str, str] = field(default_factory=dict)

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


_ACTIVE: Session | None = None


def active() -> Session | None:
    """The active test-mode session, or None."""
    return _ACTIVE


def require_active(what: str) -> Session:
    if _ACTIVE is None:
        raise SealError(f"{what}: the sealed test window opens only inside the logged test-mode "
                        f"context, which only `run_slice --window test` enters")
    return _ACTIVE


def _append(path: Path, record: dict) -> None:
    """Append one JSONL line ("a" mode) and fsync it before returning."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


def _base_record(s: Session, event: str) -> dict:
    return {"event": event, "utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "session": s.session_id, "code_commit": s.auth.code_commit,
            "config_sha256": s.freeze.sha256, "freeze_commit": s.freeze.freeze_commit}


def log_event(event: str, **fields: Any) -> None:
    """Append a non-read event (e.g. the run id, an export) to the active session's log."""
    s = require_active(f"log_event({event})")
    _append(s.log_path, _base_record(s, event) | fields)


@contextmanager
def test_mode(auth: Authorization) -> Iterator[Session]:
    """The active test-mode context. Logs the invocation (with any rerun reason) on entry and
    the outcome on exit."""
    global _ACTIVE
    if not isinstance(auth, Authorization) or auth._token is not _TOKEN:
        raise SealError("test_mode needs the Authorization that `authorize` returns")
    if _ACTIVE is not None:
        raise SealError("test mode is already active")
    s = Session(auth=auth, session_id=uuid.uuid4().hex[:16])
    _append(s.log_path, _base_record(s, "invocation") | {
        "test_F": iso(auth.F), "rerun_reason": auth.rerun_reason,
        "inputs_sha256": auth.input_sha256, "manifests_sha256": auth.manifests_sha256,
        "argv": list(sys.argv)})
    _ACTIVE = s
    outcome = "error"
    try:
        yield s
        outcome = "ok"
    except BaseException as e:
        outcome = f"error: {type(e).__name__}: {e}"[:500]
        raise
    finally:
        _ACTIVE = None
        _append(s.log_path, _base_record(s, "close") | {"outcome": outcome,
                                                         "n_reads": s.n_reads,
                                                         "run_id": s.run_id})


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
                reader: Callable[[Path], pl.DataFrame] | None = None) -> pl.DataFrame:
    """Rows of `path` with `ts_col` in [time_range) (and `where`), as `columns`.

    The only function allowed to return rows at or after TEST_START. Refuses outside the
    active test-mode context, past F, and on any file that is not a frozen input (or built in
    this session) with its recorded sha256. Before returning it appends one fsynced JSONL line
    to `results/test_reads.jsonl`. Parquet files are scanned lazily; any other format needs a
    `reader(path) -> DataFrame` (e.g. the BA-workbook parser)."""
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
    sha = file_sha256(path)
    s._check_input(path, sha)
    _append(s.log_path, _base_record(s, "read") | {
        "purpose": purpose.strip(), "path": str(path), "sha256": sha, "columns": cols,
        "ts_col": ts_col, "time_range": [iso(start), iso(end)],
        "filter": None if where is None else str(where), "caller": _caller(),
        "run_id": s.run_id})
    s.n_reads += 1
    if reader is not None:
        lazy = reader(path).lazy()
    elif path.suffix == ".parquet":
        lazy = pl.scan_parquet(path)
    else:
        raise SealError(f"{path.name}: sealed_read needs a reader for {path.suffix} files")
    lazy = lazy.filter((pl.col(ts_col) >= start) & (pl.col(ts_col) < end))
    if where is not None:
        lazy = lazy.filter(where)
    return lazy.select(cols).collect()


def data_path(rel: str) -> Path:
    """`rel` under the active session's data directory (test mode), else gridpilot.paths."""
    s = active()
    return (s.data_dir if s else paths.DATA_DIR) / rel


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
    "freeze_errors",
    "freeze_tag_message",
    "load_freeze",
    "log_event",
    "require_active",
    "sealed_read",
    "test_mode",
]
