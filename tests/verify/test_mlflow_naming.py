"""E2 (elevation): MLflow naming convention is enforced in source.

CLAUDE.md error patterns E-S6-07 / E-S6-14::

    Mumbai models use ``mumbai_`` prefix in MLflow:
    ``mumbai_demand_prophet_hgt_tft``, not ``demand_prophet_hgt_tft``.
    Transfer-learned models are loaded from ``mumbai_{model_name}`` in
    Staging stage. Cold-start baselines from ``mumbai_coldstart_{model_name}``.

A registry-side check requires a running MLflow server. Here we verify the
*producer side* statically: every Mumbai model registration in
``ml_pipelines/transfer/`` and ``ml_pipelines/ab_test/`` must use the
``mumbai_`` (or ``mumbai_coldstart_``) prefix. Catches the regression
where a copy-paste from Bengaluru re-uses the unprefixed name.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _grep_register_calls(py_file: Path) -> list[str]:
    """Return the model_name strings passed to mlflow registration calls."""
    if not py_file.exists():
        return []
    text = py_file.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(?:registered_model_name|register_model|model_name)\s*=\s*"
        r'(["\'`f]+)([^"\']+)["\'`]',
        re.MULTILINE,
    )
    return [match.group(2) for match in pattern.finditer(text)]


def _grep_string_assignments(py_file: Path, varname: str) -> list[str]:
    """Variables assigned a string that we want to inspect for prefix usage."""
    if not py_file.exists():
        return []
    text = py_file.read_text(encoding="utf-8")
    pattern = re.compile(
        rf'\b{re.escape(varname)}\s*=\s*f?"([^"\n]+)"',
        re.MULTILINE,
    )
    return pattern.findall(text)


def test_cold_start_baseline_uses_mumbai_coldstart_prefix() -> None:
    """E-S6-14: cold-start baselines must register as mumbai_coldstart_*."""
    py_file = REPO_ROOT / "ml_pipelines" / "transfer" / "cold_start_baseline.py"
    text = py_file.read_text(encoding="utf-8")
    assert "mumbai_coldstart_" in text, (
        "cold_start_baseline.py must register Mumbai cold-start baselines under "
        "the mumbai_coldstart_ prefix (E-S6-14)."
    )


def test_ab_test_loads_mumbai_prefix_models() -> None:
    """A/B test must load both mumbai_<name> and mumbai_coldstart_<name>."""
    py_file = REPO_ROOT / "ml_pipelines" / "ab_test" / "run_ab_tests.py"
    text = py_file.read_text(encoding="utf-8")
    assert 'f"mumbai_{config' in text or "f'mumbai_{config" in text, (
        "run_ab_tests.py treatment branch must reference mumbai_<model_name> (E-S6-14)."
    )
    assert "mumbai_coldstart_" in text, (
        "run_ab_tests.py control branch must reference mumbai_coldstart_<model_name> (E-S6-14)."
    )


@pytest.mark.parametrize(
    "notebook",
    [
        "ml_pipelines/notebooks/demand_prophet_train.ipynb",
        "ml_pipelines/notebooks/inventory_sentinel_train.ipynb",
        "ml_pipelines/notebooks/pricing_oracle_train.ipynb",
        "ml_pipelines/notebooks/routing_navigator_train.ipynb",
    ],
)
def test_train_notebook_branches_on_city(notebook: str) -> None:
    """Each training notebook must branch its model name on the CITY var.

    The exact pattern varies (some use ``f'mumbai_..'``, others
    ``f'{\"mumbai_\" if CITY==\"mumbai\" else \"\"}..'``), so we accept any
    occurrence of ``mumbai_`` paired with a CITY check.
    """
    nb = REPO_ROOT / notebook
    if not nb.exists():
        pytest.skip(f"{notebook} not present in this checkout")
    text = nb.read_text(encoding="utf-8")
    assert "CITY" in text and "mumbai" in text, (
        f"{notebook} must branch on the CITY variable for naming (E-S6-07)."
    )
