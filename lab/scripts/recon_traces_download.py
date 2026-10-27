"""Download the public GPU-cluster job traces chosen in the data recon.

Writes raw files to data/raw/traces/<name>/ and one manifest per trace to
data/manifests/traces_<name>.json (url, retrieved_at UTC, bytes, sha256, license).
Raw files are immutable: an existing file is kept and re-hashed, never overwritten.

    cd lab && uv run python scripts/recon_traces_download.py [acme pai2020 alibaba_spot2026]
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from gridpilot.paths import MANIFEST_DIR, RAW_DIR

CC_BY_4 = "CC-BY-4.0"
ACME_GH = "https://raw.githubusercontent.com/InternLM/AcmeTrace/master"
ALI_GH = "https://raw.githubusercontent.com/alibaba/clusterdata/master"
ALI_OSS = "https://aliopentrace.oss-cn-beijing.aliyuncs.com/v2020GPUTraces"

# Published sha256 of the PAI 2020 archives (cluster-trace-gpu-v2020/README.md).
PAI_SHA256 = {
    "pai_group_tag_table.tar.gz": "722fef30b7fb7aa50dabd79155614b5423a9d65cf45a9b26c590d57725423a14",
    "pai_job_table.tar.gz": "5aad7f7caac501136d14ed6a48e40546f825d7b0617a3a4f337e2348fe0a6cb0",
    "pai_machine_spec.tar.gz": "cc0d38a4045af1b1af8179de8b1b54b1ddd995e6160d6d061a6b1000f1276c2d",
    "pai_sensor_table.tar.gz": "9a0b82e8bdf3949281e4ba1423d9b4b34847e52799eecb138966de46da69c7a0",
    "pai_task_table.tar.gz": "cd1d6dc3215d2a8607ccf6b6dd952b5db776df86926c73259fea7c1499ac40e5",
}

_ACME_PKL = [
    "gpu_power_kalos.pkl",
    "gpu_power_seren.pkl",
    "server_power.pkl",
    "util_gpu_kalos.pkl",
    "util_gpu_seren.pkl",
    "util_gpu_pai.pkl",
    "util_gpu_philly.pkl",
]

SOURCES: dict[str, dict] = {
    "acme": {
        "title": "Acme traces (Shanghai AI Lab), clusters Seren and Kalos, Mar-Aug 2023",
        "homepage": "https://github.com/InternLM/AcmeTrace",
        "license": CC_BY_4,
        "license_url": f"{ACME_GH}/LICENSE.txt",
        "citation": "Hu et al., Characterization of Large Language Model Development in the "
        "Datacenter, NSDI '24",
        "notes": "Job tables only. The DCGM/IPMI telemetry (~80 GB on HuggingFace "
        "Qinghao/AcmeTrace) is skipped; the small processed CDF pickles in util_pkl/ are kept.",
        "files": [
            (f"{ACME_GH}/data/job_trace/trace_seren.csv", "trace_seren.csv"),
            (f"{ACME_GH}/data/job_trace/trace_kalos.csv", "trace_kalos.csv"),
            (f"{ACME_GH}/data/cluster_summary.csv", "cluster_summary.csv"),
            (f"{ACME_GH}/data/utils.py", "upstream/utils.py.txt"),
            (f"{ACME_GH}/data/generate_utilization_pkl.ipynb", "upstream/generate_utilization_pkl.ipynb"),
            (f"{ACME_GH}/README.md", "upstream/README.md"),
            (f"{ACME_GH}/LICENSE.txt", "LICENSE.txt"),
        ]
        + [(f"{ACME_GH}/data/utilization/util_pkl/{p}", f"util_pkl/{p}") for p in _ACME_PKL],
    },
    "pai2020": {
        "title": "Alibaba PAI GPU trace cluster-trace-gpu-v2020 (MLaaS), Jul-Aug 2020",
        "homepage": "https://github.com/alibaba/clusterdata/tree/master/cluster-trace-gpu-v2020",
        "license": CC_BY_4,
        "license_url": f"{ALI_GH}/cluster-trace-gpu-v2020/LICENSE",
        "citation": "Weng et al., MLaaS in the Wild: Workload Analysis and Scheduling in "
        "Large-Scale Heterogeneous GPU Clusters, NSDI '22",
        "notes": "Job, task, group-tag, machine-spec and per-instance sensor tables. Skipped: "
        "pai_instance_table (663 MB) and pai_machine_metric (198 MB). Times are shifted by a "
        "constant; in Asia/Shanghai they keep the true time of day and day of week.",
        "files": [
            (f"{ALI_OSS}/{n}", n)
            for n in [
                "pai_job_table.tar.gz",
                "pai_task_table.tar.gz",
                "pai_group_tag_table.tar.gz",
                "pai_machine_spec.tar.gz",
                "pai_sensor_table.tar.gz",
            ]
        ]
        + [
            (f"{ALI_GH}/cluster-trace-gpu-v2020/data/{t}.header", f"{t}.header")
            for t in [
                "pai_job_table",
                "pai_task_table",
                "pai_group_tag_table",
                "pai_machine_spec",
                "pai_sensor_table",
            ]
        ]
        + [
            (f"{ALI_GH}/cluster-trace-gpu-v2020/README.md", "upstream/README.md"),
            (f"{ALI_GH}/cluster-trace-gpu-v2020/LICENSE", "LICENSE"),
        ],
    },
    "alibaba_spot2026": {
        "title": "Alibaba cluster-trace-v2026-spot-gpu (HP vs Spot AI jobs), supplementary",
        "homepage": "https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2026-spot-gpu",
        "license": "Alibaba Cluster Trace Program terms: free use for research or study "
        "(top-level README); no per-trace license file",
        "license_url": f"{ALI_GH}/README.md",
        "citation": "Duan et al., GFS: A Preemptive Scheduling Framework for GPU Clusters with "
        "Predictive Spot Management, ASPLOS '26",
        "notes": "Supplementary: used only for the HP vs Spot (interruptible) share. Times are "
        "seconds from the first submitted job; no calendar date or time zone.",
        "files": [
            (f"{ALI_GH}/cluster-trace-v2026-spot-gpu/job_info_df.csv", "job_info_df.csv"),
            (f"{ALI_GH}/cluster-trace-v2026-spot-gpu/node_info_df.csv", "node_info_df.csv"),
            (f"{ALI_GH}/cluster-trace-v2026-spot-gpu/README.md", "upstream/README.md"),
            (f"{ALI_GH}/README.md", "upstream/clusterdata_README.md"),
        ],
    },
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(client: httpx.Client, url: str, dest: Path, tries: int = 4) -> str:
    """Stream url to dest (atomic rename). Returns the retrieval time (UTC ISO)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, tries + 1):
        try:
            with client.stream("GET", url) as r:
                r.raise_for_status()
                with tmp.open("wb") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        f.write(chunk)
            tmp.rename(dest)
            return datetime.now(UTC).isoformat(timespec="seconds")
        except (httpx.HTTPError, OSError) as exc:
            print(f"  attempt {attempt} failed for {url}: {exc!r}", flush=True)
            time.sleep(5 * attempt)
    raise RuntimeError(f"giving up on {url}")


def download_source(name: str) -> dict:
    spec = SOURCES[name]
    out_dir = RAW_DIR / "traces" / name
    manifest_path = MANIFEST_DIR / f"traces_{name}.json"
    previous = {}
    if manifest_path.exists():
        previous = {f["path"]: f for f in json.loads(manifest_path.read_text())["files"]}
    files = []
    with httpx.Client(timeout=httpx.Timeout(60.0, read=300.0), follow_redirects=True) as client:
        for url, rel in spec["files"]:
            dest = out_dir / rel
            rel_to_data = str(dest.relative_to(RAW_DIR.parent))
            if dest.exists():
                retrieved = previous.get(rel_to_data, {}).get("retrieved_at", "unknown")
                print(f"[{name}] exists, keeping: {rel}", flush=True)
            else:
                print(f"[{name}] downloading {url}", flush=True)
                retrieved = fetch(client, url, dest)
            digest = sha256_of(dest)
            expected = PAI_SHA256.get(rel) if name == "pai2020" else None
            if expected and digest != expected:
                raise RuntimeError(f"sha256 mismatch for {rel}: {digest} != {expected}")
            files.append(
                {
                    "url": url,
                    "path": rel_to_data,
                    "retrieved_at": retrieved,
                    "bytes": dest.stat().st_size,
                    "sha256": digest,
                    "sha256_matches_published": (digest == expected) if expected else None,
                }
            )
            print(f"[{name}]   {rel}: {dest.stat().st_size:,} bytes", flush=True)
    manifest = {
        "source": f"traces/{name}",
        "title": spec["title"],
        "homepage": spec["homepage"],
        "license": spec["license"],
        "license_url": spec["license_url"],
        "citation": spec["citation"],
        "notes": spec["notes"],
        "files": files,
    }
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"[{name}] manifest -> {manifest_path}", flush=True)
    return manifest


def main(argv: list[str]) -> None:
    names = argv or list(SOURCES)
    for name in names:
        download_source(name)


if __name__ == "__main__":
    main(sys.argv[1:])
