"""Write results/outlook.json: the grid outlook (Stage 3 T19).

    cd lab && uv run python scripts/outlook.py                       # validation-dated demo
    cd lab && uv run python scripts/outlook.py --issue 2025-06-15    # another validation date
    cd lab && uv run python scripts/outlook.py --live                # after the seal opens (T13)

Both modes fit the outlook models at the validation fit (2024-10-29) and measure skill by
horizon on the validation issues (pre-seal rows only, through ``drop_sealed``); the skill table
sets the days shown and the p10/p90 bands.

* **Demo** (default): the issue is 10:00 America/Denver on ``--issue`` (a validation date); the
  forecast uses the validation-fit models on pre-seal rows published by the issue. An issue
  whose horizon reaches 2025-11-01 is refused.
* **Live** (``--live``): refuses unless a completed test run exists (``results/test/
  manifest.json``). The issue is the latest 10:00 America/Denver at or before now; models are
  refitted at the test fit (2025-10-29, history from 2023-01-01; pre-seal rows); the newest
  weeks come from a fresh download of the four BA workbooks (``gridpilot.data.eia930``) into
  the run directory, each read through ``gridpilot.outlook.live_read`` with a logged purpose
  (``results/outlook_reads.jsonl``). The S ranking is the freeze record's.

The run directory ``runs/outlook/<UTC>/`` holds the config, git SHA, skill table and (live) the
downloaded workbooks with their manifest entries.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import UTC, date, datetime, time, timedelta
from functools import partial
from pathlib import Path

import polars as pl

from gridpilot import forecast as fc
from gridpilot import outlook as ol
from gridpilot import seal
from gridpilot.data.eia_co2 import CARBON_PATH, parse_ba_workbook, s_ranking_at
from gridpilot.paths import REPO_ROOT, RESULTS_DIR
from gridpilot.results import iso
from gridpilot.splits import TEST_START

log = logging.getLogger("outlook")
DEMO_ISSUE = date(2025, 6, 15)
RANK_NOTE = ("mean consumed CI per region over the training rows, ascending; S tries regions in "
             "this order (home PACE at its rank)")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True,
                          check=False).stdout.strip()


def _issue_at(d: date) -> datetime:
    return datetime.combine(d, time(fc.ISSUE_HOUR), fc.ISSUE_TZ).astimezone(UTC)


def _fit_all(series: pl.DataFrame, fit_at: datetime, start: datetime) -> dict[str, ol.Models]:
    out = {}
    for ba in ol.SITES:
        log.info("fitting %s at %s", ba, iso(fit_at))
        out[ba] = ol.fit_models(series, ba, fit_at, start)
    return out


def _skill_json(skill: dict) -> dict:
    return {ba: {str(d): {k: (list(v) if isinstance(v, tuple) else v)
                          for k, v in row.items() if k != "q"} | {
        "q": {m: list(q) for m, q in row["q"].items()}} for d, row in rows.items()}
        for ba, rows in skill.items()}


def _live_series(issue: datetime, run_dir: Path) -> tuple[pl.DataFrame, list[dict]]:
    """Fresh BA workbooks (EIA, public, no key) into the run directory, read through
    ``live_read``: the rows of [issue - 1100 h, issue) only."""
    from gridpilot.data.eia930 import BA_WORKBOOK_URL, download_file

    raw = run_dir / "raw"
    entries, frames = [], []
    lo = issue - timedelta(hours=fc.WINDOW_H + ol.ENV_H + 100)
    for ba in ol.SITES:
        e = download_file(f"{ba}.xlsx", raw, url=BA_WORKBOOK_URL.format(ba=ba))
        entries.append(e)
        f = ol.live_read(raw / f"{ba}.xlsx", live=True,
                         purpose=f"live outlook: {ba} consumed CI, issue-time features",
                         columns=["ba", "ts_utc", "ci_consumed_g_kwh"], time_range=(lo, issue),
                         reader=partial(parse_ba_workbook, ba=ba))
        frames.append(f.rename({"ci_consumed_g_kwh": "value"}))
    s = pl.concat(frames).select(pl.col("ba").cast(pl.Utf8), "ts_utc",
                                 pl.col("value").cast(pl.Float64)).sort("ba", "ts_utc")
    return s, entries


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--issue", type=date.fromisoformat, default=None,
                    help=f"demo issue date (10:00 America/Denver); default {DEMO_ISSUE}")
    ap.add_argument("--live", action="store_true",
                    help="live outlook from a fresh download; only after the seal opens (T13)")
    ap.add_argument("--days", type=int, default=None,
                    help="days to show (default 7; each region-day is flagged by the skill rule)")
    ap.add_argument("--out", type=Path, default=RESULTS_DIR / "outlook.json")
    ap.add_argument("--runs", type=Path, default=REPO_ROOT / "runs" / "outlook")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    if a.live:
        if a.issue is not None:
            ap.error("--live issues at the latest 10:00 America/Denver; --issue is demo only")
        if not ol.seal_opened():
            print("refused: the sealed window has not been opened (no completed test run at "
                  "results/test/manifest.json); a live outlook waits for T13", file=sys.stderr)
            return 2
        issue = ol.latest_issue(datetime.now(UTC))
    else:
        issue = _issue_at(a.issue or DEMO_ISSUE)
        last = ol.day_hours(issue, a.days or ol.MAX_DAYS)[-1] + fc.H
        if issue >= TEST_START or last > TEST_START:
            print(f"refused: issue {iso(issue)} reaches the sealed window; the demo needs a "
                  f"validation date (live mode: --live after T13)", file=sys.stderr)
            return 2

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = a.runs / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    pre = fc.load_series(ol.TARGET)  # pre-seal rows only (drop_sealed in the lazy scan)
    val_models = _fit_all(pre, fc.VAL_FIT_AT, fc.VAL_HISTORY_START)
    log.info("skill by horizon on %d validation issues", len(ol.skill_issues()))
    skill = ol.skill_by_horizon(pre, val_models)
    days = a.days or ol.MAX_DAYS  # every day is shown; each (region, day) carries its status
    (run_dir / "skill.json").write_text(json.dumps(_skill_json(skill), indent=1, default=str))

    downloads: list[dict] = []
    if a.live:
        models = _fit_all(pre, fc.TEST_FIT_AT, fc.TEST_HISTORY_START)
        series, downloads = _live_series(issue, run_dir)
        try:
            fz = seal.load_freeze()
            ranking, means = fz.s_order, {b: fz.s_means[b] for b in fz.s_order}
            rank_note = RANK_NOTE + "; from the freeze record (config/freeze.json)"
        except seal.SealError:
            ranking, means = s_ranking_at(fc.VAL_HISTORY_START, fc.VAL_FIT_AT, sites=ol.SITES,
                                          path=CARBON_PATH)
            rank_note = RANK_NOTE + "; validation ranking (no freeze record found)"
    else:
        models = val_models
        series = pre.filter(pl.col("ts_utc") < issue)  # the as_of cut follows in build_outlook
        ranking, means = s_ranking_at(fc.VAL_HISTORY_START, fc.VAL_FIT_AT, sites=ol.SITES,
                                      path=CARBON_PATH)
        rank_note = RANK_NOTE + "; validation ranking, 2022-01-01 to 2024-10-29"

    meta = {"git_sha": _git("rev-parse", "HEAD"), "git_clean": _git("status", "--porcelain") == "",
            "run_dir": f"runs/outlook/{run_id}",
            "fit_at": iso(models["PACE"].fit_at),
            "history_start": iso(models["PACE"].history_start),
            "skill_fit_at": iso(fc.VAL_FIT_AT),
            "reproduce": ("make outlook LIVE=1" if a.live else
                          f"make outlook ISSUE={(a.issue or DEMO_ISSUE).isoformat()}"),
            "reads_log": f"results/{ol.LIVE_LOG_NAME}" if a.live else None,
            "downloads": downloads}
    art = ol.build_outlook(series, models, skill, issue, days=days, ranking=ranking,
                           ranking_means=means, ranking_note=rank_note, live=a.live,
                           run_id=run_id, meta=meta)
    art["wallclock_generated_at"] = datetime.now(UTC).isoformat()
    (run_dir / "config.json").write_text(json.dumps(
        {"run_id": run_id, "live": a.live, "issue": iso(issue), "days": days, **meta}, indent=1))
    ol.write_outlook(a.out, art, live=a.live)
    print(f"{a.out} ({'live' if a.live else 'demo'}, issue {iso(issue)}, {days} day(s)); "
          f"run {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
