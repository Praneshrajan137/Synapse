"""Flagger canary webhook (Sprint 9 §M-prod-4).

Deployed alongside Flagger as a tiny FastAPI service that translates
canary HTTP calls into golden-trace eval + KV-cache hit-rate checks.
Returns 200 on pass, 4xx on regression — Flagger then halts the canary
promotion and rolls back.

Endpoints:
  POST /eval        — runs `tests/eval/run.py:run_suite()` and asserts
                      overall accuracy >= metadata.tier_floor.
  POST /kv-cache    — asserts ``synapse_ollama_cache_hit_rate`` >= metadata.floor.
  GET  /health      — liveness/readiness.

Sprint 10 wires this behind the canary CRD's webhook URLs.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, HTTPException

logger = structlog.get_logger(__name__)

app = FastAPI(title="SYNAPSE Flagger Eval Webhook", version="9.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/eval")
def eval_canary(body: dict[str, str] | None = None) -> dict[str, object]:
    """Run the golden-trace suite and assert per-city accuracy."""
    body = body or {}
    floor = float(body.get("tier_floor", "0.80"))
    from tests.eval.run import run_suite

    _, summary = run_suite()
    accuracy = summary["correct"] / summary["total"] if summary["total"] else 0.0
    if accuracy < floor:
        raise HTTPException(
            status_code=400,
            detail=f"tier-routing accuracy {accuracy:.2%} below canary floor {floor:.2%}",
        )
    return {"ok": True, "accuracy": accuracy, "summary": summary}


@app.post("/kv-cache")
def kv_cache(body: dict[str, str] | None = None) -> dict[str, object]:
    body = body or {}
    floor = float(body.get("floor", "0.70"))
    try:
        from synapse_common.metrics import OLLAMA_CACHE_HIT_RATE
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"metrics module missing: {exc}") from exc

    samples = []
    for metric in OLLAMA_CACHE_HIT_RATE.collect():
        for sample in metric.samples:
            if sample.name.endswith("_total") or sample.name.endswith("_created"):
                continue
            samples.append(sample.value)
    if not samples:
        raise HTTPException(status_code=400, detail="no KV-cache samples — canary blocked")
    rate = sum(samples) / len(samples)
    if rate < floor:
        raise HTTPException(
            status_code=400,
            detail=f"KV-cache hit rate {rate:.3f} below canary floor {floor:.2f}",
        )
    return {"ok": True, "rate": rate}
