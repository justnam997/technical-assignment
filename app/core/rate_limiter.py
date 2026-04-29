"""Token-bucket rate limiter — own implementation, stdlib only.

Why token bucket
----------------
Dashboard usage is bursty: a user pages through 5 screens in 2 seconds,
then idle for a minute. Token bucket allows the burst (up to bucket
capacity) and refills at a steady rate, which matches the use case.

Alternatives considered (see DESIGN.md ADR-004):
  - sliding window log: more accurate, O(N) memory per key
  - fixed window: simpler, suffers boundary-burst (2x limit possible)

Concurrency
-----------
The in-memory `Bucket` uses a `threading.Lock`. For asyncio, the call
sites are awaited but `Lock.acquire()` releases instantly when there's
no contention; for high-contention paths swap to `asyncio.Lock`.

Production swap
---------------
`InMemoryBucketStore` loses state on restart. Replace with
`RedisBucketStore` (same interface) backed by an EVAL+Lua script for
atomic check-and-decrement. The interface (`BucketStore` Protocol) is
intentionally narrow so the swap is one-class.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Protocol


@dataclass
class BucketState:
    """Pure data — what gets persisted by any backend."""

    tokens: float          # current available tokens
    last_refill: float     # monotonic seconds


class BucketStore(Protocol):
    """Pluggable backend interface. In-memory now; Redis swap later."""

    def take(self, key: str, capacity: int, refill_per_sec: float) -> bool:
        """Atomically refill and try to consume one token.

        Returns True if granted, False if denied.
        """
        ...


class InMemoryBucketStore:
    """Process-local store. Thread-safe via per-bucket lock."""

    def __init__(self) -> None:
        self._buckets: dict[str, BucketState] = {}
        self._global_lock = threading.Lock()  # guards _buckets dict
        # Per-key locks, lazily created. Avoids serialising unrelated keys.
        self._key_locks: dict[str, threading.Lock] = {}

    def _get_lock(self, key: str) -> threading.Lock:
        # Fast path: lock-free read.
        lock = self._key_locks.get(key)
        if lock is not None:
            return lock
        with self._global_lock:
            lock = self._key_locks.setdefault(key, threading.Lock())
        return lock

    def take(self, key: str, capacity: int, refill_per_sec: float) -> bool:
        now = time.monotonic()
        lock = self._get_lock(key)
        with lock:
            state = self._buckets.get(key)
            if state is None:
                # Brand new key: start full.
                state = BucketState(tokens=float(capacity), last_refill=now)
                self._buckets[key] = state

            # Refill based on elapsed time, capped at capacity.
            elapsed = now - state.last_refill
            state.tokens = min(
                float(capacity),
                state.tokens + elapsed * refill_per_sec,
            )
            state.last_refill = now

            if state.tokens >= 1.0:
                state.tokens -= 1.0
                return True
            return False


class RateLimiter:
    """Public surface used by middleware / dependencies.

    Per-key state — typical key: f"{org_id}:{principal_id}".
    """

    def __init__(
        self,
        capacity: int,
        refill_per_sec: float,
        store: BucketStore | None = None,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        if refill_per_sec <= 0:
            raise ValueError("refill_per_sec must be > 0")
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self.store: BucketStore = store or InMemoryBucketStore()

    def allow(self, key: str) -> bool:
        return self.store.take(key, self.capacity, self.refill_per_sec)


class RateLimitExceeded(Exception):
    """Raised by middleware/dep when caller exceeds the bucket."""

    def __init__(self, retry_after_seconds: float) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"rate limit exceeded; retry after {retry_after_seconds:.2f}s")
