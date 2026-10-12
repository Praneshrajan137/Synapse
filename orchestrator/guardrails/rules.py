"""
SYNAPSE Orchestrator — Hard guardrails enforcement (I-6).

These rules CANNOT be overridden by any agent or RL policy.
Implementation is a deterministic rule engine (no NeMo Guardrails LLM overhead)
to meet Tier 1-2 latency requirements (I-10).

Configuration totality (R5.3): every entry in :data:`HARD_GUARDRAILS` must
resolve to a check function on :class:`GuardrailEngine`. A declared enforcement
with no implementation is a construction-time :class:`GuardrailConfigurationError`,
not a silent no-op — a guardrail that cannot bite is a vacuous guarantee (I-7).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final, NamedTuple

import deal
import structlog

from orchestrator.guardrails.thresholds import (
    ConfidenceThresholdProvider,
    resolve_threshold_provider,
)

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from synapse_common.models import ConsensusDecision

logger = structlog.get_logger(__name__)

ESSENTIAL_CATEGORIES: frozenset[str] = frozenset(
    ["rice", "dal", "milk", "bread", "eggs", "cooking_oil", "vegetables", "fruits"],
)

HARD_GUARDRAILS: dict[str, dict[str, Any]] = {
    "essential_price_cap": {
        "rule": "price_multiplier <= 1.3 for essential categories",
        "max_multiplier": 1.3,
        "enforcement": "CLIP",
    },
    "rider_shift_limit": {
        "rule": "rider shift duration <= 10 hours",
        "max_hours": 10,
        "enforcement": "REJECT",
    },
    "service_level_minimum": {
        "rule": "predicted fill rate >= 85%",
        "min_fill_rate": 0.85,
        "enforcement": "ESCALATE",
    },
    "privacy_boundary": {
        "rule": "no raw demand data crosses store boundaries",
        "enforcement": "BLOCK",
    },
    "confidence_floor": {
        "rule": "execution requires confidence >= threshold or HITL approval",
        "default_threshold": 0.7,
        "enforcement": "ESCALATE",
    },
}

# Enforcements that withhold dispatch when violated. Exposed so a caller can
# narrow the totality requirement to the blocking subset; the default applied by
# `GuardrailEngine._validate_configuration` is stricter (every declared rule).
BLOCKING_ENFORCEMENTS: frozenset[str] = frozenset({"BLOCK", "REJECT", "ESCALATE"})

#: The confidence floor the committed table declares as its *default*, read from the
#: table rather than written as a literal so the two cannot drift apart.
#:
#: It is a default, not an absolute floor: nothing in this repository commits to 0.7 as
#: a lower bound on operator policy - ``OrchestratorConfig.confidence_threshold``
#: defaults to the same number and ADR-054 D4 / R5.4 make it reloadable. So this value
#: is what a *direct* :func:`execute_consensus` call is judged against, while the
#: production choke point always passes the boundary in force
#: (:attr:`GuardrailEngine.confidence_threshold`) instead. Treating the default as a
#: floor would state a guarantee the table does not declare (I-7).
DEFAULT_CONFIDENCE_FLOOR: Final[float] = float(
    HARD_GUARDRAILS["confidence_floor"]["default_threshold"],
)

# A rule's check function is `_check_<rule_name>` unless it is aliased here.
_CHECK_METHOD_ALIASES: Mapping[str, str] = {
    "service_level_minimum": "_check_service_level",
}

# ---------------------------------------------------------------- I-11 privacy

# Fields that name a store, i.e. that place a payload on one side of a store
# boundary. Two distinct values means the action spans a boundary.
STORE_IDENTITY_FIELDS: frozenset[str] = frozenset(
    [
        "store_id",
        "source_store_id",
        "origin_store_id",
        "from_store_id",
        "target_store_id",
        "destination_store_id",
        "to_store_id",
        "recipient_store_id",
        "peer_store_id",
    ],
)

# Fields whose mere presence declares an intent to send the payload to another
# store, even when only one store identity appears in the action.
CROSS_STORE_RECIPIENT_FIELDS: frozenset[str] = frozenset(
    [
        "share_with",
        "shared_with",
        "recipients",
        "broadcast_to",
        "peer_stores",
        "target_stores",
        "destination_stores",
    ],
)

# Raw, store-local demand data. I-11 / DPDPA 2023: only derived quantities
# (gradients, aggregates, forecasts) may leave a store; these may not. The first
# three names are the same ones `tests/compliance/test_dpdpa.py` bans from the
# Flower client, so the two checks agree on what "raw" means.
RAW_DEMAND_FIELDS: frozenset[str] = frozenset(
    [
        "raw_data",
        "raw_demand",
        "raw_demand_series",
        "raw_orders",
        "order_history",
        "order_ids",
        "customer_id",
        "customer_ids",
        "customer_orders",
        "demand_history",
        "transactions",
        "basket_history",
    ],
)

# Traversal budget. A selected action is agent-supplied and may be adversarial or
# self-referential; the scan is bounded so the check stays Tier 1 affordable
# (I-10). Exhausting the budget is reported as unverifiable, never as clean.
_MAX_SCAN_NODES: int = 10_000


class GuardrailConfigurationError(RuntimeError):
    """A declared guardrail resolves to no check function (R5.3)."""

    def __init__(self, unimplemented: Sequence[tuple[str, str]]) -> None:
        self.unimplemented: tuple[tuple[str, str], ...] = tuple(unimplemented)
        detail = "; ".join(
            f"{name} (enforcement={enforcement or 'UNDECLARED'}, "
            f"expected {check_method_name(name)}())"
            for name, enforcement in self.unimplemented
        )
        super().__init__(
            f"Guardrail configuration is not total: {len(self.unimplemented)} declared "
            f"rule(s) have no check function: {detail}",
        )


def check_method_name(rule_name: str) -> str:
    """Return the check-function name a guardrail rule resolves to."""
    return _CHECK_METHOD_ALIASES.get(rule_name, f"_check_{rule_name}")


def unimplemented_guardrails(
    config: Mapping[str, Mapping[str, Any]],
    available_checks: Collection[str],
    *,
    enforcements_requiring_check: Collection[str] | None = None,
) -> tuple[tuple[str, str], ...]:
    """Declared rules in *config* that resolve to no name in *available_checks*.

    Pure function of its arguments — the seam the totality property drives.

    Returns ``(rule_name, declared_enforcement)`` pairs, sorted by rule name.
    ``enforcements_requiring_check`` of ``None`` (the default) requires a check
    for **every** declared rule; pass :data:`BLOCKING_ENFORCEMENTS` to require
    one only where a violation withholds dispatch.
    """
    required = (
        None
        if enforcements_requiring_check is None
        else {str(item).strip().upper() for item in enforcements_requiring_check}
    )
    missing: list[tuple[str, str]] = []
    for rule_name in sorted(config):
        spec = config[rule_name]
        enforcement = str(spec.get("enforcement", "")).strip().upper()
        if required is not None and enforcement not in required:
            continue
        if check_method_name(rule_name) not in available_checks:
            missing.append((rule_name, enforcement))
    return tuple(missing)


def validate_guardrail_configuration(
    config: Mapping[str, Mapping[str, Any]],
    available_checks: Collection[str],
    *,
    enforcements_requiring_check: Collection[str] | None = None,
) -> None:
    """Raise :class:`GuardrailConfigurationError` naming every unimplemented rule."""
    missing = unimplemented_guardrails(
        config,
        available_checks,
        enforcements_requiring_check=enforcements_requiring_check,
    )
    if missing:
        raise GuardrailConfigurationError(missing)


def _is_present(value: Any) -> bool:
    """True when *value* carries a payload (``None`` and empty containers do not)."""
    if value is None:
        return False
    if isinstance(value, str | bytes | list | tuple | dict | set | frozenset):
        return len(value) > 0
    return True


class PrivacyScan(NamedTuple):
    """What a selected action reveals about store boundaries and raw demand."""

    store_ids: tuple[str, ...]
    raw_demand_paths: tuple[str, ...]
    recipient_paths: tuple[str, ...]
    truncated: bool

    @property
    def crosses_store_boundary(self) -> bool:
        """True when the action names two stores or declares another recipient."""
        return len(self.store_ids) > 1 or bool(self.recipient_paths)

    @property
    def violates_privacy_boundary(self) -> bool:
        """True when raw demand crosses a boundary, or the scan could not finish."""
        if self.truncated:
            return True
        return bool(self.raw_demand_paths) and self.crosses_store_boundary


def scan_privacy_boundary(
    action: Mapping[str, Any],
    *,
    max_nodes: int = _MAX_SCAN_NODES,
) -> PrivacyScan:
    """Scan *action* for a cross-store raw demand payload (I-11).

    Pure and deterministic: walks the action, collecting store identities, raw
    demand payload paths, and cross-store recipient declarations. Traversal is
    bounded by *max_nodes*; exceeding it sets ``truncated`` so the caller fails
    closed rather than reporting an unscanned action clean (I-7).
    """
    store_ids: set[str] = set()
    raw_demand_paths: list[str] = []
    recipient_paths: list[str] = []
    budget = max_nodes
    stack: list[tuple[str, Any]] = [("", action)]

    while stack:
        path, node = stack.pop()
        budget -= 1
        if budget < 0:
            return PrivacyScan(
                store_ids=tuple(sorted(store_ids)),
                raw_demand_paths=tuple(sorted(raw_demand_paths)),
                recipient_paths=tuple(sorted(recipient_paths)),
                truncated=True,
            )
        if isinstance(node, Mapping):
            for key, value in node.items():
                child = f"{path}.{key}" if path else str(key)
                field = str(key).strip().lower()
                if field in STORE_IDENTITY_FIELDS and isinstance(value, str) and value:
                    store_ids.add(value)
                if field in RAW_DEMAND_FIELDS and _is_present(value):
                    raw_demand_paths.append(child)
                if field in CROSS_STORE_RECIPIENT_FIELDS and _is_present(value):
                    recipient_paths.append(child)
                stack.append((child, value))
        elif isinstance(node, list | tuple):
            for index, item in enumerate(node):
                stack.append((f"{path}[{index}]", item))

    return PrivacyScan(
        store_ids=tuple(sorted(store_ids)),
        raw_demand_paths=tuple(sorted(raw_demand_paths)),
        recipient_paths=tuple(sorted(recipient_paths)),
        truncated=False,
    )


class GuardrailEngine:
    """Evaluate hard guardrails against a consensus decision."""

    def __init__(
        self,
        confidence_threshold: float | ConfidenceThresholdProvider = 0.7,
        *,
        guardrails: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        """Bind the I-5 escalation boundary as a *provider*, not as a value.

        ADR-054 D4 / R5.4: the boundary is read on every validation via
        :meth:`ConfidenceThresholdProvider.current`, so a configuration reload moves
        it on every tier with no process restart and no source-file change. Passing a
        plain float still works and is coerced to a
        :class:`~orchestrator.guardrails.thresholds.StaticConfidenceThresholdProvider`,
        which is the right shape for a test and for the uplift harness (one fixed
        boundary per replicate set, or the arms are not comparable).
        """
        self._threshold: ConfidenceThresholdProvider = resolve_threshold_provider(
            confidence_threshold,
        )
        self._guardrails: Mapping[str, Mapping[str, Any]] = (
            HARD_GUARDRAILS if guardrails is None else guardrails
        )
        self._validate_configuration()

    @property
    def threshold_provider(self) -> ConfidenceThresholdProvider:
        """The bound provider. The seam Property 24 (task 8.2) drives."""
        return self._threshold

    @property
    def confidence_threshold(self) -> float:
        """The boundary in force right now - never a value captured at construction."""
        return self._threshold.current()

    @classmethod
    def available_check_functions(cls) -> frozenset[str]:
        """Names of the check functions this engine actually implements."""
        return frozenset(
            name
            for name in dir(cls)
            if name.startswith("_check_") and callable(getattr(cls, name, None))
        )

    def _validate_configuration(self) -> None:
        """Reject a configuration that declares a rule it cannot enforce (R5.3).

        Every declared guardrail must resolve to a check function; a declared
        enforcement with no implementation raises
        :class:`GuardrailConfigurationError` naming the rule. This is stricter
        than the blocking-only reading of R5.3 and strictly implies it.
        """
        validate_guardrail_configuration(self._guardrails, self.available_check_functions())

    def validate_decision(
        self,
        decision: ConsensusDecision,
    ) -> tuple[bool, list[str]]:
        """Validate *decision* against all hard guardrails.

        Returns ``(passed, violations)``.  ``passed`` is ``True`` only when all
        rules are satisfied (clip-only violations still pass).
        """
        violations: list[str] = []
        action = decision.selected_action

        # BLOCK is the strongest enforcement and is evaluated first, before any
        # rule that mutates the action, so a cross-store raw demand payload can
        # never reach dispatch on any tier (R5.2).
        if not self._check_privacy_boundary(action, violations):
            return False, violations

        self._check_essential_price_cap(action, violations)

        if not self._check_rider_shift_limit(action, violations):
            return False, violations

        if not self._check_confidence_floor(decision, violations):
            return False, violations

        self._check_service_level(action, violations)

        all_clipped = all("clipped" in v.lower() for v in violations) if violations else True
        return all_clipped, violations

    @staticmethod
    def _check_privacy_boundary(
        action: dict[str, Any],
        violations: list[str],
    ) -> bool:
        """BLOCK: no raw demand payload crosses a store boundary (I-11, R5.3)."""
        scan = scan_privacy_boundary(action)
        if not scan.violates_privacy_boundary:
            return True

        if scan.truncated:
            violations.append(
                "Privacy boundary BLOCKED: selected action exceeded the "
                f"{_MAX_SCAN_NODES}-node scan budget; cross-store raw demand "
                "could not be ruled out",
            )
            logger.error(
                "privacy_boundary_unverifiable",
                scan_budget=_MAX_SCAN_NODES,
                enforcement="BLOCK",
            )
            return False

        violations.append(
            "Privacy boundary BLOCKED: raw demand payload at "
            f"{', '.join(scan.raw_demand_paths)} crosses a store boundary "
            f"(stores={', '.join(scan.store_ids) or 'none'}; "
            f"recipients={', '.join(scan.recipient_paths) or 'none'})",
        )
        logger.error(
            "privacy_boundary_violation",
            raw_demand_paths=list(scan.raw_demand_paths),
            store_ids=list(scan.store_ids),
            recipient_paths=list(scan.recipient_paths),
            enforcement="BLOCK",
        )
        return False

    @staticmethod
    def _check_essential_price_cap(
        action: dict[str, Any],
        violations: list[str],
    ) -> None:
        pricing_actions: list[dict[str, Any]] = action.get("pricing_actions", [])
        for pa in pricing_actions:
            category = pa.get("category", "")
            multiplier = pa.get("multiplier", 1.0)
            if category in ESSENTIAL_CATEGORIES and multiplier > 1.3:
                pa["multiplier"] = 1.3  # CLIP — do not reject
                violations.append(
                    f"Essential price cap CLIPPED: {category} from {multiplier:.2f} to 1.3",
                )

    @staticmethod
    def _check_rider_shift_limit(
        action: dict[str, Any],
        violations: list[str],
    ) -> bool:
        routing_actions: list[dict[str, Any]] = action.get("routing_actions", [])
        for ra in routing_actions:
            hours = ra.get("rider_shift_hours", 0)
            if hours > 10:
                violations.append(
                    f"Rider shift limit exceeded: {hours}h > 10h max",
                )
                return False
        return True

    def _check_confidence_floor(
        self,
        decision: ConsensusDecision,
        violations: list[str],
    ) -> bool:
        # R5.4: read the boundary per validation. A float captured in __init__ would
        # pin the escalation boundary to wiring time and require a restart to move it.
        threshold = self._threshold.current()
        if decision.confidence < threshold:
            violations.append(
                f"Confidence {decision.confidence:.3f} below threshold {threshold}",
            )
            return False
        return True

    @staticmethod
    def _check_service_level(
        action: dict[str, Any],
        violations: list[str],
    ) -> None:
        fill_rate = action.get("predicted_fill_rate")
        if fill_rate is not None and fill_rate < 0.85:
            violations.append(
                f"Predicted fill rate {fill_rate:.2%} below 85% minimum",
            )


def satisfies_confidence_floor(
    decision: ConsensusDecision,
    *,
    confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR,
) -> bool:
    """The I-5 dispatch precondition: at or above *confidence_floor*, or escalated.

    One definition with two call sites, deliberately (purpose-achievement-audit task
    12.1a):

    * it is :func:`execute_consensus`'s ``@deal.pre`` validator, and
    * ``ConsensusProtocol._ratify_and_dispatch`` evaluates it as a pre-flight **before**
      it appends the I-4 audit row, against the same floor it then hands the contract.

    Two call sites of one predicate cannot disagree, which is the point: the contract can
    no longer fail *after* an append-only row has been written, because the identical
    check already ran before the append and routed the failure into the recorded
    withhold (I-4, I-7). A second, separately-worded copy of the comparison is exactly
    how the ``0.7`` literal this repairs drifted away from the reloadable boundary.

    The disjunct is not a loophole: ``escalated_to_human`` is set by
    ``HITLEscalation.escalate``, which awaits a human future and dispatches nothing, so a
    sub-floor decision that satisfies this predicate is one a human already took
    responsibility for.
    """
    return decision.confidence >= confidence_floor or decision.escalated_to_human


@deal.pre(
    satisfies_confidence_floor,
    message="I-5 VIOLATION: Low-confidence decision not escalated to HITL",
)
@deal.post(
    lambda result: result.audit_id is not None,
    message="I-4 VIOLATION: Decision not logged to audit trail",
)
def execute_consensus(
    decision: ConsensusDecision,
    *,
    confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR,
) -> ConsensusDecision:
    """Contract-guarded execution entry point.

    Args:
        decision: the decision about to be enacted. ``@deal.post`` requires its
            ``audit_id`` to be set, so the I-4 row exists before the world is mutated.
        confidence_floor: the boundary the I-5 precondition is judged against. The
            production caller passes the boundary **in force at that moment**
            (:attr:`GuardrailEngine.confidence_threshold`, which reads
            :meth:`~orchestrator.guardrails.thresholds.ConfidenceThresholdProvider.current`
            per validation), so the contract agrees with live policy instead of with a
            literal captured when this module was written. Defaults to
            :data:`DEFAULT_CONFIDENCE_FLOOR` - the committed table default - which is
            what a direct call with no boundary stated is judged against.
    """
    return decision
