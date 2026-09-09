"""Unit tests for the decision data-provenance builder (audit R4.4, task 10.11).

``build_provenance`` is the pure half of the writer: perceived state in, an append-only
``decision_data_provenance`` row (or ``None``) out. It is where every honesty decision about
provenance lives, so it is tested directly rather than through Postgres.

The obligation under test is R4.4's *distinctness*: a decision convened from a non-synthetic
state must record a value a simulation-sourced decision cannot. The two ways to break that
are to invent a class when none was declared, and to normalise away a disagreement - both
are covered below.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from synapse_common.world.models import SourceProvenance, WorldState

from orchestrator.audit.data_provenance import build_provenance

_FALLBACK = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _state(**overrides: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "city": "bengaluru",
        "source_class": "EXTERNAL",
        "is_synthetic": False,
        "as_of": "2026-02-03T04:05:06+00:00",
        "feed_revision": "ext:o-4213",
    }
    state.update(overrides)
    return state


def test_external_state_records_a_distinct_non_synthetic_provenance() -> None:
    row = build_provenance(decision_id=uuid4(), state=_state(), observed_at=_FALLBACK)
    assert row is not None
    assert row.source_class == "EXTERNAL"
    assert row.is_synthetic is False
    assert row.feed_revision == "ext:o-4213"
    assert row.observed_at == datetime(2026, 2, 3, 4, 5, 6, tzinfo=UTC)


def test_seeded_state_records_the_synthetic_provenance() -> None:
    row = build_provenance(
        decision_id=uuid4(),
        state=_state(source_class="SEEDED", is_synthetic=True, feed_revision=None),
        observed_at=_FALLBACK,
    )
    assert row is not None
    assert row.source_class == "SEEDED"
    assert row.is_synthetic is True
    assert row.feed_revision is None


def test_an_undeclared_source_class_yields_no_row_rather_than_a_default() -> None:
    """No row is the honest outcome: a defaulted SEEDED would be unreadable as a guess."""
    state = _state()
    del state["source_class"]
    assert build_provenance(decision_id=uuid4(), state=state, observed_at=_FALLBACK) is None


def test_an_unknown_source_class_yields_no_row() -> None:
    row = build_provenance(
        decision_id=uuid4(), state=_state(source_class="MADE_UP"), observed_at=_FALLBACK
    )
    assert row is None


def test_an_unusable_decision_id_yields_no_row() -> None:
    assert build_provenance(decision_id="not-a-uuid", state=_state()) is None
    assert build_provenance(decision_id=None, state=_state()) is None


def test_a_flag_contradicting_its_class_is_recorded_as_reported() -> None:
    """The disagreement stays in the audit trail instead of being normalised away."""
    row = build_provenance(
        decision_id=uuid4(),
        state=_state(source_class="SEEDED", is_synthetic=False),
        observed_at=_FALLBACK,
    )
    assert row is not None
    assert row.source_class == "SEEDED"
    assert row.is_synthetic is False


def test_a_missing_flag_is_derived_from_the_class() -> None:
    state = _state(source_class="STUB")
    del state["is_synthetic"]
    row = build_provenance(decision_id=uuid4(), state=state, observed_at=_FALLBACK)
    assert row is not None
    assert row.is_synthetic is False  # a stub is not a seeded generator


def test_an_unparseable_timestamp_falls_back_to_the_supplied_clock() -> None:
    row = build_provenance(
        decision_id=uuid4(), state=_state(as_of="yesterday"), observed_at=_FALLBACK
    )
    assert row is not None
    assert row.observed_at == _FALLBACK


def test_a_real_perceived_state_round_trips_into_a_provenance_row() -> None:
    """The AD-11 chain end to end: source class -> derived is_synthetic -> recorded row."""
    state = WorldState(
        city="bengaluru", sim_time_min=60.0, source_class=SourceProvenance.EXTERNAL
    ).model_dump(mode="json")
    assert state["is_synthetic"] is False

    row = build_provenance(decision_id=uuid4(), state=state, observed_at=_FALLBACK)
    assert row is not None
    seeded = WorldState(city="bengaluru", sim_time_min=60.0).model_dump(mode="json")
    seeded_row = build_provenance(decision_id=uuid4(), state=seeded, observed_at=_FALLBACK)
    assert seeded_row is not None

    # R4.4: the two decisions carry values that cannot be confused for one another.
    # This runs BEFORE the per-row equality assertions below, and the order is
    # load-bearing. Asserting `row.source_class == "EXTERNAL"` narrows that member
    # expression to `Literal["EXTERNAL"]`; after both narrowings mypy can PROVE the
    # inequality, and `comparison-overlap` was reporting exactly that -- an
    # assertion that cannot fail. Observed first, it can.
    assert seeded_row.source_class != row.source_class

    assert row.source_class == "EXTERNAL"
    assert row.is_synthetic is False
    assert seeded_row.source_class == "SEEDED"
    assert seeded_row.is_synthetic is True
