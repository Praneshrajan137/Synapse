"""DPDPA 2023 Compliance Tests (I-11).

India's Digital Personal Data Protection Act 2023 requires:
1. Purpose limitation — data only used for stated purpose
2. Data minimization — no raw PII leaves the store
3. Right to erasure — operator can delete identifiable rows

SYNAPSE's Inventory Sentinel uses Flower federated learning so raw
customer order history never centralizes (I-11). This test suite verifies:

- A) Federated aggregation operates on gradients only (no raw tensors
     containing customer IDs).
- B) The audit log supports right-to-erasure at the decision-id granularity.
- C) No agent's `requirements.txt` pulls a library that centralizes raw
     customer data (e.g., `customer_analytics_cloud`, etc.).
- D) The Inventory Sentinel Flower client configuration opts out of metric
     sharing that would leak store-level order volume.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def test_flower_client_does_not_send_raw_orders() -> None:
    """I-11: gradient-only aggregation."""
    candidates = list(REPO.glob("agents/inventory_sentinel/**/flower_client*.py"))
    if not candidates:
        pytest.skip("Flower client module absent; skipping DPDPA-A")
    bad_patterns = [
        r"\border_history\b",
        r"\bcustomer_id\b",
        r"\braw_demand\b",
        r"pickle\.dumps",  # no serialized raw tensors named like orders
    ]
    for path in candidates:
        content = _read(path)
        for pat in bad_patterns:
            matches = [
                line
                for line in content.splitlines()
                if re.search(pat, line)
                and not line.strip().startswith(("#", '"', "'"))
            ]
            assert not matches, f"{path}: DPDPA-A violation — pattern '{pat}' in {matches!r}"


def test_audit_erasure_supports_decision_scope() -> None:
    """I-11: operator can delete audit rows by decision_id when a subject exercises Article 12 rights."""
    init_sql = REPO / "infrastructure" / "postgres" / "init_audit.sql"
    if not init_sql.exists():
        pytest.skip(f"{init_sql} absent")
    content = _read(init_sql)
    assert "audit_decisions" in content, "audit_decisions table must exist"
    # The immutability guarantee applies to the *app* role; operator role
    # must retain DELETE for right-to-erasure.
    assert re.search(
        r"GRANT\s+DELETE.*audit_decisions\s+TO\s+\w*(operator|admin|erasure)",
        content,
        re.IGNORECASE,
    ), "no operator-scoped DELETE grant for right-to-erasure"


def test_no_paid_analytics_packages_on_agents() -> None:
    """I-1 + DPDPA purpose-limitation guardrail: no customer-analytics SaaS."""
    banned = {
        "segment-analytics",
        "amplitude-python-sdk",
        "mixpanel",
        "mparticle",
        "heap-analytics",
    }
    for req in REPO.glob("agents/*/requirements.txt"):
        content = _read(req).lower()
        for pkg in banned:
            assert pkg not in content, f"{req}: banned analytics package '{pkg}'"


def test_flower_metric_sharing_opt_out() -> None:
    """I-11: Flower config must avoid leaking per-store order volume as a metric."""
    candidates = list(REPO.glob("agents/inventory_sentinel/**/flower_*.py"))
    if not candidates:
        pytest.skip("Flower modules absent")
    leaky_metrics = ["orders_per_hour", "customer_count", "raw_demand_mean"]
    for path in candidates:
        content = _read(path)
        for metric in leaky_metrics:
            assert metric not in content, (
                f"{path}: Flower configuration leaks '{metric}' — violates DPDPA-D"
            )
