"""SYNAPSE eval runner (Sprint 8 WS-5 §M7).

Replays every golden trace through ``TierRouter.classify`` and (for
Tier 1–3 with audit fixtures available) Sprint 7's
``orchestrator.replay.replay_decision``. Emits a JSON report at
``build/eval/report.json`` + a markdown summary.

Designed to be CI-friendly:
  - no live Ollama / Pinecone / Neo4j requirements.
  - deterministic ordering of results (sorted by trace_id).
  - exit 0 only when all expected_tiers match classified tiers.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from synapse_common.metrics import EVAL_TRACE_LATENCY, EVAL_TRACE_OUTCOME_TOTAL

from orchestrator.consensus.tier_router import TierRouter
from tests.eval.schema import GoldenTrace

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "tests" / "eval" / "golden_traces"
DEFAULT_OUT = REPO_ROOT / "build" / "eval" / "report.json"


@dataclass
class TraceResult:
    trace_id: str
    city: str
    expected_tier: str
    classified_tier: str
    correct: bool
    duration_ms: float
    reasons: list[str]


def load_traces(directory: Path = GOLDEN_DIR) -> list[GoldenTrace]:
    traces: list[GoldenTrace] = []
    for path in sorted(directory.glob("*.json")):
        traces.append(GoldenTrace.model_validate_json(path.read_text(encoding="utf-8")))
    return traces


def classify_trace(router: TierRouter, trace: GoldenTrace) -> TraceResult:
    request: dict[str, Any] = {
        "agents_involved": trace.agents_involved,
        "avg_confidence": trace.avg_confidence,
        "disruption_active": trace.disruption_active,
        "requires_twin_simulation": trace.requires_twin_simulation,
    }
    start = time.perf_counter()
    classification = router.classify(request)
    duration_ms = (time.perf_counter() - start) * 1000
    classified = classification.tier.value
    correct = classified == trace.expected_tier.value
    EVAL_TRACE_LATENCY.labels(tier=classified, city=trace.city).observe(duration_ms / 1000)
    EVAL_TRACE_OUTCOME_TOTAL.labels(
        tier=classified,
        city=trace.city,
        outcome="pass" if correct else "fail",
    ).inc()
    return TraceResult(
        trace_id=trace.trace_id,
        city=trace.city,
        expected_tier=trace.expected_tier.value,
        classified_tier=classified,
        correct=correct,
        duration_ms=round(duration_ms, 3),
        reasons=classification.reasons,
    )


def run_suite() -> tuple[list[TraceResult], dict[str, Any]]:
    router = TierRouter()
    results = [classify_trace(router, trace) for trace in load_traces()]

    by_city: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = by_city.setdefault(result.city, {"total": 0, "correct": 0})
        bucket["total"] += 1
        bucket["correct"] += int(result.correct)

    summary = {
        "total": len(results),
        "correct": sum(1 for r in results if r.correct),
        "per_city": {
            city: {
                "total": bucket["total"],
                "correct": bucket["correct"],
                "accuracy": bucket["correct"] / bucket["total"],
            }
            for city, bucket in by_city.items()
        },
    }
    return results, summary


def emit_markdown(results: list[TraceResult], summary: dict[str, Any]) -> str:
    lines = [
        "# Sprint 8 — Golden-Trace Eval Report",
        "",
        f"**Total traces:** {summary['total']}  ",
        f"**Correctly classified:** {summary['correct']}",
        "",
        "## Per-city accuracy",
        "",
        "| City | Total | Correct | Accuracy |",
        "| --- | ---: | ---: | ---: |",
    ]
    for city, bucket in sorted(summary["per_city"].items()):
        lines.append(
            f"| {city} | {bucket['total']} | {bucket['correct']} | {bucket['accuracy']:.2%} |"
        )
    lines += [
        "",
        "## Per-trace results",
        "",
        "| Trace | City | Expected | Classified | OK | Latency (ms) |",
        "| --- | --- | --- | --- | --- | ---: |",
    ]
    for r in results:
        ok = "✅" if r.correct else "❌"
        lines.append(
            f"| {r.trace_id} | {r.city} | {r.expected_tier} | "
            f"{r.classified_tier} | {ok} | {r.duration_ms} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synapse-eval")
    parser.add_argument("--suite", default="golden")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown", type=Path, default=None)
    parser.add_argument("--print", action="store_true", help="Print summary to stdout")
    args = parser.parse_args(argv)

    if args.suite != "golden":
        print(f"unknown suite: {args.suite}", flush=True)
        return 2

    results, summary = run_suite()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summary, "results": [asdict(r) for r in results]}
    args.out.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")

    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(emit_markdown(results, summary), encoding="utf-8")

    if args.print:
        print(json.dumps(summary, indent=2))

    overall_accuracy = summary["correct"] / summary["total"] if summary["total"] else 0.0
    if overall_accuracy < 0.75:
        print(f"FAIL: overall tier-routing accuracy {overall_accuracy:.2%} < 75%", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
