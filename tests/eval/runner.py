"""CLI for the SYNAPSE LLM-judge golden-trace monitor."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tests.eval.llm_judge import LIVE_ENV, JudgeInput, LLMJudge
from tests.eval.schema import GoldenTrace

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "tests" / "eval" / "golden_traces"
DEFAULT_REPORT = REPO_ROOT / "build" / "eval" / "llm-judge-report.json"
DEFAULT_TIERS = ("tier_3", "tier_4")


@dataclass(frozen=True)
class JudgeTraceResult:
    """Serializable result for one judged golden trace."""

    trace_id: str
    city: str
    tier: str
    overall: float | None
    regression: bool
    ci_stub: bool
    raw: dict[str, Any]


def _load_traces(directory: Path, tiers: set[str], limit: int | None) -> list[GoldenTrace]:
    traces: list[GoldenTrace] = []
    for path in sorted(directory.glob("*.json")):
        trace = GoldenTrace.model_validate_json(path.read_text(encoding="utf-8"))
        if trace.expected_tier.value in tiers:
            traces.append(trace)
        if limit is not None and len(traces) >= limit:
            break
    return traces


def _make_judge_input(trace: GoldenTrace) -> JudgeInput:
    decision = {
        "agents_involved": trace.agents_involved,
        "avg_confidence": trace.avg_confidence,
        "disruption_active": trace.disruption_active,
        "expected_tier": trace.expected_tier.value,
        "payload": trace.payload,
        "requires_twin_simulation": trace.requires_twin_simulation,
    }
    context = {
        "description": trace.description,
        "expected_essential": trace.expected_essential,
        "expected_invariants": trace.expected_invariants,
    }
    return JudgeInput(
        trace_id=trace.trace_id,
        tier=trace.expected_tier.value,
        city=trace.city,
        decision=decision,
        context=context,
    )


def _overall(payload: dict[str, Any]) -> float | None:
    value = payload.get("overall", payload.get("score"))
    if value is None:
        return None
    return float(value)


def _run_judge(
    traces: list[GoldenTrace],
    *,
    judge_mode: str,
    model: str | None,
    min_score: float,
) -> tuple[list[JudgeTraceResult], dict[str, Any]]:
    if judge_mode == "live":
        os.environ[LIVE_ENV] = "1"
    else:
        os.environ.pop(LIVE_ENV, None)

    judge = LLMJudge() if model is None else LLMJudge(model=model)
    results: list[JudgeTraceResult] = []
    for trace in traces:
        payload = judge.score_response(_make_judge_input(trace))
        score = _overall(payload)
        if judge_mode == "live" and score is None:
            raise RuntimeError(f"live judge returned no score for {trace.trace_id}")
        regression = score is not None and score < min_score
        results.append(
            JudgeTraceResult(
                trace_id=trace.trace_id,
                city=trace.city,
                tier=trace.expected_tier.value,
                overall=score,
                regression=regression,
                ci_stub=bool(payload.get("ci_stub", False)),
                raw=payload,
            )
        )

    scores = [result.overall for result in results if result.overall is not None]
    mean_score = round(sum(scores) / len(scores), 6) if scores else None
    regression_count = sum(1 for result in results if result.regression)
    summary = {
        "judge": judge_mode,
        "mean_overall": mean_score,
        "min_score": min_score,
        "model": judge.model,
        "regression": regression_count > 0,
        "regressions": regression_count,
        "scored": len(scores),
        "total": len(results),
    }
    return results, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synapse-llm-judge")
    parser.add_argument("--suite", default="golden")
    parser.add_argument("--judge", choices=("stub", "live"), default="stub")
    parser.add_argument("--model", default=os.environ.get("SYNAPSE_LLM_JUDGE_MODEL"))
    parser.add_argument("--report", "--out", dest="report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-score", type=float, default=0.6)
    parser.add_argument("--tiers", nargs="+", default=list(DEFAULT_TIERS))
    args = parser.parse_args(argv)

    if args.suite != "golden":
        sys.stderr.write(f"unknown suite: {args.suite}\n")
        return 2

    traces = _load_traces(GOLDEN_DIR, set(args.tiers), args.limit)
    if not traces:
        sys.stderr.write("no golden traces matched the requested tiers\n")
        return 2

    results, summary = _run_judge(
        traces,
        judge_mode=args.judge,
        model=args.model,
        min_score=args.min_score,
    )
    payload = {"results": [asdict(result) for result in results], "summary": summary}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    sys.stdout.write(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
