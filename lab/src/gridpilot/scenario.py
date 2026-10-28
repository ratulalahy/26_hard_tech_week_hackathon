"""Evaluation windows and scenario knobs for `run_pipeline` (Stage 3 T10, Part A).

`Window` is one evaluation window (F14.4), defined in `gridpilot.window` and re-exported
here. `validation` and `fallback` can always be built; the sealed test window only inside the
logged test-mode context (`gridpilot.seal`, Stage 3 T11).

`Scenario` is one point in the §7 assumption registry. Every knob is **assumed**. The
defaults are the registered primary scenario; `EXTENSIONS` holds the one-axis endpoint
sensitivities the owner chose (D-058). F14.1 says which knobs change U or its deadlines:
- `batch_delay_s` changes deadlines (it is one of the F14.1 scenarios, so it is already in
  the common A);
- `phase_days` changes the arrival stream, so each phase has its own A;
- `dest_slots`, `transfer_s` and `mobility_max_gpus` leave U and its deadlines unchanged.

A sensitivity scenario never changes the registered primary results: it runs in its own
run directory and is never exported into the primary `results/` artifacts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import polars as pl

from gridpilot.cohort import _batch_delay
from gridpilot.sim import HOME, SITES, TRANSFER_S
from gridpilot.window import CONSTRUCTIBLE_WINDOWS, WARMUP_MIN, Window  # noqa: F401 (re-export)

# --------------------------------------------------------------------------- Scenario

PHASES = (0, 49, 98)  # pre-registered workload alignments (spec §7)
PRIMARY_POLICIES = ("U", "G", "S", "K", "W", "L", "H", "W_time", "L_time")
EXTENSION_POLICIES = ("U", "S", "K", "W", "L")
TIME_ONLY_POLICIES = ("W_time", "L_time")
_DEFAULTS = {"dest_slots": SITES["BPAT"], "transfer_s": TRANSFER_S, "batch_delay_s": 21600,
             "mobility_max_gpus": None, "phase_days": 0}


@dataclass(frozen=True)
class Scenario:
    name: str = "primary"
    dest_slots: int = _DEFAULTS["dest_slots"]  # spare GPU slots at each destination
    transfer_s: float = _DEFAULTS["transfer_s"]  # remote staging before execution
    batch_delay_s: int = _DEFAULTS["batch_delay_s"]  # flexible Pretrain/SFT/MLLM delay
    mobility_max_gpus: int | None = _DEFAULTS["mobility_max_gpus"]  # None = no limit
    phase_days: int = _DEFAULTS["phase_days"]
    note: str = "registered primary scenario"

    def __post_init__(self):
        if self.phase_days not in PHASES:
            raise ValueError(f"phase_days must be one of {PHASES} (pre-registered)")
        if self.dest_slots < 0:
            raise ValueError("dest_slots must be >= 0")
        if not (self.transfer_s >= 0) or self.transfer_s != self.transfer_s:
            raise ValueError("transfer_s must be finite and >= 0")
        if self.batch_delay_s < 0 or self.batch_delay_s % 3600:
            raise ValueError("batch_delay_s must be a whole number of hours >= 0")
        if self.mobility_max_gpus is not None and self.mobility_max_gpus < 1:
            raise ValueError("mobility_max_gpus must be None or >= 1")
        if self.name == "primary" and not self._knobs_default():
            raise ValueError("the name 'primary' is reserved for the registered defaults")
        object.__setattr__(self, "transfer_s", float(self.transfer_s))

    def _knobs_default(self) -> bool:
        return all(getattr(self, k) == v for k, v in _DEFAULTS.items())

    @classmethod
    def primary(cls) -> Scenario:
        return cls()

    @classmethod
    def named(cls, name: str) -> Scenario:
        if name == "primary":
            return cls.primary()
        if name not in EXTENSIONS:
            raise ValueError(f"unknown scenario {name!r}; registered: primary, "
                             f"{', '.join(EXTENSIONS)}")
        return EXTENSIONS[name]

    @property
    def is_primary(self) -> bool:
        return self.name == "primary" and self._knobs_default()

    @property
    def has_destinations(self) -> bool:
        return self.dest_slots > 0

    @property
    def changes_deadlines(self) -> bool:
        """F14.1: the knob changes U's deadlines (and so may change A)."""
        return self.batch_delay_s != _DEFAULTS["batch_delay_s"]

    @property
    def own_cohort(self) -> bool:
        """F14.1: phases 49 and 98 have their own arrival streams and their own A."""
        return self.phase_days != 0

    def sites(self) -> dict[str, int]:
        return {s: (n if s == HOME else self.dest_slots) for s, n in SITES.items()}

    def time_only_sites(self) -> dict[str, int]:
        return {s: (n if s == HOME else 0) for s, n in SITES.items()}

    def policies(self) -> tuple[str, ...]:
        if self.is_primary:
            return PRIMARY_POLICIES
        return EXTENSION_POLICIES + (TIME_ONLY_POLICIES if self.has_destinations else ())

    def transform(self, jobs: pl.DataFrame) -> pl.DataFrame:
        """The replay frame under this scenario's flags and delays (assumed). The primary
        scenario returns the frame unchanged."""
        out = jobs
        if self.batch_delay_s != _DEFAULTS["batch_delay_s"]:
            # the same rule as the registered F14.1 batch-delay scenarios (fix r1 M-10)
            out = _batch_delay(self.batch_delay_s // 3600)(out)
        if self.mobility_max_gpus is not None:
            out = out.with_columns(
                (pl.col("mobile") & (pl.col("gpus") <= self.mobility_max_gpus)).alias("mobile"))
        return out

    def cohort_fn(self):
        """A prefix_cohort scenario callable: (jobs, sites) -> (jobs, this scenario's
        sites)."""
        def f(jobs, _sites):
            return self.transform(jobs), self.sites()
        return f

    def config(self) -> dict:
        d = asdict(self)
        d["sites"] = self.sites()
        d["time_only_sites"] = self.time_only_sites()
        d["policies"] = list(self.policies())
        d["changes_deadlines"] = self.changes_deadlines
        d["own_cohort"] = self.own_cohort
        return d


EXTENSIONS: dict[str, Scenario] = {s.name: s for s in (
    Scenario("phase_49", phase_days=49,
             note="workload phase 49 days: same primary knobs, own arrival stream and A"),
    Scenario("phase_98", phase_days=98,
             note="workload phase 98 days: same primary knobs, own arrival stream and A"),
    Scenario("dest_slots_0", dest_slots=0,
             note="destination capacity 0 at CISO, BPAT and NEVP: time-only"),
    Scenario("dest_slots_1024", dest_slots=1024,
             note="destination capacity 1,024 slots at CISO, BPAT and NEVP"),
    Scenario("transfer_120min", transfer_s=7200.0,
             note="remote transfer time 120 min before execution"),
    Scenario("batch_delay_24h", batch_delay_s=86400,
             note="flexible Pretrain/SFT/MLLM allowed delay 24 h; Eval stays 1 h"),
    Scenario("mobility_le_8gpus", mobility_max_gpus=8,
             note="only jobs requesting at most 8 GPUs may move (data gravity)"),
)}

@dataclass(frozen=True)
class RunResult:
    """What `run_pipeline` produced. `metrics_canonical_sha256` is set for the primary
    scenario (results/metrics.json), `summary_canonical_sha256` for an extension
    (summary.json in the run directory)."""

    run_id: str
    run_dir: Path
    rc: int
    window: Window
    scenario: Scenario
    ledger_sha256: dict[str, str] = field(default_factory=dict)
    metrics_canonical_sha256: str | None = None
    summary_canonical_sha256: str | None = None
    exported: bool = False
    # test window only (T20): the in-memory ledgers, cohort and truth the D-071 extras reuse,
    # so the session never re-reads its own run directory
    objects: dict | None = field(default=None, compare=False, repr=False)


__all__ = ["EXTENSIONS", "PRIMARY_POLICIES", "RunResult", "Scenario", "Window"]
