"""Unit tests for the token-bucket rate limiter.

Covers:
  - basic allow/deny
  - refill over time
  - burst capacity
  - per-key isolation (one key's burst doesn't drain another)
  - thread safety
"""
from __future__ import annotations

import threading
import time

import pytest

from app.core.rate_limiter import InMemoryBucketStore, RateLimiter


def test_allows_up_to_capacity_then_denies():
    rl = RateLimiter(capacity=3, refill_per_sec=0.001, store=InMemoryBucketStore())
    # First 3 requests succeed (full bucket).
    assert rl.allow("k") is True
    assert rl.allow("k") is True
    assert rl.allow("k") is True
    # 4th denied — bucket empty, refill rate too slow to have produced one yet.
    assert rl.allow("k") is False


def test_refills_at_configured_rate():
    rl = RateLimiter(capacity=1, refill_per_sec=10.0, store=InMemoryBucketStore())
    assert rl.allow("k") is True
    assert rl.allow("k") is False
    # Sleep enough to refill 1 token (10/sec → 0.1s for 1 token).
    time.sleep(0.15)
    assert rl.allow("k") is True


def test_keys_are_isolated():
    rl = RateLimiter(capacity=1, refill_per_sec=0.001, store=InMemoryBucketStore())
    assert rl.allow("user_a") is True
    assert rl.allow("user_b") is True  # different key, full bucket
    assert rl.allow("user_a") is False
    assert rl.allow("user_b") is False


def test_burst_then_sustained():
    """Bucket=20, refill=10/sec — should allow 20 immediate, then ~10/sec."""
    rl = RateLimiter(capacity=20, refill_per_sec=10.0, store=InMemoryBucketStore())
    # Burst — all 20 should succeed.
    for _ in range(20):
        assert rl.allow("k") is True
    # 21st — denied (no refill yet, monotonic time barely advanced).
    assert rl.allow("k") is False
    time.sleep(1.0)
    # After 1s, ~10 tokens refilled.
    grants = sum(1 for _ in range(15) if rl.allow("k"))
    assert 8 <= grants <= 12  # tolerate timing jitter


def test_thread_safety_under_contention():
    rl = RateLimiter(capacity=100, refill_per_sec=0.001, store=InMemoryBucketStore())
    grant_count = [0]
    lock = threading.Lock()

    def worker():
        if rl.allow("shared"):
            with lock:
                grant_count[0] += 1

    threads = [threading.Thread(target=worker) for _ in range(500)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Bucket cap is 100, refill negligible during the run → at most 100 grants.
    # Race conditions would let more through; we assert the safety bound.
    assert grant_count[0] <= 100


@pytest.mark.parametrize(
    "capacity,refill",
    [(0, 1.0), (1, 0.0), (1, -0.1)],
)
def test_invalid_config_rejected(capacity: int, refill: float):
    with pytest.raises(ValueError):
        RateLimiter(capacity=capacity, refill_per_sec=refill, store=InMemoryBucketStore())
