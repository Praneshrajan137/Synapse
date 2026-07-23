"""Unit tests for the pre-registered metric-contract loader/validator.

Feature: decision-integrity-uplift-proof (task 5.2)

Covers the schema and malformed-contract handling of ``uplift.contract``:

- The real, version-controlled ``uplift/metric_contract.yaml`` loads successfully
  into a well-formed :class:`MetricContract` with the expected declared fields
  (Requirements 3.1, 3.3, 3.4).
- A missing contract file raises :class:`MetricContractError` (Requirement 3.10).
- Every malformed contract — invalid YAML, empty file, empty/unknown/non-KPI
  ``primary_kpis``, ``alpha`` outside ``(0, 1)``, non-numeric MDE, an MDE missing for
  a declared primary KPI, an unsupported ``effect_size`` / ``decision_rule``, and any
  missing required key — raises :class:`MetricContractError`, so the harness/CLI exits
  with a failure status and produces no uplift outcome (Requirement 3.10).

Validates: Requirements 3.1, 3.3, 3.4, 3.10
"""
from __future__ import annotations

from pathlib import Path

import pytest

from uplift.contract import (
    DEFAULT_CONTRACT_PATH,
    MetricContract,
    MetricContractError,
    load_contract,
)
from uplift.interfaces import Direction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
# A valid contract mapping rendered as YAML text; individual tests mutate one field
# to construct each malformed case, proving each violation is caught in isolation.
_VALID_CONTRACT_YAML = """\
version: 1
primary_kpis:
  fill_rate: higher
effect_size: cohens_d+rel_pct
significance_test: mann_whitney_u
alpha: 0.05
mde:
  fill_rate: 0.2
decision_rule: significant_and_favorable_and_meets_mde
"""


def _write_contract(tmp_path: Path, text: str, name: str = "contract.yaml") -> Path:
    """Write ``text`` to a temp contract file and return its path."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Valid contract — the real artifact loads with the expected fields (R3.1/3.3/3.4)
# ---------------------------------------------------------------------------
def test_real_metric_contract_loads_successfully() -> None:
    """The version-controlled ``metric_contract.yaml`` loads into a MetricContract."""
    contract = load_contract()  # defaults to DEFAULT_CONTRACT_PATH

    assert isinstance(contract, MetricContract)
    # Primary KPI(s) + direction (R3.1)
    assert contract.primary_kpis == {"fill_rate": Direction.HIGHER_IS_BETTER}
    # Effect-size measure (R3.2)
    assert contract.effect_size == "cohens_d+rel_pct"
    # Significance test + alpha in (0, 1) (R3.3)
    assert contract.significance_test == "mann_whitney_u"
    assert contract.alpha == pytest.approx(0.05)
    assert 0.0 < contract.alpha < 1.0
    # Per-primary-KPI numeric MDE (R3.4)
    assert contract.mde == {"fill_rate": pytest.approx(0.2)}
    # Decision rule (R3.5) + version
    assert contract.decision_rule == "significant_and_favorable_and_meets_mde"
    assert contract.version == 1


def test_default_contract_path_points_at_the_committed_artifact() -> None:
    """The default path resolves to the committed ``uplift/metric_contract.yaml``."""
    assert DEFAULT_CONTRACT_PATH.name == "metric_contract.yaml"
    assert DEFAULT_CONTRACT_PATH.exists()


def test_valid_contract_from_tmp_path_loads(tmp_path: Path) -> None:
    """A well-formed contract written to tmp_path loads without error."""
    path = _write_contract(tmp_path, _VALID_CONTRACT_YAML)
    contract = load_contract(path)
    assert contract.primary_kpis == {"fill_rate": Direction.HIGHER_IS_BETTER}
    assert contract.mde == {"fill_rate": pytest.approx(0.2)}


def test_load_contract_accepts_str_path(tmp_path: Path) -> None:
    """``load_contract`` accepts a string path as well as a ``Path`` (R3.6 loader)."""
    path = _write_contract(tmp_path, _VALID_CONTRACT_YAML)
    contract = load_contract(str(path))
    assert isinstance(contract, MetricContract)


def test_loaded_contract_is_immutable(tmp_path: Path) -> None:
    """The loaded contract is a frozen dataclass and cannot be mutated in place."""
    path = _write_contract(tmp_path, _VALID_CONTRACT_YAML)
    contract = load_contract(path)
    with pytest.raises(Exception):  # FrozenInstanceError (a dataclasses subclass)
        contract.alpha = 0.1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Missing contract — raises MetricContractError (R3.10)
# ---------------------------------------------------------------------------
def test_missing_contract_file_raises(tmp_path: Path) -> None:
    """A non-existent contract path raises MetricContractError (R3.10)."""
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(MetricContractError):
        load_contract(missing)


# ---------------------------------------------------------------------------
# Malformed contracts — each raises MetricContractError (R3.10)
# ---------------------------------------------------------------------------
def test_invalid_yaml_raises(tmp_path: Path) -> None:
    """Unparseable YAML raises MetricContractError (R3.10)."""
    path = _write_contract(tmp_path, "primary_kpis: [unbalanced: {")
    with pytest.raises(MetricContractError):
        load_contract(path)


def test_empty_file_raises(tmp_path: Path) -> None:
    """An empty contract file (parses to None) raises MetricContractError (R3.10)."""
    path = _write_contract(tmp_path, "")
    with pytest.raises(MetricContractError):
        load_contract(path)


def test_non_mapping_top_level_raises(tmp_path: Path) -> None:
    """A contract whose top level is not a mapping raises MetricContractError."""
    path = _write_contract(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(MetricContractError):
        load_contract(path)


@pytest.mark.parametrize(
    "missing_key",
    ["primary_kpis", "effect_size", "significance_test", "alpha", "mde", "decision_rule"],
)
def test_missing_required_key_raises(tmp_path: Path, missing_key: str) -> None:
    """Dropping any required top-level key raises MetricContractError (R3.10)."""
    lines = _VALID_CONTRACT_YAML.splitlines(keepends=True)
    # Rebuild the YAML omitting the block that starts with the missing key. For the
    # two mapping-valued keys (primary_kpis, mde) also drop their indented child line.
    kept: list[str] = []
    skipping = False
    for line in lines:
        stripped = line.lstrip()
        is_top_level = line == stripped  # no leading whitespace
        if is_top_level and stripped.startswith(f"{missing_key}:"):
            skipping = True
            continue
        if skipping:
            # Continue skipping indented child lines belonging to the removed key.
            if not is_top_level and stripped:
                continue
            skipping = False
        kept.append(line)
    path = _write_contract(tmp_path, "".join(kept))
    with pytest.raises(MetricContractError):
        load_contract(path)


def test_empty_primary_kpis_raises(tmp_path: Path) -> None:
    """An empty ``primary_kpis`` mapping raises MetricContractError (R3.1)."""
    text = _VALID_CONTRACT_YAML.replace(
        "primary_kpis:\n  fill_rate: higher\n", "primary_kpis: {}\n"
    )
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError):
        load_contract(path)


def test_unknown_kpi_name_raises(tmp_path: Path) -> None:
    """A ``primary_kpis`` key that is not a KpiVector field raises (R3.1)."""
    text = _VALID_CONTRACT_YAML.replace("fill_rate: higher", "not_a_kpi: higher")
    # keep the MDE keyed to the (now unknown) primary KPI so the failure is the KPI name
    text = text.replace("  fill_rate: 0.2", "  not_a_kpi: 0.2")
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError):
        load_contract(path)


def test_invalid_direction_raises(tmp_path: Path) -> None:
    """An unrecognized improvement direction raises MetricContractError (R3.1)."""
    text = _VALID_CONTRACT_YAML.replace("fill_rate: higher", "fill_rate: sideways")
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError):
        load_contract(path)


@pytest.mark.parametrize("bad_alpha", ["0.0", "1.0", "-0.1", "1.5", "'not-a-number'"])
def test_alpha_out_of_open_interval_raises(tmp_path: Path, bad_alpha: str) -> None:
    """``alpha`` outside the open interval (0, 1) or non-numeric raises (R3.3)."""
    text = _VALID_CONTRACT_YAML.replace("alpha: 0.05", f"alpha: {bad_alpha}")
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError):
        load_contract(path)


def test_non_numeric_mde_raises(tmp_path: Path) -> None:
    """A non-numeric MDE value raises MetricContractError (R3.4)."""
    text = _VALID_CONTRACT_YAML.replace("  fill_rate: 0.2", "  fill_rate: 'big'")
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError):
        load_contract(path)


def test_empty_mde_raises(tmp_path: Path) -> None:
    """An empty ``mde`` mapping raises MetricContractError (R3.4)."""
    text = _VALID_CONTRACT_YAML.replace("mde:\n  fill_rate: 0.2\n", "mde: {}\n")
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError):
        load_contract(path)


def test_missing_mde_for_primary_kpi_raises(tmp_path: Path) -> None:
    """A primary KPI without a declared MDE raises MetricContractError (R3.4)."""
    # Declare an MDE for a different (valid) KPI than the declared primary KPI.
    text = _VALID_CONTRACT_YAML.replace("  fill_rate: 0.2", "  margin: 0.2")
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError):
        load_contract(path)


def test_unsupported_effect_size_raises(tmp_path: Path) -> None:
    """An unsupported ``effect_size`` measure raises MetricContractError (R3.2)."""
    text = _VALID_CONTRACT_YAML.replace(
        "effect_size: cohens_d+rel_pct", "effect_size: glass_delta"
    )
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError):
        load_contract(path)


def test_unsupported_decision_rule_raises(tmp_path: Path) -> None:
    """An unsupported ``decision_rule`` raises MetricContractError (R3.5)."""
    text = _VALID_CONTRACT_YAML.replace(
        "decision_rule: significant_and_favorable_and_meets_mde",
        "decision_rule: whoever_feels_luckier",
    )
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError):
        load_contract(path)


def test_empty_significance_test_raises(tmp_path: Path) -> None:
    """An empty ``significance_test`` string raises MetricContractError (R3.3)."""
    text = _VALID_CONTRACT_YAML.replace(
        "significance_test: mann_whitney_u", "significance_test: '   '"
    )
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError):
        load_contract(path)
