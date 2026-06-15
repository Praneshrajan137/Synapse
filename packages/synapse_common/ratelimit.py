"""Application-layer token-bucket rate limiter (no external dependency).

nginx already rate-limits by ``$binary_remote_addr`` at the edge (E-S5-06), but
the API gateway must also protect itself when reached directly (compose/dev, or a
mesh-internal caller). This is a small, dependency-free token bucket — chosen over
``slowapi`` to avoid a new dependency and keep the logic testable and pinned to
this repo's semantics.

Design:
  * One :class:`TokenBucket` per key (client IP, by default). Capacity = burst
    size; ``refill_per_sec`` = sustained rate. ``allow`` refills lazily on each
    call (no background timer), so an idle client regains its full burst.
  * :class:`RateLimiter` owns the per-key bucket map behind a lock and evicts
    idle buckets to bound memory.
  * Deterministic and monotonic-clock based — unit-testable by injecting ``now``.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    """A single token bucket. ``tokens`` refills toward ``capacity`` over time."""

    capacity: float
    refill_per_sec: float
    tokens: float
    last: float

    def _refill(self, now: float) -> None:
        if now > self.last:
            self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.refill_per_sec)
            self.last = now

    def allow(self, now: float, cost: float = 1.0) -> bool:
        """Consume ``cost`` tokens if available; return whether the call is allowed."""
        self._refill(now)
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False

    def retry_after(self, cost: float = 1.0) -> float:
        """Seconds until ``cost`` tokens are available (for the Retry-After header)."""
        if self.tokens >= cost or self.refill_per_sec <= 0:
            return 0.0
        return (cost - self.tokens) / self.refill_per_sec


class RateLimiter:
    """Per-key token-bucket rate limiter, safe for concurrent use."""

    def __init__(
        self,
        *,
        rate_per_sec: float,
        burst: float,
        idle_evict_sec: float = 300.0,
    ) -> None:
        if rate_per_sec <= 0 or burst <= 0:
            raise ValueError("rate_per_sec and burst must be positive")
        self._rate = rate_per_sec
        self._burst = burst
        self._idle_evict = idle_evict_sec
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
        self._last_evict = 0.0

    def check(self, key: str, *, now: float | None = None, cost: float = 1.0) -> tuple[bool, float]:
        """Return ``(allowed, retry_after_seconds)`` for ``key``."""
        ts = time.monotonic() if now is None else now
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket(
                    capacity=self._burst, refill_per_sec=self._rate, tokens=self._burst, last=ts
                )
                self._buckets[key] = bucket
            allowed = bucket.allow(ts, cost)
            retry = 0.0 if allowed else bucket.retry_after(cost)
            self._maybe_evict(ts)
            return allowed, retry

    def _maybe_evict(self, now: float) -> None:
        """Drop buckets idle past the eviction horizon (bounds memory).

        PR-5: scan at most once per idle window (bounds the O(n) cost), but always
        when the map grows large (bounds memory under many unique IPs even within a
        single window). Previously eviction NEVER ran below 1024 buckets, so a long-
        lived process leaked one bucket per distinct IP it ever saw, up to 1024.
        """
        if now - self._last_evict < self._idle_evict and len(self._buckets) < 1024:
            return
        self._last_evict = now
        stale = [k for k, b in self._buckets.items() if now - b.last > self._idle_evict]
        for k in stale:
            del self._buckets[k]


__all__ = ["RateLimiter", "TokenBucket"]
