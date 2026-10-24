"""
Integration test for the one-command reproduction CLI (task 14.4).

Runs ``uplift.cli.main`` end-to-end, in-process, on the smallest seeded config that
exercises the real closed loop, and asserts the honesty contract of the reproduction
command (``make prove-uplift`` invokes ``python -m uplift.cli``):

* R7.2 / R7.7 — a successful run prints the headline uplift number co-located with its
  twin-fidelity report (KL divergence, confidence, and the "bounded by twin fidelity"
  statement), and returns success.
* R7.4 — the output states the applied, version-controlled noise tolerance
  (``NOISE_TOLERANCE_PP``, e.g. "<= 1.0 percentage point").
* R7.3 — the result artifact is written with a numeric ``headline_uplift`` (feeds the
  C60 gate); reproduction *stability* itself is covered by the Property 23 test (14.3).
* R7.8 — a missing required input (the metric contract) exits with a non-zero failure
  code (``EXIT_MISSING_INPUT``), names the missing input, and prints NO headline number.

Under Metric_Contract v2 (decision-quality-proof tasks 15.1, 15.5 and 29.4) the same run is
also held to what v2 changed: the printed headline is in objective units and sits beside
its interval and verdict (R7.14, R7.19), and the artifact parses as a v2
:class:`~uplift.harness.UpliftArtifact` that records its comparator -- for the canonical
five arms with no comparator flag, a pool of the four declared baselines (AD-16).

The run is kept cheap: 2 replicates, a 1-hour horizon, and ``--output`` pointed at a
``tmp_path`` so the real ``artifacts/uplift/result.json`` is never clobbered. The twin
emits verbose logs during the run; that is expected.

Validates: Requirements 7.2, 7.3, 7.4, 7.8
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from uplift.cli import CANONICAL_ARM_NAMES, EXIT_MISSING_INPUT, NOISE_TOLERANCE_PP, main
from uplift.harness import (
    ARTIFACT_SCHEMA_VERSION,
    DEFAULT_CONSENSUS_ARM,
    EXIT_SUCCESS,
    POOLED_COMPARATOR_PREFIX,
    UpliftArtifact,
    comparator_label,
)


# The smallest config that still runs the real closed loop fast: a couple of replicates
# over a single closed-loop step. Shared by the success-path tests below.
SMOKE_ARGV = ["--smoke", "--n", "2", "--duration-hours", "1", "--step-hours", "1"]


def _run_cli(argv: list[str], capsys) -> tuple[int, str, str]:
    """Invoke ``main(argv)`` in-process and return (exit_code, stdout, stderr)."""
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_reproduction_prints_headline_with_fidelity_and_tolerance(tmp_path, capsys):
    """R7.2/R7.7/R7.4: success prints the headline uplift + fidelity context + tolerance."""
    output = tmp_path / "result.json"

    code, out, _err = _run_cli(SMOKE_ARGV + ["--output", str(output)], capsys)

    # R7.2: at least one scenario completed for some arm => success exit.
    assert code == EXIT_SUCCESS

    # R7.7 / R7.2: the headline uplift number is printed, co-located with its fidelity
    # report — the KL-divergence line, the confidence annotation, and the fixed
    # "bounded by twin fidelity" statement all appear in the same output.
    assert "headline uplift:" in out
    assert "primary KPI:" in out
    assert "twin KL divergence:" in out
    assert "fidelity confidence:" in out
    assert "bounded by twin fidelity" in out

    # v2 (R7.14, R7.19): the headline is a cost difference in objective units, and it is
    # co-located with its interval, its verdict and the comparator it was measured against
    # -- for the canonical five with no comparator flag, a recorded pool (AD-16). The unit
    # is checked on the headline line itself: the tolerance disclosure names it too.
    headline_lines = [line for line in out.splitlines() if line.startswith("headline uplift:")]
    assert len(headline_lines) == 1, headline_lines
    assert "objective units" in headline_lines[0]
    assert f"comparator: {POOLED_COMPARATOR_PREFIX}" in headline_lines[0]
    assert "interval:" in out
    assert "verdict:" in out

    # R7.4: the applied version-controlled noise tolerance is stated.
    assert "applied noise tolerance:" in out
    assert f"<= {NOISE_TOLERANCE_PP:.1f} percentage point" in out

    # Provenance / honesty disclosures accompany the number (R7.5/R7.6).
    assert "synthetic seed-generated data only" in out
    assert "no external paid service" in out


def test_reproduction_writes_numeric_headline_artifact(tmp_path, capsys):
    """R7.3: the artifact for the C60 gate is written with a numeric headline_uplift."""
    output = tmp_path / "nested" / "result.json"

    code, out, _err = _run_cli(SMOKE_ARGV + ["--output", str(output)], capsys)

    assert code == EXIT_SUCCESS
    assert output.exists(), "CLI must persist the result artifact at --output"
    assert f"wrote result artifact: {output}" in out

    payload = json.loads(output.read_text(encoding="utf-8"))
    # The C60 uplift_truth gate reads a numeric headline_uplift.
    assert "headline_uplift" in payload
    assert isinstance(payload["headline_uplift"], (int, float))
    assert not isinstance(payload["headline_uplift"], bool)
    # The version-controlled tolerance is recorded alongside it.
    assert payload["noise_tolerance_pp"] == NOISE_TOLERANCE_PP
    # Fidelity context is co-located in the artifact too (R5.6).
    assert "fidelity" in payload
    assert "fidelity_bound_statement" in payload["fidelity"]

    # v2: the C60 gate reads this file through the model, not as raw JSON, so it must parse
    # as a valid v2 UpliftArtifact -- whose validators tie the headline to its interval and
    # re-derive the verdict. The canonical five arms with no comparator flag are recorded
    # with their declared roles and compared against a POOL of the four baselines, never an
    # implicit one (AD-16).
    artifact = UpliftArtifact.read(output)
    assert artifact.schema_version == ARTIFACT_SCHEMA_VERSION
    assert artifact.headline_uplift == payload["headline_uplift"]
    baselines = [name for name in CANONICAL_ARM_NAMES if name != DEFAULT_CONSENSUS_ARM]
    assert len(baselines) == len(CANONICAL_ARM_NAMES) - 1
    assert artifact.provenance.arm_roles == {
        DEFAULT_CONSENSUS_ARM: "consensus",
        **{name: "baseline" for name in baselines},
    }
    assert artifact.comparator == comparator_label(None, baselines)


def test_missing_contract_input_fails_named_with_no_headline(tmp_path, capsys):
    """R7.8: a missing required input exits failure, names it, prints no headline number."""
    missing = tmp_path / "does_not_exist_contract.yaml"
    assert not missing.exists()

    code, out, err = _run_cli(["--smoke", "--contract", str(missing)], capsys)

    # Non-zero failure, distinct EXIT_MISSING_INPUT (not the harness no-run code).
    assert code == EXIT_MISSING_INPUT
    assert code != EXIT_SUCCESS

    combined = out + err
    # The missing input is named: it is the metric contract, and its path is echoed.
    assert "metric contract" in combined
    assert str(missing) in combined

    # NO headline uplift number is produced (the rendered report is absent). The FAIL
    # message may contain the words "headline uplift", so we key off the rendered
    # report's distinctive tokens (the "headline uplift:" line and the KL line).
    assert "headline uplift:" not in combined
    assert "twin KL divergence:" not in combined


def test_makefile_prove_uplift_invokes_cli_module():
    """R7.1: the Makefile `prove-uplift` target invokes `python -m uplift.cli`."""
    makefile = Path(__file__).resolve().parents[2] / "Makefile"
    text = makefile.read_text(encoding="utf-8")
    assert "prove-uplift:" in text
    assert "python -m uplift.cli" in text
