"""LLM-as-judge harness — Sprint 9 live path (ADR-031 sibling).

Sprint 8 shipped the prompt template + ``LLMJudge`` stub. Sprint 9
unblocks the ``SYNAPSE_LLM_JUDGE_LIVE=1`` branch:

  - direct ``httpx`` call to a local Ollama (``OLLAMA_URL``) running the
    ``llama3.3:70b-instruct-q4_K_M`` model (configurable),
  - deterministic params (``temperature=0.0, seed=0xCAFEBABE``),
  - tight JSON-response validation with 2x retry on parse failure,
  - latency Histogram ``synapse_llm_judge_latency_seconds`` (Sprint 9 M0).

CI keeps the stub (``SYNAPSE_LLM_JUDGE_LIVE`` unset). Local devs with
Ollama can flip the flag for a live run.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from synapse_common.metrics import LLM_JUDGE_LATENCY_SECONDS

logger = structlog.get_logger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent / "judge_prompt.md"
LIVE_ENV = "SYNAPSE_LLM_JUDGE_LIVE"
OLLAMA_URL_ENV = "SYNAPSE_OLLAMA_URL"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
JUDGE_SEED = 0xCAFEBABE


@dataclass
class JudgeInput:
    trace_id: str
    tier: str
    city: str
    decision: dict[str, Any]
    context: dict[str, Any]


class LLMJudge:
    """Sprint-9 live judge (with Sprint-8 stub fallback)."""

    def __init__(self, model: str = "llama3.3:70b-instruct-q4_K_M") -> None:
        self.model = model
        self._prompt = PROMPT_PATH.read_text(encoding="utf-8")

    @property
    def prompt_template(self) -> str:
        return self._prompt

    def score_response(self, judge_input: JudgeInput) -> dict[str, Any]:
        """Return a structured judge result.

        - ``SYNAPSE_LLM_JUDGE_LIVE`` unset → CI stub
          (``{"ci_stub": True, "score": None}``).
        - ``SYNAPSE_LLM_JUDGE_LIVE=1`` → live Ollama call against ``self.model``,
          validated response, latency histogram observation.
        """
        if os.environ.get(LIVE_ENV, "").lower() not in {"1", "true", "yes"}:
            return self._stub(judge_input)
        return self._live(judge_input)

    # -- stub ----------------------------------------------------------------

    def _stub(self, judge_input: JudgeInput) -> dict[str, Any]:
        return {
            "ci_stub": True,
            "score": None,
            "model": self.model,
            "trace_id": judge_input.trace_id,
            "tier": judge_input.tier,
            "city": judge_input.city,
            "prompt_template_path": str(PROMPT_PATH),
        }

    # -- live ----------------------------------------------------------------

    def _live(self, judge_input: JudgeInput) -> dict[str, Any]:
        import httpx  # imported lazily so the stub path stays dependency-free

        ollama_url = os.environ.get(OLLAMA_URL_ENV, DEFAULT_OLLAMA_URL)
        endpoint = f"{ollama_url.rstrip('/')}/api/chat"
        user_blob = json.dumps(
            {
                "trace_id": judge_input.trace_id,
                "tier": judge_input.tier,
                "city": judge_input.city,
                "decision": judge_input.decision,
                "context": judge_input.context,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._prompt},
                {"role": "user", "content": user_blob},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0,
                "top_p": 1.0,
                "seed": JUDGE_SEED,
            },
        }

        last_error: str | None = None
        for attempt in range(3):
            start = time.perf_counter()
            try:
                with httpx.Client(timeout=120.0) as client:
                    resp = client.post(endpoint, json=body)
                resp.raise_for_status()
                LLM_JUDGE_LATENCY_SECONDS.labels(model=self.model).observe(
                    time.perf_counter() - start
                )
                payload = resp.json()
                content = payload.get("message", {}).get("content", "")
                parsed = self._parse_response(content)
                parsed["model"] = self.model
                parsed["trace_id"] = judge_input.trace_id
                parsed["tier"] = judge_input.tier
                parsed["city"] = judge_input.city
                parsed["ci_stub"] = False
                return parsed
            except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
                last_error = str(exc)
                logger.warning(
                    "llm_judge_live_attempt_failed",
                    attempt=attempt + 1,
                    model=self.model,
                    error=last_error,
                )
        raise RuntimeError(f"LLM-judge live call failed after 3 attempts: {last_error}")

    @staticmethod
    def _parse_response(content: str) -> dict[str, Any]:
        """Parse + validate the judge's JSON response.

        Required keys: factual, constraint, coherence, safety, overall.
        Each must be in [0.0, 1.0]. ``rationale`` is optional ≤200 chars.
        """
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError(f"judge response not a JSON object: {content[:200]!r}")
        required = ("factual", "constraint", "coherence", "safety", "overall")
        for key in required:
            if key not in parsed:
                raise ValueError(f"judge response missing key {key!r}: {content[:200]!r}")
            value = parsed[key]
            if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"judge response {key} out of range [0,1]: {value!r}")
        return parsed
