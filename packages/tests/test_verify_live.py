"""Unit tests for the deploy-truth oracle's pure assertion logic.

The network/subprocess layers are exercised on the real deploy by
cd-gcp.yml and live-truth.yml; these tests pin the decision logic so a
refactor cannot silently weaken an assertion.
"""

from __future__ import annotations

import json

from scripts.deploy.verify_live import (
    evaluate_containers,
    evaluate_restart_counts,
    evaluate_status,
    parse_compose_ps,
    sha_matches,
)


def test_sha_matches_full_vs_short_prefix() -> None:
    full = "3b454773af2f58dbb3d1fc80aeb99c2ec151ea10"
    assert sha_matches(full, full)
    assert sha_matches("3b45477", full)
    assert sha_matches(full, "3b45477")
    assert sha_matches("3B45477", full)  # case-insensitive


def test_sha_matches_rejects_mismatch_and_short_input() -> None:
    full = "3b454773af2f58dbb3d1fc80aeb99c2ec151ea10"
    assert not sha_matches("deadbeef", full)
    assert not sha_matches("3b4547", full)  # < 7 chars can collide too easily
    assert not sha_matches("", full)
    assert not sha_matches(full, "")


def test_parse_compose_ps_accepts_ndjson_and_array() -> None:
    ndjson = (
        '{"Service": "api", "State": "running", "Health": "healthy"}\n'
        '{"Service": "nginx", "State": "running", "Health": ""}\n'
    )
    array = json.dumps(
        [
            {"Service": "api", "State": "running", "Health": "healthy"},
            {"Service": "nginx", "State": "running", "Health": ""},
        ]
    )
    assert len(parse_compose_ps(ndjson)) == 2
    assert len(parse_compose_ps(array)) == 2
    assert parse_compose_ps("") == []
    assert parse_compose_ps("  \n ") == []


def test_evaluate_containers_all_healthy_passes() -> None:
    rows = [
        {"Service": "api", "State": "running", "Health": "healthy"},
        {"Service": "kafka", "State": "running", "Health": "healthy"},
        {"Service": "mlflow", "State": "running", "Health": ""},  # no healthcheck
    ]
    results = evaluate_containers(rows)
    assert all(r.ok for r in results)
    assert len(results) == 3


def test_evaluate_containers_fails_on_crashloop_states() -> None:
    # The jsonschema incident signature: agents Restarting, api stuck Created.
    rows = [
        {"Service": "pricing-oracle", "State": "restarting", "Health": ""},
        {"Service": "api", "State": "created", "Health": ""},
        {"Service": "nginx", "State": "running", "Health": "healthy"},
    ]
    results = evaluate_containers(rows)
    failed = {r.name for r in results if not r.ok}
    assert failed == {"running:pricing-oracle", "running:api"}


def test_evaluate_containers_fails_on_unhealthy_and_starting() -> None:
    rows = [
        {"Service": "orchestrator", "State": "running", "Health": "unhealthy"},
        {"Service": "postgres", "State": "running", "Health": "starting"},
    ]
    results = evaluate_containers(rows)
    assert not any(r.ok for r in results)


def test_evaluate_containers_empty_ps_is_a_failure() -> None:
    results = evaluate_containers([])
    assert len(results) == 1
    assert not results[0].ok


def test_evaluate_restart_counts_threshold() -> None:
    counts = [("synapse-api", 0), ("synapse-pricing-oracle", 3)]
    strict = evaluate_restart_counts(counts, max_restarts=0)
    assert [r.ok for r in strict] == [True, False]
    lenient = evaluate_restart_counts(counts, max_restarts=3)
    assert all(r.ok for r in lenient)


def test_evaluate_status_allowed_set() -> None:
    assert evaluate_status("decisions_auth_gate", 401, (200, 401)).ok
    assert evaluate_status("decisions_auth_gate", 200, (200, 401)).ok
    assert not evaluate_status("decisions_auth_gate", 503, (200, 401)).ok
    # The 307 regression class: only exactly 200 passes, redirects fail.
    assert not evaluate_status("agents_no_redirect", 307, (200,)).ok
