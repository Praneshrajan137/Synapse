"""Tests for the SLO -> alerts generator (Sprint 8, WS-4)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from slo_to_alerts import (  # noqa: E402  -- import after sys.path adjustment
    BurnRate,
    Slo,
    discover_slo_files,
    load_slo_file,
    main,
    render_rules_yaml,
)


def _latency_slo(target: float = 99.5, threshold: float = 0.1) -> Slo:
    return Slo(
        service="synapse-orchestrator",
        name="tier1_latency",
        description="Tier 1 latency",
        target_sli=target,
        window_days=28,
        metric={
            "type": "latency_bucket",
            "bucket_metric": "synapse_inference_latency_seconds_bucket",
            "threshold_seconds": threshold,
            "labels": {"tier": "tier_1"},
        },
        burn_rates=(
            BurnRate(severity="page", long_window="1h", short_window="5m", burn=14.4),
            BurnRate(severity="ticket", long_window="6h", short_window="30m", burn=6.0),
        ),
        labels={"team": "platform"},
    )


class TestSloDataclass:
    def test_error_budget_from_target(self) -> None:
        s = _latency_slo(target=99.5)
        assert s.error_budget == pytest.approx(0.005)

    def test_error_budget_clamped_to_zero(self) -> None:
        s = _latency_slo(target=200.0)
        assert s.error_budget == 0.0


class TestRenderRulesYaml:
    def test_emits_two_alerts_per_slo(self) -> None:
        text = render_rules_yaml([_latency_slo()])
        loaded = yaml.safe_load(text)
        assert "groups" in loaded
        rules = loaded["groups"][0]["rules"]
        # 2 burn rates -> 2 alert rules.
        assert len(rules) == 2
        assert {r["labels"]["burn_window"] for r in rules} == {"1h", "6h"}

    def test_alert_expr_is_two_window_form(self) -> None:
        text = render_rules_yaml([_latency_slo()])
        loaded = yaml.safe_load(text)
        rule = loaded["groups"][0]["rules"][0]
        # Both the long and short window queries must appear in the expression.
        expr = rule["expr"]
        assert "[1h]" in expr
        assert "[5m]" in expr
        # Threshold for 14.4x burn over 0.005 budget = 0.072.
        assert "0.072" in expr
        # The two clauses are joined by "and".
        assert "\nand\n" in expr

    def test_threshold_scales_with_burn(self) -> None:
        text = render_rules_yaml([_latency_slo()])
        loaded = yaml.safe_load(text)
        rules = {r["labels"]["burn_window"]: r for r in loaded["groups"][0]["rules"]}
        # 14.4 * 0.005 = 0.072
        assert "0.072" in rules["1h"]["expr"]
        # 6.0 * 0.005 = 0.03
        assert "0.03" in rules["6h"]["expr"]

    def test_labels_propagated(self) -> None:
        text = render_rules_yaml([_latency_slo()])
        loaded = yaml.safe_load(text)
        rule = loaded["groups"][0]["rules"][0]
        labels = rule["labels"]
        assert labels["service"] == "synapse-orchestrator"
        assert labels["slo"] == "tier1_latency"
        assert labels["severity"] == "page"
        assert labels["team"] == "platform"

    def test_alert_runbook_url_present(self) -> None:
        text = render_rules_yaml([_latency_slo()])
        loaded = yaml.safe_load(text)
        rule = loaded["groups"][0]["rules"][0]
        assert rule["annotations"]["runbook_url"].endswith("slo-tier1_latency.md")

    def test_unsupported_metric_type_raises(self) -> None:
        bad = Slo(
            service="x",
            name="weird",
            description="",
            target_sli=99.0,
            window_days=28,
            metric={"type": "ouija_board"},
            burn_rates=(
                BurnRate(severity="page", long_window="1h", short_window="5m", burn=14.4),
            ),
            labels={},
        )
        with pytest.raises(ValueError, match="unsupported SLO metric type"):
            render_rules_yaml([bad])


class TestAvailabilityRatio:
    def test_availability_ratio_renders_window_substitution(self) -> None:
        slo = Slo(
            service="x",
            name="kafka_lag",
            description="lag healthy",
            target_sli=99.0,
            window_days=28,
            metric={
                "type": "availability_ratio",
                "good_query": "sum(rate(good[{{.window}}]))",
                "total_query": "sum(rate(total[{{.window}}]))",
            },
            burn_rates=(
                BurnRate(severity="page", long_window="1h", short_window="5m", burn=14.4),
            ),
            labels={},
        )
        text = render_rules_yaml([slo])
        rule = yaml.safe_load(text)["groups"][0]["rules"][0]
        assert "rate(good[1h])" in rule["expr"]
        assert "rate(good[5m])" in rule["expr"]
        assert "{{.window}}" not in rule["expr"]


class TestRealSloFiles:
    def test_orchestrator_slo_loads(self) -> None:
        slos = load_slo_file(REPO_ROOT / "infrastructure" / "observability" / "slos" / "orchestrator.slo.yaml")
        names = {s.name for s in slos}
        assert {
            "tier1_latency",
            "tier2_latency",
            "tier3_latency",
            "tier4_latency",
        }.issubset(names)

    def test_agents_slo_loads(self) -> None:
        slos = load_slo_file(REPO_ROOT / "infrastructure" / "observability" / "slos" / "agents.slo.yaml")
        names = {s.name for s in slos}
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
            assert any(agent in n for n in names), f"missing SLO covering {agent}"

    def test_real_slos_render_to_yaml(self) -> None:
        slos: list[Slo] = []
        for path in discover_slo_files():
            slos.extend(load_slo_file(path))
        text = render_rules_yaml(slos)
        loaded = yaml.safe_load(text)
        assert "groups" in loaded
        # At minimum: every SLO with at least one burn rate produces a rule.
        rule_count = sum(len(g["rules"]) for g in loaded["groups"])
        expected_min = sum(len(s.burn_rates) for s in slos)
        assert rule_count == expected_min


class TestMainEntry:
    def test_main_stdout_emits_yaml(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["--stdout"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "groups:" in captured.out
        # Should at least contain orchestrator and agents groupings.
        assert "synapse-orchestrator-slo-burn" in captured.out
        assert "synapse-agents-slo-burn" in captured.out
