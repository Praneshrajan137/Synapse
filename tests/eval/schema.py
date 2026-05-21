"""Golden-trace schema (Sprint 8 WS-5 §M6).

Each trace is one canonical decision the orchestrator must reproduce
deterministically. The schema mirrors the keys ``TierRouter.classify``
reads ([orchestrator/consensus/tier_router.py:69](orchestrator/consensus/tier_router.py:69))
plus identifying metadata so the eval runner can:

  - replay against ``orchestrator.replay.replay_decision`` (Sprint 7),
  - cross-check the produced tier against ``expected_tier``,
  - verify each ``expected_invariant`` survived,
  - bucket per-city accuracy (Mumbai vs Bengaluru).

The 20 Sprint-8 traces are synthetic and deterministic. Sprint 9 will
expand to 200 traces captured from actual orchestrator runs.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from synapse_common.models import DecisionTier


class GoldenTrace(BaseModel):
    """One golden trace fixture, loaded from ``tests/eval/golden_traces/*.json``."""

    trace_id: str = Field(..., description="Stable string id; doubles as filename.")
    city: str = Field(..., pattern="^(bengaluru|mumbai)$")
    description: str = ""

    # Inputs to TierRouter.classify (must mirror tier_router.py:71-75).
    agents_involved: list[str] = Field(default_factory=list)
    avg_confidence: float = Field(ge=0.0, le=1.0)
    disruption_active: bool = False
    requires_twin_simulation: bool = False

    # Expectations.
    expected_tier: DecisionTier
    expected_invariants: list[str] = Field(default_factory=list)
    expected_essential: bool = Field(
        default=False,
        description="If True, brownout MUST NOT shed this decision (WS-1 §5).",
    )

    # Optional payload exercised by Tier-3/4 LLM-judge harness when wired in Sprint 9.
    payload: dict[str, Any] = Field(default_factory=dict)
