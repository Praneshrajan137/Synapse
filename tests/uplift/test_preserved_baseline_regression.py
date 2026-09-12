"""Regression / smoke assertions for the preserved baseline (task 11.1).

Feature: core-purpose-uplift — this feature is a *wiring* feature: it adds the
`build_consensus_arm` assembly seam, the CLI wiring, the C56 headline pin, and the
floor/registry edits, and it must leave the genuinely strong existing engineering
untouched. This module is the mechanical guard on that promise. Nothing here is a
property test; these are cheap structural/smoke assertions over the *preserved*
baseline:

1. **Regression floor (R9.1).** The full suite must still carry at least the 623
   previously passing tests. This test asserts the number of tests pytest *collects*
   across the configured ``testpaths``, which is a necessary condition for ">= 623
   passing" and is honest about what it measures: it does **not** re-run the whole
   suite from inside a test (a nested full-suite run would be quadratic and would
   recurse into this very module). Whether every collected test *passes* is decided by
   the suite run itself (locally and in CI, ``.github/workflows/ci.yml``) — the run
   that executes this file. The collected count is therefore the floor check; the pass
   check is the surrounding run.
2. **Reuse, not fork (R1.6, R9.8).** ``uplift/consensus_arm.py`` must import the real
   ``orchestrator.consensus.protocol.ConsensusProtocol`` / ``AGENT_ENDPOINTS`` /
   ``TWIN_ENDPOINT``, must not define or subclass any consensus decision logic of its
   own, and the protocol it assembles must be the real class with real collaborators.
3. **$0, network-free, synthetic-seed-only reproduction and verification (R3.6, R3.7,
   R9.2, R9.6, R10.1, R10.3).** The reproduction command and the C60 verification gate
   run with every socket entry point and every installed paid-SDK client monkeypatched
   to fail: the paths must still complete in-process (or degrade honestly), dial no paid
   host, construct no paid client, and read no real/scraped data file. Decisions never
   travel over a socket — the only outbound attempt the reproduction makes is a
   best-effort call to the free self-hosted Ollama reasoner, which falls back to
   rule-based reasoning when it cannot connect (I-7); the C60 gate makes none at all.
4. **A single importable numeric floor (R4.1, R4.7).** ``UPLIFT_FLOOR`` is declared
   exactly once, is a finite number, and — if it has been ratcheted above ``0.0`` — is
   backed by a co-located committed powered proof artifact.
5. **Invariant suites (R9.3, R9.4, R9.5, R9.6, R9.7).** The existing I-2 / I-3 / I-5 /
   I-7 / I-14 suites are reused, not rewritten: this module pins their locations and
   asserts they still exist, still declare tests, and still collect cleanly, so they
   cannot be silently deleted or renamed while the invariants are claimed to hold.
   Their pass/fail verdict comes from running them (they are part of the same suite).

_Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 10.1, 10.3_
"""
from __future__ import annotations

import ast
import builtins
import importlib
import importlib.util
import inspect
import io
import json
import math
import os
import re
import socket
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Iterable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The previously passing test count this feature must not regress below (R9.1).
REGRESSION_FLOOR = 623

#: The existing invariant suites this feature reuses rather than rewrites (R9.3–R9.7).
INVARIANT_SUITES: dict[str, tuple[str, ...]] = {
    # I-2 — agent reward signals stay independent (no cross-agent reward imports; the
    # meta-RL learner never owns an agent reward).
    "I-2": (
        "agents/demand_prophet/tests/test_reward.py",
        "agents/pricing_oracle/tests/test_reward.py",
        "orchestrator/tests/test_meta_rl.py",
    ),
    # I-3 — request/decision schemas are validated at the handler boundary.
    "I-3": ("tests/contracts/test_schema_at_handler_boundary.py",),
    # I-5 — confidence-gated human-in-the-loop escalation in the consensus path.
    "I-5": (
        "tests/dbc/test_guardrails_contracts.py",
        "tests/eval/test_consensus_properties.py",
    ),
    # I-7 — honest degradation for unavailable models/services.
    "I-7": ("packages/tests/test_honesty_contract.py",),
    # I-14 — consensus context is append-only.
    "I-14": (
        "orchestrator/tests/test_context_immutability.py",
        "orchestrator/tests/consensus/test_append_only_pbt.py",
    ),
}

_INVARIANT_PATHS: tuple[str, ...] = tuple(
    path for paths in INVARIANT_SUITES.values() for path in paths
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _collect_only(paths: Iterable[str]) -> subprocess.CompletedProcess[str]:
    """Run ``pytest --collect-only`` in a subprocess (never nested in-process)."""
    command = [
        sys.executable,
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "-p",
        "no:cacheprovider",
        "--continue-on-collection-errors",
        *paths,
    ]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(  # noqa: S603 — fixed argv, no shell
        command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=3600,
    )


def _collected_count(output: str) -> int | None:
    """Parse pytest's ``N tests collected`` / ``collected N items`` summary."""
    for pattern in (r"(\d+)\s+tests?\s+collected", r"collected\s+(\d+)\s+items?"):
        matches = re.findall(pattern, output)
        if matches:
            return max(int(value) for value in matches)
    return None


def _module_ast(relative: str) -> ast.Module:
    return ast.parse((REPO_ROOT / relative).read_text(encoding="utf-8"))


def _imported_names(tree: ast.Module, module: str) -> set[str]:
    """Every name imported from ``module`` anywhere in ``tree`` (incl. local imports)."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            names.update(alias.name for alias in node.names)
    return names


# ---------------------------------------------------------------------------
# 1. The 623-test regression floor (R9.1)
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_full_suite_still_carries_the_regression_floor() -> None:
    """R9.1: the suite collects at least the 623 previously passing tests.

    Collected-count, not pass-count, on purpose (see the module docstring): running the
    whole suite from inside one of its own tests would recurse. Collection is still a
    real, honest signal — it imports every test module, so a deleted module, a renamed
    package, or an import-time break in the baseline shows up here.
    """
    completed = _collect_only(())
    collected = _collected_count(completed.stdout + completed.stderr)

    assert collected is not None, (
        "could not parse pytest's collection summary; "
        f"stdout tail: {completed.stdout[-2000:]!r}"
    )
    assert collected >= REGRESSION_FLOOR, (
        f"regression floor breached: pytest collected {collected} tests, "
        f"below the preserved baseline of {REGRESSION_FLOOR} (R9.1)"
    )


@pytest.mark.slow
def test_this_features_own_suites_collect_without_error() -> None:
    """R9.1: the feature's own test packages import cleanly (no collection errors)."""
    completed = _collect_only(("tests/uplift", "tests/verify"))
    output = completed.stdout + completed.stderr

    # pytest reports collection failures as `ERROR <path>` lines in the short summary.
    error_lines = re.findall(r"^ERROR .*$", output, flags=re.MULTILINE)
    assert not error_lines, error_lines
    assert completed.returncode == 0, output[-2000:]
    assert (_collected_count(output) or 0) > 0, output[-2000:]


# ---------------------------------------------------------------------------
# 2. Reuse, not fork: the real ConsensusProtocol / AGENT_ENDPOINTS (R1.6, R9.8)
# ---------------------------------------------------------------------------
def test_consensus_arm_imports_the_real_protocol_and_endpoints() -> None:
    """R1.6/R9.8: the arm dials the real protocol module's own names."""
    tree = _module_ast("uplift/consensus_arm.py")
    imported = _imported_names(tree, "orchestrator.consensus.protocol")

    assert {"ConsensusProtocol", "AGENT_ENDPOINTS", "TWIN_ENDPOINT"} <= imported, (
        "uplift/consensus_arm.py must import the real ConsensusProtocol, "
        f"AGENT_ENDPOINTS and TWIN_ENDPOINT; found {sorted(imported)}"
    )

    # The names resolve to the real objects (not a local re-definition).
    from orchestrator.consensus.protocol import (  # noqa: PLC0415 — asserted import
        AGENT_ENDPOINTS,
        TWIN_ENDPOINT,
    )

    assert len(AGENT_ENDPOINTS) == 8
    assert TWIN_ENDPOINT not in set(AGENT_ENDPOINTS.values())

    # No shadowing definition of either name inside the arm module.
    module_level_names = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    } | {
        node.target.id
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert {"AGENT_ENDPOINTS", "TWIN_ENDPOINT"}.isdisjoint(module_level_names)


def test_consensus_arm_forks_no_decision_logic() -> None:
    """R1.6/R9.8: no consensus phase/tier logic is re-implemented in the arm module."""
    tree = _module_ast("uplift/consensus_arm.py")

    forked = {
        "run_consensus",
        "_phase_proposal",
        "_phase_debate",
        "_phase_arbitration",
        "_phase_twin_verify",
        "_phase_learn",
        "_run_concession_round",
        "classify",
        "route",
    }
    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert forked.isdisjoint(defined), (
        f"uplift/consensus_arm.py re-implements consensus logic: {sorted(forked & defined)}"
    )

    # Nor does it subclass (and therefore override) the real collaborators.
    real_bases = {"ConsensusProtocol", "TierRouter", "GuardrailEngine", "ContextBuilder"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        base_names = {
            base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
            for base in node.bases
        }
        assert real_bases.isdisjoint(base_names), (
            f"{node.name} subclasses a real consensus collaborator: {sorted(base_names)}"
        )

    # And the arm's decision really delegates to the real ``run_consensus``.
    from uplift.consensus_arm import ConsensusArm  # noqa: PLC0415 — asserted import

    source = inspect.getsource(ConsensusArm._run_consensus)
    assert "self._protocol.run_consensus(" in source


def test_assembled_protocol_is_the_real_class_with_real_collaborators() -> None:
    """R1.6/R9.8: ``build_consensus_protocol`` returns the real, unmodified protocol."""
    from orchestrator.audit.logger import AuditLogger
    from orchestrator.consensus.protocol import ConsensusProtocol
    from orchestrator.consensus.tier_router import TierRouter
    from orchestrator.guardrails.rules import GuardrailEngine
    from orchestrator.hitl.escalation import HITLEscalation
    from orchestrator.llm.context_builder import ContextBuilder
    from orchestrator.llm.semantic_cache import SemanticDecisionCache
    from orchestrator.meta_rl.meta_agent import MetaRLAgent

    from uplift.consensus_arm import ConsensusArmUnavailable, build_consensus_protocol

    try:
        protocol = build_consensus_protocol()
    except ConsensusArmUnavailable as exc:  # pragma: no cover — environment-dependent
        pytest.skip(f"consensus protocol cannot be assembled here: {exc}")

    # The real class itself — not a subclass with overridden phases.
    assert type(protocol) is ConsensusProtocol

    assert isinstance(protocol._tier_router, TierRouter)  # I-3/tier routing reused
    assert isinstance(protocol._guardrails, GuardrailEngine)
    assert isinstance(protocol._audit, AuditLogger)  # hash-chained audit reused
    assert isinstance(protocol._hitl, HITLEscalation)  # I-5 escalation intact
    assert isinstance(protocol._ctx_builder, ContextBuilder)  # I-14 append-only context
    assert isinstance(protocol._meta_rl, MetaRLAgent)  # I-2 weights, not agent rewards
    assert isinstance(protocol._semantic_cache, SemanticDecisionCache)
    # No external fan-out is wired in for the $0 run (I-1).
    assert protocol._kafka is None
    assert protocol._world_observer is None


# ---------------------------------------------------------------------------
# 3. A single importable numeric floor (R4.1, R4.7)
# ---------------------------------------------------------------------------
def test_uplift_floor_is_a_single_importable_numeric_constant() -> None:
    """R4.1: one declaration site, importable, a finite number (not a bool)."""
    from uplift.uplift_floor import UPLIFT_FLOOR

    assert isinstance(UPLIFT_FLOOR, (int, float))
    assert not isinstance(UPLIFT_FLOOR, bool)
    assert math.isfinite(float(UPLIFT_FLOOR))

    tree = _module_ast("uplift/uplift_floor.py")
    declarations = [
        node
        for node in tree.body
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "UPLIFT_FLOOR"
        )
        or (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "UPLIFT_FLOOR"
                for target in node.targets
            )
        )
    ]
    assert len(declarations) == 1, (
        f"UPLIFT_FLOOR must be declared exactly once in uplift/uplift_floor.py; "
        f"found {len(declarations)} declarations"
    )


def test_uplift_floor_has_no_second_definition_in_the_codebase() -> None:
    """R4.1: production code imports the floor; nothing re-declares its own copy."""
    owner = (REPO_ROOT / "uplift" / "uplift_floor.py").resolve()
    offenders: list[str] = []

    for package in ("uplift", "scripts", "orchestrator", "api", "packages", "agents"):
        for path in (REPO_ROOT / package).rglob("*.py"):
            if path.resolve() == owner or "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError):  # pragma: no cover
                continue
            for node in tree.body:  # module level only — locals are not the constant
                targets: list[ast.expr] = []
                if isinstance(node, ast.Assign):
                    targets = list(node.targets)
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                if any(
                    isinstance(target, ast.Name) and target.id == "UPLIFT_FLOOR"
                    for target in targets
                ):
                    offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert not offenders, (
        f"UPLIFT_FLOOR is re-declared outside uplift/uplift_floor.py: {offenders}"
    )


def test_a_raised_floor_is_backed_by_a_committed_powered_proof() -> None:
    """R4.7: ``UPLIFT_FLOOR > 0`` requires a co-located powered proof artifact."""
    from uplift.uplift_floor import UPLIFT_FLOOR, PoweredProof

    if UPLIFT_FLOOR <= 0.0:
        pytest.skip("floor is still the honest 0.0 — no measured gain is asserted")

    proof = PoweredProof.from_artifact(  # pragma: no cover — only once a gain lands
        REPO_ROOT / "artifacts" / "uplift" / "result.json"
    )
    assert proof is not None, (
        "UPLIFT_FLOOR was raised above 0.0 with no readable proof artifact (R4.7)"
    )
    assert proof.supports(UPLIFT_FLOOR), (
        f"committed proof (headline {proof.headline_uplift} pp over {proof.replicates} "
        f"replicates/arm, incomplete={proof.incomplete}, "
        f"within_fidelity_bound={proof.within_fidelity_bound}) does not support "
        f"UPLIFT_FLOOR={UPLIFT_FLOOR} (R4.7)"
    )


# ---------------------------------------------------------------------------
# 4. $0, network-free, synthetic-seed-only reproduction + verification
#    (R3.6, R3.7, R9.2, R9.6, R10.1, R10.3)
# ---------------------------------------------------------------------------
#: Addresses the interpreter itself needs: asyncio's event-loop self-pipe is a loopback
#: ``socketpair`` on Windows, so a purely local loopback connect is not a network dial
#: and must stay permitted or no event loop could be created at all.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "0.0.0.0", ""})

#: Paid / hosted SDK entry points that must never be constructed on a reproduction or
#: verification path (I-1, R9.2). Only the ones actually installed here are patched.
_PAID_CLIENT_TARGETS: tuple[tuple[str, str], ...] = (
    ("openai", "OpenAI"),
    ("openai", "AsyncOpenAI"),
    ("anthropic", "Anthropic"),
    ("anthropic", "AsyncAnthropic"),
    ("ollama", "Client"),
    ("ollama", "AsyncClient"),
    ("pinecone", "Pinecone"),
    ("boto3", "client"),
)

#: Suffixes that would indicate a real/scraped/purchased dataset read (R10.1).
_DATA_SUFFIXES = frozenset(
    {".csv", ".tsv", ".parquet", ".arrow", ".feather", ".xlsx", ".xls", ".db",
     ".sqlite", ".sqlite3", ".pkl"}
)

#: Real-data directories the proof must never read from (R3.6, R10.1).
_REAL_DATA_DIRS = (REPO_ROOT / "data", REPO_ROOT / "data_fabric")

#: Hosts that would cost money to reach. A blocked dial to any of these on a
#: reproduction/verification path is an I-1 (``$0``) violation regardless of whether it
#: degrades honestly, so the guard's recorded attempts are checked against this list.
_PAID_HOST_MARKERS: tuple[str, ...] = (
    "openai.com",
    "anthropic.com",
    "cohere.ai",
    "pinecone.io",
    "amazonaws.com",
    "azure.com",
    "googleapis.com",
    "rapidapi.com",
    "twilio.com",
    "stripe.com",
)


class _ZeroCostGuard:
    """Make every socket dial and paid-SDK client fail, and record real-data reads.

    Installed around a reproduction or verification path so that:

    * ``httpx`` send/request (what an outbound A2A/LLM call really uses) fails with
      :class:`httpx.ConnectError` — exactly what a real unreachable peer raises, so a
      component that dials must take its own documented honest-degradation path (I-7)
      rather than a synthetic error path reality never produces;
    * ``socket.getaddrinfo`` / ``create_connection`` / ``connect`` fail with ``OSError``
      for any non-loopback address (loopback stays open because asyncio's event-loop
      self-pipe is a local ``socketpair`` on Windows);
    * constructing any installed paid/hosted SDK client fails loudly (I-1);
    * every file *read* of a real-data directory or dataset suffix is recorded.

    Each blocked dial is recorded with its target, so a test can assert the stronger
    property that matters: nothing paid was reachable, and the path still produced an
    honest result. Best-effort dials to *free, self-hosted* services (e.g. the local
    Ollama reasoner, which falls back to rule-based reasoning when it cannot connect)
    are legitimate — they cost ``$0`` and degrade honestly.
    """

    def __init__(self) -> None:
        self.network_attempts: list[str] = []
        self.paid_client_attempts: list[str] = []
        self.data_file_reads: list[str] = []
        self._saved: dict[str, Any] = {}
        self._saved_paid: list[tuple[Any, str, Any]] = []

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _host_of(address: Any) -> str:
        if isinstance(address, tuple) and address:
            return str(address[0])
        return str(address)

    def _fail(self, label: str, sink: list[str]) -> Any:
        def guard(*_: Any, **__: Any) -> Any:
            sink.append(label)
            raise AssertionError(f"forbidden on a $0 path: {label}")

        return guard

    def _blocked_http(self, label: str) -> Any:
        """Fail an httpx send/request the way an unreachable peer does."""
        import httpx

        def guard(_self: Any, request: Any = None, *_: Any, **kwargs: Any) -> Any:
            target = getattr(request, "url", None) or kwargs.get("url") or ""
            self.network_attempts.append(f"{label}->{target}")
            raise httpx.ConnectError(f"network blocked by the $0 guard ({label} {target})")

        return guard

    def _fail_unless_loopback(self, label: str, original: Any, index: int) -> Any:
        def guard(*args: Any, **kwargs: Any) -> Any:
            address = args[index] if len(args) > index else kwargs.get("address")
            if self._host_of(address) in _LOOPBACK_HOSTS:
                return original(*args, **kwargs)
            self.network_attempts.append(f"{label}->{address!r}")
            raise OSError(f"network blocked by the $0 guard ({label} {address!r})")

        return guard

    def paid_host_attempts(self) -> list[str]:
        """Recorded dials whose target looks like a paid third-party service."""
        return [
            attempt
            for attempt in self.network_attempts
            if any(marker in attempt.lower() for marker in _PAID_HOST_MARKERS)
        ]

    def _recording_open(self, original: Any) -> Any:
        def guard(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
            if isinstance(file, (str, os.PathLike)) and "r" in mode and "+" not in mode:
                path = Path(os.fspath(file))
                suffix = path.suffix.lower()
                resolved = path if path.is_absolute() else (REPO_ROOT / path)
                under_data = any(
                    str(resolved).lower().startswith(str(directory).lower())
                    for directory in _REAL_DATA_DIRS
                )
                if suffix in _DATA_SUFFIXES or under_data:
                    self.data_file_reads.append(str(path))
            return original(file, mode, *args, **kwargs)

        return guard

    # -- context manager ----------------------------------------------------
    def __enter__(self) -> "_ZeroCostGuard":
        import httpx

        self._saved = {
            "socket.create_connection": socket.create_connection,
            "socket.getaddrinfo": socket.getaddrinfo,
            "socket.socket.connect": socket.socket.connect,
            "socket.socket.connect_ex": socket.socket.connect_ex,
            "httpx.AsyncClient.send": httpx.AsyncClient.send,
            "httpx.Client.send": httpx.Client.send,
            "builtins.open": builtins.open,
        }
        socket.create_connection = self._fail_unless_loopback(  # type: ignore[assignment]
            "socket.create_connection", self._saved["socket.create_connection"], 0
        )
        socket.getaddrinfo = self._fail_unless_loopback(  # type: ignore[assignment]
            "socket.getaddrinfo", self._saved["socket.getaddrinfo"], 0
        )
        socket.socket.connect = self._fail_unless_loopback(  # type: ignore[method-assign]
            "socket.connect", self._saved["socket.socket.connect"], 1
        )
        socket.socket.connect_ex = self._fail_unless_loopback(  # type: ignore[method-assign]
            "socket.connect_ex", self._saved["socket.socket.connect_ex"], 1
        )
        httpx.AsyncClient.send = self._blocked_http(  # type: ignore[method-assign]
            "httpx.AsyncClient.send"
        )
        httpx.Client.send = self._blocked_http("httpx.Client.send")  # type: ignore[method-assign]
        builtins.open = self._recording_open(self._saved["builtins.open"])  # type: ignore[assignment]

        for module_name, attribute in _PAID_CLIENT_TARGETS:
            if importlib.util.find_spec(module_name) is None:
                continue
            try:
                module = importlib.import_module(module_name)
            except Exception:  # noqa: BLE001 — an unimportable SDK cannot be used anyway
                continue
            original = getattr(module, attribute, None)
            if original is None:
                continue
            self._saved_paid.append((module, attribute, original))
            setattr(
                module,
                attribute,
                self._fail(f"{module_name}.{attribute}", self.paid_client_attempts),
            )
        return self

    def __exit__(self, *_: Any) -> None:
        import httpx

        socket.create_connection = self._saved["socket.create_connection"]  # type: ignore[assignment]
        socket.getaddrinfo = self._saved["socket.getaddrinfo"]  # type: ignore[assignment]
        socket.socket.connect = self._saved["socket.socket.connect"]  # type: ignore[method-assign]
        socket.socket.connect_ex = self._saved["socket.socket.connect_ex"]  # type: ignore[method-assign]
        httpx.AsyncClient.send = self._saved["httpx.AsyncClient.send"]  # type: ignore[method-assign]
        httpx.Client.send = self._saved["httpx.Client.send"]  # type: ignore[method-assign]
        builtins.open = self._saved["builtins.open"]  # type: ignore[assignment]
        for module, attribute, original in self._saved_paid:
            setattr(module, attribute, original)
        self._saved_paid.clear()


def _unavailable_twin_handler(request: dict[str, Any]) -> dict[str, Any]:
    """A twin A2A handler that honestly reports the twin is unavailable in-process.

    The default twin handler honours INV-TW-002 and runs 1000 Monte-Carlo scenarios per
    shocked decision, which would make this regression smoke test a multi-minute run.
    Rather than cheapen that verification (fabricating a "verification" that never ran),
    this returns the same JSON-RPC *error* an unreachable twin produces, so the protocol
    takes its existing honest ``twin_unavailable`` degradation path (I-7).
    """
    return {
        "jsonrpc": "2.0",
        "id": str(request.get("id", "")),
        "error": {"code": -32004, "message": "twin verification unavailable (no handler injected)"},
    }


def test_declared_scenario_suite_is_synthetic_seeds_only() -> None:
    """R3.6/R10.1: every declared scenario is an integer seed, not a data pointer."""
    import dataclasses

    from uplift.scenarios import adversarial_suite

    scenarios = adversarial_suite()
    assert scenarios, "the adversarial suite must declare scenarios"

    for scenario in scenarios:
        assert isinstance(scenario.seed, int) and not isinstance(scenario.seed, bool)
        for field in dataclasses.fields(scenario):
            value = getattr(scenario, field.name)
            if isinstance(value, str):
                lowered = value.lower()
                assert "http" not in lowered
                assert not any(lowered.endswith(suffix) for suffix in _DATA_SUFFIXES)


@pytest.mark.slow
def test_reproduction_path_is_zero_cost_network_free_and_synthetic_only(tmp_path) -> None:
    """R3.6/R3.7/R9.2/R9.6/R10.1/R10.3: the one command reproduces at $0, in-process.

    Every socket entry point and every installed paid-SDK client is patched to fail. The
    command must still complete on synthetic seeds, disclose its provenance, and write
    the artifact — or, if the in-process consensus network cannot stand up here, degrade
    honestly (failed consensus runs, result marked incomplete) rather than crash or
    fabricate a credited decision.

    What "network-free" means here, precisely. Every A2A/twin dispatch is in-process, so
    no socket carries a *decision*. One component still makes a best-effort outbound
    call: ``agents/disruption_shield/models/reasoning.py`` POSTs to the free,
    self-hosted Ollama endpoint and falls back to rule-based reasoning when it cannot
    connect (I-7). That is ``$0`` and honest, so the assertion is the one the invariant
    actually needs: **no paid** host is dialed, no paid SDK client is constructed, no
    real-data file is read, and the run still produces a complete honest result with
    every dial failing.
    """
    import uplift.cli as cli
    from uplift.consensus_arm import build_consensus_arm
    from uplift.harness import DEFAULT_CONSENSUS_ARM, EXIT_SUCCESS

    captured: dict[str, Any] = {}
    output = tmp_path / "result.json"
    stdout = io.StringIO()

    def _cheap_twin_build(**kwargs: Any):
        kwargs.setdefault("twin_handler", _unavailable_twin_handler)
        return build_consensus_arm(**kwargs)

    real_assemble = cli.assemble_uplift_result

    def _spy_assemble(harness_result, contract, **kwargs):
        captured["harness_result"] = harness_result
        return real_assemble(harness_result, contract, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cli, "build_consensus_arm", _cheap_twin_build)
        patch.setattr(cli, "assemble_uplift_result", _spy_assemble)
        with _ZeroCostGuard() as guard:
            with redirect_stdout(stdout):
                exit_code = cli.main(
                    [
                        "--smoke",
                        "--n",
                        "1",
                        "--duration-hours",
                        "1",
                        "--step-hours",
                        "1",
                        "--output",
                        str(output),
                    ]
                )

    printed = stdout.getvalue()

    # $0 (I-1, R3.7, R9.2, R10.3): nothing paid was dialed or constructed, and no
    # decision travelled over a socket — every dial the run attempted failed.
    assert guard.paid_host_attempts() == [], f"paid host dialed: {guard.paid_host_attempts()}"
    assert guard.paid_client_attempts == [], f"paid client used: {guard.paid_client_attempts}"
    # Synthetic seeds only (R3.6, R10.1).
    assert guard.data_file_reads == [], f"real-data file read: {guard.data_file_reads}"

    # The run completed (never crashed) and disclosed what it is.
    assert exit_code == EXIT_SUCCESS
    assert "data provenance: synthetic seed-generated data only" in printed
    assert "external services: none" in printed

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(payload["headline_uplift"], (int, float))
    assert not isinstance(payload["headline_uplift"], bool)

    # Honest failure, never a fabricated credit (R9.6): if the consensus arm could not
    # complete a single scenario here, the result must say so.
    harness_result = captured["harness_result"]
    completed = sum(
        len(harness_result.completed_runs(scenario.name, DEFAULT_CONSENSUS_ARM))
        for scenario in harness_result.scenarios
    )
    if completed == 0:  # pragma: no cover — environment-dependent degradation
        assert payload["incomplete"] is True
    else:
        assert all(
            run.kpis is not None
            for scenario in harness_result.scenarios
            for run in harness_result.completed_runs(scenario.name, DEFAULT_CONSENSUS_ARM)
        )


def test_c60_verification_path_is_network_free(tmp_path, monkeypatch) -> None:
    """R9.2/R10.3: the C60 gate verifies from its result artifact alone, no network.

    Retargeted for the purpose-achievement-audit R2 remediation: the gate no longer reads
    a bare ``headline_uplift``, so the fixture is a proof-grade
    :class:`~uplift.harness.UpliftArtifact` -- complete, powered at
    ``MIN_POWERED_REPLICATES``, within the twin fidelity bound, and attributed to the
    evaluating run. The preserved claim is unchanged: verification touches no socket, no
    paid client, and no real-data file.
    """
    from scripts.audit import uplift_truth
    from uplift.harness import (
        ArtifactFidelity,
        UpliftArtifact,
        UpliftProvenance,
    )
    from uplift.uplift_floor import MIN_POWERED_REPLICATES, UPLIFT_FLOOR

    revision, run_id = "c0ffee", "run-4242"
    monkeypatch.setenv("SYNAPSE_REVISION", revision)
    monkeypatch.setenv("SYNAPSE_RUN_ID", run_id)

    artifact = tmp_path / "result.json"
    UpliftArtifact(
        headline_uplift=float(UPLIFT_FLOOR) + 1.0,
        primary_kpi="fill_rate",
        noise_tolerance_pp=1.0,
        incomplete=False,
        all_wins_warning=False,
        replicates_per_arm=MIN_POWERED_REPLICATES,
        fidelity=ArtifactFidelity(
            kl_divergence=0.02,
            threshold=0.1,
            confidence="high",
            within_fidelity_bound=True,
            fidelity_bound_statement="bounded by twin fidelity",
        ),
        provenance=UpliftProvenance(
            arms=("baseline-0", "consensus"),
            replicates_per_arm=MIN_POWERED_REPLICATES,
            revision=revision,
            run_id=run_id,
            seeds=(4001,),
            written_at="2026-01-01T00:00:00Z",
        ),
    ).write(artifact)

    with _ZeroCostGuard() as guard:
        with redirect_stdout(io.StringIO()):
            exit_code = uplift_truth.run(
                check=True, require_fresh_run=True, artifact=artifact
            )

    assert exit_code == uplift_truth.EXIT_PASS
    # The gate reads its result artifact and nothing else: no dial at all, no paid
    # client, no real-data file.
    assert guard.network_attempts == []
    assert guard.paid_client_attempts == []
    assert guard.data_file_reads == []


# ---------------------------------------------------------------------------
# 5. The reused invariant suites stay in place (R9.3, R9.4, R9.5, R9.6, R9.7)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("invariant", "relative"),
    [(invariant, path) for invariant, paths in INVARIANT_SUITES.items() for path in paths],
)
def test_invariant_suite_still_exists_and_declares_tests(invariant: str, relative: str) -> None:
    """R9.3–R9.7: the invariant suites are reused, not deleted or emptied."""
    path = REPO_ROOT / relative
    assert path.is_file(), f"{invariant} suite missing: {relative}"

    tree = ast.parse(path.read_text(encoding="utf-8"))
    declared = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    assert declared, f"{invariant} suite declares no tests: {relative}"


@pytest.mark.slow
def test_invariant_suites_still_collect() -> None:
    """R9.3–R9.7: every pinned invariant suite still imports and collects cleanly."""
    completed = _collect_only(_INVARIANT_PATHS)
    output = completed.stdout + completed.stderr

    assert completed.returncode == 0, output[-2000:]
    collected = _collected_count(output) or 0
    assert collected >= len(_INVARIANT_PATHS), output[-2000:]
