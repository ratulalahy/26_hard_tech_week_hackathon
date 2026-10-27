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

SCHEMA_VERSION = "gridpilot.results.v1"
EVIDENCE_CLASSES = ("observed", "measured", "forecast", "modeled", "assumed", "simulated")
STATUSES = ("ok", "not_run", "not_evaluated", "unavailable")
ENVELOPE_KEYS = ("value", "unit", "evidence", "provenance_id", "status", "reason")
# The only exempt key: the export's own build time (wall clock, not data time).
WALLCLOCK_KEY = "wallclock_generated_at"
# String fields that describe the seal itself; date substrings inside them are not data.
SEAL_DESCRIPTION_KEYS = frozenset({"sealed_window", "evidence_scope"})

CLAIM_FRAME = (
    "simulated advance-reservation scheduling scenario; baseline-relative deadlines; "
    "exact declared runtimes; runtime uncertainty untested; EIA-attributed "
    "(consumption-basis) emissions; conditional temporal block-resampling intervals")
IMPORT_CONVENTION = (
    "EIA's consumption-basis intensity assigns imports from Canada and Mexico the average US "
    "emissions rate (EIA-930 convention).")
# F12.5 / F12.7 limitations (fix round 1 #2); check_claim_frame requires the first two.
LIMIT_ZERO_MISSES = ("Zero deadline misses hold by construction under baseline bookings; they "
                     "are not evidence of production reliability.")
LIMIT_BOOKINGS_UNSIGNED = "The bookings' effect on realized savings is not signed."
LIMIT_SHADOW_U = ("The shadow-U sensitivity ('possible without advance reservations') is "
                  "pending.")
LIMIT_PHASES = "Only workload phase 0 is run; phases 49 and 98 are pending."
REQUIRED_LIMITATIONS = (LIMIT_ZERO_MISSES, LIMIT_BOOKINGS_UNSIGNED)

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


def _sealed_in(s: str) -> bool:
    """True if `s` is, or contains, an ISO date/timestamp at or after TEST_START."""
    t = _parse(s)
    if t is not None:
        return t >= TEST_START
    for m in _ISO_SUB.finditer(s):
        t = _parse(m.group(0))
        if t is not None and t >= TEST_START:
            return True
    return False


def sealed_timestamps(obj: Any) -> list[str]:
    """JSON paths of ISO dates/timestamps at or after TEST_START, in values or keys,
    including date substrings inside longer strings. Exempt: the exact key
    `wallclock_generated_at` (build time), and the seal-description strings under
    SEAL_DESCRIPTION_KEYS."""
    bad: list[str] = []

    def walk(x, path, key=None):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == WALLCLOCK_KEY:
                    continue
                if isinstance(k, str) and _sealed_in(k):
                    bad.append(f"{path}.{k} (key)")
                walk(v, f"{path}.{k}", k)
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]", key)
        elif isinstance(x, str):
            if key in SEAL_DESCRIPTION_KEYS:
                return
            if _sealed_in(x):
                bad.append(path)

    walk(obj, "$")
    return bad


def validate_artifact(obj: Any) -> list[str]:
    return ([f"unenveloped number at {p}" for p in unenveloped_numbers(obj)]
            + [f"sealed timestamp at {p}" for p in sealed_timestamps(obj)])


def check_claim_frame(manifest: dict) -> None:
    """The manifest carries the F12.5/F12.7 claim frame and the required limitations."""
    from gridpilot.forecast import LIMITATION

    if manifest.get("claim_frame") != CLAIM_FRAME:
        raise ValueError("manifest claim_frame differs from the registered text (F12.5, D-050)")
    lim = manifest.get("limitations") or []
    for need, what in ((LIMITATION, "the Task 2 forecast limitation"),
                       (IMPORT_CONVENTION, "the EIA import convention"),
                       (LIMIT_ZERO_MISSES, "the zero-misses-by-construction limitation"),
                       (LIMIT_BOOKINGS_UNSIGNED, "the unsigned-bookings-effect limitation")):
        if need not in lim:
            raise ValueError(f"manifest limitations must include {what}")


# --------------------------------------------------------------------------- hashing

CANONICAL_DROP_KEYS = frozenset({"provenance_id", "run_id"})


def _canonical(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: _canonical(v) for k, v in sorted(x.items()) if k not in CANONICAL_DROP_KEYS}
    if isinstance(x, list):
        return [_canonical(v) for v in x]
    if isinstance(x, float):
        r = round(x, 6)
        return 0.0 if r == 0 else r  # -0.0 and 0.0 hash alike
    return x


def canonical_hash(obj: Any) -> str:
    """sha256 of `obj` with floats rounded to 1e-6, provenance_id/run_id removed and keys
    sorted (F12.6: reproduction by canonical values, not bytes)."""
    text = json.dumps(_canonical(obj), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


# --------------------------------------------------------------------------- writing


def write_json_atomic(path: Path, obj: Any) -> str:
    """Validate, then write `obj` atomically (temp file, then rename). Returns the text."""
    errs = validate_artifact(obj)
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
