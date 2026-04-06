"""SYNAPSE Routing Navigator -- Model unit tests."""
from __future__ import annotations

import torch

from agents.routing_navigator.models.decoder import PointerDecoder
from agents.routing_navigator.models.encoder import RouteEncoder
from agents.routing_navigator.models.student import DistilledStudent


class TestRouteEncoder:
    def test_forward_pass(self) -> None:
        encoder = RouteEncoder(feature_dim=10, embed_dim=64, num_heads=4, num_layers=2)
        orders = torch.randn(4, 20, 10)
        out = encoder(orders)
        assert out.shape == (4, 20, 64)

    def test_embedding_dim(self) -> None:
        encoder = RouteEncoder(embed_dim=128)
        assert encoder.get_embedding_dim() == 128


class TestPointerDecoder:
    def test_forward_pass(self) -> None:
        decoder = PointerDecoder(embed_dim=64, hidden_dim=64)
        encoder_outputs = torch.randn(2, 10, 64)
        tour, log_probs = decoder(encoder_outputs, greedy=True)
        assert tour.shape == (2, 10)
        assert log_probs.shape == (2, 10)

    def test_no_revisit(self) -> None:
        decoder = PointerDecoder(embed_dim=64, hidden_dim=64)
        encoder_outputs = torch.randn(1, 8, 64)
        tour, _ = decoder(encoder_outputs, greedy=True)
        unique = tour[0].unique()
        assert len(unique) == 8, "Each order must be visited exactly once"


class TestStudent:
    def test_forward_pass(self) -> None:
        student = DistilledStudent(input_dim=500, hidden_1=128, hidden_2=64, max_orders=50)
        x = torch.randn(4, 500)
        out = student(x)
        assert out.shape == (4, 50)

    def test_predict_route(self) -> None:
        student = DistilledStudent(input_dim=500, max_orders=50)
        x = torch.randn(1, 500)
        route = student.predict_route(x, num_orders=10)
        assert route.shape == (1, 10)
