"""
SYNAPSE Disruption Shield — DeepSeek-R1 Reasoning via Ollama (I-1: zero cost).

Generates structured reasoning chains from anomaly scores and affected nodes.
Uses httpx for async-capable HTTP. Falls back gracefully if Ollama is down (I-7).
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a supply chain disruption analyst. Given anomaly scores and affected "
    "supply chain nodes, produce a structured reasoning chain explaining:\n"
    "1. What type of disruption is detected\n"
    "2. Which nodes are most affected and why\n"
    "3. Severity assessment (low/medium/high/critical)\n"
    "4. Recommended immediate actions\n"
    "Respond ONLY with a JSON object: "
    '{"reasoning_steps": ["step1", ...], "severity": "...", "summary": "..."}'
)


class DeepSeekReasoner:
    """Generates reasoning chains via DeepSeek-R1 on Ollama (I-1: zero cost)."""

    def __init__(
        self,
        ollama_base_url: str = "http://ollama:11434",
        model: str = "deepseek-r1:14b",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._base_url = ollama_base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds

    def reason(
        self,
        ensemble_score: float,
        anomalous_nodes: list[str],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate reasoning chain from anomaly data.

        Returns dict with keys: reasoning_steps, severity, summary.
        Falls back to rule-based reasoning if Ollama is unavailable (I-7).
        """
        prompt = self._build_prompt(ensemble_score, anomalous_nodes, context)

        try:
            result = self._call_ollama(prompt)
            logger.info(
                "reasoning_generated",
                model=self._model,
                steps=len(result.get("reasoning_steps", [])),
            )
            return result
        except (httpx.HTTPError, httpx.TimeoutException, json.JSONDecodeError) as exc:
            logger.warning(
                "ollama_unavailable",
                error=str(exc),
                fallback="rule_based_reasoning",
            )
            return self._fallback_reasoning(ensemble_score, anomalous_nodes)

    def _build_prompt(
        self,
        ensemble_score: float,
        anomalous_nodes: list[str],
        context: dict[str, Any] | None,
    ) -> str:
        parts = [
            f"Ensemble anomaly score: {ensemble_score:.4f}",
            f"Affected nodes ({len(anomalous_nodes)}): {', '.join(anomalous_nodes[:20])}",
        ]
        if context:
            parts.append(
                f"Additional context: {json.dumps(context, sort_keys=True, separators=(',', ':'))}"
            )
        return "\n".join(parts)

    def _call_ollama(self, prompt: str) -> dict[str, Any]:
        """POST to Ollama /api/generate and parse structured JSON response."""
        start = time.monotonic()

        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": _SYSTEM_PROMPT,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 512},
        }

        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._base_url}/api/generate",
                json=payload,
            )
            resp.raise_for_status()

        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info("ollama_call_completed", elapsed_ms=round(elapsed_ms, 1))

        body = resp.json()
        raw_text: str = body.get("response", "{}")

        json_start = raw_text.find("{")
        json_end = raw_text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            parsed: dict[str, Any] = json.loads(raw_text[json_start:json_end])
        else:
            parsed = {
                "reasoning_steps": [raw_text.strip()],
                "severity": "unknown",
                "summary": raw_text.strip()[:200],
            }

        if "reasoning_steps" not in parsed:
            parsed["reasoning_steps"] = [parsed.get("summary", "No reasoning provided")]

        return parsed

    @staticmethod
    def _fallback_reasoning(
        ensemble_score: float,
        anomalous_nodes: list[str],
    ) -> dict[str, Any]:
        """Rule-based fallback when Ollama is unavailable (I-7)."""
        if ensemble_score >= 0.95:
            severity = "critical"
        elif ensemble_score >= 0.80:
            severity = "high"
        elif ensemble_score >= 0.65:
            severity = "medium"
        else:
            severity = "low"

        steps = [
            f"Anomaly ensemble score: {ensemble_score:.4f}",
            f"Number of affected nodes: {len(anomalous_nodes)}",
            f"Severity classified as: {severity} (rule-based fallback)",
        ]
        if anomalous_nodes:
            steps.append(f"Most affected nodes: {', '.join(anomalous_nodes[:5])}")
        steps.append("Recommended: review affected nodes and activate recovery playbook")

        return {
            "reasoning_steps": steps,
            "severity": severity,
            "summary": (
                f"Disruption detected (score={ensemble_score:.4f}, "
                f"{len(anomalous_nodes)} nodes affected, severity={severity})"
            ),
        }
