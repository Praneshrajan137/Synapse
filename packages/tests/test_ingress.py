"""Tests for the ingress adapter boundary (Phase 2.1, synapse_common.ingress).

Guards the honesty invariant: an order's origin is an explicit first-class field,
consistent with the deployed synthetic marker (synapse_common.synthetic) so the
two can never disagree and a synthetic order can never present as real. Also
covers determinism, the Tier-P contract (no silent synthetic fallback), and the
explicit-config factory.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from synapse_common.ingress import (
    IngressOrder,
    IngressSourceKind,
    RealIngressSource,
    SyntheticIngressSource,
    make_ingress_source,
)
from synapse_common.synthetic import SYNTHETIC_ORDER_PREFIX, is_synthetic_order_id


def _real_order(order_id: str) -> IngressOrder:
    return IngressOrder(
        order_id=order_id,
        city="bengaluru",
        store_id="STORE-001",
        sku_id="SKU-0001",
        quantity=3,
        source=IngressSourceKind.REAL_API,
    )


def test_synthetic_source_emits_labelled_synthetic_orders() -> None:
    orders = SyntheticIngressSource(seed=1).fetch_batch(3)
    assert len(orders) == 3
    for o in orders:
        assert o.source is IngressSourceKind.SYNTHETIC
        assert o.is_synthetic is True
        # Consistent with the deployed single-source-of-truth.
        assert o.order_id.startswith(SYNTHETIC_ORDER_PREFIX)
        assert is_synthetic_order_id(o.order_id) is True


def test_real_order_is_not_synthetic() -> None:
    assert _real_order("ORD-12345").is_synthetic is False


def test_synthetic_prefix_overrides_a_mislabelled_real_order() -> None:
    # A real-labelled order carrying the synthetic prefix must still read as
    # synthetic — origin can never be downgraded to "real" by a wrong label.
    assert _real_order(f"{SYNTHETIC_ORDER_PREFIX}999").is_synthetic is True


def test_to_demand_payload_shape() -> None:
    o = _real_order("ORD-1")
    payload = o.to_demand_payload()
    assert set(payload) == {"order_id", "city", "store_id", "sku_id", "quantity", "timestamp"}
    assert payload["order_id"] == "ORD-1"
    assert payload["quantity"] == 3
    assert payload["timestamp"].endswith("Z")


def test_ingress_order_is_frozen() -> None:
    o = _real_order("ORD-1")
    with pytest.raises(ValidationError):
        o.quantity = 9  # type: ignore[misc]


def test_synthetic_source_is_deterministic_under_seed() -> None:
    a = SyntheticIngressSource(seed=7).fetch_batch(5)
    b = SyntheticIngressSource(seed=7).fetch_batch(5)
    rng_fields = lambda os_: [(o.store_id, o.sku_id, o.quantity) for o in os_]  # noqa: E731
    assert rng_fields(a) == rng_fields(b)


def test_real_source_raises_the_tier_p_contract() -> None:
    with pytest.raises(NotImplementedError, match="Tier-P"):
        RealIngressSource().fetch_batch()


def test_factory_defaults_to_synthetic() -> None:
    assert isinstance(make_ingress_source(), SyntheticIngressSource)
    assert isinstance(make_ingress_source("synthetic"), SyntheticIngressSource)


@pytest.mark.parametrize("kind", ["real_api", "real_queue"])
def test_factory_real_source_is_an_honest_gap(kind: str) -> None:
    with pytest.raises(NotImplementedError):
        make_ingress_source(kind)


def test_factory_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="unknown"):
        make_ingress_source("bogus")


def test_factory_respects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNAPSE_INGRESS_SOURCE", "real_queue")
    with pytest.raises(NotImplementedError):
        make_ingress_source()
    monkeypatch.setenv("SYNAPSE_INGRESS_SOURCE", "synthetic")
    assert isinstance(make_ingress_source(), SyntheticIngressSource)
