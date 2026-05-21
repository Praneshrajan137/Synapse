"""Tests for the spec CLI (Sprint 8, WS-3)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from spec_cli import (  # noqa: E402  -- import after sys.path adjustment
    NumericInvariant,
    SpecRef,
    discover_specs,
    extract_numeric_invariants,
    main,
    render_alert_yaml,
    validate_spec,
)


def _spec_ref(data: dict[str, object], path: Path | None = None) -> SpecRef:
    return SpecRef(path=path or Path("/tmp/test_spec.yaml"), data=data)


def _minimal_valid_spec() -> dict[str, object]:
    return {
        "agent_name": "demand_prophet",
        "invariants": [
            {
                "id": "INV-DP-001",
                "description": "Forecast includes intervals",
                "assertion": "lower is not None",
                "severity": "critical",
            },
            {
                "id": "INV-DP-008",
                "description": "Inference latency within Tier 2 SLA",
                "assertion": "inference_latency_ms < 500",
                "severity": "high",
            },
        ],
        "state_machine": {
            "initial_state": "IDLE",
            "states": ["IDLE", "PROPOSING", "ERROR"],
            "transitions": [
                {"from": "IDLE", "to": "PROPOSING", "trigger": "go"},
                {"from": "PROPOSING", "to": "ERROR", "trigger": "boom"},
                {"from": "ERROR", "to": "IDLE", "trigger": "recover"},
            ],
        },
    }


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


class TestValidate:
    def test_minimal_passes(self) -> None:
        assert validate_spec(_spec_ref(_minimal_valid_spec())) == []

    def test_missing_agent_name_flagged(self) -> None:
        spec = _minimal_valid_spec()
        del spec["agent_name"]
        errs = validate_spec(_spec_ref(spec))
        assert any("missing required key 'agent_name'" in e for e in errs)

    def test_duplicate_invariant_id_flagged(self) -> None:
        spec = _minimal_valid_spec()
        invs = list(spec["invariants"])  # type: ignore[arg-type]
        invs.append(dict(invs[0]))
        spec["invariants"] = invs
        errs = validate_spec(_spec_ref(spec))
        assert any("duplicate invariant id" in e for e in errs)

    def test_invalid_severity_flagged(self) -> None:
        spec = _minimal_valid_spec()
        spec["invariants"][0]["severity"] = "vibes"  # type: ignore[index]
        errs = validate_spec(_spec_ref(spec))
        assert any("invalid severity" in e for e in errs)

    def test_unknown_state_in_transition_flagged(self) -> None:
        spec = _minimal_valid_spec()
        spec["state_machine"]["transitions"].append(  # type: ignore[index]
            {"from": "IDLE", "to": "OUTER_SPACE", "trigger": "warp"}
        )
        errs = validate_spec(_spec_ref(spec))
        assert any("OUTER_SPACE" in e for e in errs)

    def test_initial_state_not_in_states_flagged(self) -> None:
        spec = _minimal_valid_spec()
        spec["state_machine"]["initial_state"] = "MISSING"  # type: ignore[index]
        errs = validate_spec(_spec_ref(spec))
        assert any("initial_state 'MISSING'" in e for e in errs)

    def test_unreachable_states_flagged(self) -> None:
        spec = _minimal_valid_spec()
        # Add an island state with no incoming transition.
        spec["state_machine"]["states"].append("ISLAND")  # type: ignore[index]
        errs = validate_spec(_spec_ref(spec))
        assert any("unreachable states" in e for e in errs)

    def test_missing_assertion_flagged(self) -> None:
        spec = _minimal_valid_spec()
        del spec["invariants"][0]["assertion"]  # type: ignore[index]
        errs = validate_spec(_spec_ref(spec))
        assert any("missing assertion" in e for e in errs)


# ---------------------------------------------------------------------------
# generate-alerts
# ---------------------------------------------------------------------------


class TestExtractNumericInvariants:
    def test_extracts_threshold_invariants(self) -> None:
        ref = _spec_ref(_minimal_valid_spec())
        nis = list(extract_numeric_invariants(ref))
        # Only INV-DP-008 has a numeric threshold.
        assert len(nis) == 1
        ni = nis[0]
        assert ni.id == "INV-DP-008"
        assert ni.op == "<"
        assert ni.threshold == 500.0
        assert "latency" in ni.metric.lower()

    def test_skips_non_numeric_assertions(self) -> None:
        spec = {
            "agent_name": "x",
            "invariants": [
                {
                    "id": "INV-X-001",
                    "description": "no number here",
                    "assertion": "result is not None",
                    "severity": "critical",
                }
            ],
        }
        nis = list(extract_numeric_invariants(_spec_ref(spec)))
        assert nis == []

    def test_supports_decimal_thresholds(self) -> None:
        spec = {
            "agent_name": "x",
            "invariants": [
                {
                    "id": "INV-X-002",
                    "description": "coverage",
                    "assertion": "empirical_coverage >= 0.85",
                    "severity": "critical",
                }
            ],
        }
        ni = next(iter(extract_numeric_invariants(_spec_ref(spec))))
        assert ni.threshold == pytest.approx(0.85)
        assert ni.op == ">="


class TestRenderAlertYaml:
    def test_emits_valid_yaml(self) -> None:
        nis = [
            NumericInvariant(
                spec_path=Path("/x"),
                agent="demand_prophet",
                id="INV-DP-008",
                description="latency",
                severity="high",
                metric="inference_latency_ms",
                op="<",
                threshold=500.0,
            )
        ]
        text = render_alert_yaml(nis)
        loaded = yaml.safe_load(text)
        assert "groups" in loaded
        assert loaded["groups"][0]["name"] == "synapse-demand_prophet-invariants"
        rule = loaded["groups"][0]["rules"][0]
        assert rule["alert"] == "SynapseInvariantBreach_INV_DP_008"
        # The fire-condition operator should be the *opposite* of the spec
        # condition (alert when invariant is violated).
        assert " >= " in rule["expr"]
        assert "500.0" in rule["expr"]
        assert rule["labels"]["severity"] == "high"
        assert rule["labels"]["agent"] == "demand_prophet"
        assert "runbook_url" in rule["annotations"]

    def test_groups_per_agent(self) -> None:
        nis = [
            NumericInvariant(
                spec_path=Path("/x"),
                agent="demand_prophet",
                id="INV-DP-008",
                description="d1",
                severity="high",
                metric="x",
                op="<",
                threshold=1.0,
            ),
            NumericInvariant(
                spec_path=Path("/y"),
                agent="pricing_oracle",
                id="INV-PO-005",
                description="d2",
                severity="critical",
                metric="y",
                op="<",
                threshold=2.0,
            ),
        ]
        loaded = yaml.safe_load(render_alert_yaml(nis))
        names = {g["name"] for g in loaded["groups"]}
        assert names == {
            "synapse-demand_prophet-invariants",
            "synapse-pricing_oracle-invariants",
        }


# ---------------------------------------------------------------------------
# discovery + main()
# ---------------------------------------------------------------------------


class TestDiscoverSpecs:
    def test_finds_real_specs(self) -> None:
        paths = discover_specs()
        names = {p.parent.name for p in paths}
        # At minimum the eight agents.
        for agent in (
            "demand_prophet",
            "routing_navigator",
            "inventory_sentinel",
            "pricing_oracle",
            "freshness_guardian",
            "disruption_shield",
            "supplier_trust",
            "sustainability_agent",
        ):
            assert agent in names, f"missing spec for {agent}"


class TestMainEntry:
    def test_validate_against_real_specs(self) -> None:
        # Should pass on the real repo specs.
        rc = main(["validate"])
        assert rc == 0

    def test_unknown_subcommand_returns_error(self) -> None:
        with pytest.raises(SystemExit):
            main(["nonsense"])
