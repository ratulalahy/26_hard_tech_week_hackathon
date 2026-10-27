"""Open-Meteo archived weather forecasts: the Historical Forecast API and the Previous Runs API.

License: CC BY 4.0. Attribution: "Weather data by Open-Meteo.com" (https://open-meteo.com/),
licence https://open-meteo.com/en/license. Free tier: non-commercial, < 10,000 calls/day,
5,000/hour, 600/minute; a request counts as max(1, days/14) x max(1, n_vars/10) calls.

Two archives, two meanings (docs quoted in ``docs/data-profile/grid.md``):

* Historical Forecast API (``historical-forecast``): "Each run's first few hours are stitched into
  a continuous hourly timeseries." Every hour comes from a run initialised a few hours before it,
  i.e. a 0-6 h lead. Good for training on near-observed weather; NOT an honest day-ahead feature.
* Previous Runs API (``previous-runs``): "``_previous_day1`` returns the value predicted 24 hours
  before valid time; ``_previous_day2`` returns 48 hours before, and so on up to day 7." The
  un-suffixed variable is ``_previous_day0`` (the latest run). Open-Meteo's launch post explains
  the construction: "the initial 24 hours of each weather model run are disregarded. In models
  updating every 3 hours, time steps 24, 25, and 26 are utilized to form a continuous
  time-series ... for Previous Day 2, time steps 48, 49, and 50 are used." So ``_previous_dayN``
  at valid time t comes from the latest run initialised at or before t - 24N h (lead 24N h to
  24N h + run interval - 1 h). An honest day-ahead feature comes from here;
  :func:`safe_previous_day` picks the smallest N that was knowable at a given issue time.

Timestamp semantics. We always request ``timezone=GMT``, so Open-Meteo's ``time`` labels are UTC.
``temperature_2m`` and ``wind_speed_100m`` are instantaneous values at the label. Hourly
``shortwave_radiation`` is the mean over the PRECEDING hour (docs: "Solar radiation is averaged
over the past hour"), so the value labelled T covers [T-1h, T).

The tidy frame from :func:`load` shifts every label back one hour: ``ts_utc = label - 1h``, the
start of the hour, matching ``gridpilot.data.eia930`` (EIA's "hour ending T" row has
``ts_utc = T - 1h``). After the shift, radiation is the mean over [ts_utc, ts_utc + 1h) -- exactly
the EIA hour -- and temperature/wind are the instants at that hour's END (ts_utc + 1h). Joining
on ``ts_utc`` is therefore the same as joining EIA "hour ending T" with Open-Meteo label T.
The original label is kept as ``valid_time_utc``.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import httpx
import polars as pl

from gridpilot.paths import DATA_DIR, MANIFEST_DIR, RAW_DIR
from gridpilot.splits import drop_sealed

RAW_OM_DIR = RAW_DIR / "openmeteo"
MANIFEST_PATH = MANIFEST_DIR / "openmeteo.json"

APIS = {
    "historical-forecast": "https://historical-forecast-api.open-meteo.com/v1/forecast",
    "previous-runs": "https://previous-runs-api.open-meteo.com/v1/forecast",
}
BASE_VARS = ("temperature_2m", "shortwave_radiation", "wind_speed_100m")
LEADS = (1, 2)  # previous_day offsets downloaded next to the base (day-0) variable
FIXED_PARAMS = {"timezone": "GMT", "wind_speed_unit": "ms"}

LICENSE = {
    "name": "CC BY 4.0",
    "url": "https://open-meteo.com/en/license",
    "attribution": "Weather data by Open-Meteo.com",
    "attribution_link": "https://open-meteo.com/",
    "terms": "Free API is for non-commercial use; < 10,000 calls/day, 5,000/hour, 600/minute "
    "(https://open-meteo.com/en/terms).",
}
EVIDENCE_LABEL = "forecast"  # AGENTS.md evidence labels: archived NWP output, not observations


@dataclass(frozen=True)
class Point:
    point_id: str
    ba: str
    role: str  # "load" (load-center city) or "wind" / "solar" (resource site)
    name: str
    lat: float
    lon: float
    priority: int  # 1 = primary load center, 2 = secondary load or resource site


POINTS: tuple[Point, ...] = (
    # Priority 1: one load-center point per candidate BA.
    Point("PACE_SLC", "PACE", "load", "Salt Lake City UT", 40.7608, -111.8910, 1),
    Point("CISO_LA", "CISO", "load", "Los Angeles CA", 34.0522, -118.2437, 1),
    Point("ERCO_DFW", "ERCO", "load", "Dallas TX", 32.7767, -96.7970, 1),
    Point("BPAT_PDX", "BPAT", "load", "Portland OR", 45.5152, -122.6784, 1),
    Point("PJM_PHL", "PJM", "load", "Philadelphia PA", 39.9526, -75.1652, 1),
    Point("MISO_IND", "MISO", "load", "Indianapolis IN", 39.7684, -86.1581, 1),
    Point("SWPP_OKC", "SWPP", "load", "Oklahoma City OK", 35.4676, -97.5164, 1),
    Point("NYIS_NYC", "NYIS", "load", "New York NY", 40.7128, -74.0060, 1),
    Point("ISNE_BOS", "ISNE", "load", "Boston MA", 42.3601, -71.0589, 1),
    Point("SOCO_ATL", "SOCO", "load", "Atlanta GA", 33.7490, -84.3880, 1),
    Point("FPL_MIA", "FPL", "load", "Miami FL", 25.7617, -80.1918, 1),
    Point("TVA_BNA", "TVA", "load", "Nashville TN", 36.1627, -86.7816, 1),
    Point("DUK_CLT", "DUK", "load", "Charlotte NC", 35.2271, -80.8431, 1),
    Point("AZPS_PHX", "AZPS", "load", "Phoenix AZ", 33.4484, -112.0740, 1),
    Point("NEVP_LAS", "NEVP", "load", "Las Vegas NV", 36.1699, -115.1398, 1),
    Point("PSCO_DEN", "PSCO", "load", "Denver CO", 39.7392, -104.9903, 1),
    Point("IPCO_BOI", "IPCO", "load", "Boise ID", 43.6150, -116.2023, 1),
    # Priority 2: secondary load centers for large multi-climate BAs.
    Point("CISO_SJC", "CISO", "load", "San Jose CA", 37.3382, -121.8863, 2),
    Point("CISO_RIV", "CISO", "load", "Riverside CA", 33.9806, -117.3755, 2),
    Point("ERCO_IAH", "ERCO", "load", "Houston TX", 29.7604, -95.3698, 2),
    Point("ERCO_SAT", "ERCO", "load", "San Antonio TX", 29.4241, -98.4936, 2),
    Point("PJM_CHI", "PJM", "load", "Chicago IL", 41.8781, -87.6298, 2),
    Point("PJM_DCA", "PJM", "load", "Washington DC", 38.9072, -77.0369, 2),
    Point("PJM_CMH", "PJM", "load", "Columbus OH", 39.9612, -82.9988, 2),
    Point("MISO_MSP", "MISO", "load", "Minneapolis MN", 44.9778, -93.2650, 2),
    Point("MISO_DTW", "MISO", "load", "Detroit MI", 42.3314, -83.0458, 2),
    Point("MISO_MSY", "MISO", "load", "New Orleans LA", 29.9511, -90.0715, 2),
    Point("SWPP_MCI", "SWPP", "load", "Kansas City MO", 39.0997, -94.5786, 2),
    # Priority 2: wind / solar resource sites (net load depends on them, not on the load center).
    Point("PACE_WIND_WY", "PACE", "wind", "Medicine Bow WY wind belt", 41.90, -106.20, 2),
    Point("PACE_SOLAR_UT", "PACE", "solar", "Milford UT solar", 38.40, -113.01, 2),
    Point("ERCO_WIND_WTX", "ERCO", "wind", "Sweetwater TX wind", 32.47, -100.41, 2),
    Point("ERCO_SOLAR_WTX", "ERCO", "solar", "Fort Stockton TX solar", 30.89, -102.88, 2),
    Point("CISO_SOLAR_MOJ", "CISO", "solar", "Mojave CA solar", 34.87, -118.20, 2),
    Point("SWPP_WIND_KS", "SWPP", "wind", "Dodge City KS wind", 37.75, -100.02, 2),
    Point("MISO_WIND_IA", "MISO", "wind", "North-central Iowa wind", 42.50, -94.20, 2),
    Point("BPAT_WIND_GORGE", "BPAT", "wind", "Columbia Gorge wind", 45.70, -120.20, 2),
)
POINTS_BY_ID = {p.point_id: p for p in POINTS}


def variables_for(api: str, base: Sequence[str] = BASE_VARS, leads: Sequence[int] = LEADS) -> list[str]:
    """Hourly variable names to request: the base set, plus ``_previous_dayN`` for Previous Runs."""
    if api == "historical-forecast":
        return list(base)
    if api == "previous-runs":
        return [*base, *(f"{v}_previous_day{n}" for n in leads for v in base)]
    raise ValueError(f"unknown api {api!r}")


def build_url(
    api: str, point: Point, start: date, end: date, variables: Sequence[str], model: str | None = None
) -> str:
    """Full request URL (dates inclusive, UTC). ``model=None`` means Open-Meteo's best_match."""
    params = {
        "latitude": f"{point.lat:.4f}",
        "longitude": f"{point.lon:.4f}",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": ",".join(variables),
        **FIXED_PARAMS,
    }
    if model and model != "best_match":
        params["models"] = model
    return f"{APIS[api]}?{urlencode(params, safe=',')}"


def request_weight(n_days: int, n_vars: int) -> float:
    """Worst-case API-call weight of one request (each HTTP request counts at least 1)."""
    return max(1.0, n_days / 14) * max(1.0, n_vars / 10)


class RateBudget:
    """Client-side limiter on weighted calls, kept well under Open-Meteo's free-tier limits."""

    def __init__(self, per_minute: float = 300, per_hour: float = 4000, per_day: float = 8000,
                 already_used_today: float = 0.0, events: Iterable[tuple[float, float]] = ()):
        self.limits = ((60.0, per_minute), (3600.0, per_hour), (86400.0, per_day))
        self.events: deque[tuple[float, float]] = deque(sorted(events))
        if already_used_today:  # counted as used 61 s ago: blocks the hour/day, not the minute
            self.events.append((time.time() - 61, already_used_today))
        self.total = sum(w for _, w in self.events)

    @classmethod
    def from_manifest(cls, extra_used: float = 0.0, **limits) -> RateBudget:
        """Seed the windows with the weighted calls of manifest files retrieved in the last 24 h,
        so sequential runs of the downloader share one budget."""
        now = time.time()
        events = []
        if MANIFEST_PATH.exists():
            for f in json.loads(MANIFEST_PATH.read_text()).get("files", []):
                if not f.get("retrieved_at"):
                    continue
                t = datetime.strptime(f["retrieved_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=UTC).timestamp()
                if now - t < 86400:
                    days = (date.fromisoformat(f["end_date"])
                            - date.fromisoformat(f["start_date"])).days + 1
                    events.append((t, request_weight(days, len(f["variables"]))))
        return cls(already_used_today=extra_used, events=events, **limits)

    def _used(self, window: float, now: float) -> float:
        return sum(w for t, w in self.events if now - t < window)

    def wait_for(self, weight: float) -> None:
        while True:
            now = time.time()
            while self.events and now - self.events[0][0] >= 86400:
                self.events.popleft()
            blocked = [(win, cap) for win, cap in self.limits if self._used(win, now) + weight > cap]
            if not blocked:
                self.events.append((now, weight))
                self.total += weight
                return
            win, _ = blocked[-1]
            if win >= 86400:
                raise RuntimeError(f"daily budget exhausted ({self.total:.0f} weighted calls)")
            time.sleep(5 if win <= 60 else 30)


def fetch(url: str, client: httpx.Client, max_retries: int = 6) -> bytes:
    """GET with exponential backoff on 429 / 5xx / transport errors. Returns the raw body."""
    delay = 5.0
    for attempt in range(max_retries + 1):
        try:
            r = client.get(url)
            if r.status_code == 200:
                return r.content
            if r.status_code not in (429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError(f"{r.status_code}: {r.text[:300]}", request=r.request,
                                            response=r)
        except httpx.TransportError:
            if attempt == max_retries:
                raise
        if attempt == max_retries:
            r.raise_for_status()
        time.sleep(delay)
        delay = min(delay * 2, 300)
    raise RuntimeError("unreachable")


def year_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """Split [start, end] (inclusive) into calendar-year chunks."""
    out, cur = [], start
    while cur <= end:
        stop = min(date(cur.year, 12, 31), end)
        out.append((cur, stop))
        cur = stop + timedelta(days=1)
    return out


def raw_path(api: str, model: str | None, point_id: str, start: date, end: date) -> Path:
    return RAW_OM_DIR / api / (model or "best_match") / point_id / f"{start}_{end}.json"


def completeness(body: bytes) -> dict:
    """Row count and null count per variable, plus the first/last non-null label per variable.

    Completeness only (no values): safe to compute on any window, including the sealed one.
    """
    j = json.loads(body)
    hourly = j.get("hourly", {})
    times = hourly.get("time", [])
    out = {"n_hours": len(times), "nulls": {}, "first_non_null": {}, "last_non_null": {}}
    for k, v in hourly.items():
        if k == "time":
            continue
        idx = [i for i, x in enumerate(v) if x is not None]
        out["nulls"][k] = len(v) - len(idx)
        out["first_non_null"][k] = times[idx[0]] if idx else None
        out["last_non_null"][k] = times[idx[-1]] if idx else None
    return out


def download_chunk(
    api: str, point: Point, start: date, end: date, client: httpx.Client, budget: RateBudget,
    model: str | None = None, variables: Sequence[str] | None = None, overwrite: bool = False,
) -> dict:
    """Download one (api, model, point, date range) chunk; return its manifest entry."""
    variables = list(variables or variables_for(api))
    url = build_url(api, point, start, end, variables, model)
    dest = raw_path(api, model, point.point_id, start, end)
    if dest.exists() and not overwrite:
        body = dest.read_bytes()
        status, retrieved_at = "kept-existing", None
    else:
        budget.wait_for(request_weight((end - start).days + 1, len(variables)))
        retrieved_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        body = fetch(url, client)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".part")
        tmp.write_bytes(body)
        tmp.replace(dest)
        status = "downloaded"
    return {
        "path": str(dest.relative_to(DATA_DIR)),
        "url": url,
        "retrieved_at": retrieved_at,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "api": api,
        "model": model or "best_match",
        "point": asdict(point),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "variables": variables,
        "completeness": completeness(body),
        "status": status,
    }


def write_manifest(entries: Iterable[dict], findings: dict | None = None) -> Path:
    """Merge entries into ``data/manifests/openmeteo.json`` keyed by path; keep old retrieved_at."""
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {}
    files = {f["path"]: f for f in manifest.get("files", [])}
    for e in entries:
        old = files.get(e["path"], {})
        merged = {**old, **{k: v for k, v in e.items() if v is not None}}
        merged.pop("status", None)
        files[e["path"]] = merged
    manifest.update({
        "source": "Open-Meteo archived weather forecasts (Historical Forecast API, Previous Runs API)",
        "apis": APIS,
        "license": LICENSE,
        "evidence_label": EVIDENCE_LABEL,
        "fixed_params": FIXED_PARAMS,
        "timestamp_convention": (
            "Raw JSON 'time' labels are UTC (timezone=GMT). temperature_2m and wind_speed_100m are "
            "instantaneous at the label; shortwave_radiation is the mean over the preceding hour. "
            "gridpilot.data.weather.load() sets ts_utc = label - 1h (hour-start, like eia930)."
        ),
    })
    if findings:
        manifest.setdefault("findings", {}).update(findings)
    manifest["files"] = sorted(files.values(), key=lambda f: f["path"])
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    return MANIFEST_PATH


def load(
    api: str, model: str | None = None, point_ids: Sequence[str] | None = None,
    include_sealed: bool = False,
) -> pl.DataFrame:
    """Tidy hourly frame (point_id, ba, ts_utc, valid_time_utc, <variables>) from the raw JSON.

    ``ts_utc`` = Open-Meteo label - 1 h (hour-start, see module docstring). Rows in the sealed test
    window are dropped unless ``include_sealed`` is set, which only completeness checks and the
    test-evaluation entry point may do (AGENTS.md, "Data rules").
    """
    root = RAW_OM_DIR / api / (model or "best_match")
    frames = []
    for pdir in sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []:
        if point_ids and pdir.name not in point_ids:
            continue
        for f in sorted(pdir.glob("*.json")):
            hourly = json.loads(f.read_bytes())["hourly"]
            frame = pl.DataFrame(hourly).with_columns(
                pl.col("time").str.to_datetime("%Y-%m-%dT%H:%M", time_zone="UTC")
                .alias("valid_time_utc")
            ).drop("time")
            frames.append(frame.with_columns(pl.lit(pdir.name).alias("point_id")))
    if not frames:
        return pl.DataFrame()
    df = pl.concat(frames, how="diagonal_relaxed")
    value_cols = [c for c in df.columns if c not in ("valid_time_utc", "point_id")]
    df = (
        df.with_columns(
            (pl.col("valid_time_utc") - pl.duration(hours=1)).alias("ts_utc"),
            pl.col("point_id").replace_strict(
                {p.point_id: p.ba for p in POINTS}, default=None).alias("ba"),
            *(pl.col(c).cast(pl.Float32) for c in value_cols),
        )
        .unique(subset=["point_id", "ts_utc"], keep="last")
        .sort("point_id", "ts_utc")
        .select("point_id", "ba", "ts_utc", "valid_time_utc", *value_cols)
    )
    return df if include_sealed else drop_sealed(df)


def safe_previous_day(valid_time_utc: datetime, issue_time_utc: datetime, latency_h: float = 6.0) -> int:
    """Smallest ``N`` such that ``_previous_dayN`` at ``valid_time_utc`` was knowable at issue time.

    Model-agnostic and conservative: ``_previous_dayN`` comes from a run initialised no later than
    ``valid - 24N h``; that run is published ``latency_h`` after initialisation (Open-Meteo:
    "typically 4-6 hours for global models (e.g. ECMWF IFS, GFS) and 1-3 hours for regional
    models"). Requires ``valid - 24N h <= issue - latency``, i.e.
    ``N = ceil((valid - issue + latency) / 24 h)``. Pass the Open-Meteo label (``valid_time_utc``),
    not the hour-start ``ts_utc``.
    """
    hours = (valid_time_utc - issue_time_utc).total_seconds() / 3600 + latency_h
    n = max(0, math.ceil(hours / 24 - 1e-9))
    if n > 7:
        raise ValueError(f"needs previous_day{n}; the archive stops at 7")
    return n
