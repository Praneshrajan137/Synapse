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

Validates: Requirements 3.5
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.contract import load_contract
from uplift.interfaces import Outcome

# The full set of Outcome members the rule must map into.
_OUTCOMES = frozenset(Outcome)

# Load the real, version-controlled metric contract once. Its primary KPI is
# ``fill_rate`` (see uplift/metric_contract.yaml), which the KPI-name strategy
# includes alongside non-primary and unknown names.
_CONTRACT = load_contract()


# ---------------------------------------------------------------------------
# Strategies
#
# Floats span the whole space including non-finite values, so degenerate arrays
# (NaN/inf, zero-variance/constant) exercise the totality guarantees baked into
# ``classify`` (cohens_d / significance return neutral values, never raise).
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

# KPI names: the real primary KPI, other KpiVector fields (declared but non-primary
# in the contract), and arbitrary/unknown names.
_kpi_names = st.one_of(
    st.just("fill_rate"),
    st.sampled_from(
        ["spoilage_rate", "stockout_rate", "avg_delivery_time_min", "margin", "co2_estimate"]
    ),
    st.text(max_size=16),
)


# ---------------------------------------------------------------------------
# Property 12: classify is a total, deterministic one-of-three mapping (R3.5)
# ---------------------------------------------------------------------------
@settings(max_examples=300)
@given(consensus=_varied_arrays, baseline=_varied_arrays, kpi=_kpi_names)
def test_classify_is_total_deterministic_mapping(
    consensus: list[float], baseline: list[float], kpi: str
) -> None:
    """classify returns exactly one Outcome, deterministically, never raising."""
    # (3) Totality: the call must not raise for any input.
    first = _CONTRACT.classify(consensus, baseline, kpi)

    # (1) The result is exactly one member of the Outcome enum.
    assert isinstance(first, Outcome)
    assert first in _OUTCOMES

    # (2) Determinism: identical inputs yield the identical outcome on a second call.
    second = _CONTRACT.classify(consensus, baseline, kpi)
    assert second == first
