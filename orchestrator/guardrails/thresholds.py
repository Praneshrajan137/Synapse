"""Reloadable confidence threshold seam for the I-5 escalation boundary (R5.4).

Feature: purpose-achievement-audit, task 8.1. Recorded in
`docs/adr/ADR-054-dispatch-ratification-choke-point.md` (D4).

The escalation boundary used to be a float captured once at construction
(`rules.py:57`), sourced from `orchestrator/config.py` and injected a single time at
`orchestrator/inference/serve.py:98`. Moving the boundary therefore required a process
restart, which R5.4 rejects: "WHEN `confidence_threshold` is changed in configuration
and the configuration is reloaded, THE Consensus_Protocol SHALL escalate at the new
threshold on every tier without a process restart and without a change to any source
file."

The seam is a two-method protocol. :class:`GuardrailEngine` reads :meth:`current` on
**every** validation, so the boundary a decision is judged against is the boundary
configured at that moment - never one frozen at wiring time.

Invariants this module is careful about
---------------------------------------

**I-13 (KV-cache stable prefix) is unaffected.** The threshold is read only by the
deterministic rule engine. It is not interpolated into an LLM system prompt, not written
into a context message, and not serialised into any prefix the KV cache depends on.
Nothing here changes what enters a prompt.

**No frozen model is mutated.** :meth:`ConfigConfidenceThresholdProvider.reload` builds a
*new* settings instance through its factory and rebinds it. The previously bound instance
is left exactly as it was, so a caller holding a reference to it observes no change and no
Pydantic model is written to. Rebinding a single attribute is atomic from a reader's
perspective in CPython, so a concurrent :meth:`current` call reads either the old
settings or the new one, never a half-updated object.

**I-7 (honest degradation).** A malformed environment makes ``OrchestratorConfig()``
raise, and :meth:`reload` lets that propagate to the caller that asked for the reload.
The previous known-good threshold stays in force. The provider never substitutes a
default on failure: silently falling back would *lower* a safety gate, and reporting a
successful reload that did not happen would be a fabricated result.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog

from orchestrator.config import OrchestratorConfig

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)

__all__ = [
    "ConfidenceThresholdProvider",
    "ConfigConfidenceThresholdProvider",
    "StaticConfidenceThresholdProvider",
    "resolve_threshold_provider",
]


@runtime_checkable
class ConfidenceThresholdProvider(Protocol):
    """The I-5 escalation boundary, read per validation rather than per construction."""

    def current(self) -> float:
        """Return the confidence threshold in force right now."""
        ...

    def reload(self) -> None:
        """Re-read the backing configuration source.

        Raises whatever the backing source raises when it cannot be read. A provider
        that raises leaves its previously reported value in force (I-7): it never
        substitutes a default, because a default would lower the gate.
        """
        ...


class StaticConfidenceThresholdProvider:
    """A fixed threshold. ``reload()`` is honestly a no-op: there is no source to re-read.

    This is the compatibility shape for the existing callers that pass a float
    (`orchestrator/tests`, `tests/dbc`, `uplift/consensus_arm.py`), and it is the right
    provider for the uplift harness specifically: a replicate set must be judged against
    one fixed boundary or the arms are not comparable.
    """

    __slots__ = ("_value",)

    def __init__(self, value: float) -> None:
        self._value = float(value)

    def current(self) -> float:
        return self._value

    def reload(self) -> None:
        """No source to re-read; the value is pinned by construction."""
        return


class ConfigConfidenceThresholdProvider:
    """The threshold as configured in :class:`~orchestrator.config.OrchestratorConfig`.

    ``reload()`` constructs a **new** settings instance through ``settings_factory``
    (default: ``OrchestratorConfig``, which re-reads ``SYNAPSE_ORCHESTRATOR_*`` and
    ``.env``) and rebinds it. The instance previously held is never mutated.
    """

    __slots__ = ("_settings", "_settings_factory")

    def __init__(
        self,
        settings: OrchestratorConfig | None = None,
        *,
        settings_factory: Callable[[], OrchestratorConfig] | None = None,
    ) -> None:
        self._settings_factory: Callable[[], OrchestratorConfig] = (
            settings_factory if settings_factory is not None else OrchestratorConfig
        )
        self._settings: OrchestratorConfig = (
            settings if settings is not None else self._settings_factory()
        )

    def current(self) -> float:
        return float(self._settings.confidence_threshold)

    def reload(self) -> None:
        """Rebind to a freshly built settings instance.

        The new instance is constructed *before* anything is rebound, so a factory that
        raises leaves the provider reporting its previous value unchanged.
        """
        previous = self._settings.confidence_threshold
        refreshed = self._settings_factory()
        self._settings = refreshed
        if refreshed.confidence_threshold != previous:
            logger.info(
                "confidence_threshold_reloaded",
                previous=previous,
                current=refreshed.confidence_threshold,
            )


def resolve_threshold_provider(
    threshold: float | ConfidenceThresholdProvider,
) -> ConfidenceThresholdProvider:
    """Coerce a float or a provider to a provider.

    Keeps the ``GuardrailEngine(confidence_threshold=0.7)`` call shape working while the
    engine itself only ever talks to a provider (ADR-054 D4).
    """
    if isinstance(threshold, ConfidenceThresholdProvider):
        return threshold
    return StaticConfidenceThresholdProvider(float(threshold))
