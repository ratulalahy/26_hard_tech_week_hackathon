"""Open-Meteo recon: find where archived-forecast coverage starts, then download it.

  uv run python scripts/recon_grid_weather.py probe            # coverage start per API x model x var
  uv run python scripts/recon_grid_weather.py download --priority 1
  uv run python scripts/recon_grid_weather.py summary          # completeness only (row/null counts)

Requests are strictly sequential with a pause between them, under a weighted-call budget
(gridpilot.data.weather.RateBudget). The probe looks only at null / non-null (completeness).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, date, datetime, timedelta

import httpx

from gridpilot.data import weather as w

PROBE_OUT = w.RAW_OM_DIR / "_probe" / "coverage_probe.json"
PAUSE_S = 1.0
PROBE_LO = date(2016, 1, 1)  # both APIs reject start_date < 2016-01-01
PROBE_HI = date(2025, 6, 1)  # last probe date; stays before the sealed window
PROBE_COMBOS = {
    "historical-forecast": ["best_match", "ncep_gfs_seamless", "ecmwf_ifs025", "ecmwf_ifs",
                            "ncep_hrrr_conus"],
    "previous-runs": ["best_match", "ncep_gfs_seamless", "ncep_gfs_global", "ecmwf_ifs025",
                      "ncep_hrrr_conus", "ncep_nbm_conus"],
}
SPOT_POINTS = ["ERCO_DFW", "CISO_LA", "ISNE_BOS"]


class Prober:
    def __init__(self, client: httpx.Client, budget: w.RateBudget):
        self.client, self.budget, self.cache, self.n_requests = client, budget, {}, 0

    def day(self, api: str, model: str, point: w.Point, d: date, variables: list[str]) -> dict:
        """{var: first non-null label on day d, or None}. One 1-day request, cached."""
        key = (api, model, point.point_id, d)
        if key not in self.cache:
            url = w.build_url(api, point, d, d, variables, model)
            self.budget.wait_for(w.request_weight(1, len(variables)))
            try:
                body = w.fetch(url, self.client)
                self.cache[key] = w.completeness(body)["first_non_null"]
            except httpx.HTTPStatusError as e:  # e.g. model not offered by this API
                self.cache[key] = {"_error": str(e)[:200]}
                if "out of allowed range" in str(e):
                    self.cache[key] = {"_note": str(e)[:200]}  # outside the API window: no data
            self.n_requests += 1
            time.sleep(PAUSE_S)
        return self.cache[key]

    def first_date(self, api: str, model: str, point: w.Point, variables: list[str]) -> dict:
        """Coarse yearly scan, then bisection by day, per variable."""
        samples = [PROBE_LO] + [date(y, 1, 15) for y in range(PROBE_LO.year + 1, PROBE_HI.year + 1)]
        samples += [PROBE_HI]
        seen = {d: self.day(api, model, point, d, variables) for d in samples}
        if all("_error" in v for v in seen.values()):
            return {"error": next(v["_error"] for v in seen.values() if "_error" in v)}
        out = {}
        for var in variables:
            has = [d for d in samples if seen[d].get(var)]
            if not has:
                out[var] = {"first_date": None, "note": f"no data on any probe date <= {PROBE_HI}"}
                continue
            hi = has[0]
            lo_candidates = [d for d in samples if d < hi]
            gaps_after = [str(d) for d in samples if d > hi and not seen[d].get(var)]
            if not lo_candidates:
                out[var] = {"first_date": str(hi), "first_non_null_utc": seen[hi].get(var),
                            "note": f"data on the API's earliest allowed date {hi}",
                            "yearly_samples_null_after_start": gaps_after}
                continue
            lo = lo_candidates[-1]
            while (hi - lo).days > 1:
                mid = lo + timedelta(days=(hi - lo).days // 2)
                if self.day(api, model, point, mid, variables).get(var):
                    hi = mid
                else:
                    lo = mid
            first_label = self.day(api, model, point, hi, variables).get(var)
            out[var] = {"first_date": str(hi), "first_non_null_utc": first_label,
                        "yearly_samples_null_after_start": gaps_after}
        return out


def cmd_probe(args) -> None:
    budget = w.RateBudget(per_hour=1500)
    result = {"probed_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "method": "1-day requests: yearly samples (Jan 15, 2015-2025, + 2025-06-01), then "
                        "bisection by day; a day counts as covered if any hour is non-null",
              "point": "PACE_SLC", "combos": {}, "spot_checks": {}}
    pace = w.POINTS_BY_ID["PACE_SLC"]
    with httpx.Client(timeout=60) as client:
        p = Prober(client, budget)
        for api, models in PROBE_COMBOS.items():
            variables = w.variables_for(api)
            for model in models:
                res = p.first_date(api, model, pace, variables)
                result["combos"][f"{api}/{model}"] = res
                print(api, model, json.dumps(res), flush=True)
                PROBE_OUT.parent.mkdir(parents=True, exist_ok=True)
                PROBE_OUT.write_text(json.dumps(result, indent=2))
        # Spot checks: same best_match start dates at other points (day before vs start day).
        for pid in SPOT_POINTS:
            pt = w.POINTS_BY_ID[pid]
            for api in PROBE_COMBOS:
                variables = w.variables_for(api)
                starts = {v["first_date"] for v in result["combos"][f"{api}/best_match"].values()
                          if isinstance(v, dict) and v.get("first_date")}
                chk = {}
                for s in sorted(starts):
                    d = date.fromisoformat(s)
                    before = p.day(api, "best_match", pt, d - timedelta(days=1), variables)
                    on = p.day(api, "best_match", pt, d, variables)
                    chk[s] = {"vars_non_null_day_before": sorted(k for k, v in before.items() if v),
                              "vars_non_null_on_start": sorted(k for k, v in on.items() if v)}
                result["spot_checks"][f"{pid}/{api}/best_match"] = chk
                print(pid, api, json.dumps(chk), flush=True)
        result["n_requests"] = p.n_requests
        result["weighted_calls_worst_case"] = budget.total
    PROBE_OUT.write_text(json.dumps(result, indent=2))
    print("probe done:", p.n_requests, "requests,", budget.total, "weighted calls", flush=True)


def cmd_download(args) -> None:
    budget = w.RateBudget.from_manifest(extra_used=args.already_used, per_hour=args.per_hour,
                                        per_day=args.per_day)
    print(f"budget seeded from manifest + extra: {budget.total:.0f} weighted calls in last 24 h",
          flush=True)
    end = date.fromisoformat(args.end) if args.end else (datetime.now(UTC) - timedelta(days=1)).date()
    points = [p for p in w.POINTS if p.priority in args.priority]
    if args.points:
        points = [w.POINTS_BY_ID[p] for p in args.points]
    plan = []
    for api, start, model in args.jobs:
        for pt in points:
            for s, e in w.year_chunks(date.fromisoformat(start), end):
                plan.append((api, model, pt, s, e))
    est = sum(w.request_weight((e - s).days + 1, len(w.variables_for(a))) for a, _, _, s, e in plan)
    print(f"plan: {len(plan)} requests, worst-case weight {est:.0f}", flush=True)
    entries = []
    with httpx.Client(timeout=httpx.Timeout(60, read=300)) as client:
        for i, (api, model, pt, s, e) in enumerate(plan):
            try:
                entry = w.download_chunk(api, pt, s, e, client, budget,
                                         model=None if model == "best_match" else model)
            except (httpx.HTTPError, OSError, ValueError, RuntimeError) as exc:  # keep going
                print(f"[{i + 1}/{len(plan)}] FAIL {api} {model} {pt.point_id} {s}..{e}: {exc}",
                      flush=True)
                continue
            entries.append(entry)
            print(f"[{i + 1}/{len(plan)}] {entry['status']} {api} {model} {pt.point_id} {s}..{e} "
                  f"{entry['bytes']} B; budget used {budget.total:.0f}", flush=True)
            if entry["status"] == "downloaded":
                time.sleep(PAUSE_S)
            if len(entries) % 20 == 0:
                w.write_manifest(entries)
    w.write_manifest(entries)
    print("download done:", len(entries), "files; weighted calls", round(budget.total), flush=True)


def cmd_summary(args) -> None:
    """Completeness per (api, model, point, window): row counts and null counts only."""
    from gridpilot.splits import TEST_START

    m = json.loads(w.MANIFEST_PATH.read_text())
    rows = {}
    for f in m["files"]:
        key = (f["api"], f["model"], f["point"]["point_id"])
        r = rows.setdefault(key, {"files": 0, "bytes": 0, "start": f["start_date"],
                                  "end": f["end_date"]})
        r["files"] += 1
        r["bytes"] += f["bytes"]
        r["start"] = min(r["start"], f["start_date"])
        r["end"] = max(r["end"], f["end_date"])
    for key, r in sorted(rows.items()):
        print(*key, r)
    # Hour-level completeness, split at the seal boundary (counts only).
    import polars as pl

    for api in w.APIS:
        for model_dir in sorted((w.RAW_OM_DIR / api).glob("*")) if (w.RAW_OM_DIR / api).exists() else []:
            df = w.load(api, model_dir.name, include_sealed=True)
            if df.is_empty():
                continue
            vcols = [c for c in df.columns if c not in ("point_id", "ba", "ts_utc", "valid_time_utc")]
            agg = (
                df.with_columns((pl.col("ts_utc") >= TEST_START).alias("sealed_window"))
                .group_by("point_id", "sealed_window")
                .agg(pl.len().alias("rows"), pl.col("ts_utc").min().alias("first"),
                     pl.col("ts_utc").max().alias("last"),
                     *(pl.col(c).null_count().alias(f"null_{c}") for c in vcols))
                .sort("point_id", "sealed_window")
            )
            with pl.Config(tbl_rows=200, tbl_cols=30, tbl_width_chars=250):
                print(api, model_dir.name)
                print(agg)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe")
    d = sub.add_parser("download")
    d.add_argument("--priority", type=int, nargs="+", default=[1])
    d.add_argument("--points", nargs="+")
    d.add_argument("--job", dest="jobs", nargs=3, action="append", required=True,
                   metavar=("API", "START", "MODEL"))
    d.add_argument("--end")
    d.add_argument("--per-hour", type=float, default=3800)
    d.add_argument("--per-day", type=float, default=8000)
    d.add_argument("--already-used", type=float, default=0.0)
    sub.add_parser("summary")
    args = ap.parse_args(argv)
    {"probe": cmd_probe, "download": cmd_download, "summary": cmd_summary}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
