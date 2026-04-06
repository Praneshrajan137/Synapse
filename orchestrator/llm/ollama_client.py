"""
SYNAPSE Orchestrator — Ollama client with cache-aware retry and fallback.

Features:
  - Full Jitter retry via ``synapse_common.retry.retry_with_jitter`` (ADR-016)
  - Model fallback chain (I-7 graceful degradation)
  - Request coalescing (identical in-flight requests share a single future)
  - KV-cache hit-rate Prometheus metrics (I-13)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

import httpx
import structlog

from synapse_common.metrics import OLLAMA_CACHE_HIT_RATE, OLLAMA_PREFILL_TOKENS
from synapse_common.retry import retry_with_jitter

from orchestrator.config import OrchestratorConfig

logger = structlog.get_logger(__name__)

MODEL_CONFIGS: dict[str, dict[str, Any]] = {
    "phi3:mini": {"ram_gb": 4, "tiers": ["tier_2"], "timeout_s": 10, "max_tokens": 2048},
    "qwen2.5:7b": {"ram_gb": 6, "tiers": ["tier_2"], "timeout_s": 10, "max_tokens": 4096},
    "deepseek-r1:14b": {
        "ram_gb": 12,
        "tiers": ["tier_3"],
        "timeout_s": 30,
        "max_tokens": 8192,
    },
    "llama3.3:70b-instruct-q4_K_M": {
        "ram_gb": 48,
        "tiers": ["tier_4"],
        "timeout_s": 120,
        "max_tokens": 16384,
    },
}

FALLBACK_CHAIN: dict[str, list[str]] = {
    "llama3.3:70b-instruct-q4_K_M": ["deepseek-r1:14b", "phi3:mini"],
    "deepseek-r1:14b": ["phi3:mini", "qwen2.5:7b"],
    "phi3:mini": ["qwen2.5:7b"],
    "qwen2.5:7b": ["phi3:mini"],
}


def _request_key(model: str, messages: list[dict[str, str]]) -> str:
    raw = json.dumps({"model": model, "messages": messages}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


class OllamaClient:
    """Extended Ollama HTTP client for the Orchestrator."""

    def __init__(self, config: OrchestratorConfig) -> None:
        self._base_url = config.ollama_base_url
        self._timeout = config.ollama_timeout_seconds
        self._inflight: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._client: httpx.AsyncClient | None = None
        self._cache_hits: int = 0
        self._cache_misses: int = 0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    @retry_with_jitter(max_retries=3, base_delay=0.5, cap=30.0)
    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        prefill: str | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request, with coalescing and fallback."""
        key = _request_key(model, messages)

        if key in self._inflight:
            return await self._inflight[key]

        future: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
        self._inflight[key] = future

        try:
            result = await self._do_chat(model, messages, prefill)
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            self._inflight.pop(key, None)

    async def _do_chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        prefill: str | None,
    ) -> dict[str, Any]:
        """Attempt the primary model, then walk the fallback chain (I-7)."""
        chain = [model, *FALLBACK_CHAIN.get(model, [])]
        last_exc: Exception | None = None
        for candidate in chain:
            try:
                return await self._raw_chat(candidate, messages, prefill)
            except Exception as exc:
                logger.warning(
                    "ollama_model_fallback",
                    failed_model=candidate,
                    error=str(exc),
                )
                last_exc = exc
        raise RuntimeError(
            f"All models in fallback chain exhausted: {chain}"
        ) from last_exc

    async def _raw_chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        prefill: str | None,
    ) -> dict[str, Any]:
        client = await self._get_client()
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False}
        if prefill:
            payload["messages"] = [*messages, {"role": "assistant", "content": prefill}]

        cfg = MODEL_CONFIGS.get(model, {})
        timeout = cfg.get("timeout_s", self._timeout)

        resp = await client.post(
            f"{self._base_url}/api/chat",
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        prompt_eval = data.get("prompt_eval_count", 0)
        eval_count = data.get("eval_count", 0)
        tier_label = ",".join(cfg.get("tiers", ["unknown"]))

        OLLAMA_PREFILL_TOKENS.labels(model=model, tier=tier_label).observe(prompt_eval)

        if prompt_eval > 0 and eval_count > 0:
            hit_rate = 1.0 - (prompt_eval / (prompt_eval + eval_count))
            OLLAMA_CACHE_HIT_RATE.labels(model=model, tier=tier_label).set(hit_rate)

        return data

    async def warm_model(self, model: str) -> None:
        """Pre-load a model into Ollama's memory."""
        try:
            client = await self._get_client()
            await client.post(
                f"{self._base_url}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": "5m"},
                timeout=30,
            )
            logger.info("ollama_model_warmed", model=model)
        except Exception as exc:
            logger.warning("ollama_warm_failed", model=model, error=str(exc))

    async def health_check(self) -> dict[str, Any]:
        """Check Ollama availability and loaded models."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self._base_url}/api/tags")
            models = response.json().get("models", [])
            return {
                "status": "healthy",
                "loaded_models": [m["name"] for m in models],
            }
        except Exception as exc:
            return {"status": "unhealthy", "error": str(exc)}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
