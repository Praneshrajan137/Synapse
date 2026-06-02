"""Feast feature-ref consistency (WS-C, ADR-043).

The FeatureProvider passes the agent's ``FEATURE_REFS`` straight to Feast's
``get_online_features(features=...)``. If a ref names a view/field that the
registered ``FeatureView`` does not define, real Feast rejects the request and the
provider degrades to FALLBACK *forever* — silently, because the degradation is
"honest" (degraded=True). That exact mismatch existed: the pipeline asked for
``demand_features:rolling_7d_mean`` while the view is ``sku_demand_signals`` with
field ``rolling_mean_7d``.

This test pins the pipeline's refs to the registered view *definition* — no Redis,
no materialization, no ``feast apply`` needed; it imports the FeatureView source of
truth. It SKIPs only when ``feast`` itself is not installed (the dev box), and runs
wherever the ML stack is present (the CI training-smoke job).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FEAST_REPO = ROOT / "data_fabric" / "feast"


def _load_demand_view() -> object:
    """Import the registered demand FeatureView (source of truth). Needs feast."""
    pytest.importorskip("feast")
    # The feature modules do `from features.entities import sku, store`, so the
    # feast repo dir must be importable as the `features` package root.
    repo = str(FEAST_REPO)
    if repo not in sys.path:
        sys.path.insert(0, repo)
    import importlib  # noqa: PLC0415

    module = importlib.import_module("features.demand_features")
    return module.demand_features


def test_pipeline_feature_refs_exist_in_registered_view() -> None:
    """Every demand_prophet FEATURE_REF must resolve against the real FeatureView."""
    from agents.demand_prophet.inference.pipeline import FEATURE_REFS

    view = _load_demand_view()
    view_name = view.name  # type: ignore[attr-defined]
    fields = {f.name for f in view.schema}  # type: ignore[attr-defined]
    allowed = {f"{view_name}:{field}" for field in fields}

    for ref in FEATURE_REFS:
        assert ref in allowed, (
            f"FEATURE_REF {ref!r} is not a field of FeatureView {view_name!r} "
            f"(real Feast would reject it → permanent FALLBACK). Allowed: {sorted(allowed)}"
        )


def test_feature_refs_are_view_qualified() -> None:
    """Refs must be `view:field` (Feast's required form), not bare field names."""
    from agents.demand_prophet.inference.pipeline import FEATURE_REFS

    for ref in FEATURE_REFS:
        assert ref.count(":") == 1 and all(ref.split(":")), f"malformed feature ref {ref!r}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
