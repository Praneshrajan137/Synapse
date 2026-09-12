"""The regret CLI's ``--json`` stdout is canonical JSON, and no twin log can reach it.

Feature: decision-quality-proof, session 5. Subject: ``uplift/regret.py::main``.

**THE DECLARATION THIS EXISTS TO MAKE TRUE.**
``infrastructure/quality/blocking-steps.yaml`` declares ``uplift.yml::twin-regret``'s
measure step ``role: producer`` with
``emits: "artifacts/uplift/twin-regret.json (canonical JSON, --json)"``. That step runs
``python -m uplift.regret --replicates 200 --hours 24 --json | tee
artifacts/uplift/twin-regret.json``, and on run ``34366766968`` it uploaded
**215,293,577 bytes**: the twin's ``structlog`` writes to stdout, so ``tee`` captured a
debug flood with the report on the final line and ``json.load`` raised
``JSONDecodeError: Extra data: line 1 column 5``. **The declaration was false as
written**, and tasks 17.x, 22.3 and 25 read that artifact with a JSON parser.

**Why a test rather than an inspection.** The artifact was wrong for one run and nothing
objected, because nothing asserted its shape. A declaration in a YAML file is not a
gate; this is (I-7: a gate that reports nothing is indistinguishable from one that
passes).

**The second test is the load-bearing one.** ``digital_twin/simulation/engine.py`` binds
its logger at MODULE scope (``logger = structlog.get_logger(__name__)``, line 22), which
happens at import -- *before* ``main`` reconfigures anything. So the interesting question
is not "does a fresh logger respect the new level" but "does a logger bound before
``configure()`` respect it". This module therefore binds its own logger at module scope,
exactly as the twin does, and asserts through that binding.

Not ``slow``-marked and it drives no twin: ``_measure`` is replaced, so the two-pass
comparator never runs and I-0's category-4 prohibition is not engaged. Locus is
``ci.yml::uplift-verify``'s fast step, which collects ``tests/uplift``.

Budget inherited from the root ``conftest.py`` profile. **No ``max_examples`` literal
here** (CF-13), and no total is asserted.

**Validates: the `emits:` declaration for uplift.yml::twin-regret's producer step.**
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
import structlog
from hypothesis import given
from hypothesis import strategies as st

from uplift import regret as regret_module

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

# Bound at MODULE scope, before `main` calls `structlog.configure`, exactly as
# `digital_twin/simulation/engine.py:22` binds its own. Rebinding it inside a test would
# test the easy case and miss the one that produced the 215 MB artifact.
_module_logger = structlog.get_logger(__name__)


@pytest.fixture(autouse=True)
def _restore_structlog_configuration() -> Iterator[None]:
    """Undo ``main``'s process-global ``structlog.configure`` after every test.

    ``structlog.configure`` is global state. Without this fixture a test that exercises
    the CLI would silence logging for every test that ran after it in the same session --
    a cross-test contamination that presents as an unrelated assertion mysteriously
    passing.
    """
    saved: dict[str, Any] = dict(structlog.get_config())
    try:
        yield
    finally:
        structlog.configure(**saved)


# ---------------------------------------------------------------------------
# A strategy over the report shapes `_measure` actually returns
# ---------------------------------------------------------------------------
# `_measure` returns one of four shapes: three `status: unavailable` early exits and the
# full `status: measured` report. All four carry heterogeneous values -- floats, ints,
# strings, lists and nested mappings -- and `main` serialises whatever it is handed. The
# strategy spans that variety rather than one hand-picked example, because the defect
# being closed was about the CHANNEL, which is indifferent to the payload.
_json_scalars = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-1_000_000, max_value=1_000_000),
    st.floats(allow_nan=False, allow_infinity=False, width=64),
    st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=40),
)
_report_values = st.one_of(
    _json_scalars,
    st.lists(_json_scalars, max_size=5),
    st.dictionaries(
        st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=8
        ),
        _json_scalars,
        max_size=4,
    ),
)
_reports = st.dictionaries(
    st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=16),
    _report_values,
    max_size=12,
)
_statuses = st.sampled_from(["measured", "unavailable"])


def _canonical(payload: Mapping[str, object]) -> str:
    """The one canonical form this repository commits to (CLAUDE.md conventions)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


@given(report=_reports, status=_statuses)
def test_json_stdout_is_a_single_parseable_canonical_document(
    report: dict[str, object],
    status: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--json`` emits exactly one canonical JSON document and nothing else.

    Three clauses, and the first is the one the 215 MB artifact violated:

    1. ``json.loads`` accepts the whole of stdout -- not its last line.
    2. stdout is ONE line, so a consumer that reads the stream has no trailing data.
    3. the bytes are the canonical form, so two runs of the same report compare equal.
    """
    payload = dict(report)
    payload["status"] = status
    monkeypatch.setattr(regret_module, "_measure", lambda _r, _h: payload)

    exit_code = regret_module.main(["--json", "--replicates", "1", "--hours", "0.5"])

    captured = capsys.readouterr().out
    # Clause 1: the WHOLE stream parses. `json.loads` on the last line would have passed
    # against the 215 MB artifact, which is why the assertion is over the whole stream.
    assert json.loads(captured) == json.loads(_canonical(payload))
    # Clause 2: one document, no trailing data.
    assert len([line for line in captured.splitlines() if line.strip()]) == 1
    # Clause 3: canonical bytes, not merely equivalent JSON.
    assert captured.strip() == _canonical(payload)
    assert exit_code == (0 if status == "measured" else 2)


def test_a_twin_log_line_cannot_reach_the_json_stream(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No log line at ANY level contaminates stdout, and every one still reaches stderr.

    This is the 215 MB defect reproduced in miniature, and the ``error`` clause is the
    one that took two attempts. ``_module_logger`` was bound at import, before ``main``
    reconfigures, which is the twin's own situation (``engine.py:22``). If the suppression
    were applied at the wrong time -- or applied to freshly bound loggers only -- this
    fails while the canonicality property still passes.

    **The first version of this test asserted only that sub-ERROR lines were absent, and
    that was a tolerated-exception disjunct.** With a level floor alone, canonicality held
    only while nothing logged at ERROR, so one bad replicate would have re-broken the
    artifact. Routing the logger factory to stderr makes the clause unconditional, and the
    stderr half of this assertion is what proves no diagnostic was traded away for it:
    ``| tee`` reads stdout only, so an ERROR line stays in the job log where a reader
    needs it while the pipe carries the measurement alone.
    """

    def _noisy_measure(_replicates: int, _hours: float) -> dict[str, object]:
        _module_logger.debug("twin_debug_flood", sku="sku_0", level=97.0)
        _module_logger.info("twin_info_flood", order_id="o-1")
        _module_logger.warning("twin_warning_flood", detail="restock")
        _module_logger.error("twin_error_line", detail="a replicate went wrong")
        return {"status": "measured", "regret": 1.5}

    monkeypatch.setattr(regret_module, "_measure", _noisy_measure)

    exit_code = regret_module.main(["--json", "--replicates", "1", "--hours", "0.5"])

    streams = capsys.readouterr()
    assert exit_code == 0
    # The pipe carries the measurement and nothing else, whatever the twin logged.
    assert json.loads(streams.out) == {"status": "measured", "regret": 1.5}
    for marker in ("twin_debug_flood", "twin_info_flood", "twin_warning_flood", "twin_error_line"):
        assert marker not in streams.out
    # Volume is gone: the three sub-ERROR lines are filtered, not merely redirected.
    for marker in ("twin_debug_flood", "twin_info_flood", "twin_warning_flood"):
        assert marker not in streams.err
    # Visibility is kept: the ERROR line is still readable in the job log.
    assert "twin_error_line" in streams.err
