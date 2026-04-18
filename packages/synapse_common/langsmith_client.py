"""LangSmith trace wrapper for SYNAPSE Ollama calls.

v4.0 plan §15 specifies LangSmith for LLM telemetry. Sampling strategy:

- Tier 2 decisions: 10% sample
- Tier 3-4 decisions: trace every call

All tracing is OFF by default unless `LANGSMITH_API_KEY` is set AND
`SYNAPSE_LANGSMITH_ENABLED=true`. I-1 (no paid APIs) compatibility: the
LangSmith free tier (5k traces/month) is sufficient for post-hoc analysis;
if cost appears CI blocks the dependency bump.

Usage::

    from synapse_common.langsmith_client import traced_ollama_call

    @traced_ollama_call(tier="tier_3", sample_rate=1.0)
    def analyze_conflict(messages: list[dict]) -> str:
        return ollama_client.chat(messages)
"""

from __future__ import annotations

import functools
import os
import random
from collections.abc import Callable
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger(__name__)

LANGSMITH_ENABLED = os.environ.get("SYNAPSE_LANGSMITH_ENABLED", "false").lower() == "true" and bool(
    os.environ.get("LANGSMITH_API_KEY")
)
PROJECT = os.environ.get("LANGSMITH_PROJECT", "synapse")

_SAMPLE_RATES: dict[str, float] = {
    "tier_1": 0.0,  # no LLM in Tier 1
    "tier_2": 0.10,
    "tier_3": 1.0,
    "tier_4": 1.0,
}

F = TypeVar("F", bound=Callable[..., Any])


def _should_sample(tier: str, rate: float | None) -> bool:
    if rate is None:
        rate = _SAMPLE_RATES.get(tier, 1.0)
    return random.random() < rate  # noqa: S311 — non-crypto sampling


def traced_ollama_call(
    tier: str = "tier_3",
    sample_rate: float | None = None,
    run_type: str = "llm",
) -> Callable[[F], F]:
    """Decorator wrapping an Ollama call with LangSmith tracing.

    Degrades to a no-op when LangSmith is disabled or the SDK is missing.
    """

    def decorator(func: F) -> F:
        if not LANGSMITH_ENABLED:
            return func

        try:
            from langsmith import traceable
        except ImportError:
            logger.warning("langsmith_missing", sdk="langsmith")
            return func

        wrapped = traceable(run_type=run_type, project_name=PROJECT)(func)

        @functools.wraps(func)
        def inner(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            if _should_sample(tier, sample_rate):
                return wrapped(*args, **kwargs)
            return func(*args, **kwargs)

        return inner  # type: ignore[return-value]

    return decorator
