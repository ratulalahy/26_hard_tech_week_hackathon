"""Exact-interval GPU capacity at one site (spec §8 "Core policy", §15 F10, F11).

Occupancy is a step function of integer-microsecond time, kept as sorted breakpoints, not
hourly bins. Segment k covers [t_k, t_{k+1}) with usage u_k. The first breakpoint is a
sentinel far in the past; the last segment runs to +inf with usage 0, because every
reservation ends. Intervals are half-open: a job ending at t and one starting at t do not
overlap. Integer time makes adjacency and tolerances exact.

**Structure (window-local).** With every F11 booking pre-reserved, a site holds about two
breakpoints per job in the run (~2 M for a validation year). Queries and updates must not
touch all of them. The breakpoints are split into sorted chunks of about `chunk` entries:
- chunk c holds numpy arrays `_T[c]` (times) and `_U[c]` (raw usage); the true usage is
  `_U[c] + _add[c]`, a lazy add applied to whole chunks by long range updates;
- `_first[c]` is the chunk's first time and `_max[c]` its true maximum.

`max_in`, `fits`, `earliest_start` and range updates locate chunks by binary search, then
touch only the partial end chunks and the per-chunk maxima of chunks in the window: cost
O(log n + chunk + chunks in window). `advance(now)` drops chunks wholly in the past.
"""

from __future__ import annotations

import numpy as np

MIN_US = -(2**62)  # sentinel: the first breakpoint, before every real time
_PRUNE_CHUNKS = 64  # drop past chunks once this many have accumulated


class Capacity:
    """GPU slots at one site, with exact interval maxima over reservations (int µs)."""

    __slots__ = ("_B", "_T", "_U", "_add", "_first", "_floor", "_max", "_min", "slots")

    def __init__(self, slots: int, chunk: int = 128):
        if slots < 0:
            raise ValueError(f"slots must be >= 0, got {slots}")
        if chunk < 2:
            raise ValueError("chunk must be >= 2")
        self.slots = int(slots)
        self._B = int(chunk)
        self._T = [np.array([MIN_US], dtype=np.int64)]
        self._U = [np.zeros(1, dtype=np.int64)]
        self._first = np.array([MIN_US], dtype=np.int64)
        self._add = np.zeros(1, dtype=np.int64)
        self._max = np.zeros(1, dtype=np.int64)
        self._min = np.zeros(1, dtype=np.int64)
        self._floor = MIN_US  # no query may start before this instant

    @classmethod
    def from_intervals(
        cls,
        slots: int,
        starts: np.ndarray,
        ends: np.ndarray,
        gpus: np.ndarray,
        chunk: int = 128,
    ) -> Capacity:
        """Bulk-build from reservations [starts, ends) x gpus. Raises if any instant
        exceeds `slots`."""
        cap = cls(slots, chunk)
        starts = np.asarray(starts, dtype=np.int64)
        ends = np.asarray(ends, dtype=np.int64)
        gpus = np.asarray(gpus, dtype=np.int64)
        if starts.size == 0:
            return cap
        if (ends <= starts).any() or (gpus <= 0).any() or (starts <= MIN_US).any():
            raise ValueError("empty interval, non-positive gpus or time before the sentinel")
        times = np.concatenate([starts, ends])
        delta = np.concatenate([gpus, -gpus])
        order = np.argsort(times, kind="stable")
        times, delta = times[order], delta[order]
        uniq, first_idx = np.unique(times, return_index=True)
        usage = np.cumsum(np.add.reduceat(delta, first_idx))
        if usage.max() > cap.slots:
            raise ValueError(f"reservations reach {int(usage.max())} GPUs > {cap.slots} slots")
        t = np.concatenate([[MIN_US], uniq]).astype(np.int64)
        u = np.concatenate([[0], usage]).astype(np.int64)
        cut = range(0, len(t), cap._B)
        cap._T = [t[i:i + cap._B].copy() for i in cut]
        cap._U = [u[i:i + cap._B].copy() for i in cut]
        cap._first = np.array([a[0] for a in cap._T], dtype=np.int64)
        cap._add = np.zeros(len(cap._T), dtype=np.int64)
        cap._max = np.array([a.max() for a in cap._U], dtype=np.int64)
        cap._min = np.array([a.min() for a in cap._U], dtype=np.int64)
        return cap

    # ------------------------------------------------------------------ location

    def _locate(self, x: int) -> tuple[int, int]:
        """(chunk, index) of the segment that contains instant x."""
        c = int(np.searchsorted(self._first, x, side="right")) - 1
        i = int(np.searchsorted(self._T[c], x, side="right")) - 1
        return c, i

    def _check(self, start: int, end: int) -> None:
        if start < self._floor:
            raise ValueError(f"query at {start} is before the pruned horizon {self._floor}")
        if end <= start:
            raise ValueError(f"empty or reversed interval [{start}, {end})")

    # ------------------------------------------------------------------ queries

    def max_in(self, start: int, end: int) -> int:
        """Exact maximum GPUs in use at any instant of [start, end)."""
        self._check(start, end)
        c1, i1 = self._locate(start)
        c2, i2 = self._locate(end - 1)
        if c1 == c2:
            return int(self._U[c1][i1:i2 + 1].max() + self._add[c1])
        m = max(int(self._U[c1][i1:].max() + self._add[c1]),
                int(self._U[c2][:i2 + 1].max() + self._add[c2]))
        if c2 > c1 + 1:
            m = max(m, int(self._max[c1 + 1:c2].max()))
        return m

    def fits(self, start: int, end: int, gpus: int) -> bool:
        """True if `gpus` more GPUs are free throughout [start, end)."""
        return gpus <= self.slots and self.max_in(start, end) + gpus <= self.slots

    def earliest_start(
        self, earliest: int, duration: int, gpus: int, latest: int | None = None
    ) -> int | None:
        """Earliest start s in [earliest, latest] with `gpus` free over [s, s + duration).

        The answer is `earliest` or a release instant. Returns None if the job is larger
        than the site or nothing fits by `latest` (None means no upper bound).
        """
        self._check(earliest, earliest + duration)
        thr = self.slots - gpus
        if thr < 0 or (latest is not None and earliest > latest):
            return None
        if self.max_in(earliest, earliest + duration) <= thr:
            return int(earliest)
        cand = int(earliest)
        c, i = self._locate(cand)
        nchunks = len(self._T)
        while True:
            if latest is not None and cand > latest:
                return None
            t = self._T[c]
            v = self._U[c][i:] + self._add[c]
            blocked = np.flatnonzero(v > thr)
            if blocked.size:
                blocked += i
                nxt = self._first[c + 1] if c + 1 < nchunks else np.iinfo(np.int64).max
                seg_end = np.append(t[1:], nxt)[blocked]  # end of each blocked segment
                # Free stretches: [cand, start of 1st blocked), [end of k-th, start of k+1-th).
                s_free = np.concatenate([[cand], seg_end[:-1]])
                e_free = t[blocked]
                ok = np.flatnonzero(e_free - s_free >= duration)
                if ok.size:
                    ans = int(max(s_free[ok[0]], cand))
                    return ans if latest is None or ans <= latest else None
                cand = max(cand, int(seg_end[-1]))
            # Free from `cand` to the end of this chunk. Look for the next chunk that is
            # blocked and starts before cand + duration; otherwise cand is the answer.
            if latest is not None and cand > latest:
                return None
            cend = int(np.searchsorted(self._first, cand + duration, side="left"))
            nz = np.flatnonzero(self._max[c + 1:cend] > thr)
            if nz.size == 0:
                return cand
            c, i = c + 1 + int(nz[0]), 0

    # ------------------------------------------------------------------ updates

    def reserve(self, start: int, end: int, gpus: int) -> None:
        """Commit `gpus` over [start, end). Raises ValueError if it would exceed slots."""
        if gpus <= 0:
            raise ValueError(f"gpus must be positive, got {gpus}")
        if not self.fits(start, end, gpus):
            raise ValueError(
                f"reservation of {gpus} GPUs over [{start}, {end}) exceeds {self.slots} slots"
            )
        self._range_add(start, end, gpus)

    def release(self, start: int, end: int, gpus: int) -> None:
        """Remove a reservation made earlier with the same interval and gpus."""
        self._check(start, end)
        if self.min_in(start, end) < gpus:
            raise ValueError(f"release of {gpus} GPUs over [{start}, {end}) exceeds usage")
        self._range_add(start, end, -gpus)

    def min_in(self, start: int, end: int) -> int:
        """Exact minimum GPUs in use over [start, end) (used to guard releases)."""
        self._check(start, end)
        c1, i1 = self._locate(start)
        c2, i2 = self._locate(end - 1)
        if c1 == c2:
            return int(self._U[c1][i1:i2 + 1].min() + self._add[c1])
        m = min(int(self._U[c1][i1:].min() + self._add[c1]),
                int(self._U[c2][:i2 + 1].min() + self._add[c2]))
        if c2 > c1 + 1:
            m = min(m, int(self._min[c1 + 1:c2].min()))
        return m

    def _split(self, x: int) -> None:
        """Make x a breakpoint, if it is not one already."""
        c, i = self._locate(x)
        t = self._T[c]
        if t[i] == x:
            return
        self._T[c] = t = np.insert(t, i + 1, x)
        self._U[c] = u = np.insert(self._U[c], i + 1, self._U[c][i])
        if len(t) > 2 * self._B:  # split the chunk in two halves
            h = len(t) // 2
            self._T[c:c + 1] = [t[:h].copy(), t[h:].copy()]
            self._U[c:c + 1] = [u[:h].copy(), u[h:].copy()]
            a = self._add[c]
            self._first = np.insert(self._first, c + 1, t[h])
            self._add = np.insert(self._add, c + 1, a)
            self._max = np.insert(self._max, c + 1, 0)
            self._min = np.insert(self._min, c + 1, 0)
            self._stat(c)
            self._stat(c + 1)

    def _stat(self, c: int) -> None:
        """Refresh chunk c's true max and min."""
        u, a = self._U[c], self._add[c]
        self._max[c] = u.max() + a
        self._min[c] = u.min() + a

    def _range_add(self, start: int, end: int, g: int) -> None:
        self._check(start, end)
        self._split(start)
        self._split(end)
        c1, i1 = self._locate(start)
        c2, i2 = self._locate(end)  # segment starting at `end`, not updated
        if c1 == c2:
            self._U[c1][i1:i2] += g
            self._stat(c1)
            return
        self._U[c1][i1:] += g
        self._stat(c1)
        if c2 > c1 + 1:
            self._add[c1 + 1:c2] += g
            self._max[c1 + 1:c2] += g
            self._min[c1 + 1:c2] += g
        if i2 > 0:
            self._U[c2][:i2] += g
            self._stat(c2)

    def advance(self, now: int) -> None:
        """Declare that no query will start before `now`, and drop older chunks."""
        if now < self._floor:
            raise ValueError(f"time went backwards: {now} < {self._floor}")
        self._floor = int(now)
        c = int(np.searchsorted(self._first, now, side="right")) - 1
        if c >= _PRUNE_CHUNKS:
            del self._T[:c]
            del self._U[:c]
            self._first = self._first[c:].copy()
            self._add = self._add[c:].copy()
            self._max = self._max[c:].copy()
            self._min = self._min[c:].copy()

    # ------------------------------------------------------------------ misc

    @property
    def horizon(self) -> int:
        """The earliest instant a query may start at (the last `advance`)."""
        return self._floor

    @property
    def n_breakpoints(self) -> int:
        return sum(len(t) for t in self._T)

    def copy(self) -> Capacity:
        out = Capacity(self.slots, self._B)
        out._T = [t.copy() for t in self._T]
        out._U = [u.copy() for u in self._U]
        out._first = self._first.copy()
        out._add = self._add.copy()
        out._max = self._max.copy()
        out._min = self._min.copy()
        out._floor = self._floor
        return out

    def view(self) -> CapacityView:
        return CapacityView(self)

    def __repr__(self) -> str:
        return f"Capacity(slots={self.slots}, breakpoints={self.n_breakpoints})"


class CapacityView:
    """Read-only access to a site's capacity, the only form policies receive."""

    __slots__ = ("_c",)

    def __init__(self, cap: Capacity):
        self._c = cap

    @property
    def slots(self) -> int:
        return self._c.slots

    @property
    def horizon(self) -> int:
        return self._c.horizon

    def max_in(self, start: int, end: int) -> int:
        return self._c.max_in(start, end)

    def fits(self, start: int, end: int, gpus: int) -> bool:
        return self._c.fits(start, end, gpus)

    def earliest_start(
        self, earliest: int, duration: int, gpus: int, latest: int | None = None
    ) -> int | None:
        return self._c.earliest_start(earliest, duration, gpus, latest)
