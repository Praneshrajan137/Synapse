"""SYNAPSE runtime invariant validation (ADR-040).

DbC (``deal``) checks postconditions at *test* time against hand-built inputs.
This module re-checks an agent's own ``spec.yaml`` postconditions on the **live
serving output** immediately before it is published to Kafka / returned over A2A.
It generalizes I-3 from a test-time contract into a runtime guard: a postcondition
breach raises :class:`InvariantViolation` so a malformed prediction is never
published, rather than silently crossing the boundary and corrupting consensus.

A check is a named predicate ``(output) -> bool``. Pipelines compose the
schema check (reusing :mod:`synapse_common.schema_registry`) with the agent's
postcondition predicates — the same logical assertions already expressed as
``@deal.post`` decorators, lifted to runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from synapse_common.schema_registry import SchemaViolation
from synapse_common.schema_registry import validate as _schema_validate

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

logger = structlog.get_logger(__name__)


class InvariantViolation(ValueError):
    """Raised when a live output breaches a spec postcondition (ADR-040)."""

    def __init__(self, agent: str, failures: list[str]) -> None:
        self.agent = agent
        self.failures = failures
        super().__init__(f"agent={agent} runtime invariant failures={failures}")


@dataclass(frozen=True)
class Postcondition:
    """A named runtime postcondition lifted from an agent's spec.yaml.

    ``inv_id`` is the spec INV-*/POST-* identifier (for audit + alerting);
    ``predicate`` returns ``True`` when the output is acceptable.
    """

    inv_id: str
    description: str
    predicate: Callable[[Any], bool]


class RuntimeValidator:
    """Validates a live agent output against schema + spec postconditions."""

    def __init__(self, agent: str, postconditions: Sequence[Postcondition] = ()) -> None:
        self._agent = agent
        self._postconditions = list(postconditions)

    def validate(
        self,
        output: Any,
        *,
        schema_name: str | None = None,
    ) -> None:
        """Raise :class:`InvariantViolation` if ``output`` breaches any guard.

        ``output`` may be a single item or a list; each item is checked. When
        ``schema_name`` is given, the JSON-Schema contract (I-3) is enforced too.
        """
        items = output if isinstance(output, list) else [output]
        failures: list[str] = []

        for idx, item in enumerate(items):
            if schema_name is not None:
                try:
                    _schema_validate(item, schema_name)
                except SchemaViolation as exc:
                    failures.append(f"[{idx}] schema: {exc}")
                except KeyError as exc:
                    failures.append(f"[{idx}] schema-name: {exc}")
            for pc in self._postconditions:
                try:
                    ok = bool(pc.predicate(item))
                except Exception as exc:  # noqa: BLE001 — a predicate that crashes is a failure
                    failures.append(f"[{idx}] {pc.inv_id}: predicate error {exc}")
                    continue
                if not ok:
                    failures.append(f"[{idx}] {pc.inv_id}: {pc.description}")

        if failures:
            logger.error("runtime_invariant_violation", agent=self._agent, failures=failures)
            raise InvariantViolation(self._agent, failures)


__all__ = ["InvariantViolation", "Postcondition", "RuntimeValidator"]
