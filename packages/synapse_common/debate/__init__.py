"""SYNAPSE debate substrate (ADR-052, R3): pure rule-based concession helpers."""

from synapse_common.debate.concession import (
    concede_toward,
    consensus_position,
    within_convergence_band,
)
from synapse_common.debate.response import build_debate_response

__all__ = [
    "build_debate_response",
    "concede_toward",
    "consensus_position",
    "within_convergence_band",
]
