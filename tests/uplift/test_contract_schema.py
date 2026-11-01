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

Carried to Metric_Contract v2 (decision-quality-proof task 29.4, decision 2=a). The reader
accepts version 2 ONLY, so the well-formed contract every case mutates is a v2 contract, and
the version-1 contract this file used to load is now a refusal case: refused, not translated.
Every refusal above still applies, each pinned to the clause that refuses it, and v2 adds four:

- a version other than 2, an absent ``version`` included (it is a required key now);
- a primary KPI set other than ``{objective: lower}``;
- an ``mde`` that states a number instead of naming ``materiality_margin`` -- the committed
  value written as a number included, because it would be a second home for the margin;
- a significance test or decision rule v2 does not declare, the v1 names included.

A contract built in memory is refused the same way, because construction itself validates.

Validates: Requirements 3.1, 3.3, 3.4, 3.10
"""
from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import pytest

from digital_twin.simulation.policy import materiality_margin
from uplift.contract import (
    CONTRACT_VERSION,
    DEFAULT_CONTRACT_PATH,
    MetricContract,
    MetricContractError,
    load_contract,
)
from uplift.interfaces import Direction
from uplift.interval import METHOD, resamples_for


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
# A valid contract mapping rendered as YAML text; individual tests mutate one field
# to construct each malformed case, proving each violation is caught in isolation.
_VALID_CONTRACT_YAML = """\
version: 2
primary_kpis:
  objective: lower
effect_size: mean_paired_difference
significance_test: paired_percentile_bootstrap
alpha: 0.05
mde:
  objective: materiality_margin
decision_rule: interval_position_against_materiality_margin
"""

# The two mapping-valued blocks of the valid contract, replaced whole by the v2 cases.
_PRIMARY_BLOCK = "primary_kpis:\n  objective: lower\n"
_MDE_BLOCK = "mde:\n  objective: materiality_margin\n"

# The version-1 contract this reader used to accept: fill_rate, Cohen's d, Mann-Whitney U.
_VERSION_1_CONTRACT_YAML = """\
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

#: The committed materiality margin, read from its one canonical home and never restated here.
_COMMITTED_MARGIN = materiality_margin()


def _write_contract(tmp_path: Path, text: str, name: str = "contract.yaml") -> Path:
    """Write ``text`` to a temp contract file and return its path."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Valid contract — the real artifact loads with the expected fields (R3.1/3.3/3.4)
# ---------------------------------------------------------------------------
def test_real_metric_contract_loads_successfully() -> None:
    """The version-controlled ``metric_contract.yaml`` loads into a v2 MetricContract."""
    contract = load_contract()  # defaults to DEFAULT_CONTRACT_PATH

    assert isinstance(contract, MetricContract)
    # The sole primary KPI is the committed objective, a cost: lower is better (R3.1, R7.19)
    assert contract.primary_kpis == {"objective": Direction.LOWER_IS_BETTER}
    assert contract.objective_kpi == "objective"
    # Effect-size measure: the mean seed-paired objective difference (R3.2)
    assert contract.effect_size == "mean_paired_difference"
    # The interval estimator uplift.interval implements, at alpha in (0, 1) (R3.3)
    assert contract.significance_test == METHOD == "paired_percentile_bootstrap"
    assert contract.alpha == pytest.approx(0.05)
    assert 0.0 < contract.alpha < 1.0
    assert contract.resamples == resamples_for(contract.alpha)
    # The MDE is the committed materiality margin resolved from policy, never a number
    # written in the contract (R3.4)
    assert _COMMITTED_MARGIN is not None
    assert _COMMITTED_MARGIN > 0.0
    assert contract.mde == {"objective": _COMMITTED_MARGIN}
    assert contract.materiality_margin == _COMMITTED_MARGIN
    # Decision rule (R3.5) + version
    assert contract.decision_rule == "interval_position_against_materiality_margin"
    assert contract.version == CONTRACT_VERSION == 2


def test_default_contract_path_points_at_the_committed_artifact() -> None:
    """The default path resolves to the committed ``uplift/metric_contract.yaml``."""
    assert DEFAULT_CONTRACT_PATH.name == "metric_contract.yaml"
    assert DEFAULT_CONTRACT_PATH.exists()


def test_valid_contract_from_tmp_path_loads(tmp_path: Path) -> None:
    """A well-formed v2 contract written to tmp_path loads without error."""
    path = _write_contract(tmp_path, _VALID_CONTRACT_YAML)
    contract = load_contract(path)
    assert contract.primary_kpis == {"objective": Direction.LOWER_IS_BETTER}
    assert contract.mde == {"objective": _COMMITTED_MARGIN}


def test_load_contract_accepts_str_path(tmp_path: Path) -> None:
    """``load_contract`` accepts a string path as well as a ``Path`` (R3.6 loader)."""
    path = _write_contract(tmp_path, _VALID_CONTRACT_YAML)
    contract = load_contract(str(path))
    assert isinstance(contract, MetricContract)


def test_loaded_contract_is_immutable(tmp_path: Path) -> None:
    """The loaded contract is a frozen dataclass and cannot be mutated in place."""
    path = _write_contract(tmp_path, _VALID_CONTRACT_YAML)
    contract = load_contract(path)
    with pytest.raises(dataclasses.FrozenInstanceError):
        contract.alpha = 0.1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Missing contract — raises MetricContractError (R3.10)
# ---------------------------------------------------------------------------
def test_missing_contract_file_raises(tmp_path: Path) -> None:
    """A non-existent contract path raises MetricContractError (R3.10)."""
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(MetricContractError, match="not found"):
        load_contract(missing)


# ---------------------------------------------------------------------------
# Malformed contracts — each raises MetricContractError (R3.10)
# ---------------------------------------------------------------------------
def test_invalid_yaml_raises(tmp_path: Path) -> None:
    """Unparseable YAML raises MetricContractError (R3.10)."""
    path = _write_contract(tmp_path, "primary_kpis: [unbalanced: {")
    with pytest.raises(MetricContractError, match="not valid YAML"):
        load_contract(path)


def test_empty_file_raises(tmp_path: Path) -> None:
    """An empty contract file (parses to None) raises MetricContractError (R3.10)."""
    path = _write_contract(tmp_path, "")
    with pytest.raises(MetricContractError, match="is empty"):
        load_contract(path)


def test_non_mapping_top_level_raises(tmp_path: Path) -> None:
    """A contract whose top level is not a mapping raises MetricContractError."""
    path = _write_contract(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(MetricContractError, match="must be a mapping"):
        load_contract(path)


@pytest.mark.parametrize(
    "missing_key",
    [
        "version",
        "primary_kpis",
        "effect_size",
        "significance_test",
        "alpha",
        "mde",
        "decision_rule",
    ],
)
def test_missing_required_key_raises(tmp_path: Path, missing_key: str) -> None:
    """Dropping any required top-level key raises MetricContractError (R3.10).

    ``version`` is required under v2: an absent version cannot be assumed to be 2, because
    assuming it would be a default.
    """
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
    with pytest.raises(MetricContractError, match="missing required keys") as refused:
        load_contract(path)
    assert repr(missing_key) in str(refused.value)


def test_empty_primary_kpis_raises(tmp_path: Path) -> None:
    """An empty ``primary_kpis`` mapping raises MetricContractError (R3.1)."""
    text = _VALID_CONTRACT_YAML.replace(_PRIMARY_BLOCK, "primary_kpis: {}\n")
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError, match="primary_kpis must be a non-empty mapping"):
        load_contract(path)


def test_unknown_kpi_name_raises(tmp_path: Path) -> None:
    """A ``primary_kpis`` key that is not a KpiVector field raises (R3.1)."""
    text = _VALID_CONTRACT_YAML.replace("objective: lower", "not_a_kpi: lower")
    # keep the MDE keyed to the (now unknown) primary KPI so the failure is the KPI name
    text = text.replace("  objective: materiality_margin", "  not_a_kpi: materiality_margin")
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError, match="references unknown KPI"):
        load_contract(path)


def test_invalid_direction_raises(tmp_path: Path) -> None:
    """An unrecognized improvement direction raises MetricContractError (R3.1)."""
    text = _VALID_CONTRACT_YAML.replace("objective: lower", "objective: sideways")
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError, match="direction must be one of"):
        load_contract(path)


@pytest.mark.parametrize(
    "bad_alpha", ["0.0", "1.0", "-0.1", "1.5", "'not-a-number'", ".nan", "true"]
)
def test_alpha_out_of_open_interval_raises(tmp_path: Path, bad_alpha: str) -> None:
    """``alpha`` outside the open interval (0, 1), non-finite or non-numeric raises (R3.3)."""
    text = _VALID_CONTRACT_YAML.replace("alpha: 0.05", f"alpha: {bad_alpha}")
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError, match="alpha must be"):
        load_contract(path)


def test_non_numeric_mde_raises(tmp_path: Path) -> None:
    """A non-numeric MDE value other than the margin reference raises (R3.4)."""
    text = _VALID_CONTRACT_YAML.replace(
        "  objective: materiality_margin", "  objective: 'big'"
    )
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError, match="must be the reference"):
        load_contract(path)


def test_empty_mde_raises(tmp_path: Path) -> None:
    """An empty ``mde`` mapping raises MetricContractError (R3.4)."""
    text = _VALID_CONTRACT_YAML.replace(_MDE_BLOCK, "mde: {}\n")
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError, match="mde must be a non-empty mapping"):
        load_contract(path)


def test_missing_mde_for_primary_kpi_raises(tmp_path: Path) -> None:
    """A primary KPI without a declared MDE raises MetricContractError (R3.4)."""
    # Declare an MDE for a different (valid) KPI than the declared primary KPI.
    text = _VALID_CONTRACT_YAML.replace(
        "  objective: materiality_margin", "  margin: materiality_margin"
    )
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError, match="mde must declare exactly the primary KPI"):
        load_contract(path)


@pytest.mark.parametrize("bad_effect_size", ["glass_delta", "cohens_d+rel_pct"])
def test_unsupported_effect_size_raises(tmp_path: Path, bad_effect_size: str) -> None:
    """An unsupported ``effect_size`` measure raises MetricContractError (R3.2).

    ``cohens_d+rel_pct`` is the version-1 measure: v2 declares the mean paired difference.
    """
    text = _VALID_CONTRACT_YAML.replace(
        "effect_size: mean_paired_difference", f"effect_size: {bad_effect_size}"
    )
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError, match="effect_size must be"):
        load_contract(path)


@pytest.mark.parametrize(
    "bad_rule", ["whoever_feels_luckier", "significant_and_favorable_and_meets_mde"]
)
def test_unsupported_decision_rule_raises(tmp_path: Path, bad_rule: str) -> None:
    """An unsupported ``decision_rule`` raises MetricContractError (R3.5).

    ``significant_and_favorable_and_meets_mde`` is the version-1 rule: v2 declares the
    four-valued interval rule against the materiality margin.
    """
    text = _VALID_CONTRACT_YAML.replace(
        "decision_rule: interval_position_against_materiality_margin",
        f"decision_rule: {bad_rule}",
    )
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError, match="decision_rule must be"):
        load_contract(path)


def test_empty_significance_test_raises(tmp_path: Path) -> None:
    """An empty ``significance_test`` string raises MetricContractError (R3.3)."""
    text = _VALID_CONTRACT_YAML.replace(
        "significance_test: paired_percentile_bootstrap", "significance_test: '   '"
    )
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError, match="significance_test must be a non-empty string"):
        load_contract(path)


# ---------------------------------------------------------------------------
# Version 2 refusals (decision-quality-proof task 29.4)
# ---------------------------------------------------------------------------
def test_a_version_1_contract_is_refused_not_translated(tmp_path: Path) -> None:
    """The v1 contract is refused outright: its Cohen's-d MDE is never read as a margin."""
    path = _write_contract(tmp_path, _VERSION_1_CONTRACT_YAML)
    with pytest.raises(MetricContractError):
        load_contract(path)


@pytest.mark.parametrize("bad_version", ["1", "3", "0", "'2'", "2.0", "true", "null"])
def test_a_version_other_than_2_is_refused(tmp_path: Path, bad_version: str) -> None:
    """Only the integer 2 is a version this reader applies; anything else is refused."""
    text = _VALID_CONTRACT_YAML.replace("version: 2", f"version: {bad_version}")
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError, match="is not supported|must be an integer"):
        load_contract(path)


@pytest.mark.parametrize(
    ("primary_block", "mde_block"),
    [
        pytest.param(
            "primary_kpis:\n  fill_rate: higher\n",
            "mde:\n  fill_rate: materiality_margin\n",
            id="the-v1-primary-kpi",
        ),
        pytest.param(
            "primary_kpis:\n  objective: higher\n",
            _MDE_BLOCK,
            id="the-objective-as-higher-is-better",
        ),
        pytest.param(
            "primary_kpis:\n  objective: lower\n  fill_rate: higher\n",
            "mde:\n  objective: materiality_margin\n  fill_rate: materiality_margin\n",
            id="the-objective-beside-a-second-primary-kpi",
        ),
        pytest.param(
            "primary_kpis:\n  stockout_rate: lower\n",
            "mde:\n  stockout_rate: materiality_margin\n",
            id="a-secondary-cost-in-its-place",
        ),
    ],
)
def test_a_primary_kpi_set_other_than_the_objective_is_refused(
    tmp_path: Path, primary_block: str, mde_block: str
) -> None:
    """The objective, lower is better, is the sole primary KPI; any other set is refused."""
    text = _VALID_CONTRACT_YAML.replace(_PRIMARY_BLOCK, primary_block).replace(
        _MDE_BLOCK, mde_block
    )
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError, match="primary_kpis must be exactly"):
        load_contract(path)


@pytest.mark.parametrize(
    "number",
    [pytest.param(str(_COMMITTED_MARGIN), id="the-committed-value"), "0.2", "1"],
)
def test_an_mde_that_states_a_number_is_refused(tmp_path: Path, number: str) -> None:
    """The MDE must NAME the committed margin; a number, even the right one, is refused."""
    text = _VALID_CONTRACT_YAML.replace(
        "  objective: materiality_margin", f"  objective: {number}"
    )
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError, match="must be the reference"):
        load_contract(path)


@pytest.mark.parametrize("bad_test", ["mann_whitney_u", "welch_t_test"])
def test_an_unsupported_significance_test_is_refused(tmp_path: Path, bad_test: str) -> None:
    """Only the estimator ``uplift.interval`` implements may be declared (v1's rank test too)."""
    text = _VALID_CONTRACT_YAML.replace(
        "significance_test: paired_percentile_bootstrap", f"significance_test: {bad_test}"
    )
    path = _write_contract(tmp_path, text)
    with pytest.raises(MetricContractError, match=f"significance_test must be '{METHOD}'"):
        load_contract(path)


@pytest.mark.parametrize(
    ("change", "refused_by"),
    [
        pytest.param({"version": 1}, "is not supported", id="version-1"),
        pytest.param(
            {"primary_kpis": {"fill_rate": Direction.HIGHER_IS_BETTER}},
            "primary_kpis must be exactly",
            id="the-v1-primary-kpi",
        ),
        pytest.param(
            {"primary_kpis": {"objective": Direction.HIGHER_IS_BETTER}},
            "primary_kpis must be exactly",
            id="a-flipped-direction",
        ),
        pytest.param(
            {"effect_size": "cohens_d+rel_pct"}, "effect_size must be", id="the-v1-effect-size"
        ),
        pytest.param(
            {"significance_test": "mann_whitney_u"},
            "significance_test must be",
            id="the-v1-significance-test",
        ),
        pytest.param(
            {"decision_rule": "significant_and_favorable_and_meets_mde"},
            "decision_rule must be",
            id="the-v1-decision-rule",
        ),
        pytest.param({"alpha": 0.0}, "alpha must be in the open interval", id="alpha-zero"),
        pytest.param({"alpha": math.nan}, "alpha must be in the open interval", id="alpha-nan"),
        pytest.param(
            {"mde": {"objective": 0.0}}, "strictly positive finite number", id="a-zero-margin"
        ),
        pytest.param(
            {"mde": {"objective": -0.4}},
            "strictly positive finite number",
            id="a-negative-margin",
        ),
        pytest.param(
            {"mde": {"objective": math.inf}},
            "strictly positive finite number",
            id="an-infinite-margin",
        ),
        pytest.param(
            {"mde": {"fill_rate": 0.4}},
            "mde must declare exactly the primary KPI",
            id="a-margin-for-another-kpi",
        ),
    ],
)
def test_a_contract_built_in_memory_is_refused_unless_it_is_admissible(
    change: dict[str, object], refused_by: str
) -> None:
    """Construction itself validates, so ``dataclasses.replace`` cannot build a v1 contract.

    The other contract tests build their variants this way, which is why a variant may move
    only ``alpha`` or the margin -- and why a margin of ``0.0``, the v1 variant meaning "any
    effect qualifies", is now a refusal: against it every gain is material by construction.
    """
    with pytest.raises(MetricContractError, match=refused_by):
        dataclasses.replace(load_contract(), **change)


def test_an_in_memory_contract_may_move_its_alpha_and_its_margin() -> None:
    """The two inputs a variant may move are accepted, so the refusals above are not blanket."""
    committed = load_contract()
    margin = 4.0 * committed.materiality_margin

    variant = dataclasses.replace(committed, alpha=0.2, mde={"objective": margin})

    assert variant.alpha == 0.2
    assert variant.materiality_margin == margin
    assert variant.resamples == resamples_for(0.2)
    assert variant.primary_kpis == committed.primary_kpis
