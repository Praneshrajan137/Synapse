"""SYNAPSE Supplier Trust -- Metamorphic Tests (Layer 4)."""

from __future__ import annotations

import pytest

from agents.supplier_trust.inference.pipeline import SupplierTrustPipeline

pytestmark = pytest.mark.metamorphic


def _make_history(
    n: int,
    on_time: bool = True,
    lead_time: float = 3.0,
) -> list[dict[str, object]]:
    return [{"lead_time_days": lead_time, "on_time": on_time} for _ in range(n)]


class TestMetamorphicRelations:
    @pytest.fixture()
    def pipeline(self) -> SupplierTrustPipeline:
        return SupplierTrustPipeline()

    def test_mr_st_001_late_deliveries_decrease_trust(
        self,
        pipeline: SupplierTrustPipeline,
    ) -> None:
        """MR-ST-001: More late deliveries must decrease trust score.

        Transform: increase consecutive late deliveries by 3.
        Expected: trust_score decreases.
        """
        base_history = _make_history(10, on_time=True)
        base_result = pipeline.score(
            supplier_id="SUP-MR-001",
            delivery_history=base_history,
        )

        late_history = base_history + _make_history(3, on_time=False)
        late_result = pipeline.score(
            supplier_id="SUP-MR-001",
            delivery_history=late_history,
        )

        assert late_result.trust_score < base_result.trust_score, (
            f"INV-ST-002 violated: trust did not decrease with late deliveries "
            f"(base={base_result.trust_score}, late={late_result.trust_score})"
        )

    def test_mr_st_002_perfect_history_high_trust(
        self,
        pipeline: SupplierTrustPipeline,
    ) -> None:
        """MR-ST-002: Perfect delivery history should yield trust >= 0.8."""
        perfect_history = _make_history(50, on_time=True, lead_time=3.0)
        result = pipeline.score(
            supplier_id="SUP-MR-002",
            delivery_history=perfect_history,
        )
        assert result.trust_score >= 0.8, f"Perfect-history trust {result.trust_score} < 0.8"

    def test_all_late_low_trust(
        self,
        pipeline: SupplierTrustPipeline,
    ) -> None:
        """All-late supplier should have significantly lower trust than all-on-time."""
        good = pipeline.score(
            supplier_id="SUP-GOOD",
            delivery_history=_make_history(20, on_time=True),
        )
        bad = pipeline.score(
            supplier_id="SUP-BAD",
            delivery_history=_make_history(20, on_time=False),
        )
        assert bad.trust_score < good.trust_score
