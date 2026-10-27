"""The test cutoff F_test from completeness metadata (Stage 3 T12, final review B4; spec §5).

AGENTS.md ("Data rules"): until the freeze, nothing reads the sealed window's values except
completeness checks (row counts, missing hours). `test_cutoff` is that check for the freeze.

**Series.** The consumed-basis CO₂ intensity in the raw EIA BA workbooks of the four core BAs
(PACE, CISO, BPAT, NEVP; sheet "Published Hourly Data") and PACE demand (`demand_adj_mw`) in
the EIA-930 balance table `interim/eia930/balance.parquet`.

**Rule.** D is the last UTC day on or before TEST_END − 1 day on which every hour of D exists as
a published row in all five series. A row counts as present whether its value is null or not:
nulls are handled by the F14.6 fill. F_test = (D + 1 day) 00:00Z, capped at TEST_END.

**Seal discipline.** The function reads the workbooks' time column and the consumed-CI cell only
to tell an empty cell from a filled one, and the balance table's `ts_utc` and the null flag of
`demand_adj_mw`. It returns, and logs, **only counts and timestamps** (never a value). Each file
is read once into memory, hashed, and parsed from the same bytes, so the logged sha256 is the
file that was counted. Every call appends one fsynced JSON line to `log_path` (no default: a
call cannot go unlogged), including a failed call.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from gridpilot import paths
from gridpilot.data.eia_co2 import CONSUMED_COL, SHEET, TIME_COL, _clean
from gridpilot.splits import TEST_END, TEST_START

CORE_BAS = ("PACE", "CISO", "BPAT", "NEVP")
WORKBOOK_REL = "raw/eia930/ba_workbooks/{ba}.xlsx"
BALANCE_REL = "interim/eia930/balance.parquet"
DEMAND_COL = "demand_adj_mw"  # = forecast.BALANCE_COLS["demand"]
SERIES = tuple(f"{ba}/ci_consumed" for ba in CORE_BAS) + ("PACE/demand",)
TAIL_DAYS = 7  # the null-hour counts are also reported for the last 7 days through D
EVENT = "completeness"
RULE = ("D = the last UTC day <= TEST_END - 1 day on which every hour of D exists as a "
        "published row (null or not) for PACE, CISO, BPAT and NEVP consumed CO2 intensity "
        "(EIA BA workbooks) and PACE demand (EIA-930 balance); F_test = min(D + 1 day, "
        "TEST_END) at 00:00Z")
H1 = timedelta(hours=1)
D1 = timedelta(days=1)


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _workbook_presence(buf: bytes) -> pl.DataFrame:
    """(ts_utc hour start, is_null) per workbook row; the cell values are dropped here."""
    raw = pl.read_excel(io.BytesIO(buf), sheet_name=SHEET, engine="calamine",
                        columns=[TIME_COL, CONSUMED_COL],
                        schema_overrides={CONSUMED_COL: pl.Utf8})
    if raw.schema[TIME_COL] == pl.Utf8:
        time = pl.col(TIME_COL).str.to_datetime(time_unit="us", strict=False)
    else:
        time = pl.col(TIME_COL).cast(pl.Datetime("us"), strict=False)
    _, reason = _clean(pl.col(CONSUMED_COL))
    out = raw.select((time.dt.replace_time_zone("UTC") - pl.duration(hours=1)).alias("ts_utc"),
                     reason.is_not_null().alias("is_null"))
    del raw
    if out["ts_utc"].null_count():
        raise ValueError(f"{out['ts_utc'].null_count()} workbook rows with an unparseable time")
    return out


def _balance_presence(buf: bytes, ba: str = "PACE") -> pl.DataFrame:
    """(ts_utc, is_null) of `ba`'s demand rows; the demand value is never materialized."""
    return (pl.scan_parquet(io.BytesIO(buf))
            .filter(pl.col("ba").cast(pl.Utf8) == ba)
            .select("ts_utc", pl.col(DEMAND_COL).is_null().alias("is_null"))
            .collect())


def _day_floor(t: datetime) -> datetime:
    return t.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _summary(rows: pl.DataFrame) -> tuple[dict, set[datetime]]:
    """Counts and timestamps for one series, and its set of complete days in the window."""
    if rows["ts_utc"].is_duplicated().any():
        raise ValueError("duplicate hours in a series")
    win = rows.filter((pl.col("ts_utc") >= TEST_START) & (pl.col("ts_utc") < TEST_END))
    per_day = (win.group_by(pl.col("ts_utc").dt.truncate("1d").alias("day"))
               .agg(pl.len().alias("n")).sort("day"))
    complete = {d for d, n in per_day.iter_rows() if n == 24}
    last = rows["ts_utc"].max()
    first_win = win["ts_utc"].min()
    return {
        "last_row_ts_utc": _iso(last) if last is not None else None,
        "first_row_in_window_ts_utc": _iso(first_win) if first_win is not None else None,
        "n_rows_in_window": win.height,
        "n_null_in_window": int(win["is_null"].sum()),
        "n_complete_days_in_window": len(complete),
    }, complete


def _counts_through(rows: pl.DataFrame, start: datetime, end: datetime) -> dict:
    sub = rows.filter((pl.col("ts_utc") >= start) & (pl.col("ts_utc") < end))
    n_hours = int((end - start) / H1)
    return {"range": [_iso(start), _iso(end)], "n_hours": n_hours, "n_rows": sub.height,
            "n_missing_rows": n_hours - sub.height, "n_null": int(sub["is_null"].sum())}


def _git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                       check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def _append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


def test_cutoff(log_path: Path | str, *, data_dir: Path | None = None,
                repo_root: Path | None = None, purpose: str = "T12 test cutoff F_test") -> dict:
    """F_test by the completeness rule (module docstring). Returns, and appends to `log_path`
    as one JSON line, a record of counts and timestamps only: per series the last row, the
    window's row, null and complete-day counts, the counts in [TEST_START, F_test) and in the
    last 7 days through D; D, F_test, the sha256 of every file counted, and the code commit."""
    data = Path(data_dir or paths.DATA_DIR)
    root = Path(repo_root or paths.REPO_ROOT)
    rec: dict = {"event": EVENT, "utc": _iso(datetime.now(UTC)), "purpose": purpose,
                 "rule": RULE, "data_dir": str(data),
                 "code_commit": _git(root, "rev-parse", "HEAD"),
                 "lab_tree": _git(root, "rev-parse", "HEAD:lab"),
                 "tree_clean": _git(root, "status", "--porcelain", "--untracked-files=no") == "",
                 "argv": list(sys.argv), "returns": "counts and timestamps only"}
    try:
        inputs, rows = {}, {}
        for ba in CORE_BAS:
            rel = WORKBOOK_REL.format(ba=ba)
            buf = (data / rel).read_bytes()
            inputs[rel] = hashlib.sha256(buf).hexdigest()
            rows[f"{ba}/ci_consumed"] = _workbook_presence(buf)
            del buf
        buf = (data / BALANCE_REL).read_bytes()
        inputs[BALANCE_REL] = hashlib.sha256(buf).hexdigest()
        rows["PACE/demand"] = _balance_presence(buf)
        del buf
        series, complete = {}, {}
        for name in SERIES:
            series[name], complete[name] = _summary(rows[name])
        latest = _day_floor(TEST_END - D1)
        common = sorted(d for d in set.intersection(*complete.values()) if d <= latest)
        if not common:
            raise ValueError("no UTC day of the test window is complete in all five series")
        D = common[-1]
        F = min(D + D1, TEST_END)
        for name in SERIES:
            series[name]["through_F"] = _counts_through(rows[name], TEST_START, F)
            series[name]["last_days_through_D"] = _counts_through(
                rows[name], D - (TAIL_DAYS - 1) * D1, D + D1)
        rec |= {"outcome": "ok", "inputs_sha256": inputs, "series": series,
                "D": D.strftime("%Y-%m-%d"), "test_F": _iso(F),
                "last_complete_day_by_series": {
                    n: (max(c).strftime("%Y-%m-%d") if c else None)
                    for n, c in complete.items()}}
    except Exception as e:
        rec |= {"outcome": f"error: {type(e).__name__}: {e}"[:500]}
        _append(Path(log_path), rec)
        raise
    _append(Path(log_path), rec)
    return rec


def read_log(path: Path | str | bytes) -> list[dict]:
    """The records of a completeness log (bytes, or a path)."""
    raw = path if isinstance(path, bytes) else Path(path).read_bytes()
    return [json.loads(ln) for ln in raw.decode().splitlines() if ln.strip()]
