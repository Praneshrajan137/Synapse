"""SYNAPSE Orchestrator — Semantic decision cache tests (ADR-018)."""

from __future__ import annotations

import pytest

from orchestrator.llm.semantic_cache import SemanticDecisionCache


class TestCacheInitialisation:
    def test_unavailable_without_api_key(self) -> None:
        cache = SemanticDecisionCache(api_key=None)
        assert cache.available is False

    @pytest.mark.asyncio()
    async def test_check_returns_none_when_unavailable(self) -> None:
        cache = SemanticDecisionCache(api_key=None)
        result = await cache.check_cache([0.0] * 384, "test_hash")
        assert result is None

    @pytest.mark.asyncio()
    async def test_store_noop_when_unavailable(self) -> None:
        cache = SemanticDecisionCache(api_key=None)
        await cache.store_decision([0.0] * 384, {"test": True}, "test_hash")
