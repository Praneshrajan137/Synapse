"""Property-based test that a bad metric contract fails first, with no headline emitted.

Feature: core-purpose-uplift, Property 22: Missing/malformed contract fails first,
printing and writing no headline

    *For any* missing or malformed metric contract, :func:`uplift.cli.main` returns
    :data:`~uplift.cli.EXIT_MISSING_INPUT`, prints no headline number to stdout, and
    writes no headline number to the artifact — and this contract failure takes priority
    over the no-completed-run failure.

The generator covers the whole "required input missing or malformed" surface
:func:`uplift.contract.load_contract` can reject: an absent path, an unreadable path (a
directory), an empty/comment-only file, unparseable YAML, a non-mapping top level, each
required key dropped in turn, an out-of-range or non-numeric ``alpha``, an unknown
primary KPI, an unknown improvement direction, a wrong ``effect_size`` /
``decision_rule``, and a non-numeric or incomplete ``mde``.

Priority over the no-completed-run failure is exercised directly: the arm suite is
stubbed with a callable that raises if invoked and the scenario suite is stubbed to be
empty (the configuration that would otherwise yield ``EXIT_NO_COMPLETED_RUN``). A pass
therefore proves the contract check short-circuits *before* any run is assembled, and
that the returned status is the missing-input status rather than the no-completed-run
status.

Kept fast for the same reason: the real consensus arm (in-process eight-agent + twin
network, slow Tier-4 twin verification) is never assembled, no twin is built, no socket
is opened, and every artifact path lives under a pytest temp dir, so the repo's
``artifacts/uplift/result.json`` is never touched.

Validates: Requirements 7.3, 7.4
"""
from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from uplift import cli
from uplift.contract import MetricContractError, load_contract
from uplift.harness import EXIT_NO_COMPLETED_RUN

#: The well-formed pre-registered contract every malformation is derived from, so each
#: generated example differs from a *loadable* contract in exactly the intended way.
_VALID_CONTRACT: dict[str, Any] = {
    "version": 1,
    "primary_kpis": {"fill_rate": "higher"},
    "effect_size": "cohens_d+rel_pct",
    "significance_test": "mann_whitney_u",
    "alpha": 0.05,
    "mde": {"fill_rate": 0.2},
    "decision_rule": "significant_and_favorable_and_meets_mde",
}

_REQUIRED_KEYS = (
    "primary_kpis",
    "effect_size",
    "significance_test",
    "alpha",
    "mde",
    "decision_rule",
)

_KINDS = (
    "absent_path",
    "unreadable_path",
    "empty_file",
    "unparseable_yaml",
    "non_mapping",
    "missing_required_key",
    "bad_alpha",
    "unknown_kpi",
    "bad_direction",
    "bad_effect_size",
    "bad_decision_rule",
    "bad_mde",
)


@st.composite
def _malformed_contracts(draw: st.DrawFn) -> tuple[str, str | None]:
    """A ``(kind, file_text)`` pair describing a missing or malformed contract.

    ``file_text is None`` means the file must not be created as a readable file at all
    (``absent_path``) or must be created as an unreadable path (``unreadable_path``).
    """
    kind = draw(st.sampled_from(_KINDS))

    if kind in ("absent_path", "unreadable_path"):
        return kind, None

    if kind == "empty_file":
        return kind, draw(st.sampled_from(["", "\n", "   \n", "# only a comment\n"]))

    if kind == "unparseable_yaml":
        return kind, draw(
            st.sampled_from(
                [
                    "primary_kpis: [unbalanced: {",
                    "alpha: 0.05\n  mde: {\n",
                    "*anchor-without-target\n",
                    "a: b\n- c\n",
                ]
            )
        )

    if kind == "non_mapping":
        return kind, draw(
            st.sampled_from(["- just\n- a\n- list\n", "42\n", "'a bare string'\n", "true\n"])
        )

    data = dict(_VALID_CONTRACT)

    if kind == "missing_required_key":
        data.pop(draw(st.sampled_from(_REQUIRED_KEYS)))
    elif kind == "bad_alpha":
        data["alpha"] = draw(
            st.one_of(
                st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False),
                st.floats(min_value=-1e6, max_value=0.0, allow_nan=False, allow_infinity=False),
                st.sampled_from(["five percent", True, None, [0.05]]),
            )
        )
    elif kind == "unknown_kpi":
        name = draw(st.sampled_from(["fillrate", "profit", "revenue", "made_up_kpi", ""]))
        data["primary_kpis"] = {name: "higher"}
        data["mde"] = {name: 0.2}
    elif kind == "bad_direction":
        data["primary_kpis"] = {
            "fill_rate": draw(st.sampled_from(["sideways", "HIGHER", "", 1, None]))
        }
    elif kind == "bad_effect_size":
        data["effect_size"] = draw(
            st.sampled_from(["cohens_d", "rel_pct", "hedges_g", "", None])
        )
    elif kind == "bad_decision_rule":
        data["decision_rule"] = draw(
            st.sampled_from(["favorable_only", "significant_and_favorable", "", None])
        )
    else:  # bad_mde — non-numeric value, or no value for the declared primary KPI
        data["mde"] = draw(
            st.sampled_from(
                [
                    {"fill_rate": "large"},
                    {"fill_rate": None},
                    {"fill_rate": True},
                    {"stockout_rate": 0.2},
                    {},
                ]
            )
        )

    return kind, yaml.safe_dump(data, sort_keys=True)


def _materialize(kind: str, text: str | None, work: Path) -> Path:
    """Create the contract path described by ``(kind, text)`` under ``work``."""
    path = work / "metric_contract.yaml"
    if kind == "absent_path":
        return path  # deliberately never created
    if kind == "unreadable_path":
        path.mkdir()  # a directory is not a readable contract file
        return path
    assert text is not None
    path.write_text(text, encoding="utf-8")
    return path


@settings(max_examples=120, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(case=_malformed_contracts())
def test_bad_contract_fails_before_any_headline(
    case: tuple[str, str | None], tmp_path_factory: pytest.TempPathFactory
) -> None:
    """A missing/malformed contract exits EXIT_MISSING_INPUT with no headline anywhere.

    **Validates: Requirements 7.3, 7.4**
    """
    kind, text = case
    work = tmp_path_factory.mktemp("contract-failure-priority")
    contract_path = _materialize(kind, text, work)
    output = work / "artifacts" / "uplift" / "result.json"

    # Precondition: the generated contract really is unloadable, so the CLI is being
    # exercised on the missing/malformed-input path (and not on a valid contract).
    with pytest.raises(MetricContractError):
        load_contract(contract_path)

    assembly_calls: list[str] = []

    def _never_assemble(*_args: Any, **_kwargs: Any) -> Any:
        """Any run assembly is a contract-priority violation (and would be slow)."""
        assembly_calls.append("called")
        raise AssertionError("a run was assembled despite an invalid metric contract")

    stdout, stderr = io.StringIO(), io.StringIO()
    with (
        # Stub the arm suite so the real consensus arm (slow Tier-4 twin verification)
        # can never be assembled, and an empty scenario suite so a run that did happen
        # would complete nothing — i.e. the EXIT_NO_COMPLETED_RUN configuration.
        mock.patch.object(cli, "build_arms", _never_assemble),
        mock.patch.object(cli, "build_consensus_arm", _never_assemble),
        mock.patch.object(cli, "adversarial_suite", lambda *a, **k: ()),
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        code = cli.main(
            ["--smoke", "--contract", str(contract_path), "--output", str(output)]
        )

    out, err = stdout.getvalue(), stderr.getvalue()

    # 1. The contract failure is the missing-input failure (R7.3) ...
    assert code == cli.EXIT_MISSING_INPUT
    # ... and it takes priority over the no-completed-run failure (R7.4): the exit status
    # is the missing-input one, and no run was ever assembled to fail for lack of runs.
    assert code != EXIT_NO_COMPLETED_RUN
    assert assembly_calls == []

    # 2. No headline number is printed to stdout — no number is emitted there at all.
    assert not any(ch.isdigit() for ch in out)
    assert "headline" not in out.lower()

    # 3. No headline number is written to the artifact: the output file does not exist,
    #    and nothing anywhere under the run directory carries a headline value.
    assert not output.exists()
    for stray in work.rglob("*"):
        if stray.is_file():
            assert "headline_uplift" not in stray.read_text(encoding="utf-8", errors="ignore")

    # 4. The failure names the missing/malformed input so it is diagnosable (R7.3).
    assert str(contract_path) in err
    assert "metric contract" in err.lower()
