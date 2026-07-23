"""
SYNAPSE Decision-Integrity Uplift Proof — closed-loop counterfactual harness.

This package measures — and either proves or honestly refutes — whether SYNAPSE's
four-tier consensus decisions beat a transparent baseline policy on business KPIs,
using the existing SimPy digital twin as the shared world.

Public surface (core interfaces + data models) is re-exported here for convenience;
the concrete baselines, harness, contract, and gates live in their own modules.
"""
from __future__ import annotations

from uplift.interfaces import (
    ArmResult,
    DecisionPolicy,
    Direction,
    KpiVector,
    Observation,
    Outcome,
    PendingOrder,
    PolicyAction,
    RoutingAssignment,
    Scenario,
    ScenarioRun,
    Store,
    UpliftResult,
)
from uplift.consensus_arm import (
    ConsensusArm,
    ConsensusArmUnavailable,
    InProcessA2ATransport,
    consensus_decision_to_policy_action,
    observation_to_decision_request,
)
from uplift.kpi import AppliedDecisions, DeliveredOrder, KpiExtractor
from uplift.persistence import (
    PersistenceError,
    SCHEMA_VERSION,
    load_runs,
    save_runs,
)

__all__ = [
    "AppliedDecisions",
    "ArmResult",
    "ConsensusArm",
    "ConsensusArmUnavailable",
    "DecisionPolicy",
    "DeliveredOrder",
    "Direction",
    "InProcessA2ATransport",
    "KpiExtractor",
    "KpiVector",
    "Observation",
    "Outcome",
    "PendingOrder",
    "PersistenceError",
    "PolicyAction",
    "RoutingAssignment",
    "SCHEMA_VERSION",
    "Scenario",
    "ScenarioRun",
    "Store",
    "UpliftResult",
    "consensus_decision_to_policy_action",
    "load_runs",
    "observation_to_decision_request",
    "save_runs",
]
