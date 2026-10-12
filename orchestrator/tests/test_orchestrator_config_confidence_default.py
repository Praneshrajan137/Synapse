"""The I-5 boundary's committed default is present, bounded below, and unbounded above.

Feature: decision-quality-proof, session 2q. Not a property test -- these are example-class
facts about one committed number, and the universal statement over threshold sequences
already exists as Property 24.

WHY THIS FILE EXISTS. ``orchestrator/config.py`` declared the field as
``Field(0.7, ge=0.0)`` -- default passed *positionally*. This project configures no
``pydantic.mypy`` plugin, so mypy reads the field through pydantic v2's PEP-681
``dataclass_transform``, which recognises a field-specifier default only as ``default=``.
The reviewed default was therefore invisible to the type checker, the field was synthesised
as a required keyword argument, and ``mypy --strict orchestrator/`` reported
``Missing named argument "confidence_threshold" for "OrchestratorConfig"`` at 21 call
sites -- three of them production (``inference/serve.py`` x2, ``audit/cli.py``).

The repair was ``default=0.7``: one line, no runtime change. The failure mode it forecloses
is the *other* repair -- passing a value at each call site -- which would have substituted 21
unreviewed numbers for one committed number on the I-5 confidence gate, because
``GuardrailEngine(confidence_threshold=config.confidence_threshold)`` consumes it. These
tests pin the three properties the field's own comment declares, so a future edit that
re-hides the default, adds a ceiling, or drops the lower bound fails here rather than being
noticed as an error count moving somewhere else.

ENV CAVEAT, stated rather than engineered around. ``OrchestratorConfig`` is a
``BaseSettings`` with ``env_prefix="SYNAPSE_ORCHESTRATOR_"`` and ``env_file=".env"``. The
autouse fixture clears the one variable that would shadow the default; a committed ``.env``
carrying that key would still shadow it, and that SHOULD be visible rather than suppressed.
No ``.env`` exists in this tree.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.config import OrchestratorConfig
from orchestrator.guardrails.rules import DEFAULT_CONFIDENCE_FLOOR

#: The reviewed value, written once here so a drift shows as one failure and not five.
COMMITTED_DEFAULT = 0.7

_ENV_VAR = "SYNAPSE_ORCHESTRATOR_CONFIDENCE_THRESHOLD"


@pytest.fixture(autouse=True)
def _no_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Read the committed default, not an ambient one.

    No ``yield`` and no teardown: ``monkeypatch`` restores the environment itself at the end
    of each test. Returning ``None`` rather than an ``Iterator[None]`` also keeps the only
    ``collections.abc`` import out of the module, which is what ``ruff``'s TC003 asks for.
    """
    monkeypatch.delenv(_ENV_VAR, raising=False)


def test_the_default_is_present_and_needs_no_argument() -> None:
    """The property the positional ``Field(0.7, ...)`` hid from the type checker.

    Constructing with no arguments must yield the committed boundary. If this fails, the
    default is gone and every call site is silently choosing its own I-5 threshold.
    """
    assert OrchestratorConfig().confidence_threshold == pytest.approx(COMMITTED_DEFAULT)


def test_the_default_agrees_with_the_guardrail_table() -> None:
    """``rules.py`` claims this agreement in prose; this is the mechanical form.

    ``DEFAULT_CONFIDENCE_FLOOR`` is read from
    ``HARD_GUARDRAILS["confidence_floor"]["default_threshold"]``, and the comment above it
    asserts ``OrchestratorConfig.confidence_threshold`` "defaults to the same number". Two
    numbers that must agree and nothing comparing them is exactly the hole C75 exists to
    close, so they are compared here.
    """
    assert OrchestratorConfig().confidence_threshold == pytest.approx(DEFAULT_CONFIDENCE_FLOOR)


def test_ge_zero_refuses_a_negative_boundary() -> None:
    """``ge=0.0`` is load-bearing, not decoration.

    A negative threshold makes *every* decision satisfy the floor -- fail-open, the one
    direction a guardrail must never fail. It is refused at construction, which is also what
    makes ``thresholds.py``'s I-7 claim (a failed reload leaves the previous known-good
    boundary in force) true for ``-1.0`` and not only for a non-numeric value.
    """
    with pytest.raises(ValidationError):
        OrchestratorConfig(confidence_threshold=-1.0)


def test_the_lower_bound_is_inclusive() -> None:
    """``ge``, not ``gt``: the committed shape admits ``0.0``.

    Pinned as fact rather than endorsement -- a change to ``gt=0.0`` would be a real change
    to the declared contract and should fail here rather than pass silently.
    """
    assert OrchestratorConfig(confidence_threshold=0.0).confidence_threshold == pytest.approx(0.0)


def test_there_is_deliberately_no_upper_bound() -> None:
    """A boundary above ``1.0`` is a legitimate fail-closed kill switch.

    ``ConsensusDecision`` pins ``confidence <= 1``, so ``1.1`` escalates everything. Adding
    ``le=1.0`` would remove an operator's ability to escalate every decision, to guard
    against nothing.
    """
    assert OrchestratorConfig(confidence_threshold=1.1).confidence_threshold == pytest.approx(1.1)
