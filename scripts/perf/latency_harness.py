"""Per-tier decision-latency harness + budget audit (Phase 2.3; ADR-049 Tier-P prep).

Makes the declared per-tier decision SLAs *falsifiable* instead of asserted.

Modes:
  --audit (default, $0): STATIC cross-check of each tier's declared decision
     ``latency_budget_ms`` (``orchestrator.consensus.tier_router.TIER_CRITERIA``)
     against its per-agent A2A call timeout
     (``synapse_common.a2a_sdk.TIER_TIMEOUTS``). Flags budgets that are
     structurally fragile — the orchestrator fans out to up to 8 agents in
     parallel, so a single slow/retried agent (allowed up to the A2A timeout) can
     exceed the whole-decision budget; the SLA then holds only on the happy path.
     Grounded in the two real constants; needs no running stack.
  --measure --api URL --token <OPS_JWT> [--n 50]: LIVE. Drives N decisions per
     tier through ``POST /api/v1/decisions/`` and reports p50/p95/p99 vs the
     budget (met/violated). Needs the running stack + an OPS token (operator
     step) — measures REAL latency with whatever models are actually loaded.
  --self-test: verify the pure logic on synthetic samples (CI-safe).

SLA values are READ from ``TIER_CRITERIA`` (single source) — never re-declared.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass

_TIERS = ("tier_1", "tier_2", "tier_3", "tier_4")


def percentiles(samples_ms: list[float]) -> dict[str, float]:
    """p50/p95/p99/max/mean over a latency sample (ms). Empty sample -> zeros."""
    if not samples_ms:
        return {"n": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0, "mean": 0.0}
    ordered = sorted(samples_ms)
    n = len(ordered)

    def pct(p: float) -> float:
        idx = min(n - 1, max(0, int(round((p / 100.0) * (n - 1)))))  # nearest-rank
        return ordered[idx]

    return {
        "n": float(n),
        "p50": pct(50),
        "p95": pct(95),
        "p99": pct(99),
        "max": ordered[-1],
        "mean": sum(ordered) / n,
    }


def tier_verdict(p95_ms: float, budget_ms: float) -> tuple[str, float]:
    """Return ``('met'|'violated'|'unknown', p95/budget)``. met iff p95 <= budget."""
    if budget_ms <= 0:
        return "unknown", 0.0
    ratio = p95_ms / budget_ms
    return ("met" if p95_ms <= budget_ms else "violated"), ratio


@dataclass
class BudgetFinding:
    tier: str
    budget_ms: int
    a2a_timeout_ms: float
    fragile: bool
    note: str


def static_budget_audit() -> list[BudgetFinding]:
    """Cross-check each tier's decision budget against its per-agent A2A timeout."""
    from orchestrator.consensus.tier_router import TIER_CRITERIA
    from synapse_common.a2a_sdk import TIER_TIMEOUTS

    findings: list[BudgetFinding] = []
    for tier, crit in TIER_CRITERIA.items():
        budget = int(crit["latency_budget_ms"])
        a2a_ms = float(TIER_TIMEOUTS[tier]) * 1000.0
        fragile = a2a_ms > budget
        if fragile:
            note = (
                f"per-agent A2A timeout {a2a_ms:.0f}ms exceeds the {budget}ms decision "
                f"budget {a2a_ms / budget:.0f}x -- one slow/retried agent violates the SLA"
            )
        else:
            note = f"per-agent A2A timeout {a2a_ms:.0f}ms within the {budget}ms budget"
        findings.append(BudgetFinding(str(tier), budget, a2a_ms, fragile, note))
    return findings


def payload_for_tier(tier: str) -> dict[str, object]:
    """Build a ``decision_request`` that classifies into ``tier`` (tier_router rules)."""
    base: dict[str, object] = {
        "order_id": f"latency-probe-{tier}",
        "store_id": "STORE-001",
        "sku_id": "SKU-0001",
    }
    if tier == "tier_4":
        return {**base, "disruption_active": True}
    if tier == "tier_3":
        return {**base, "agents_involved": ["a", "b", "c", "d"], "avg_confidence": 0.3}
    if tier == "tier_2":
        return {**base, "agents_involved": ["a", "b"], "avg_confidence": 0.7}
    return {**base, "agents_involved": ["a"], "avg_confidence": 0.95}


def measure_tier(api_base: str, tier: str, n: int, token: str | None) -> list[float]:
    """Drive ``n`` decisions of ``tier`` through the API; return round-trip ms."""
    import urllib.request  # stdlib — no extra dependency for the harness

    body = json.dumps(payload_for_tier(tier)).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{api_base.rstrip('/')}/api/v1/decisions/"
    samples: list[float] = []
    for _ in range(max(0, n)):
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")  # noqa: S310
        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=130.0) as resp:  # noqa: S310
            resp.read()
        samples.append((time.perf_counter() - start) * 1000.0)
    return samples


def _print_audit() -> int:
    print("Per-tier decision-latency budget audit (static -- budget vs per-agent A2A timeout):")
    fragile_n = 0
    for f in static_budget_audit():
        fragile_n += int(f.fragile)
        print(f"  [{'FRAGILE' if f.fragile else 'ok':>7}] {f.tier:<8} budget={f.budget_ms}ms  {f.note}")
    print(
        f"\n{fragile_n}/4 tiers carry a decision budget the per-agent A2A timeout can exceed -- "
        "the SLA holds on the happy path; measure live (--measure) to confirm the real p95."
    )
    return 0


def _measure(api: str, token: str | None, n: int) -> int:
    from orchestrator.consensus.tier_router import TIER_CRITERIA

    budgets = {str(t): int(c["latency_budget_ms"]) for t, c in TIER_CRITERIA.items()}
    overall = 0
    for tier in _TIERS:
        stats = percentiles(measure_tier(api, tier, n, token))
        budget = budgets.get(tier, 0)
        status, ratio = tier_verdict(stats["p95"], float(budget))
        overall = 1 if status == "violated" else overall
        print(
            f"{tier}: n={int(stats['n'])} p50={stats['p50']:.0f}ms p95={stats['p95']:.0f}ms "
            f"p99={stats['p99']:.0f}ms budget={budget}ms -> {status} ({ratio:.2f}x)"
        )
    return overall


def _self_test() -> int:
    p = percentiles([10.0, 20.0, 30.0, 40.0, 50.0])
    assert p["p50"] == 30.0 and p["max"] == 50.0, p
    assert tier_verdict(80.0, 100.0)[0] == "met"
    assert tier_verdict(120.0, 100.0)[0] == "violated"
    assert len(static_budget_audit()) == 4
    print("latency_harness self-test: OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SYNAPSE per-tier decision-latency harness")
    ap.add_argument("--measure", action="store_true", help="live measurement (needs the stack)")
    ap.add_argument("--audit", action="store_true", help="static budget audit (default, $0)")
    ap.add_argument("--self-test", action="store_true", help="verify the pure logic (CI-safe)")
    ap.add_argument("--api", default="http://localhost:8000", help="API base URL for --measure")
    ap.add_argument("--token", default=None, help="OPS bearer token for --measure")
    ap.add_argument("--n", type=int, default=50, help="samples per tier for --measure")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test()
    if args.measure:
        return _measure(args.api, args.token, args.n)
    return _print_audit()


if __name__ == "__main__":
    sys.exit(main())
