"""The offline results contract (spec §11, F12.5, F12.7; Task 7): scalar evidence envelopes,
their validators, the seal check on exported timestamps, and atomic JSON writes.

**Envelope.** Every number exported to `results/` sits in
`{value, unit, evidence, provenance_id, status, reason}`:
- `value`: a number, null, or a (nested) list of numbers/nulls (a series or an interval);
  NaN and ±inf are never written (they become null).
- `evidence` ∈ observed, measured, forecast, modeled, assumed, simulated
  (`.claude/skills/hackathon-evidence/SKILL.md`).
- `status` ∈ ok, not_run, not_evaluated, unavailable. A null anywhere in `value`, or a
  status other than ok, needs a non-empty `reason`. A missing value is never zero.

Booleans, strings, IDs, dates and schema versions are metadata, not quantitative evidence.

**Seal.** No exported timestamp may be at or after TEST_START, as a value, a key, or a
date substring inside a longer string. Exempt: the exact key `wallclock_generated_at` (the
build's own wall-clock time, not data time) and the seal-description strings under
`SEAL_DESCRIPTION_KEYS`. Run IDs use the compact `YYYYMMDDTHHMMSSZ` form.

**Window (Stage 3 T11, B2).** The seal check takes the evaluation `window` (default
validation). A test-window artifact (test mode only) may carry timestamps up to F_test (its
exclusive end, as a boundary label), never after it, and must say `window: "test"` (top-level
string, or `window.name` for the grid profile).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np

from gridpilot.splits import TEST_START
from gridpilot.window import Window, resolve

SCHEMA_VERSION = "gridpilot.results.v1"
EVIDENCE_CLASSES = ("observed", "measured", "forecast", "modeled", "assumed", "simulated")
STATUSES = ("ok", "not_run", "not_evaluated", "unavailable")
ENVELOPE_KEYS = ("value", "unit", "evidence", "provenance_id", "status", "reason")
# The only exempt key: the export's own build time (wall clock, not data time).
WALLCLOCK_KEY = "wallclock_generated_at"
# Wall-clock keys exempt from the seal check: the build time, and (test artifacts) the time
# the configuration was frozen. Neither is data time.
WALLCLOCK_KEYS = frozenset({WALLCLOCK_KEY, "wallclock_frozen_at"})
# String fields that describe the seal itself; date substrings inside them are not data.
SEAL_DESCRIPTION_KEYS = frozenset({"sealed_window", "evidence_scope"})

CLAIM_FRAME = (
    "simulated advance-reservation scheduling scenario; baseline-relative deadlines; "
    "exact declared runtimes; runtime uncertainty untested; EIA-attributed "
    "(consumption-basis) emissions; conditional temporal block-resampling intervals")
IMPORT_CONVENTION = (
    "EIA's consumption-basis intensity assigns imports from Canada and Mexico the average US "
    "emissions rate (EIA-930 convention).")
# F12.5 / F12.7 limitations (fix round 1 #2); check_claim_frame requires the three in
# REQUIRED_LIMITATIONS.
LIMIT_ZERO_MISSES = ("Zero deadline misses hold by construction under baseline bookings; they "
                     "are not evidence of production reliability.")
LIMIT_BOOKINGS_UNSIGNED = "The bookings' effect on realized savings is not signed."
LIMIT_SHADOW_U = ("The shadow-U sensitivity ('possible without advance reservations') is "
                  "pending.")
LIMIT_PHASES = "Only workload phase 0 is run; phases 49 and 98 are pending."
LIMIT_VALIDATION_DEV = (
    "Validation results are development evidence: the validation year was profiled before "
    "the design, and the same period selected the learned model's settings. The sealed test "
    "year is the confirmatory evaluation.")
# The test-window counterpart of LIMIT_VALIDATION_DEV (Stage 3 T11): a test manifest carries
# this instead.
LIMIT_TEST = (
    "Test-year results: the sealed test year was opened once, through the logged entry point, "
    "after the model and policy configuration was frozen at a recorded commit; nothing was "
    "selected or refitted on it. They cover the days up to the snapshot's availability cutoff, "
    "not a full twelve months.")
REQUIRED_LIMITATIONS = (LIMIT_ZERO_MISSES, LIMIT_BOOKINGS_UNSIGNED, LIMIT_VALIDATION_DEV)

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?"
                  r"(Z|[+-]\d{2}:?\d{2})?$")
_ISO_SUB = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?"
                      r"(?:Z|[+-]\d{2}:?\d{2})?)?(?!\d)")


# --------------------------------------------------------------------------- envelopes


def _clean(v: Any) -> tuple[Any, bool]:
    """(JSON-safe value, contains-null)."""
    if v is None:
        return None, True
    if isinstance(v, (bool, np.bool_)):
        raise TypeError("a boolean is metadata, not an enveloped number")
    if isinstance(v, (np.ndarray, list, tuple)):
        out, has_null = [], False
        for x in (v.tolist() if isinstance(v, np.ndarray) else v):
            c, n = _clean(x)
            out.append(c)
            has_null |= n
        return out, has_null
    if isinstance(v, (int, np.integer)):
        return int(v), False
    if isinstance(v, (float, np.floating)):
        f = float(v)
        return (None, True) if not math.isfinite(f) else (f, False)
    raise TypeError(f"envelope value must be numeric, null or a list, got {type(v).__name__}")


def env(value: Any, unit: str, evidence: str, provenance_id: str, status: str = "ok",
        reason: str | None = None) -> dict:
    """A §11 scalar (or series) envelope; raises on an invalid one."""
    if evidence not in EVIDENCE_CLASSES:
        raise ValueError(f"evidence must be one of {EVIDENCE_CLASSES}, got {evidence!r}")
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, got {status!r}")
    v, has_null = _clean(value)
    if (has_null or status != "ok") and not reason:
        raise ValueError(f"{provenance_id}: a null value or status {status!r} needs a reason")
    return {"value": v, "unit": str(unit), "evidence": evidence,
            "provenance_id": str(provenance_id), "status": status, "reason": reason}


def not_run(unit: str, evidence: str, provenance_id: str, reason: str) -> dict:
    return env(None, unit, evidence, provenance_id, status="not_run", reason=reason)


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _envelope_errors(d: dict) -> list[str]:
    errs = []
    if set(d) != set(ENVELOPE_KEYS):
        errs.append(f"keys {sorted(d)} != {sorted(ENVELOPE_KEYS)}")
    if d.get("evidence") not in EVIDENCE_CLASSES:
        errs.append(f"evidence {d.get('evidence')!r}")
    if d.get("status") not in STATUSES:
        errs.append(f"status {d.get('status')!r}")
    if not isinstance(d.get("unit"), str) or not isinstance(d.get("provenance_id"), str):
        errs.append("unit and provenance_id must be strings")

    def leaves(v):
        if isinstance(v, list):
            for x in v:
                yield from leaves(x)
        else:
            yield v

    vals = list(leaves(d.get("value")))
    if any(not (x is None or _is_number(x)) for x in vals):
        errs.append("value holds a non-numeric leaf")
    if any(isinstance(x, float) and not math.isfinite(x) for x in vals):
        errs.append("value holds NaN or inf")
    if (any(x is None for x in vals) or d.get("status") != "ok") and not d.get("reason"):
        errs.append("null value or non-ok status without a reason")
    return errs


def unenveloped_numbers(obj: Any) -> list[str]:
    """JSON paths of numeric leaves that are not inside a valid envelope's `value`.
    A dict with a `value` key is treated as an envelope and must be a valid one."""
    bad: list[str] = []

    def walk(x, path):
        if isinstance(x, dict):
            if "value" in x:
                errs = _envelope_errors(x)
                if errs:
                    bad.append(f"{path} ({'; '.join(errs)})")
                rest = {k: v for k, v in x.items() if k != "value"}
                for k, v in rest.items():
                    if _is_number(v):
                        bad.append(f"{path}.{k}")
                return
            for k, v in x.items():
                walk(v, f"{path}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]")
        elif _is_number(x):
            bad.append(path)

    walk(obj, "$")
    return bad


def _parse(s: str) -> datetime | None:
    if not _ISO.match(s):
        return None
    try:
        if len(s) == 10:
            d = date.fromisoformat(s)
            return datetime(d.year, d.month, d.day, tzinfo=UTC)
        t = datetime.fromisoformat(s)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _past(t: datetime, window: Window | None) -> bool:
    """Validation/fallback: at or after TEST_START. Test: after F_test (F itself is the
    window's exclusive end and may appear as a boundary)."""
    if window is not None and window.is_test:
        return t > window.read_end
    return t >= TEST_START


def _sealed_in(s: str, window: Window | None = None) -> bool:
    """True if `s` is, or contains, an ISO date/timestamp past the window's bound (default:
    at or after TEST_START)."""
    t = _parse(s)
    if t is not None:
        return _past(t, window)
    for m in _ISO_SUB.finditer(s):
        t = _parse(m.group(0))
        if t is not None and _past(t, window):
            return True
    return False


def sealed_timestamps(obj: Any, *, window: Window | None = None) -> list[str]:
    """JSON paths of ISO dates/timestamps at or after TEST_START (test window: after F_test),
    in values or keys, including date substrings inside longer strings. Exempt: the exact key
    `wallclock_generated_at` (build time), and the seal-description strings under
    SEAL_DESCRIPTION_KEYS."""
    w = resolve(window, "sealed_timestamps") if window is not None else None
    bad: list[str] = []

    def walk(x, path, key=None):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in WALLCLOCK_KEYS:
                    continue
                if isinstance(k, str) and _sealed_in(k, w):
                    bad.append(f"{path}.{k} (key)")
                walk(v, f"{path}.{k}", k)
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]", key)
        elif isinstance(x, str):
            if key in SEAL_DESCRIPTION_KEYS:
                return
            if _sealed_in(x, w):
                bad.append(path)

    walk(obj, "$")
    return bad


def artifact_window(obj: Any) -> str | None:
    """The window an artifact declares: `window` (a string), or `window.name` (the grid
    profile's window object)."""
    if not isinstance(obj, dict):
        return None
    w = obj.get("window")
    if isinstance(w, dict):
        w = w.get("name")
    return w if isinstance(w, str) else None


def validate_artifact(obj: Any, *, window: Window | None = None) -> list[str]:
    errs = ([f"unenveloped number at {p}" for p in unenveloped_numbers(obj)]
            + [f"sealed timestamp at {p}" for p in sealed_timestamps(obj, window=window)])
    if window is not None and window.is_test and artifact_window(obj) != "test":
        errs.append(f"a test-window artifact must declare window 'test', got "
                    f"{artifact_window(obj)!r}")
    if (window is None or not window.is_test) and artifact_window(obj) == "test":
        errs.append("an artifact declaring window 'test' must be written with the test window")
    return errs


def check_claim_frame(manifest: dict, *, window: Window | None = None) -> None:
    """The manifest carries the F12.5/F12.7 claim frame and the required limitations. A
    test-window manifest carries LIMIT_TEST in place of the validation-year limitation, and
    never the validation wording."""
    from gridpilot.forecast import LIMITATION

    test = window is not None and window.is_test
    dev = (LIMIT_TEST, "the test-year limitation (T11)") if test else (
        LIMIT_VALIDATION_DEV, "the development-evidence limitation (A6)")
    if test and LIMIT_VALIDATION_DEV in (manifest.get("limitations") or []):
        raise ValueError("a test manifest must not carry the validation-year limitation")

    if manifest.get("claim_frame") != CLAIM_FRAME:
        raise ValueError("manifest claim_frame differs from the registered text (F12.5, D-050)")
    lim = manifest.get("limitations") or []
    for need, what in ((LIMITATION, "the Task 2 forecast limitation"),
                       (IMPORT_CONVENTION, "the EIA import convention"),
                       (LIMIT_ZERO_MISSES, "the zero-misses-by-construction limitation"),
                       (LIMIT_BOOKINGS_UNSIGNED, "the unsigned-bookings-effect limitation"),
                       dev):
        if need not in lim:
            raise ValueError(f"manifest limitations must include {what}")


# --------------------------------------------------------------------------- hashing

# Run identity and build metadata never enter the canonical hash (T10 fix r1 M-1).
CANONICAL_DROP_KEYS = frozenset({"provenance_id", "run_id", "wallclock_generated_at",
                                 "export_git_sha", "export_git_clean"})
CANONICAL_SIG_DIGITS = 10
CANONICAL_ZERO_ABS = 1e-9  # |x| below this hashes as 0 (float noise around zero; M-2)


def _canonical(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: _canonical(v) for k, v in sorted(x.items()) if k not in CANONICAL_DROP_KEYS}
    if isinstance(x, list):
        return [_canonical(v) for v in x]
    if isinstance(x, float):
        if abs(x) < CANONICAL_ZERO_ABS:
            return 0.0  # also makes -0.0 and 0.0 hash alike
        return float(f"{x:.{CANONICAL_SIG_DIGITS}g}")
    return x


def canonical_hash(obj: Any) -> str:
    """sha256 of `obj` with floats rounded to 10 significant digits after zeroing |x| < 1e-9
    (Stage 3 T10; it was an absolute 1e-6 before), run identity and build metadata
    (CANONICAL_DROP_KEYS) removed and keys sorted (F12.6: reproduction by canonical values,
    not bytes)."""
    text = json.dumps(_canonical(obj), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


# --------------------------------------------------------------------------- writing


def write_json_atomic(path: Path, obj: Any, *, window: Window | None = None) -> str:
    """Validate, then write `obj` atomically (temp file, then rename). Returns the text.
    `window` (default validation) sets the seal check; a test window needs test mode."""
    if window is not None:
        window = resolve(window, "write_json_atomic")
    errs = validate_artifact(obj, window=window)
    if errs:
        raise ValueError(f"{path.name}: {len(errs)} contract errors: {errs[:50]}")
    text = json.dumps(obj, indent=1, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return text


def iso(t: datetime | None) -> str | None:
    """ISO-8601 UTC string for a tz-aware datetime (metadata)."""
    if t is None:
        return None
    if t.tzinfo is None:
        raise ValueError(f"{t!r} must be timezone-aware")
    return t.astimezone(UTC).isoformat().replace("+00:00", "Z")
