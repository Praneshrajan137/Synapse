"""Tests for Full Jitter retry utility (ADR-016)."""
from __future__ import annotations

import pytest

from synapse_common.retry import full_jitter_delay, retry_with_jitter


class TestFullJitterDelay:

    def test_delay_within_bounds(self) -> None:
        for attempt in range(10):
            for _ in range(100):
                delay = full_jitter_delay(base_delay=0.5, attempt=attempt, cap=60.0)
                max_expected = min(60.0, 0.5 * (2 ** attempt))
                assert 0 <= delay <= max_expected

    def test_cap_enforced(self) -> None:
        for _ in range(100):
            delay = full_jitter_delay(base_delay=1.0, attempt=100, cap=10.0)
            assert delay <= 10.0

    def test_jitter_has_variance(self) -> None:
        delays = {full_jitter_delay(0.5, 3, 60.0) for _ in range(50)}
        assert len(delays) > 1


class TestRetryDecorator:

    def test_sync_success_no_retry(self) -> None:
        call_count = 0

        @retry_with_jitter(max_retries=3, base_delay=0.01)
        def success_fn() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = success_fn()
        assert result == "ok"
        assert call_count == 1

    def test_sync_retry_then_succeed(self) -> None:
        call_count = 0

        @retry_with_jitter(max_retries=3, base_delay=0.01)
        def flaky_fn() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return "recovered"

        result = flaky_fn()
        assert result == "recovered"
        assert call_count == 3

    def test_sync_all_retries_exhausted(self) -> None:
        @retry_with_jitter(max_retries=2, base_delay=0.01)
        def always_fail() -> None:
            raise ConnectionError("permanent")

        with pytest.raises(ConnectionError, match="permanent"):
            always_fail()

    def test_invalid_max_retries_raises(self) -> None:
        with pytest.raises(ValueError, match="max_retries must be > 0"):
            @retry_with_jitter(max_retries=0)
            def fn() -> None:
                pass

    def test_invalid_base_delay_raises(self) -> None:
        with pytest.raises(ValueError, match="base_delay must be > 0"):
            @retry_with_jitter(base_delay=0)
            def fn() -> None:
                pass

    @pytest.mark.asyncio
    async def test_async_retry(self) -> None:
        call_count = 0

        @retry_with_jitter(max_retries=3, base_delay=0.01)
        async def async_flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("transient")
            return "async_recovered"

        result = await async_flaky()
        assert result == "async_recovered"
        assert call_count == 2
