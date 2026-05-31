"""Tests for the dependency-free token-bucket rate limiter."""

from __future__ import annotations

import pytest

from synapse_common.ratelimit import RateLimiter, TokenBucket


class TestTokenBucket:
    def test_allows_up_to_capacity_then_blocks(self) -> None:
        b = TokenBucket(capacity=3, refill_per_sec=1, tokens=3, last=0.0)
        assert b.allow(now=0.0)
        assert b.allow(now=0.0)
        assert b.allow(now=0.0)
        assert not b.allow(now=0.0)  # bucket empty

    def test_refills_over_time(self) -> None:
        b = TokenBucket(capacity=3, refill_per_sec=1, tokens=0, last=0.0)
        assert not b.allow(now=0.0)
        assert b.allow(now=1.0)  # 1 token refilled after 1s
        assert not b.allow(now=1.0)

    def test_refill_caps_at_capacity(self) -> None:
        b = TokenBucket(capacity=2, refill_per_sec=10, tokens=0, last=0.0)
        b._refill(now=100.0)  # huge elapsed
        assert b.tokens == 2  # capped

    def test_retry_after_reflects_deficit(self) -> None:
        b = TokenBucket(capacity=2, refill_per_sec=2, tokens=0, last=0.0)
        # need 1 token at 2 tokens/sec → 0.5s
        assert b.retry_after(cost=1.0) == pytest.approx(0.5)


class TestRateLimiter:
    def test_per_key_isolation(self) -> None:
        rl = RateLimiter(rate_per_sec=1, burst=1)
        a1, _ = rl.check("ip-a", now=0.0)
        a2, _ = rl.check("ip-a", now=0.0)
        b1, _ = rl.check("ip-b", now=0.0)
        assert a1 is True
        assert a2 is False  # second request from same key blocked
        assert b1 is True  # different key has its own bucket

    def test_returns_retry_after_when_blocked(self) -> None:
        rl = RateLimiter(rate_per_sec=2, burst=1)
        allowed, retry = rl.check("k", now=0.0)
        assert allowed
        allowed2, retry2 = rl.check("k", now=0.0)
        assert not allowed2
        assert retry2 == pytest.approx(0.5)

    def test_recovers_after_refill(self) -> None:
        rl = RateLimiter(rate_per_sec=1, burst=1)
        assert rl.check("k", now=0.0)[0]
        assert not rl.check("k", now=0.0)[0]
        assert rl.check("k", now=1.0)[0]  # one token back after 1s

    def test_invalid_config_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            RateLimiter(rate_per_sec=0, burst=1)
        with pytest.raises(ValueError, match="positive"):
            RateLimiter(rate_per_sec=1, burst=0)
