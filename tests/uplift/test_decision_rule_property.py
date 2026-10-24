"""Property-based tests for the metric contract's ``classify`` decision rule.

Feature: decision-integrity-uplift-proof
Property 12: The decision rule is a total deterministic mapping.

    *For any* consensus and baseline sample arrays and any primary KPI (and even
    arbitrary/degenerate arrays — empty, single-element, constant, ``nan``/``inf``,
    normal — and any KPI name including the real primary KPI ``fill_rate`` and
    non-primary/unknown names), ``MetricContract.classify`` returns exactly one member
    of the ``Outcome`` enum ``{SYNAPSE_WINS, BASELINE_WINS, TIE_INCONCLUSIVE}``,
    identical inputs always yield the identical outcome (call twice, assert equal),
    and it never raises (totality).

Carried to Metric_Contract v2 (decision-quality-proof task 29.4). The claim is unchanged; one
name in it is not. The real primary KPI is now ``objective`` (lower is better), and
``fill_rate`` is one of the non-primary names drawn below. ``classify`` now estimates the
contract's ``1 - alpha`` paired interval and maps its four-valued verdict onto ``Outcome``, and
it pairs the two arrays element by element. So the arrays are drawn three ways: independently
(lengths usually differ, and no interval exists), as equal-length pairs over the whole float
space (``nan``/``inf`` differences and ``fsum`` overflow reach the estimator), and as
equal-length pairs of moderate costs (every verdict is reachable). Budget inherited from the
root ``conftest.py`` profile; no ``max_examples`` literal.

Validates: Requirements 3.5
"""
from __future__ import annotations

import dataclasses

from hypothesis import given
from hypothesis import strategies as st

from uplift.contract import load_contract
from uplift.interfaces import KpiVector, Outcome

# The full set of Outcome members the rule must map into.
_OUTCOMES = frozenset(Outcome)

# Load the real, version-controlled metric contract once. Its sole primary KPI is
# ``objective`` (see uplift/metric_contract.yaml), which the KPI-name strategy includes
# alongside non-primary and unknown names.
_CONTRACT = load_contract()


# ---------------------------------------------------------------------------
# Strategies
#
# Floats span the whole space including non-finite values, so degenerate arrays
# (NaN/inf, zero-variance/constant) exercise the totality guarantees baked into
# ``classify`` (an interval that cannot be estimated resolves to TIE, never raises).
# ---------------------------------------------------------------------------
_any_float = st.floats(allow_nan=True, allow_infinity=True)

# Varied float arrays: include empty, single-element, and multi-element lists. A
# separate ``constant array`` branch guarantees zero-variance inputs are covered.
_varied_arrays = st.one_of(
    st.lists(_any_float, min_size=0, max_size=12),
    # Constant arrays (all identical) — a degenerate zero-variance input.
    st.tuples(_any_float, st.integers(min_value=0, max_value=12)).map(
        lambda pair: [pair[0]] * pair[1]
    ),
)


def _equal_length_pairs(
    values: st.SearchStrategy[float],
) -> st.SearchStrategy[tuple[list[float], list[float]]]:
    """Two arrays of one drawn length (0-12): the element-by-element pairing classify reads."""
    return st.integers(min_value=0, max_value=12).flatmap(
        lambda n: st.tuples(
            st.lists(values, min_size=n, max_size=n),
            st.lists(values, min_size=n, max_size=n),
        )
    )


# Moderate costs, so the paired differences land on every side of 0 and of the committed
# margin: wins, sub-margin gains, inconclusive results and baseline wins are all reachable.
_moderate_costs = st.floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False)

_array_pairs = st.one_of(
    st.tuples(_varied_arrays, _varied_arrays),
    _equal_length_pairs(_any_float),
    _equal_length_pairs(_moderate_costs),
)

# KPI names: the real primary KPI, every other KpiVector field (non-primary in the
# contract, ``fill_rate`` among them), and arbitrary/unknown names.
_kpi_names = st.one_of(
    st.just(_CONTRACT.objective_kpi),
    st.sampled_from(
        [
            field.name
            for field in dataclasses.fields(KpiVector)
            if field.name not in _CONTRACT.primary_kpis
        ]
    ),
    st.text(max_size=16),
)


# ---------------------------------------------------------------------------
# Property 12: classify is a total, deterministic one-of-three mapping (R3.5)
# ---------------------------------------------------------------------------
@given(arrays=_array_pairs, kpi=_kpi_names)
def test_classify_is_total_deterministic_mapping(
    arrays: tuple[list[float], list[float]], kpi: str
) -> None:
    """classify returns exactly one Outcome, deterministically, never raising."""
    consensus, baseline = arrays

    # (3) Totality: the call must not raise for any input.
    first = _CONTRACT.classify(consensus, baseline, kpi)

    # (1) The result is exactly one member of the Outcome enum.
    assert isinstance(first, Outcome)
    assert first in _OUTCOMES

    # (2) Determinism: identical inputs yield the identical outcome on a second call.
    second = _CONTRACT.classify(consensus, baseline, kpi)
    assert second == first
