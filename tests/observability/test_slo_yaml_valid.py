"""SLO YAML + burn-rate alert validity test (WS-4 §1-§2 acceptance).

Verifies that:
  - every ``infrastructure/observability/slos/*.slo.yaml`` parses,
    declares the required Sloth-shaped fields, and references a runbook.
  - the generated ``infrastructure/prometheus/rules/orchestrator_burn.yml``
    is byte-identical to running the generator (drift gate).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SLO_DIR = REPO_ROOT / "infrastructure" / "observability" / "slos"
RULES_FILE = REPO_ROOT / "infrastructure" / "prometheus" / "rules" / "orchestrator_burn.yml"
GENERATOR = REPO_ROOT / "scripts" / "generate_burn_alerts.py"


def _slo_paths() -> list[Path]:
    return sorted(SLO_DIR.glob("*.slo.yaml"))


@pytest.mark.contract
@pytest.mark.parametrize("path", _slo_paths(), ids=[p.name for p in _slo_paths()])
def test_slo_yaml_is_well_formed(path: Path) -> None:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert doc["service"], f"{path.name} missing service"
    slos = doc["slos"]
    assert slos, f"{path.name} declares no SLOs"
    for slo in slos:
        assert "name" in slo
        assert 0.0 < float(slo["objective"]) <= 100.0
        events = slo["sli"]["events"]
        assert "{{.window}}" in events["error_query"]
        assert "{{.window}}" in events["total_query"]
        annotations = slo.get("alerting", {}).get("annotations", {})
        assert annotations.get("runbook_url", "").startswith("http")


@pytest.mark.contract
def test_burn_rate_rules_in_sync_with_generator() -> None:
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"burn-rate rules out of sync.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


@pytest.mark.contract
def test_burn_rate_rules_have_runbook_annotations() -> None:
    doc = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    rules = doc["groups"][0]["rules"]
    assert rules, "no burn-rate rules generated"
    for rule in rules:
        annotations = rule.get("annotations", {})
        assert annotations.get("runbook_url"), f"{rule['alert']} missing runbook_url annotation"
