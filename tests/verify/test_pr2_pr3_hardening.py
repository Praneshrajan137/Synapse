"""Tests for the Sprint 20 PR-2 (honest readiness) + PR-3 (observability) hardening.

Covers the pure, dependency-free units: the shared readiness helper's status-code
contract, the metric label-cardinality helpers, and the presence/labelability of the
new Prometheus metrics. The runtime emission paths (a2a_sdk._do_send, the twin
handlers, the orchestrator startup self-check) are exercised by their own integration
suites / a live stack; here we pin the contracts that must not regress.
"""

from __future__ import annotations

import json

from synapse_common import metrics
from synapse_common.a2a_sdk import _target_label
from synapse_common.health import readiness_response

from api.middleware.ratelimit import _coarse_path


# --- PR-2: honest readiness helper ------------------------------------------


def test_ready_is_200_healthy() -> None:
    r = readiness_response("orchestrator", ready=True, database=True)
    assert r.status_code == 200
    body = json.loads(r.body)
    assert body["status"] == "healthy"
    assert body["ready"] is True
    assert body["component"] == "orchestrator"
    assert body["database"] is True  # extra checks are surfaced for operators


def test_not_ready_is_503() -> None:
    """The whole point: an unready service returns 503 so the probe fails."""
    r = readiness_response("orchestrator", ready=False, database=False)
    assert r.status_code == 503
    assert json.loads(r.body)["status"] == "unready"


def test_degraded_is_200_but_labelled() -> None:
    """Serving-but-degraded (e.g. Kafka down) stays 200, status='degraded'."""
    r = readiness_response("orchestrator", ready=True, degraded=True, kafka="down")
    assert r.status_code == 200
    body = json.loads(r.body)
    assert body["status"] == "degraded"
    assert body["kafka"] == "down"


# --- PR-3: metric label-cardinality helpers ---------------------------------


def test_target_label_strips_scheme_port_path() -> None:
    assert _target_label("http://demand-prophet:8001") == "demand-prophet"
    assert _target_label("http://demand-prophet:8001/a2a") == "demand-prophet"
    assert _target_label("https://digital-twin:8009") == "digital-twin"


def test_coarse_path_bounds_cardinality() -> None:
    # A decision id in the path must NOT leak into the label.
    assert _coarse_path("/api/v1/decisions/123e4567/override") == "/api/v1"
    assert _coarse_path("/login") == "/login"
    assert _coarse_path("/") == "/"


# --- PR-3: the new metrics exist and are labelable --------------------------


def test_pr3_metrics_exist_and_label() -> None:
    for name in (
        "A2A_REQUEST_LATENCY",
        "A2A_REQUESTS_TOTAL",
        "RATELIMIT_REJECTIONS_TOTAL",
        "TWIN_SIMULATION_TOTAL",
        "TWIN_SIMULATION_LATENCY",
        "STARTUP_DEGRADED",
    ):
        assert hasattr(metrics, name), f"missing metric {name}"
    # Labelling must not raise (label names match definitions).
    metrics.A2A_REQUESTS_TOTAL.labels(target="x", method="proposal", outcome="ok").inc()
    metrics.A2A_REQUEST_LATENCY.labels(target="x", method="proposal").observe(0.01)
    metrics.RATELIMIT_REJECTIONS_TOTAL.labels(path="/api/v1").inc()
    metrics.TWIN_SIMULATION_TOTAL.labels(method="monte_carlo", outcome="error").inc()
    metrics.TWIN_SIMULATION_LATENCY.labels(method="simulate").observe(0.5)
    metrics.STARTUP_DEGRADED.labels(dependency="kafka").set(1.0)
