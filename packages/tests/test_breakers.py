"""Tests for the named async circuit breaker (Sprint 7, WS-1)."""

from __future__ import annotations

import asyncio
from typing import NoReturn

import pytest
from synapse_common.breakers import (
    AsyncBreaker,
    BreakerOpenError,
    BreakerState,
    get_breaker,
    reset_registry,
)


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    reset_registry()


class _BoomError(RuntimeError):
    pass


class TestBreakerStateMachine:
    @pytest.mark.asyncio
    async def test_starts_closed(self) -> None:
        b = AsyncBreaker("t", fail_max=2, reset_timeout=0.05, expected_exceptions=(_BoomError,))
        assert b.state is BreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_fail_max(self) -> None:
        b = AsyncBreaker("t", fail_max=2, reset_timeout=10.0, expected_exceptions=(_BoomError,))
        for _ in range(2):
            with pytest.raises(_BoomError):
                async with b.guard():
                    raise _BoomError
        assert b.state is BreakerState.OPEN

    @pytest.mark.asyncio
    async def test_open_breaker_rejects_immediately(self) -> None:
        b = AsyncBreaker("t", fail_max=1, reset_timeout=10.0, expected_exceptions=(_BoomError,))
        with pytest.raises(_BoomError):
            async with b.guard():
                raise _BoomError
        with pytest.raises(BreakerOpenError):
            async with b.guard():
                pytest.fail("body should not run when breaker is OPEN")

    @pytest.mark.asyncio
    async def test_half_open_success_closes(self) -> None:
        b = AsyncBreaker("t", fail_max=1, reset_timeout=0.02, expected_exceptions=(_BoomError,))
        with pytest.raises(_BoomError):
            async with b.guard():
                raise _BoomError
        await asyncio.sleep(0.03)
        async with b.guard():
            pass
        assert b.state is BreakerState.CLOSED
        assert b.failures == 0

    @pytest.mark.asyncio
    async def test_half_open_failure_re_opens(self) -> None:
        b = AsyncBreaker("t", fail_max=1, reset_timeout=0.02, expected_exceptions=(_BoomError,))
        with pytest.raises(_BoomError):
            async with b.guard():
                raise _BoomError
        await asyncio.sleep(0.03)
        with pytest.raises(_BoomError):
            async with b.guard():
                raise _BoomError
        assert b.state is BreakerState.OPEN

    @pytest.mark.asyncio
    async def test_unexpected_exception_does_not_count(self) -> None:
        b = AsyncBreaker("t", fail_max=1, reset_timeout=10.0, expected_exceptions=(_BoomError,))
        with pytest.raises(ValueError):
            async with b.guard():
                raise ValueError("unrelated")
        assert b.state is BreakerState.CLOSED
        assert b.failures == 0


class TestRegistry:
    @pytest.mark.asyncio
    async def test_get_returns_same_instance(self) -> None:
        a = get_breaker("dep", fail_max=2)
        b = get_breaker("dep", fail_max=99)
        assert a is b


class TestProtectDecorator:
    @pytest.mark.asyncio
    async def test_decorator_protects_async_function(self) -> None:
        b = AsyncBreaker("t", fail_max=1, reset_timeout=10.0, expected_exceptions=(_BoomError,))

        @b.protect()
        async def fails() -> NoReturn:
            raise _BoomError

        with pytest.raises(_BoomError):
            await fails()
        with pytest.raises(BreakerOpenError):
            await fails()


class TestConstructorValidation:
    def test_rejects_non_positive_fail_max(self) -> None:
        with pytest.raises(ValueError):
            AsyncBreaker("t", fail_max=0)

    def test_rejects_non_positive_reset(self) -> None:
        with pytest.raises(ValueError):
            AsyncBreaker("t", reset_timeout=0)
