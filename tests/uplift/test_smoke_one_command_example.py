"""Example test for the ``--smoke`` one-command path (task 2.5).

Feature: core-purpose-uplift, Task 2.5 — after the CLI wiring (task 2.1), running the
one command must actually *measure the product*: ``python -m uplift.cli --smoke`` has to
stand up the real assembled consensus arm and record at least one **completed**
(non-failed) consensus run for at least one adversarial scenario (R1.4), and it has to
write the result artifact at the path the C60 ``uplift_truth`` gate reads (R7.1).

What is real here and what is not:

* Real: the eight real agent ``handle_request`` handlers, the real
  :class:`~orchestrator.consensus.protocol.ConsensusProtocol` (real tier router,
  guardrails, hash-chained audit logger, HITL escalation, context builder, meta-RL),
  the real in-process A2A transport, the real seeded twin the harness drives, the real
  contract-based result assembly, and the real artifact writer. Nothing about the
  measurement is fabricated and no socket is opened.
* Substituted: only the **twin A2A handler** used by Tier-4 verification, via the
  documented :func:`~uplift.consensus_arm.build_consensus_arm` ``twin_handler`` seam.
  The default twin handler honours INV-TW-002 and runs 1000 Monte-Carlo scenarios per
  shocked decision (~20s each), which makes the full smoke path a ~90s test. Rather than
  cheapen that verification (which would weaken the INV-TW-002 floor and fabricate a
  "verification" that never ran), this test injects a twin handler that reports itself
  **unavailable**, so the protocol takes its existing honest ``twin_unavailable``
  degradation path (I-7) and the decision still comes from real agent proposals.

The artifact is redirected to ``tmp_path`` so the repo's ``artifacts/uplift/result.json``
is never clobbered; the default path constant is asserted separately to be exactly the
C60-read path. Marked ``slow`` because it constructs the whole eight-agent network and
runs the real closed loop.

_Requirements: 1.4, 7.1_
"""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

import uplift.cli as cli
from uplift.consensus_arm import ConsensusArm, build_consensus_arm
from uplift.harness import DEFAULT_CONSENSUS_ARM, EXIT_SUCCESS

# Smallest honest smoke configuration: one replicate per arm over a single closed-loop
# step. Still the real loop, the real arms, and every declared adversarial scenario.
SMOKE_ARGV = ["--smoke", "--n", "1", "--duration-hours", "1", "--step-hours", "1"]


def _unavailable_twin_handler(request: dict[str, Any]) -> dict[str, Any]:
    """A twin A2A handler that honestly reports the twin is not available in-process.

    Returns a JSON-RPC *error* response — the same shape an unreachable twin produces —
    so :meth:`ConsensusProtocol._phase_twin_verify` records its honest
    ``twin=twin_unavailable`` verdict. It never returns a fabricated Monte-Carlo result
    and never runs a sub-floor "verification".
    """
    return {
        "jsonrpc": "2.0",
        "id": str(request.get("id", "")),
        "error": {
            "code": -32004,
            "message": (
                "twin verification unavailable: this test injects no twin handler "
                "rather than running a sub-INV-TW-002 Monte-Carlo"
            ),
        },
    }


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory):
    """Run the ``--smoke`` CLI path once for the module and expose what it produced.

    Spies (not fakes) capture the arms the CLI built and the harness result it
    assembled; both delegate to the real implementations. Module-scoped so the real
    closed loop is driven once rather than once per assertion group.
    """
    captured: dict[str, Any] = {}

    def _cheap_twin_build(**kwargs: Any) -> ConsensusArm:
        kwargs.setdefault("twin_handler", _unavailable_twin_handler)
        return build_consensus_arm(**kwargs)

    real_build_arms = cli.build_arms

    def _spy_build_arms(seed: int = 0):
        arms = real_build_arms(seed=seed)
        captured["arms"] = arms
        return arms

    real_assemble = cli.assemble_uplift_result

    def _spy_assemble(harness_result, contract, **kwargs):
        captured["harness_result"] = harness_result
        return real_assemble(harness_result, contract, **kwargs)

    output = tmp_path_factory.mktemp("uplift_smoke") / "result.json"
    stdout = io.StringIO()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cli, "build_consensus_arm", _cheap_twin_build)
        patch.setattr(cli, "build_arms", _spy_build_arms)
        patch.setattr(cli, "assemble_uplift_result", _spy_assemble)
        with redirect_stdout(stdout):
            captured["exit_code"] = cli.main(SMOKE_ARGV + ["--output", str(output)])

    captured["output"] = output
    captured["stdout"] = stdout.getvalue()
    return captured


@pytest.mark.slow
def test_smoke_records_completed_consensus_run_for_an_adversarial_scenario(smoke_run):
    """R1.4: ``--smoke`` records >= 1 completed consensus run for >= 1 adversarial scenario."""
    assert smoke_run["exit_code"] == EXIT_SUCCESS

    # The arm under measurement is the real assembled consensus arm, not the CLI's
    # honest-failure stand-in — otherwise "completed runs" would be vacuous.
    consensus_arm = smoke_run["arms"][0]
    assert isinstance(consensus_arm, ConsensusArm)
    assert consensus_arm.name == DEFAULT_CONSENSUS_ARM

    harness_result = smoke_run["harness_result"]
    scenarios = harness_result.scenarios
    assert scenarios, "the CLI must run the declared adversarial suite"

    completed_by_scenario = {
        scenario.name: harness_result.completed_runs(scenario.name, DEFAULT_CONSENSUS_ARM)
        for scenario in scenarios
    }
    with_completed = {
        name: runs for name, runs in completed_by_scenario.items() if runs
    }

    failures = {
        name: [run.error for run in harness_result.runs_by_pair[(name, DEFAULT_CONSENSUS_ARM)]
               if run.failed]
        for name in completed_by_scenario
    }
    assert with_completed, (
        "no adversarial scenario recorded a completed consensus run; "
        f"failures: {failures}"
    )

    # A completed run carries a real KPI vector (never a fabricated one).
    for runs in with_completed.values():
        for run in runs:
            assert not run.failed
            assert run.kpis is not None
            assert 0.0 <= run.kpis.fill_rate <= 1.0


@pytest.mark.slow
def test_smoke_writes_result_artifact(smoke_run):
    """R7.1: the run writes the result artifact the C60 gate reads."""
    output: Path = smoke_run["output"]
    assert output.exists()
    assert f"wrote result artifact: {output}" in smoke_run["stdout"]

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(payload["headline_uplift"], (int, float))
    assert not isinstance(payload["headline_uplift"], bool)
    assert "incomplete" in payload
    assert "fidelity" in payload


def test_default_artifact_path_is_the_c60_read_path():
    """R7.1: the CLI's default output path is exactly ``artifacts/uplift/result.json``."""
    from scripts.audit.uplift_truth import RESULT_ARTIFACT

    default_path = cli._default_artifact_path()
    assert default_path == Path(RESULT_ARTIFACT)
    assert default_path.parts[-3:] == ("artifacts", "uplift", "result.json")
