"""SYNAPSE Supplier Trust -- Model unit tests."""
from __future__ import annotations

import pyro
import pytest
import torch
from torch_geometric.data import HeteroData

from agents.supplier_trust.models.bayesian_lead import BayesianLeadTimeModel
from agents.supplier_trust.models.trust_gnn import SupplierTrustGNN


class TestSupplierTrustGNN:
    """Unit tests for the heterogeneous GNN trust model."""

    @pytest.fixture()
    def hetero_data(self) -> HeteroData:
        """Build a small heterogeneous graph for testing."""
        data = HeteroData()

        n_suppliers, n_skus, n_stores = 5, 8, 3
        data["supplier"].x = torch.randn(n_suppliers, 16)
        data["sku"].x = torch.randn(n_skus, 12)
        data["darkstore"].x = torch.randn(n_stores, 10)

        data["supplier", "supplies", "sku"].edge_index = torch.tensor(
            [[0, 1, 2, 3, 4], [0, 1, 2, 3, 4]], dtype=torch.long,
        )
        data["sku", "stocked_at", "darkstore"].edge_index = torch.tensor(
            [[0, 1, 2, 3, 4], [0, 1, 2, 0, 1]], dtype=torch.long,
        )
        data["supplier", "delivers_to", "darkstore"].edge_index = torch.tensor(
            [[0, 1, 2], [0, 1, 2]], dtype=torch.long,
        )
        data["darkstore", "orders_from", "supplier"].edge_index = torch.tensor(
            [[0, 1, 2], [0, 1, 2]], dtype=torch.long,
        )
        return data

    def test_forward_pass(self, hetero_data: HeteroData) -> None:
        model = SupplierTrustGNN(
            supplier_in_dim=16, sku_in_dim=12, store_in_dim=10,
            hidden_dim=32, out_dim=16, num_layers=2,
        )
        out = model(hetero_data)
        assert "supplier" in out
        assert "sku" in out
        assert "darkstore" in out
        assert out["supplier"].shape == (5, 16)
        assert out["sku"].shape == (8, 16)
        assert out["darkstore"].shape == (3, 16)

    def test_get_supplier_embeddings(self, hetero_data: HeteroData) -> None:
        model = SupplierTrustGNN(
            supplier_in_dim=16, sku_in_dim=12, store_in_dim=10,
            hidden_dim=32, out_dim=16, num_layers=2,
        )
        emb = model.get_supplier_embeddings(hetero_data)
        assert emb.shape == (5, 16)

    def test_gradient_flow(self, hetero_data: HeteroData) -> None:
        model = SupplierTrustGNN(
            supplier_in_dim=16, sku_in_dim=12, store_in_dim=10,
            hidden_dim=32, out_dim=16, num_layers=2,
        )
        out = model(hetero_data)
        loss = out["supplier"].sum()
        loss.backward()
        for param in model.parameters():
            if param.requires_grad:
                assert param.grad is not None


class TestBayesianLeadTimeModel:
    """Unit tests for the Bayesian lead-time posterior model."""

    def test_posterior_has_required_fields(self) -> None:
        """POST-ST-002: posterior must contain mean, std, p10, p90."""
        pyro.clear_param_store()
        model = BayesianLeadTimeModel(num_steps=100, num_samples=50)
        observed = torch.tensor([3.0, 4.5, 5.0, 3.5, 4.0])
        posterior = model.predict(observed)
        result = posterior.to_dict()

        assert "mean_days" in result
        assert "std_days" in result
        assert "p10_days" in result
        assert "p90_days" in result

    def test_posterior_std_positive(self) -> None:
        """INV-ST-003: std_days must be > 0."""
        pyro.clear_param_store()
        model = BayesianLeadTimeModel(num_steps=100, num_samples=50)
        observed = torch.tensor([2.0, 3.0, 4.0, 5.0, 6.0])
        posterior = model.predict(observed)
        assert posterior.std_days > 0

    def test_posterior_quantile_ordering(self) -> None:
        """p10 <= mean <= p90."""
        pyro.clear_param_store()
        model = BayesianLeadTimeModel(num_steps=200, num_samples=100)
        observed = torch.tensor([2.0, 3.0, 4.0, 5.0, 6.0, 3.5, 4.5])
        posterior = model.predict(observed)
        assert posterior.p10_days <= posterior.mean_days
        assert posterior.mean_days <= posterior.p90_days

    def test_rejects_empty_input(self) -> None:
        model = BayesianLeadTimeModel()
        with pytest.raises(ValueError, match="PRE-ST-002"):
            model.fit(torch.tensor([]))

    def test_rejects_negative_input(self) -> None:
        model = BayesianLeadTimeModel()
        with pytest.raises(ValueError, match="positive"):
            model.fit(torch.tensor([-1.0, 2.0]))
