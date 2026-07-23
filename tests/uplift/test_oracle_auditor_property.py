"""Property-based tests for the ``oracle_truth`` docstring-body auditor.

Feature: decision-integrity-uplift-proof
Property 24: The oracle auditor flags exactly the docstring-body mismatches.

    *For any* ``tests/oracle/`` test, the auditor flags it as a docstring-body
    mismatch if and only if the test has a non-empty docstring describing a
    measurable outcome for which the body contains no assertion referencing that
    outcome; it never flags a test with no docstring or a docstring describing no
    measurable outcome; and its ``--check`` mode exits non-zero if and only if at
    least one unresolved mismatch remains.

Validates: Requirements 8.2, 8.4, 8.7

Strategy: synthesize a single-test module for one of four controlled categories
and run the real auditor (``scan_module`` / ``run``) over it. The categories
partition the input space that the IFF condition ranges over:

  1. ``no_doc``             — no docstring                    -> never flagged (8.7)
  2. ``non_measurable``     — docstring, no measurable outcome -> never flagged (8.7)
  3. ``measurable_asserted``— measurable outcome IS asserted   -> not flagged   (8.2)
  4. ``measurable_unasserted`` — measurable outcome NOT asserted -> flagged     (8.2)

The synthetic source is generated from Hypothesis-chosen pieces (the domain
term + the category) so the auditor's verdict can be predicted exactly.
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.audit import oracle_truth as ot

# ---------------------------------------------------------------------------
# Strategies — a curated set of domain outcome terms (>= 4 alpha chars, none of
# them auditor stopwords or scaffolding words) and the four IFF categories.
# ---------------------------------------------------------------------------
_DOMAIN_TERMS = [
    "revenue",
    "carbon",
    "margin",
    "stockout",
    "emissions",
    "latency",
    "profit",
    "freight",
]
_domain_term = st.sampled_from(_DOMAIN_TERMS)
_category = st.sampled_from(
    ["no_doc", "non_measurable", "measurable_asserted", "measurable_unasserted"]
)


def _build_module(category: str, term: str) -> str:
    """Return valid Python source for a single ``test_synth`` in ``category``.

    The measurable docstring carries a percentage ("within 20%") so the
    auditor's ``_is_measurable`` heuristic fires; the domain ``term`` is the
    outcome word whose presence/absence in an assertion decides the flag.
    """
    if category == "no_doc":
        # No docstring at all — 8.7: must never be flagged.
        return "def test_synth():\n    assert True\n"

    if category == "non_measurable":
        # Docstring present but describes no measurable outcome (no number, no
        # comparator, no bound keyword) — 8.7: must never be flagged.
        return (
            "def test_synth():\n"
            f'    """Checks the {term} pipeline stays healthy."""\n'
            "    assert True\n"
        )

    # Both measurable categories share the same measurable docstring.
    doc = (
        f'    """{term.capitalize()} impact is within 20% of the '
        'predicted delta."""\n'
    )
    if category == "measurable_asserted":
        # Body asserts a name carrying the domain term -> outcome IS referenced.
        body = (
            f"    measured_{term} = 0.1\n"
            f"    assert measured_{term} <= 0.2\n"
        )
    else:  # measurable_unasserted
        # Body only asserts scaffolding (scenario count) -> outcome NOT
        # referenced. This is R8.1's exact failure mode.
        body = "    n_scenarios = 1000\n    assert n_scenarios == 1000\n"
    return "def test_synth():\n" + doc + body


def _expected_flag(category: str) -> bool:
    """The IFF verdict: only the measurable-but-unasserted case is a mismatch."""
    return category == "measurable_unasserted"


# ---------------------------------------------------------------------------
# Property 24 (IFF): the flag equals the measurable-but-unasserted condition.
# ---------------------------------------------------------------------------
@settings(max_examples=200)
@given(category=_category, term=_domain_term)
def test_flag_iff_measurable_unasserted(
    category: str, term: str, tmp_path, monkeypatch
) -> None:
    """scan_module flags a test IFF a measurable docstring is left unasserted."""
    # ``scan_module`` derives node ids via ``path.relative_to(ROOT)``; point ROOT
    # at the temp dir so the synthetic module resolves cleanly.
    monkeypatch.setattr(ot, "ROOT", tmp_path)
    path = tmp_path / "test_synth.py"
    path.write_text(_build_module(category, term), encoding="utf-8")

    report = ot.scan_module(path)
    assert len(report.tests) == 1
    tr = report.tests[0]

    flagged = tr.mismatch is not None
    assert flagged is _expected_flag(category)

    # 8.7: a test with no docstring is never measurable and never flagged.
    if category == "no_doc":
        assert tr.has_docstring is False
        assert tr.measurable is False
        assert flagged is False

    # 8.7: a docstring with no measurable outcome is never flagged.
    if category == "non_measurable":
        assert tr.has_docstring is True
        assert tr.measurable is False
        assert flagged is False

    # Both measurable categories are detected as measurable (8.2 precondition).
    if category in ("measurable_asserted", "measurable_unasserted"):
        assert tr.has_docstring is True
        assert tr.measurable is True

    # 8.2: an asserted measurable outcome is NOT a mismatch.
    if category == "measurable_asserted":
        assert flagged is False

    # 8.2/8.3: when flagged, the unasserted domain term is reported.
    if flagged:
        assert term in tr.mismatch.unasserted_terms


# ---------------------------------------------------------------------------
# Property 24 (--check IFF): exit non-zero iff >= 1 unresolved mismatch remains.
# ---------------------------------------------------------------------------
@settings(max_examples=100)
@given(category=_category, term=_domain_term)
def test_check_exit_code_tracks_mismatch(
    category: str, term: str, tmp_path, monkeypatch, capsys
) -> None:
    """run(check=True) exits 1 iff the scanned oracle dir holds a mismatch (8.4)."""
    oracle = tmp_path / "tests" / "oracle"
    oracle.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ot, "ROOT", tmp_path)
    monkeypatch.setattr(ot, "ORACLE_DIR", oracle)
    (oracle / "test_case.py").write_text(
        _build_module(category, term), encoding="utf-8"
    )

    exit_code = ot.run(check=True)
    capsys.readouterr()  # swallow report output

    if _expected_flag(category):
        assert exit_code == 1
    else:
        assert exit_code == 0


# ---------------------------------------------------------------------------
# Property 24 (--check, no mismatches): an oracle dir with no flagged test — or
# no tests at all — exits zero (8.4 'exits zero when none remain').
# ---------------------------------------------------------------------------
def test_check_exits_zero_when_no_mismatches(tmp_path, monkeypatch, capsys) -> None:
    """A clean oracle dir (only asserted outcomes) exits zero under --check."""
    oracle = tmp_path / "tests" / "oracle"
    oracle.mkdir(parents=True)
    monkeypatch.setattr(ot, "ROOT", tmp_path)
    monkeypatch.setattr(ot, "ORACLE_DIR", oracle)
    (oracle / "test_ok.py").write_text(
        _build_module("measurable_asserted", "revenue"), encoding="utf-8"
    )
    assert ot.run(check=True) == 0
    capsys.readouterr()


def test_check_exits_zero_when_no_tests(tmp_path, monkeypatch, capsys) -> None:
    """An oracle dir with no test modules has no mismatch and exits zero."""
    oracle = tmp_path / "tests" / "oracle"
    oracle.mkdir(parents=True)
    monkeypatch.setattr(ot, "ROOT", tmp_path)
    monkeypatch.setattr(ot, "ORACLE_DIR", oracle)
    assert ot.run(check=True) == 0
    capsys.readouterr()


# ---------------------------------------------------------------------------
# Property 24 (non-check mode): run() without --check always returns 0, even
# when a mismatch is present — only --check is the gate (8.4).
# ---------------------------------------------------------------------------
def test_run_without_check_returns_zero_despite_mismatch(
    tmp_path, monkeypatch, capsys
) -> None:
    """Without --check the auditor reports but never fails (0), even on a mismatch."""
    oracle = tmp_path / "tests" / "oracle"
    oracle.mkdir(parents=True)
    monkeypatch.setattr(ot, "ROOT", tmp_path)
    monkeypatch.setattr(ot, "ORACLE_DIR", oracle)
    (oracle / "test_flagged.py").write_text(
        _build_module("measurable_unasserted", "revenue"), encoding="utf-8"
    )
    # A mismatch exists...
    assert len(ot.all_mismatches(ot.collect())) == 1
    capsys.readouterr()
    # ...but non-check mode still returns 0.
    assert ot.run(check=False) == 0
    capsys.readouterr()
