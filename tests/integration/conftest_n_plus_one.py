"""N+1 query guard fixture (Sprint 8 WS-8 §M15).

Wraps Neo4j AsyncSession + Pinecone Index in a thin counting proxy so
integration tests can assert ``with assert_max_queries(N): ...``. Targets
the most likely Sprint-8 hotspots:

  - ``digital_twin/graph/supply_network.py:get_neighbors`` (per-node query).
  - ``orchestrator/llm/semantic_cache.py:check_cache`` (per-key Pinecone hit).

Scoped to ``tests/integration/`` only — not enabled in the all-tests
baseline so unit tests stay fast.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator


class QueryCounter:
    """Lightweight counter wrapping an arbitrary backend client."""

    def __init__(self, target: Any, method_names: tuple[str, ...]) -> None:
        self._target = target
        self._method_names = method_names
        self.count: int = 0
        self._originals: dict[str, Any] = {}

    def install(self) -> None:
        for name in self._method_names:
            original = getattr(self._target, name, None)
            if original is None:
                continue
            self._originals[name] = original
            setattr(self._target, name, self._wrap(original))

    def _wrap(self, fn: Any) -> Any:  # noqa: ANN401
        import asyncio

        counter = self

        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            counter.count += 1
            return fn(*args, **kwargs)

        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            counter.count += 1
            return await fn(*args, **kwargs)

        return async_wrapper if asyncio.iscoroutinefunction(fn) else sync_wrapper

    def restore(self) -> None:
        for name, original in self._originals.items():
            setattr(self._target, name, original)
        self._originals.clear()


@contextmanager
def assert_max_queries(
    target: Any, max_queries: int, method_names: tuple[str, ...] = ("query", "run", "execute")
) -> Iterator[QueryCounter]:
    """Context manager asserting ``target.<method>`` is called ≤``max_queries`` times."""
    counter = QueryCounter(target, method_names)
    counter.install()
    try:
        yield counter
    finally:
        counter.restore()
    assert counter.count <= max_queries, (
        f"N+1 detected: {counter.count} calls > max_queries={max_queries} on {target}"
    )


@pytest.fixture
def query_guard() -> Any:
    """pytest fixture surface — call as ``with query_guard(client, 1): ...``."""
    return assert_max_queries
