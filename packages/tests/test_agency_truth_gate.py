"""The ADR-052 agency gate must report the loop as real in this repo, and its ratchet
must actually bite. Guards both the loop AND the gate from rotting.

This module also implements **Property 18** (the gate classifies actuating handlers as
converted, not stubs — R8.6) and the gate unit tests (R8.1, 8.2, 8.3, 8.7, 9.1, 9.2, 9.4).

Implementation under test: ``scripts.audit.agency_truth`` (the gate) and the C57
``check_agency_loop`` in ``scripts.audit.verify_claims`` that surfaces the gate verdict.

Example budget for the property test is controlled by the active Hypothesis profile (see
the root ``conftest.py``): ``dev`` (10), ``default``/``ci`` (500), ``nightly`` (5_000).
"""

from __future__ import annotations

import ast
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

import scripts.audit.agency_truth as agency_truth
import scripts.audit.verify_claims as verify_claims
from scripts.audit.agency_truth import (
    DEFAULT_MAX_STUBS,
    STRUCTURAL_INVARIANTS,
    Check,
    Probe,
    _agent_actuation,
    _execute_returns_stub,
    evaluate,
)

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
except ImportError:  # hypothesis is optional in some environments
    pytest.skip("hypothesis not installed", allow_module_level=True)


# ---------------------------------------------------------------------------
# Existing guards — the loop and the ratchet are real in this repo.
# ---------------------------------------------------------------------------


def test_agentic_loop_is_real() -> None:
    probe = evaluate()
    assert probe.ok, probe.detail
    # All five structural loop invariants hold.
    assert all(c.ok for c in probe.checks), [c.name for c in probe.checks if not c.ok]
    # The vertical-slice agents are genuinely converted (real actuation).
    assert "inventory_sentinel" in probe.converted
    assert "supplier_trust" in probe.converted


def test_ratchet_actually_bites() -> None:
    # ADR-052 / R8.1-R8.2: every agent execute() is now converted to real actuation or an
    # Honest No-Op, so there are zero stubs and the ceiling is ratcheted to 0. The ratchet
    # is still live (not decorative): the gate passes at the 0 ceiling only because no stub
    # remains, and any ceiling below the current stub count must FAIL — so a regression that
    # reintroduces a status-dict stub immediately trips the gate.
    from scripts.audit.agency_truth import DEFAULT_MAX_STUBS

    assert DEFAULT_MAX_STUBS == 0
    probe = evaluate()
    assert probe.stubs == []  # fully ratcheted: no stub execute()s remain
    assert evaluate(max_stubs=0).ok is True
    # A ceiling below the (zero) stub count fails — the `len(stubs) <= max_stubs` gate is
    # genuinely enforced, proving the ratchet bites rather than being cosmetic.
    assert evaluate(max_stubs=-1).ok is False


# ===========================================================================
# Task 10.3 — Property 18: the gate classifies actuating handlers as converted,
# not stubs (Validates: Requirements 8.6).
# ===========================================================================
#
# We exercise the gate's real classifier primitives:
#   * ``_execute_returns_stub`` — the AST helper that decides "stub shape"; an execute()
#     that actuates (calls an actuator ``.apply(...)`` / ``.produce(...)``) is never a stub.
#   * ``_agent_actuation`` — the per-handler classifier; pointed at a synthetic agents
#     tree it must put an actuating handler in ``converted`` and a status-dict-only
#     handler in ``stubs``.
# Synthetic handler sources are generated over actuating vs non-actuating bodies, parsed
# with ``ast``, and the classifier's verdict is asserted.

# An actuation body that genuinely mutates the world / event-sources. Each form contains a
# real ``.apply(...)``/``.produce(...)`` call and a converted source marker
# (``WorldAction`` / ``self._actuator`` / ``self._kafka.produce``).
_actuation_form_st = st.sampled_from(
    [
        "        outcome = self._actuator.apply(action)\n",
        '        outcome = self._kafka.produce("topic", b"payload")\n',
        "        action = WorldAction(city=params.get('city'))\n"
        "        outcome = self._actuator.apply(action)\n",
    ]
)
_status_st = st.sampled_from(["executed", "diverged", "revised", "ok"])
_extra_keys_st = st.lists(
    st.sampled_from(["decision_id", "city", "agent", "reason"]),
    unique=True,
    max_size=4,
)


def _extra_lines(keys: list[str]) -> str:
    return "".join(f'            "{k}": params.get("{k}"),\n' for k in keys)


def _converted_source(form: str, status: str, extra: list[str]) -> str:
    """A handler whose execute() genuinely actuates — must be classified converted.

    ``kafka_published`` is a *variable* (not the literal ``True``), so the body never
    matches the stub return shape even before the actuation markers are considered.
    """
    return (
        "class Handler:\n"
        "    def execute(self, params):\n"
        f"{form}"
        "        published = bool(outcome)\n"
        "        return {\n"
        '            "kafka_published": published,\n'
        f'            "status": "{status}",\n'
        f"{_extra_lines(extra)}"
        "        }\n"
    )


def _stub_source(status: str, extra: list[str]) -> str:
    """A status-dict-only handler: returns ``kafka_published: True`` and never actuates."""
    return (
        "class Handler:\n"
        "    def execute(self, params):\n"
        "        return {\n"
        '            "kafka_published": True,\n'
        f'            "status": "{status}",\n'
        f"{_extra_lines(extra)}"
        "        }\n"
    )


def _find_execute(src: str) -> ast.FunctionDef:
    """Return the ``execute`` FunctionDef parsed from ``src``."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "execute":
            return node
    raise AssertionError("synthetic source has no execute() function")


@contextmanager
def _temp_agents(handlers: dict[str, str]) -> Iterator[None]:
    """Point ``agency_truth.AGENTS_DIR`` at a synthetic agents tree for the duration."""
    original = agency_truth.AGENTS_DIR
    tmp = Path(tempfile.mkdtemp())
    try:
        for agent, src in handlers.items():
            handler_path = tmp / agent / "a2a" / "handler.py"
            handler_path.parent.mkdir(parents=True, exist_ok=True)
            handler_path.write_text(src, encoding="utf-8")
        agency_truth.AGENTS_DIR = tmp
        yield
    finally:
        agency_truth.AGENTS_DIR = original
        shutil.rmtree(tmp, ignore_errors=True)


@given(
    form=_actuation_form_st,
    status=_status_st,
    extra=_extra_keys_st,
    stub_status=_status_st,
    stub_extra=_extra_keys_st,
)
@settings(deadline=None)
def test_actuating_handlers_classified_converted_not_stub(
    form: str,
    status: str,
    extra: list[str],
    stub_status: str,
    stub_extra: list[str],
) -> None:
    """An actuating execute() is classified converted; a status-dict stub is a stub.

    **Validates: Requirements 8.6**
    """
    converted_src = _converted_source(form, status, extra)
    stub_src = _stub_source(stub_status, stub_extra)

    # Classifier primitive: an actuating execute() is never the stub shape; a
    # status-dict-only execute() always is.
    assert _execute_returns_stub(_find_execute(converted_src)) is False
    assert _execute_returns_stub(_find_execute(stub_src)) is True

    # Full per-handler classifier against a synthetic agents tree: the actuating handler
    # lands in `converted` (never `stubs`), the status-dict handler lands in `stubs`.
    with _temp_agents({"act_agent": converted_src, "stub_agent": stub_src}):
        converted, stubs = _agent_actuation()

    assert "act_agent" in converted
    assert "act_agent" not in stubs
    assert "stub_agent" in stubs
    assert "stub_agent" not in converted


# ===========================================================================
# Task 10.4 — Gate unit tests (Validates: R8.1, 8.2, 8.3, 8.7, 9.1, 9.2, 9.4).
# ===========================================================================


def test_default_max_stubs_is_zero() -> None:
    """The ratchet ceiling is fully ratcheted to 0 (R8.2)."""
    assert DEFAULT_MAX_STUBS == 0


def test_evaluate_reports_zero_stubs_and_binding_check_present() -> None:
    """``evaluate()`` reports 0 stubs (R8.1) and the binding check is present + ok (R9.1)."""
    probe = evaluate()
    assert probe.stubs == []  # R8.1: no status-dict stubs remain
    # R9.1: the binding-arbitration signal is exposed and contributes to the verdict.
    assert probe.binding.name == "binding_arbitration"
    assert probe.binding.ok, probe.binding.detail
    assert any(c.name == "binding_arbitration" for c in probe.checks)


def test_converted_count_is_int_in_range() -> None:
    """The independent actuation-count signal is an int in [0, 8] (R9.2)."""
    probe = evaluate()
    assert isinstance(probe.converted_count, int)
    assert 0 <= probe.converted_count <= 8
    # It mirrors the converted list, computed independently of the binding check.
    assert probe.converted_count == len(probe.converted)


def test_five_structural_invariants_present() -> None:
    """All five structural loop invariants are enforced as checks (R8.7)."""
    assert len(STRUCTURAL_INVARIANTS) == 5
    assert set(STRUCTURAL_INVARIANTS) == {
        "autonomous_trigger",
        "sensor_wired",
        "standing_world",
        "learn_from_world",
        "real_actuation",
    }
    probe = evaluate()
    check_names = {c.name for c in probe.checks}
    for invariant in STRUCTURAL_INVARIANTS:
        assert invariant in check_names, f"{invariant} missing from gate checks"


def test_ceiling_below_stub_count_fails_and_lists_stubs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ceiling below the stub count fails, surfacing the offending agents (R8.3).

    Real stubs are 0, so we simulate a regression by making ``_agent_actuation`` report a
    non-empty stub list; a ceiling below that count must fail and list the stubs.
    """
    monkeypatch.setattr(
        agency_truth,
        "_agent_actuation",
        lambda: (["inventory_sentinel"], ["pricing_oracle", "demand_prophet"]),
    )
    probe = agency_truth.evaluate(max_stubs=1)
    assert probe.ok is False
    # The offending stubs are surfaced for the operator.
    assert probe.stubs == ["pricing_oracle", "demand_prophet"]
    # And a ceiling that accommodates the count would pass the ratchet portion.
    assert agency_truth.evaluate(max_stubs=2).stubs == ["pricing_oracle", "demand_prophet"]


# ---------------------------------------------------------------------------
# R9.4: C57 reflects the probe verdict.
# ---------------------------------------------------------------------------


def _make_probe(
    ok: bool,
    *,
    binding_ok: bool = True,
    converted_count: int = 8,
    stubs: list[str] | None = None,
) -> Probe:
    return Probe(
        ok=ok,
        checks=[],
        converted=[],
        stubs=stubs if stubs is not None else [],
        max_stubs=0,
        converted_count=converted_count,
        binding=Check("binding_arbitration", binding_ok, ""),
    )


def test_c57_fails_on_argmax_regression(monkeypatch: pytest.MonkeyPatch) -> None:
    """An argmax regression (binding check fails → probe not ok) makes C57 FAIL (R9.4)."""
    monkeypatch.setattr(
        agency_truth,
        "evaluate",
        lambda *a, **k: _make_probe(False, binding_ok=False),
    )
    result = verify_claims.check_agency_loop()
    assert result.cid == "C57"
    assert result.status == "FAIL"


def test_c57_fails_on_under_eight_converted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fewer than 8 converted agents (probe not ok) makes C57 FAIL (R9.4)."""
    monkeypatch.setattr(
        agency_truth,
        "evaluate",
        lambda *a, **k: _make_probe(False, converted_count=7, stubs=["sustainability_agent"]),
    )
    result = verify_claims.check_agency_loop()
    assert result.status == "FAIL"


def test_c57_passes_on_healthy_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """A healthy probe (binding ok, all 8 converted, ok=True) makes C57 PASS (R9.4)."""
    monkeypatch.setattr(
        agency_truth,
        "evaluate",
        lambda *a, **k: _make_probe(True),
    )
    result = verify_claims.check_agency_loop()
    assert result.status == "PASS"
