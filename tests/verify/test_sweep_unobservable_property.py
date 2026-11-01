"""A sweep that could not observe reports that it could not observe, and exits non-zero.

Feature: decision-quality-proof, task 5.9. Requirements **R1.11, R1.16**.

The shape of the risk
---------------------

Every other property in this family is about a sweep that ran. This one is about the ways it
does not, and it exists because those are the paths where a non-passing result is easiest to
lose. A harness that raises leaves a job with a traceback and no verdict; one that returns
early leaves it with exit 0 and no probe. R1.11 names four conditions and R1.16 names a
fifth, and the obligation is identical for all five: **record a non-passing result, naming
the cause.**

The five conditions, and why each is separate
---------------------------------------------

1. **The sweep could not start.** An unreadable declaration, an unimportable Check_Registry,
   or an operating-system failure while copying the tree. Reported ``unavailable`` naming the
   cause -- never raised, because a step that aborts emits no status a job can gate on.
2. **The committed bound could not be read.** ``--sweep`` reads
   ``sweep_budget.per_subprocess_timeout_s`` and, absent a usable block, probes **nothing**.
   The refusal is the substantive half: ``DEFAULT_TIMEOUT_S`` is ten times the committed
   value, so a silent fallback would schedule 30 subprocesses against a bound the committed
   job budget cannot hold, and would do it invisibly (AD-22).
3. **A probe could not observe.** A timeout, an unstartable subprocess, or a
   signal-terminated one, each named separately, each ``indeterminate``, and any of them
   forcing the aggregate to ``unavailable``.
4. **The report could not be serialised.** A consumer that cannot parse the payload cannot
   tell a pass from a defect, so the run reports the serialisation failure rather than
   printing the fragment. The same reasoning covers a payload that could not be *written*:
   the sweep step promises its consumer a report, and C72 reports SKIP when it finds none, so
   a silent write failure would turn a real sweep into an invisible one.
5. **The baseline was suppressed.** ``--no-baseline`` stays available for diagnosis, but
   without a baseline an already-red gate stays red under mutation and reads as
   ``falsified`` -- which would turn the diagnostic mode into a machine for manufacturing
   proof (R1.16).

Every assertion below is on the **exit status** as well as the message, because the message
is what a human reads and the exit status is what the job gates on, and only one of the two
is load-bearing when nobody is looking.

Nothing here starts a process. ``sweep`` and ``evaluate`` are the harness's own seams; no
gate's evaluator is replaced (R9.5).

``max_examples`` is never set -- the budget comes from the root ``conftest.py`` profiles.

Locus: ``ci.yml::uplift-verify``'s fast step.

**Validates: Requirements 1.11, 1.16**
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
from pathlib import Path
from typing import Any, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import gate_fault_injection as gfi
from scripts.audit.gate_fault_injection import (
    EXIT_PASS,
    EXIT_UNAVAILABLE,
    MutationOperator,
    OperatorKind,
)
from tests.verify.sweep_strategies import (
    PROBE_DIR,
    SweepDraft,
    gate_runs,
    patched_sweep,
    probe_result,
    sweep_drafts,
)

REGISTERED_IDS: Final[tuple[str, ...]] = gfi.registered_ids()

#: The three ways one probe fails to observe, as ``(label, GateRun kwargs)``. Kept as data
#: so the "each is named separately" assertion is a loop over a declared set rather than
#: three copies of one assertion.
UNOBSERVABLE_RUNS: Final[tuple[tuple[str, dict[str, Any]], ...]] = (
    ("timeout", {"exit_code": None, "timed_out": True}),
    (
        "unstartable",
        {"exit_code": None, "output": "gate subprocess could not be started: ENOENT"},
    ),
    ("signalled", {"exit_code": -9}),
)


def _render(**kwargs: Any) -> tuple[int, str]:
    """Run the CLI and capture ``(exit code, stdout)``.

    The rendered output is asserted as well as the return code because a CI log is the only
    place a reader learns *which* of the five conditions fired.
    """
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = gfi.run(**kwargs)
    return code, stdout.getvalue()


# ---------------------------------------------------------------------------
# 1. The sweep could not start
# ---------------------------------------------------------------------------


@given(
    failure=st.sampled_from(
        (
            gfi.DeclarationError("declaration not found: infrastructure/quality/absent.yaml"),
            ImportError("no module named scripts.audit.verify_claims"),
            OSError(28, "No space left on device"),
        )
    ),
    as_json=st.booleans(),
)
def test_a_sweep_that_could_not_start_is_unavailable_and_never_raises(
    failure: Exception, as_json: bool
) -> None:
    """R1.11: a step that aborts emits no status a job can gate on.

    All three failures are raised from ``evaluate`` -- the point at which the declaration is
    read, the registry is imported and the tree is copied -- and all three must come back as
    exit 2 with the cause named. The JSON branch is asserted to stay canonical: a consumer
    parsing the payload has to be able to read the failure, so the failure path emits a
    document rather than prose.
    """

    def raising(**_kwargs: object) -> gfi.FaultInjectionReport:
        raise failure

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(gfi, "evaluate", raising)
        code, text = _render(as_json=as_json, probe=True)

    assert code == EXIT_UNAVAILABLE
    assert code != EXIT_PASS
    if as_json:
        payload = json.loads(text)
        assert text.strip() == json.dumps(payload, sort_keys=True, separators=(",", ":"))
        assert payload["verdict"] == "unavailable"
        assert str(failure).split(":")[0] in payload["reason"]
    else:
        assert "UNAVAILABLE" in text
        assert str(failure).split(":")[0] in text

    # An OSError is specifically "the sweep could not start" rather than a traceback a log
    # reader has to interpret: the tree copy precedes every probe, so a copy that fails has
    # learned nothing about any gate.
    if isinstance(failure, OSError):
        assert "could not start" in text


# ---------------------------------------------------------------------------
# 2. The committed bound could not be read
# ---------------------------------------------------------------------------


# Feature: decision-quality-proof, Property 40: A sweep that could not observe is non-passing
@given(draft=sweep_drafts(registered=REGISTERED_IDS, budget=False))
def test_a_sweep_with_no_committed_bound_probes_nothing_and_says_so(
    draft: SweepDraft,
) -> None:
    """R1.11 / AD-22: the refusal to default is the substantive half.

    ``DEFAULT_TIMEOUT_S`` is 900s against a committed 90s, so 30 subprocesses at the default
    is 7.5 hours against a 60-minute job. A silent fallback would schedule a sweep that
    cannot finish, and would schedule it invisibly. So the run reports what it could not
    read, having started nothing -- and the assertion that it started nothing is the one that
    matters, because a partial sweep under an impossible bound would report survivors that
    are really timeouts.
    """
    sentinel = probe_result(draft.declared[0], draft.declared_pairs[0][1], "falsified")

    with tempfile.TemporaryDirectory(prefix="sweep-unobservable-budget-") as tmp:
        declaration_path = draft.write(Path(tmp))
        with patched_sweep((sentinel,)) as seen:
            report = gfi.evaluate(
                declaration_path=declaration_path, schema_path=gfi.SCHEMA_FILE, probe=True
            )

    assert seen == [], "no sweep may be orchestrated when no bound could be read"
    assert report.probed is False
    assert report.results == ()
    assert report.sweep_timeout_s is None
    assert report.sweep_timeout_source == "not-probed"
    assert report.verdict == "unavailable"
    assert report.passing is False
    assert report.exit_code == EXIT_UNAVAILABLE
    assert gfi.SWEEP_BUDGET_KEY in report.reason
    assert f"{gfi.DEFAULT_TIMEOUT_S:.0f}s" in report.reason
    assert str(report.declared_operators) in report.reason


@given(draft=sweep_drafts(registered=REGISTERED_IDS), override=st.floats(1.0, 500.0))
def test_the_bound_that_was_applied_and_its_provenance_travel_with_the_report(
    draft: SweepDraft, override: float
) -> None:
    """R1.5, R1.11: "indeterminate naming the timeout" needs to say *whose* timeout.

    A report that says a gate exceeded its bound without carrying the bound, or without
    saying whether that bound was the committed one or a command-line override, leaves a
    reader unable to tell a slow gate from a mis-set flag. Both directions are asserted:
    the committed value with ``committed-budget`` provenance, and an override with
    ``explicit-override``, which the human report labels as *not* the committed budget.
    """
    results = tuple(
        probe_result(check, operator_id, "falsified")
        for check, operator_id in draft.declared_pairs
    )
    with tempfile.TemporaryDirectory(prefix="sweep-unobservable-bound-") as tmp:
        declaration_path = draft.write(Path(tmp))
        with patched_sweep(results) as seen:
            committed = gfi.evaluate(
                declaration_path=declaration_path, schema_path=gfi.SCHEMA_FILE, probe=True
            )
        assert seen[-1][3] == 90.0
        with patched_sweep(results) as seen:
            overridden = gfi.evaluate(
                declaration_path=declaration_path,
                schema_path=gfi.SCHEMA_FILE,
                probe=True,
                timeout=override,
            )
        assert seen[-1][3] == override

    assert committed.sweep_timeout_s == 90.0
    assert committed.sweep_timeout_source == "committed-budget"
    assert overridden.sweep_timeout_s == override
    assert overridden.sweep_timeout_source == "explicit-override"

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        gfi._print_report(overridden)
    rendered = stdout.getvalue()
    assert "NOT the committed budget" in rendered


# ---------------------------------------------------------------------------
# 3. A probe could not observe
# ---------------------------------------------------------------------------


@given(kind=st.sampled_from(tuple(label for label, _kwargs in UNOBSERVABLE_RUNS)))
def test_each_unobservable_probe_is_indeterminate_naming_which_condition_fired(
    kind: str,
) -> None:
    """R1.5, R1.11: three conditions, three details, and none of them a falsification.

    Run through the real classifier with the mutation really applied, so the assertion is
    about a probe that got as far as launching a gate and no further. The naming clause is
    the actionable half: a timeout is answered by raising the bound or sharding, an
    unstartable subprocess by fixing the environment, and a signal by looking at what killed
    it -- three repairs that a single "did not answer" message would collapse.
    """
    kwargs = dict(next(value for label, value in UNOBSERVABLE_RUNS if label == kind))
    operator = MutationOperator(
        id="probe-operator",
        operator=OperatorKind.CREATE_FILE,
        target=f"{PROBE_DIR}/planted.py",
        expect_names=("NAME_ALPHA",),
        body='"""Planted by the unobservable-sweep property."""\n',
    )

    with tempfile.TemporaryDirectory(prefix="sweep-unobservable-probe-") as tmp:
        tree = Path(tmp) / "synapse"
        (tree / PROBE_DIR).mkdir(parents=True)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                gfi,
                "run_gate",
                lambda check, _tree, **_kw: gate_runs(check, **kwargs),
            )
            result = gfi.falsifies(
                "C16", operator, tree=tree, baseline=gate_runs("C16", exit_code=0)
            )

    assert result.outcome == "indeterminate"
    assert result.falsified is False
    assert "nothing was proven" in result.detail
    expected_fragment = {
        "timeout": "per-subprocess bound",
        "unstartable": "could not be started",
        "signalled": "terminated by signal",
    }[kind]
    assert expected_fragment in result.detail
    # The other two conditions are NOT claimed, which is what makes the naming useful.
    for other, fragment in (
        ("timeout", "per-subprocess bound"),
        ("unstartable", "could not be started"),
        ("signalled", "terminated by signal"),
    ):
        if other != kind:
            assert fragment not in result.detail


@given(draft=sweep_drafts(registered=REGISTERED_IDS))
def test_one_unobservable_probe_makes_the_gating_step_non_passing(
    draft: SweepDraft,
) -> None:
    """R1.11: the aggregate cannot pass over an absence, however small the absence is.

    Exactly one operator reports ``indeterminate`` and every other falsifies. A sweep that
    averaged, or that treated an indeterminate probe as "no news", would return exit 0 here
    -- which is the single most expensive thing this whole requirement exists to prevent,
    because it is indistinguishable from a clean run.
    """
    pairs = draft.declared_pairs
    results = tuple(
        probe_result(check, operator_id, "indeterminate" if index == 0 else "falsified")
        for index, (check, operator_id) in enumerate(pairs)
    )

    with tempfile.TemporaryDirectory(prefix="sweep-unobservable-aggregate-") as tmp:
        declaration_path = draft.write(Path(tmp))
        with patched_sweep(results):
            report = gfi.evaluate(
                declaration_path=declaration_path, schema_path=gfi.SCHEMA_FILE, probe=True
            )

    assert report.verdict == "unavailable"
    assert report.exit_code == EXIT_UNAVAILABLE
    assert report.passing is False
    assert f"{pairs[0][0]}/{pairs[0][1]}" in report.reason
    assert pairs[0][0] not in report.falsified_ids
    assert pairs[0][0] not in report.pass_eligible_ids


# ---------------------------------------------------------------------------
# 4. The report could not be serialised, or could not be written
# ---------------------------------------------------------------------------


class _BrokenJson:
    """A ``json`` stand-in whose first ``dumps`` fails and whose later ones succeed.

    Replacing the module reference inside ``gate_fault_injection`` rather than patching the
    real ``json`` module: a global patch would break the very fallback path under test, and
    the fallback is the half that matters -- the run must report the serialisation failure
    instead of printing a fragment.
    """

    def __init__(self, error: Exception) -> None:
        self._error = error
        self.calls = 0

    def dumps(self, *args: object, **kwargs: object) -> str:
        self.calls += 1
        if self.calls == 1:
            raise self._error
        return json.dumps(*args, **kwargs)  # type: ignore[arg-type]

    def __getattr__(self, name: str) -> object:
        return getattr(json, name)


@given(
    error=st.sampled_from(
        (TypeError("Object of type set is not JSON serializable"), ValueError("circular"))
    )
)
def test_a_report_that_cannot_be_serialised_reports_that_and_emits_no_fragment(
    error: Exception,
) -> None:
    """R1.11: a half-written payload is worse than none.

    A consumer reading a truncated document cannot distinguish a pass from a defect, and the
    consumer here is C72's registry row. So the failure is reported as a failure, in a
    document the consumer *can* parse, and the exit status is non-passing.
    """
    broken = _BrokenJson(error)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(gfi, "json", broken)
        code, text = _render(as_json=True)

    assert code == EXIT_UNAVAILABLE
    payload = json.loads(text)
    assert payload["verdict"] == "unavailable"
    assert "could not be serialised" in payload["reason"]
    assert broken.calls >= 2, "the fallback document must itself be emitted"


def test_a_report_that_cannot_be_written_is_unavailable_naming_the_path() -> None:
    """R1.11, R1.12: the sweep step promises its consumer a report.

    C72 keeps its unprobed detail and reports SKIP when it finds no payload. A write failure
    that exited 0 would therefore produce a green sweep beside a registry row saying nothing
    was probed -- two statements about one run that contradict each other, with no way for a
    reader to tell which is true.

    The unwritable path is a *directory* standing where the file should be, which
    ``mkdir(parents=True, exist_ok=True)`` cannot resolve and ``write_text`` refuses. No
    permission bits are changed, so the case is reproducible on every platform.
    """
    with tempfile.TemporaryDirectory(prefix="sweep-unobservable-write-") as tmp:
        blocked = Path(tmp) / "report.json"
        blocked.mkdir()
        code, text = _render(as_json=False, report_json=blocked)

    assert code == EXIT_UNAVAILABLE
    assert "could not be written" in text
    assert "report.json" in text


# ---------------------------------------------------------------------------
# 5. The baseline was suppressed
# ---------------------------------------------------------------------------


@given(as_json=st.booleans())
def test_the_gating_step_exits_non_zero_when_the_baseline_is_suppressed(
    as_json: bool,
) -> None:
    """R1.16: the diagnostic mode may not be able to produce a pass.

    Asserted through the CLI against the **committed** declaration, because that is the
    invocation an operator would reach for and the one that must not be usable as evidence.
    ``--no-baseline`` is ahead of every other verdict rule, including declaration defects,
    which stay visible in the findings either way: a report produced without a baseline
    cannot support any verdict about a gate, so it reports the one thing it does know.
    """
    code, text = _render(as_json=as_json, probe=False, with_baseline=False)

    assert code == EXIT_UNAVAILABLE
    assert code != EXIT_PASS
    if as_json:
        payload = json.loads(text)
        assert payload["verdict"] == "unavailable"
        assert payload["baseline_suppressed"] is True
        assert payload["falsified_ids"] == []
        assert payload["pass_eligible_ids"] == []
        assert "baseline" in payload["reason"]
    else:
        assert "BASELINE SUPPRESSED" in text
        assert "reads as falsified" in text


def test_every_unobservable_path_shares_one_exit_status_and_it_is_not_pass() -> None:
    """The unifying claim, asserted once rather than implied five times.

    R1.11's four conditions and R1.16's fifth have different causes, different messages and
    different repairs. What they have in common is the only thing a job can act on: the exit
    status is ``2``, ``2`` is not ``0``, and the module's own mapping says so. A vocabulary
    that let any of them reach ``EXIT_PASS`` would make the distinctions above decorative.
    """
    assert gfi.EXIT_UNAVAILABLE != gfi.EXIT_PASS
    assert gfi._EXIT_CODES["unavailable"] == gfi.EXIT_UNAVAILABLE
    assert set(gfi._EXIT_CODES) == {"pass", "fail", "unavailable"}
    # Only `pass` maps to the passing exit status; the other two are the non-passing states
    # every condition above lands in.
    for verdict, expected in (("pass", True), ("fail", False), ("unavailable", False)):
        assert (gfi._EXIT_CODES[verdict] == gfi.EXIT_PASS) is expected


def test_the_unobservable_reason_is_none_exactly_when_the_run_observed() -> None:
    """The classifier's precondition: "unobservable" is decided, never defaulted.

    If :func:`unobservable_reason` returned a string for an ordinary non-zero exit, every
    falsification in the tree would silently become ``indeterminate`` and the sweep would
    report that it can never learn anything. The negative direction is therefore as
    load-bearing as the positive one.
    """
    bound = 90.0
    for exit_code in (0, 1, 2, 5, 130):
        assert gfi.unobservable_reason(gate_runs("C16", exit_code=exit_code), timeout=bound) is None
    for _label, kwargs in UNOBSERVABLE_RUNS:
        run = gate_runs("C16", **kwargs)
        assert gfi.unobservable_reason(run, timeout=bound) is not None
