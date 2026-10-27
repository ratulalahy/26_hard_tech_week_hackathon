"""EIA-930 hourly grid data: download the six-month bulk files, parse them into a tidy table.

Source: U.S. Energy Information Administration, Form EIA-930 (Hourly Electric Grid Monitor),
https://www.eia.gov/electricity/gridmonitor/. Keyless bulk CSVs, one per half-year.

Timestamp convention of the tidy table (see ``docs/data-profile/grid.md``):
``ts_utc`` is the START of the hour (hour-beginning, UTC). EIA labels each row with the END of
the hour ("UTC Time at End of Hour"); we subtract one hour so that half-open windows such as the
sealed test window [2025-11-01T00:00Z, 2026-11-01T00:00Z) select exactly the hours inside them.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import httpx
import polars as pl

from gridpilot.paths import INTERIM_DIR, MANIFEST_DIR, RAW_DIR

BASE_URL = "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles"
RAW_EIA_DIR = RAW_DIR / "eia930"
INTERIM_EIA_DIR = INTERIM_DIR / "eia930"
MANIFEST_PATH = MANIFEST_DIR / "eia930.json"
HALVES = ("Jan_Jun", "Jul_Dec")
LICENSE_NOTE = (
    "U.S. Government work (EIA), public domain; no copyright restrictions. EIA asks users to "
    "acknowledge the source, e.g. 'Source: U.S. Energy Information Administration, Form EIA-930 "
    "Hourly Electric Grid Monitor (retrieved <date>)'. See https://www.eia.gov/about/copyrights_reuse.php"
)


# --------------------------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------------------------


def file_name(kind: str, year: int, half: str) -> str:
    if half not in HALVES:
        raise ValueError(f"half must be one of {HALVES}, got {half!r}")
    return f"EIA930_{kind.upper()}_{year}_{half}.csv"


def six_month_files(
    kind: str = "BALANCE", first_year: int = 2019, last_year: int = 2026
) -> list[str]:
    return [file_name(kind, y, h) for y in range(first_year, last_year + 1) for h in HALVES]


def _sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def download_file(
    name: str, dest_dir: Path = RAW_EIA_DIR, overwrite: bool = False, url: str | None = None
) -> dict:
    """Stream one file to ``dest_dir`` (atomic rename, read-only) and return its manifest entry.

    ``url`` defaults to the six-month-file location for ``name``. Raw data is immutable: an
    existing file is kept unless ``overwrite`` is set.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    url = url or f"{BASE_URL}/{name}"
    dest = dest_dir / name
    if dest.exists() and not overwrite:
        return {"file": name, "url": url, "bytes": dest.stat().st_size, "sha256": _sha256(dest),
                "retrieved_at": None, "status": "kept-existing"}
    h = hashlib.sha256()
    retrieved_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with httpx.stream("GET", url, timeout=httpx.Timeout(60.0, read=300.0), follow_redirects=True) as r:
        r.raise_for_status()
        last_modified = r.headers.get("last-modified")
        fd, tmp = tempfile.mkstemp(dir=dest_dir, prefix=f".{name}.", suffix=".part")
        try:
            with os.fdopen(fd, "wb") as f:
                for block in r.iter_bytes(1 << 20):
                    h.update(block)
                    f.write(block)
            os.chmod(tmp, 0o444)
            os.replace(tmp, dest)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
    return {"file": name, "url": url, "retrieved_at": retrieved_at, "bytes": dest.stat().st_size,
            "sha256": h.hexdigest(), "server_last_modified": last_modified, "status": "downloaded"}


def download(names: Iterable[str], workers: int = 4, overwrite: bool = False) -> list[dict]:
    names = list(names)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda n: download_file(n, overwrite=overwrite), names))


BA_WORKBOOK_URL = "https://www.eia.gov/electricity/gridmonitor/knownissues/xls/{ba}.xlsx"
REFERENCE_TABLES_URL = "https://www.eia.gov/electricity/930-content/EIA930_Reference_Tables.xlsx"


def download_ba_workbooks(bas: Iterable[str], workers: int = 4) -> list[dict]:
    """Per-BA workbooks (all history, plus EIA's hourly CO2 estimates from 2018-07-01)."""
    bas = list(bas)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        entries = list(pool.map(
            lambda b: download_file(f"{b}.xlsx", RAW_EIA_DIR / "ba_workbooks",
                                    url=BA_WORKBOOK_URL.format(ba=b)), bas))
    for e in entries:  # manifest keys are paths relative to data/raw/eia930/
        e["file"] = f"ba_workbooks/{e['file']}"
    return entries


def write_manifest(entries: Sequence[dict], notes: dict | None = None) -> Path:
    """Merge ``entries`` into ``data/manifests/eia930.json`` (keyed by file name).

    An entry whose file was kept (not re-downloaded) keeps its original ``retrieved_at``.
    """
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {}
    files = {f["file"]: f for f in manifest.get("files", [])}
    for e in entries:
        old = files.get(e["file"], {})
        merged = {**old, **{k: v for k, v in e.items() if v is not None}}
        merged.pop("status", None)
        merged["license"] = LICENSE_NOTE
        files[e["file"]] = merged
    manifest["source"] = "EIA Form EIA-930 Hourly Electric Grid Monitor, six-month bulk files"
    manifest["base_url"] = BASE_URL
    manifest["license"] = LICENSE_NOTE
    if notes:
        manifest.setdefault("notes", {}).update(notes)
    manifest["files"] = sorted(files.values(), key=lambda f: f["file"])
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    return MANIFEST_PATH


# --------------------------------------------------------------------------------------------
# Parse
# --------------------------------------------------------------------------------------------

# Energy-source names as they appear in "Net Generation (MW) from <name>", mapped to our codes.
# Files up to 2024 Jan_Jun use the old 9-source taxonomy; from 2024 Jul_Dec EIA splits hydro,
# solar and wind and adds storage and geothermal (EIA-930 instructions, data codes WAT ... UNK).
FUEL_NAMES: dict[str, str] = {
    "Coal": "coal",
    "Natural Gas": "gas",
    "Nuclear": "nuclear",
    "All Petroleum Products": "oil",
    "Hydropower and Pumped Storage": "hydro",  # old taxonomy: WAT incl. pumped storage
    "Hydropower Excluding Pumped Storage": "hydro_conv",  # new: WAT
    "Pumped Storage": "pumped_storage",  # new: PS
    "Solar": "solar",  # old taxonomy: all solar
    "Solar without Integrated Battery Storage": "solar_nobatt",  # new: SUN
    "Solar with Integrated Battery Storage": "solar_batt",  # new: SNB
    "Wind": "wind",  # old taxonomy: all wind
    "Wind without Integrated Battery Storage": "wind_nobatt",  # new: WND
    "Wind with Integrated Battery Storage": "wind_batt",  # new: WNB
    "Battery Storage": "battery",  # new: BAT
    "Other Energy Storage": "other_storage",  # new: OES
    "Unknown Energy Storage": "unknown_storage",  # new
    "Geothermal": "geothermal",  # new: GEO (in "Other" before 2024 Jul_Dec)
    "Other Fuel Sources": "other",  # OTH
    "Unknown Fuel Sources": "unknown",  # UNK
}

# Harmonized fuel columns in the tidy table (each as gen_<f>_mw and gen_<f>_adj_mw). hydro, solar
# and wind keep the old (combined) meaning across the 2024 taxonomy change; the new split
# columns are kept alongside and are null before 2024-07.
TIDY_FUELS = (
    "coal", "gas", "oil", "nuclear", "hydro", "solar", "wind", "geothermal", "battery",
    "other_storage", "unknown_storage", "other", "unknown",
    "hydro_conv", "pumped_storage", "solar_batt", "wind_batt",
)
# Fuels that partition total generation (sum of these = generation by fuel). The last four
# TIDY_FUELS are sub-components of hydro/solar/wind and must not be added again.
PARTITION_FUELS = TIDY_FUELS[:13]

_TOTALS = {
    "Demand Forecast (MW)": "demand_forecast_mw",
    "Demand (MW)": "demand_mw",
    "Net Generation (MW)": "net_gen_mw",
    "Total Interchange (MW)": "interchange_mw",
    "Sum(Valid DIBAs) (MW)": "sum_valid_dibas_mw",
}
_TS_FMT = "%m/%d/%Y %I:%M:%S %p"


def normalize_header(name: str) -> str:
    """Collapse whitespace and fix EIA's header typos (e.g. 'Solar witho Integrated')."""
    name = re.sub(r"\s+", " ", name.strip().strip('"')).strip()
    return name.replace(" witho Integrated", " with Integrated")


def column_name(header: str) -> str | None:
    """Map one EIA header to its tidy name (None = drop)."""
    h = normalize_header(header)
    fixed = {"Balancing Authority": "ba", "Region": "region", "UTC Time at End of Hour": "utc_end",
             "Local Time at End of Hour": "local_end", "Data Date": None, "Hour Number": None}
    if h in fixed:
        return fixed[h]
    m = re.fullmatch(r"(.+?) \((Imputed|Adjusted)\)", h)
    base, kind = (m.group(1), m.group(2)) if m else (h, None)
    suffix = {None: "", "Imputed": "__imputed", "Adjusted": "__adj"}[kind]
    if base in _TOTALS:
        return _TOTALS[base] + suffix
    m = re.fullmatch(r"Net Generation \(MW\) from (.+)", base)
    if m and m.group(1) in FUEL_NAMES:
        return f"fuel__{FUEL_NAMES[m.group(1)]}{suffix}"
    raise ValueError(f"unknown EIA-930 BALANCE column: {header!r}")


def _sum_or_null(cols: Sequence[str], frame_cols: Sequence[str]) -> pl.Expr:
    """Row-wise sum that is null when every input is null (polars' sum_horizontal gives 0)."""
    present = [c for c in cols if c in frame_cols]
    if not present:
        return pl.lit(None, dtype=pl.Float32)
    any_nn = pl.any_horizontal([pl.col(c).is_not_null() for c in present])
    return pl.when(any_nn).then(pl.sum_horizontal(present)).otherwise(None)


def parse_balance_csv(path: str | Path) -> pl.DataFrame:
    """Parse one BALANCE six-month file into the tidy schema (one row per BA-hour)."""
    raw = pl.read_csv(path, infer_schema=False)
    names = {c: column_name(c) for c in raw.columns}
    raw = raw.select([pl.col(c).alias(n) for c, n in names.items() if n is not None])
    value_cols = [c for c in raw.columns if c not in ("ba", "region", "utc_end", "local_end")]
    df = raw.with_columns(
        pl.col("utc_end").str.to_datetime(_TS_FMT, time_zone="UTC", time_unit="us"),
        pl.col("local_end").str.to_datetime(_TS_FMT, time_unit="us"),
        *[pl.col(c).str.strip_chars().str.replace_all(",", "").cast(pl.Float32) for c in value_cols],
    )
    cols = df.columns
    out = [
        pl.col("ba"),
        (pl.col("utc_end") - pl.duration(hours=1)).alias("ts_utc"),
        ((pl.col("local_end") - pl.col("utc_end").dt.replace_time_zone(None)).dt.total_minutes()
         // 60).cast(pl.Int8).alias("utc_offset_h"),
        pl.col("region"),
        pl.col("demand_forecast_mw"),
    ]
    for base in ("demand_mw", "net_gen_mw", "interchange_mw"):
        adj = f"{base}__adj"
        out += [pl.col(base), pl.col(adj).alias(base.replace("_mw", "_adj_mw")),
                pl.col(f"{base}__imputed").is_not_null().alias(base.replace("_mw", "_imputed"))]
    out.append(pl.col("sum_valid_dibas_mw"))

    # Fuels: harmonize hydro/solar/wind across the taxonomy change, raw and adjusted.
    for sfx, tidy_sfx in (("", "_mw"), ("__adj", "_adj_mw")):
        def fc(code: str, sfx: str = sfx) -> str:
            return f"fuel__{code}{sfx}"
        for f in TIDY_FUELS:
            if f == "hydro" and fc("hydro") not in cols:
                expr = _sum_or_null([fc("hydro_conv"), fc("pumped_storage")], cols)
            elif f == "solar" and fc("solar") not in cols:
                expr = _sum_or_null([fc("solar_nobatt"), fc("solar_batt")], cols)
            elif f == "wind" and fc("wind") not in cols:
                expr = _sum_or_null([fc("wind_nobatt"), fc("wind_batt")], cols)
            elif fc(f) in cols:
                expr = pl.col(fc(f))
            else:
                expr = pl.lit(None, dtype=pl.Float32)
            out.append(expr.cast(pl.Float32).alias(f"gen_{f}{tidy_sfx}"))
    imputed_fuel = [c for c in cols if c.startswith("fuel__") and c.endswith("__imputed")]
    out.append(pl.sum_horizontal([pl.col(c).is_not_null() for c in imputed_fuel])
               .cast(pl.Int8).alias("fuel_imputed_n"))
    out.append(pl.lit(Path(path).stem.removeprefix("EIA930_BALANCE_")).alias("source_file"))
    return df.select(out)


def build_balance(paths: Iterable[str | Path] | None = None,
                  out_path: Path = INTERIM_EIA_DIR / "balance.parquet") -> pl.DataFrame:
    """Parse every BALANCE file into one tidy table, sorted by (ba, ts_utc); write Parquet."""
    paths = sorted(paths or RAW_EIA_DIR.glob("EIA930_BALANCE_*.csv"))
    frames = [parse_balance_csv(p) for p in paths]
    df = pl.concat(frames, how="vertical_relaxed")
    dup = df.height - df.unique(["ba", "ts_utc"]).height
    if dup:
        # Keep the row from the later file (EIA's most recent half-year publication).
        df = df.unique(["ba", "ts_utc"], keep="last", maintain_order=True)
    df = df.with_columns(pl.col("ba").cast(pl.Categorical), pl.col("region").cast(pl.Categorical),
                         pl.col("source_file").cast(pl.Categorical)).sort("ba", "ts_utc")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out_path, compression="zstd", statistics=True)
    return df


def parse_interchange_csv(path: str | Path) -> pl.DataFrame:
    """Parse one INTERCHANGE six-month file: one row per (ba, directly interconnected BA, hour).

    ``interchange_mw`` > 0 means flow OUT of ``ba`` into ``diba`` (EIA sign convention).
    """
    raw = pl.read_csv(path, infer_schema=False)
    raw = raw.rename({c: normalize_header(c) for c in raw.columns})
    return raw.select(
        pl.col("Balancing Authority").alias("ba"),
        pl.col("Directly Interconnected Balancing Authority").alias("diba"),
        (pl.col("UTC Time at End of Hour").str.to_datetime(_TS_FMT, time_zone="UTC", time_unit="us")
         - pl.duration(hours=1)).alias("ts_utc"),
        pl.col("Interchange (MW)").str.replace_all(",", "").cast(pl.Float32).alias("interchange_mw"),
    )


def build_interchange(out_path: Path = INTERIM_EIA_DIR / "interchange.parquet") -> pl.DataFrame:
    paths = sorted(RAW_EIA_DIR.glob("EIA930_INTERCHANGE_*.csv"))
    df = pl.concat([parse_interchange_csv(p) for p in paths]).unique(
        ["ba", "diba", "ts_utc"], keep="last", maintain_order=True)
    df = df.with_columns(pl.col("ba").cast(pl.Categorical), pl.col("diba").cast(pl.Categorical))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.sort("ba", "diba", "ts_utc").write_parquet(out_path, compression="zstd")
    return df
