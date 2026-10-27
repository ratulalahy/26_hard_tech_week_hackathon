"""Exact-interval GPU capacity at one site (spec §8 "Core policy", §15 F10).

Occupancy is a step function of time kept as sorted breakpoints, not hourly bins:
`_t[k]` is a breakpoint and `_u[k]` the GPUs in use on `[_t[k], _t[k+1])`. The last
segment runs to +inf with usage 0, because every reservation ends. Intervals are
half-open, so a job ending at t and one starting at t do not overlap.

Times are float seconds (the simulator uses Unix seconds). Reservations are immutable:
there is no release. `advance(now)` lets the structure forget the past, so its size
tracks the reservations still running or pending, not the whole history.
"""

from __future__ import annotations

import math

import numpy as np

_PRUNE_AT = 512  # drop past breakpoints once this many have accumulated


class Capacity:
    """GPU slots at one site, with exact interval maxima over reservations."""

    __slots__ = ("_floor", "_t", "_u", "slots")

    def __init__(self, slots: int):
        if slots < 0:
            raise ValueError(f"slots must be >= 0, got {slots}")
        self.slots = int(slots)
        self._t = np.array([-math.inf])
        self._u = np.zeros(1, dtype=np.int64)
        self._floor = -math.inf  # no query may start before this instant

    # ------------------------------------------------------------------ queries

    def _check(self, start: float, end: float) -> None:
        if start < self._floor:
            raise ValueError(f"query at {start} is before the pruned horizon {self._floor}")
        if not end > start:
            raise ValueError(f"empty or reversed interval [{start}, {end})")

    def _span(self, start: float, end: float) -> tuple[int, int]:
        """Segment indices [i, j) that overlap [start, end)."""
        i = int(np.searchsorted(self._t, start, side="right")) - 1
        j = int(np.searchsorted(self._t, end, side="left"))
        return i, j

    def max_in(self, start: float, end: float) -> int:
        """Exact maximum GPUs in use at any instant of [start, end)."""
        self._check(start, end)
        i, j = self._span(start, end)
        return int(self._u[i:j].max())

    def fits(self, start: float, end: float, gpus: int) -> bool:
        """True if `gpus` more GPUs are free throughout [start, end)."""
        return gpus <= self.slots and self.max_in(start, end) + gpus <= self.slots

    def earliest_start(
        self, earliest: float, duration: float, gpus: int, latest: float = math.inf
    ) -> float | None:
        """Earliest start s in [earliest, latest] with `gpus` free over [s, s + duration).

        The answer is `earliest` or a release instant. Returns None if the job is larger
        than the site or nothing fits by `latest`.
        """
        self._check(earliest, earliest + duration)
        if gpus > self.slots or earliest > latest:
            return None
        t = self._t
        blocked = np.flatnonzero(self._u > self.slots - gpus)  # segments too full for gpus
        s = earliest
        while s <= latest:
            i, j = self._span(s, s + duration)
            a = int(np.searchsorted(blocked, i, side="left"))
            b = int(np.searchsorted(blocked, j, side="left"))
            if a == b:
                return float(s)
            # Any start before the end of the last blocked segment in the window still
            # overlaps it, so jump there. The final segment is never blocked.
            s = float(t[blocked[b - 1] + 1])
        return None

    # ------------------------------------------------------------------ updates

    def reserve(self, start: float, end: float, gpus: int) -> None:
        """Commit `gpus` over [start, end). Raises ValueError if it would exceed slots."""
        if gpus <= 0:
            raise ValueError(f"gpus must be positive, got {gpus}")
        if not self.fits(start, end, gpus):
            raise ValueError(
                f"reservation of {gpus} GPUs over [{start}, {end}) exceeds {self.slots} slots"
            )
        self._split(start)
        self._split(end)
        i = int(np.searchsorted(self._t, start, side="left"))
        j = int(np.searchsorted(self._t, end, side="left"))
        self._u[i:j] += gpus

    def _split(self, x: float) -> None:
        """Make x a breakpoint, if it is not one already."""
        k = int(np.searchsorted(self._t, x, side="left"))
        if k < len(self._t) and self._t[k] == x:
            return
        self._t = np.insert(self._t, k, x)
        self._u = np.insert(self._u, k, self._u[k - 1])

    def advance(self, now: float) -> None:
        """Declare that no query will start before `now`, and drop older breakpoints."""
        if now < self._floor:
            raise ValueError(f"time went backwards: {now} < {self._floor}")
        self._floor = now
        k = int(np.searchsorted(self._t, now, side="right")) - 1  # segment holding now
        if k >= _PRUNE_AT:
            self._t = self._t[k:].copy()
            self._t[0] = -math.inf
            self._u = self._u[k:].copy()

    # ------------------------------------------------------------------ misc

    @property
    def horizon(self) -> float:
        """The earliest instant a query may start at (the last `advance`)."""
        return self._floor

    def copy(self) -> Capacity:
        out = Capacity(self.slots)
        out._t = self._t.copy()
        out._u = self._u.copy()
        out._floor = self._floor
        return out

    def __repr__(self) -> str:
        return f"Capacity(slots={self.slots}, breakpoints={len(self._t)})"
