"""Tests for synapse_common.a2a_envelope, the one reader of the ``proposal`` envelope.

The consensus protocol sends ``params={"decision_context": request}`` (finding 112). The wire
key is written out as a literal here rather than read from ``PROPOSAL_ENVELOPE_KEY``, so renaming
the constant away from what the protocol sends fails these tests.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from synapse_common.a2a_envelope import (
    MissingDecisionContext,
    MissingDecisionContextError,
    decision_context,
)

#: The key ``ConsensusProtocol._request_proposal`` sends (orchestrator/consensus/protocol.py).
_WIRE_KEY = "decision_context"

_SCALARS = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False),
    st.text(max_size=8),
)
_VALUES = st.recursive(
    _SCALARS,
    lambda children: st.one_of(
        st.lists(children, max_size=3),
        st.dictionaries(st.text(max_size=6), children, max_size=3),
    ),
    max_leaves=8,
)
_REQUESTS = st.dictionaries(st.text(max_size=12), _VALUES, max_size=6)


def test_the_reading_is_the_request_inside_the_envelope() -> None:
    request = {"sku_ids": ["sku-1", "sku-2"], "store_id": "STORE_BLR_001", "sim_time": 90.0}

    assert decision_context({_WIRE_KEY: request}) == request


def test_a_none_value_reads_as_absent_and_every_other_falsy_value_is_kept() -> None:
    envelope = {"store_id": None, "order_id": None, "n": 0, "name": "", "ok": False, "skus": []}

    assert decision_context({_WIRE_KEY: envelope}) == {"n": 0, "name": "", "ok": False, "skus": []}


@given(request=_REQUESTS)
def test_the_reading_keeps_every_value_but_none_and_adds_nothing(request: dict[str, Any]) -> None:
    reading = decision_context({_WIRE_KEY: request})

    assert all(value is not None for value in reading.values())
    assert all(reading[key] == value for key, value in request.items() if value is not None)
    assert set(reading) <= set(request)


@given(request=_REQUESTS)
def test_reading_the_envelope_modifies_neither_params_nor_the_envelope(
    request: dict[str, Any],
) -> None:
    params = {_WIRE_KEY: request, "unrelated": [1, 2]}
    before = copy.deepcopy(params)

    reading = decision_context(params)
    # A reading that aliased the envelope would carry this write back into params.
    reading["written_by_the_caller"] = 1

    assert params == before


@pytest.mark.parametrize(
    "params",
    [{}, {"sku_ids": ["sku-1"], "store_id": "S1"}, {"decision-context": {"sku_ids": ["sku-1"]}}],
    ids=["empty", "flat", "misspelt-key"],
)
def test_params_without_the_envelope_are_refused_naming_the_key_and_its_sender(
    params: dict[str, Any],
) -> None:
    with pytest.raises(MissingDecisionContextError) as refusal:
        decision_context(params)

    assert _WIRE_KEY in str(refusal.value)
    assert "_request_proposal" in str(refusal.value)


@pytest.mark.parametrize(
    "envelope",
    [None, "sku-1", 7, ["sku-1"], ("sku-1",)],
    ids=["null", "string", "number", "list", "tuple"],
)
def test_an_envelope_that_is_not_an_object_is_refused_naming_the_key(envelope: Any) -> None:
    with pytest.raises(MissingDecisionContextError) as refusal:
        decision_context({_WIRE_KEY: envelope})

    assert _WIRE_KEY in str(refusal.value)


@pytest.mark.parametrize(
    "params",
    [None, [], [_WIRE_KEY], _WIRE_KEY, 3],
    ids=["null", "empty-array", "array-holding-the-key", "string-holding-the-key", "number"],
)
def test_params_that_are_not_an_object_are_refused_naming_the_key(params: Any) -> None:
    # The two "holding the key" cases pass a bare membership test and would then fail on
    # indexing as a TypeError, so they pin the type check rather than the key check.
    with pytest.raises(MissingDecisionContextError) as refusal:
        decision_context(params)

    assert _WIRE_KEY in str(refusal.value)


def test_the_contracted_name_catches_the_refusal() -> None:
    # The Inventory Sentinel's handler catches `MissingDecisionContext`; it must be the class
    # `decision_context` raises, or that handler's refusal path would never run.
    with pytest.raises(MissingDecisionContext):
        decision_context({"sku_ids": ["sku-1"]})
