"""Evaluation windows (F14.4; Stage 3 T10 Part A, T11 B2).

`Window` is one evaluation window. It carries its `name` (validation, fallback or test) and
the upper bound every layer may read up to, `read_end`:
- validation and fallback: TEST_START (the seal); their F is earlier (2025-10-24);
- test: F_test from the freeze record, never past TEST_END.

Every data layer takes a `window` explicitly and defaults to `Window.validation()`. The test
window is constructible only inside the active test-mode context (`gridpilot.seal.test_mode`,
entered only by `run_slice --window test`); outside it, `Window.test()` raises `SealError`.

This module is import-light (no simulator) so every layer can import it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from gridpilot import seal
from gridpilot.splits import TEST_END, TEST_START

WARMUP_MIN = timedelta(days=15)  # F2
WINDOW_NAMES = ("validation", "fallback", "test")
CONSTRUCTIBLE_WINDOWS = ("validation", "fallback")  # without the test-mode context
_WINDOWS = {
    "validation": (datetime(2024, 10, 17, tzinfo=UTC), datetime(2024, 11, 1, tzinfo=UTC),
                   datetime(2025, 10, 24, tzinfo=UTC)),
    "fallback": (datetime(2025, 7, 10, tzinfo=UTC), datetime(2025, 7, 25, tzinfo=UTC),
                 datetime(2025, 10, 24, tzinfo=UTC)),
}


@dataclass(frozen=True)
class Window:
    """[init, eval_start) is the U warm-up; arrivals in [eval_start, A) are scored; F ends
    the drain (F2, F14.4)."""

    name: str
    init: datetime
    eval_start: datetime
    F: datetime

    def __post_init__(self):
        if self.name not in WINDOW_NAMES:
            raise ValueError(f"unknown window {self.name!r}; one of {WINDOW_NAMES}")
        for k in ("init", "eval_start", "F"):
            t = getattr(self, k)
            if not isinstance(t, datetime) or t.tzinfo is None:
                raise ValueError(f"window {k} must be timezone-aware, got {t!r}")
        if not self.init < self.eval_start < self.F:
            raise ValueError("window needs init < eval_start < F")
        if self.eval_start - self.init < WARMUP_MIN:
            raise ValueError("warm-up shorter than 15 days (F2)")
        if self.name == "test":
            s = seal.require_active("Window.test")
            if (self.init, self.eval_start) != (seal.TEST_INIT, TEST_START):
                raise ValueError("the test window is [2025-10-17, 2025-11-01) warm-up then "
                                 "arrivals from TEST_START (F14.4)")
            if self.F != s.F:
                raise ValueError(f"test F {self.F} differs from the freeze record's {s.F}")
            if self.F > TEST_END:
                raise ValueError("test F is past TEST_END")
        elif self.F > TEST_START:
            raise ValueError("F reaches the seal (TEST_START)")

    @property
    def is_test(self) -> bool:
        return self.name == "test"

    @property
    def read_end(self) -> datetime:
        """The latest instant (exclusive) any layer may read for this window."""
        return self.F if self.is_test else TEST_START

    def check_active(self, what: str) -> None:
        """A test-window read needs the test-mode context to still be active."""
        if self.is_test:
            seal.require_active(what)

    @classmethod
    def validation(cls) -> Window:
        return cls("validation", *_WINDOWS["validation"])

    @classmethod
    def fallback(cls) -> Window:
        return cls("fallback", *_WINDOWS["fallback"])

    @classmethod
    def test(cls) -> Window:
        """The sealed test window, F from the freeze record. Only inside test mode."""
        s = seal.require_active("Window.test")
        return cls("test", seal.TEST_INIT, TEST_START, s.F)

    @classmethod
    def named(cls, name: str) -> Window:
        if name == "test":
            return cls.test()
        if name not in _WINDOWS:
            raise ValueError(f"unknown window {name!r}")
        return cls(name, *_WINDOWS[name])


def resolve(window: Window | None, what: str = "read") -> Window:
    """`window`, defaulting to validation; a test window must still be inside test mode."""
    w = window if window is not None else Window.validation()
    if not isinstance(w, Window):
        raise TypeError(f"window must be a Window, got {type(w).__name__}")
    w.check_active(what)
    return w


__all__ = ["CONSTRUCTIBLE_WINDOWS", "WARMUP_MIN", "WINDOW_NAMES", "Window", "resolve"]
