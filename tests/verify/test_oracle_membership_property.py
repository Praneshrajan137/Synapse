"""Property-based test for oracle-layer membership (design E2.3; R12.1, R12.2, R12.5, R12.6).

Feature: purpose-achievement-audit, Property 37: Oracle-layer membership is earned, not
declared

    *For any* test declaring an oracle subject, membership in the Oracle layer holds iff
    the test imports that subject and invokes it on the path producing the asserted value
    **and** the reference value is computed without executing the implementation under
    test; a closed-form restatement of the implementation is rejected from the layer
    regardless of the test's file path or title; and an allowlisted docstring/assertion
    mismatch is accepted only with both a dated rationale and a stated removal condition.

Why a property and not examples. The audit's finding here is not that one test was wrong;
it is that *nothing was measuring*. ``tests/oracle/`` was the Oracle layer because of its
path, and each module was an oracle for an agent because of its title, so the layer's
membership was whatever its authors said it was. Examples cannot express the repair,
because the repair is a rule about *all* tests: any future module dropped into the suite
with a confident title must be judged by the same observations. So the driver is a
*generated oracle suite* - Python modules rendered from a draft whose knobs are the ground
truth (does it import the subject, does it call it, does the called value reach an
``assert``, is the reference side independent, does the tolerance bound anything) - and the
auditor has to rediscover every one of those facts from the AST alone. Agreement is the
derivation rediscovering something it was not told. A title and a file name are generated
too, precisely so they can be shown to buy nothing (R12.6).

The four predicates are not symmetrical, and this file keeps them apart on purpose.
Membership is granted by three of them plus a declared subject
(``OracleSubject.earned``); the fourth, ``tolerance_constraining``, is a separate R12.7
finding. So a test *can* earn membership and still leave the gate non-passing, because
agreement inside a bound wide enough to admit a two-fold error proves nothing (I-7). That
combination is asserted explicitly below - it is the case a "membership implies pass" gate
would silently swallow.

Totality is asserted as firmly as the positive cases. Every test function in the suite
yields exactly one classification; a registered oracle is either a member or carries at
least one membership finding, never neither and never both; an unregistered test is never
promoted into the layer by proximity; and an empty suite or an unreadable layer
configuration is ``unavailable``, never ``pass`` (I-7 - absence of proof is not proof).

Ground truth. Every expectation is recomputed from the draft with the R12 clauses restated
from ``requirements.md``, so the test compares two implementations of the same rule rather
than asking the auditor to agree with itself. Tolerance bounds are drawn around the ceiling
committed in ``infrastructure/quality/oracle-layers.yaml`` and the layer numbers are read
out of its ``layer_names`` table, so no threshold and no layer index is a literal here.

Hermetic roots. ``oracle_truth`` resolves node ids with ``path.relative_to(ROOT)`` and
discovers modules by globbing ``ORACLE_DIR``; neither is a parameter, so
:func:`synthetic_suite` rebinds exactly those two module globals for the duration of one
example and restores them in a ``finally``. Nothing is written inside the working tree, and
the generated modules are *parsed, never imported* - they name ``agents.pricing_oracle``
and ``digital_twin`` without either package being loaded.

I-0: this test parses small generated files. It imports no agent, drives no twin, and runs
no subprocess and no suite, so it is deliberately **not** ``slow``-marked. ``max_examples``
is never set here - the budget comes from the root ``conftest.py`` profiles (``dev``=10,
``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 12.1, 12.2, 12.5, 12.6**
"""

from __future__ import annotations

import ast
import contextlib
import dataclasses
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import oracle_truth as ot
from tests.verify.strategies import threshold_sequences

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

#: How a generated test registers itself in the topology.
MarkerKind = Literal["oracle", "metamorphic", "none"]

#: What the module does with the subject it imported.
InvocationKind = Literal["asserted", "called-unasserted", "imported-unused"]

#: Where the value the subject is judged against comes from.
ReferenceKind = Literal["independent", "literal-only", "closed-form-admission"]

# ---------------------------------------------------------------------------
# Everything numeric or layer-shaped is read from the committed configuration
# ---------------------------------------------------------------------------

#: The committed layer configuration. Loaded once: a gate that cannot read its own
#: ceiling has no verdict to give, so an unreadable file must break this file loudly
#: rather than let the properties run against a ceiling nobody committed.
CONFIG: Final[ot.OracleLayerConfig] = ot.load_config()


def _layer_named(label: str) -> int:
    """The layer number the committed vocabulary gives *label* (never a literal)."""
    for number, name in CONFIG.layer_names.items():
        if name == label:
            return int(number)
    raise AssertionError(f"oracle-layers.yaml declares no '{label}' layer to register into")


#: The layer a ``@pytest.mark.oracle`` test declares, per the committed configuration.
ORACLE_LAYER: Final[int] = CONFIG.oracle_layer

#: The layer a rejected oracle must register in instead (R12.2, R12.6).
METAMORPHIC_LAYER: Final[int] = _layer_named("Metamorphic")

#: The ceiling a declared tolerance must sit strictly inside to constrain (R12.7).
CEILING: Final[float] = CONFIG.tolerance_ceiling

#: A bound comfortably inside the ceiling, used when a draft must earn a clean pass.
CONSTRAINING_BOUND: Final[float] = round(CEILING / 2.0, 2)

#: Drawn tolerance bounds straddle the ceiling, so both sides of R12.7 are reachable and
#: the boundary itself (bound == ceiling, which is *not* inside it) is generated.
TOLERANCE_LOW: Final[float] = 0.01
TOLERANCE_HIGH: Final[float] = round(CEILING * 2.0, 2)

# ---------------------------------------------------------------------------
# The generated suite's vocabulary
# ---------------------------------------------------------------------------

#: The subject a generated test names. The committed Layer 6 oracle names the same
#: package, so a generated module is indistinguishable from a real one to the derivation.
SUBJECT: Final[str] = "agents.pricing_oracle"

#: An import *under* the subject - the derivation must accept a submodule of the named
#: package, which is how the committed oracle imports its served elasticity path.
SUBJECT_IMPORT: Final[str] = (
    "from agents.pricing_oracle.inference.serving_model import LinearElasticityModel"
)

#: The import a test carries when it names a subject it never brought into scope: the
#: twin, and only the twin. This is exactly the shape the audit found (R12.1).
DECOY_IMPORT: Final[str] = "from digital_twin.simulation.monte_carlo import MonteCarloRunner"

#: The module-level constant a generated tolerance bound is declared as.
TOLERANCE_SYMBOL: Final[str] = "GENERATED_TOLERANCE"

#: Directory the generated suite lives in, relative to the generated root. Deliberately
#: *not* ``tests/oracle`` so no generated node id can collide with a committed allowlist
#: entry and be excused by it.
GENERATED_DIR: Final[str] = "generated"

MARKERS: Final[tuple[MarkerKind, ...]] = ("oracle", "metamorphic", "none")
INVOCATIONS: Final[tuple[InvocationKind, ...]] = (
    "asserted",
    "called-unasserted",
    "imported-unused",
)
REFERENCES: Final[tuple[ReferenceKind, ...]] = (
    "independent",
    "literal-only",
    "closed-form-admission",
)

#: The findings that decide *membership*. ``tolerance-unconstraining`` is excluded on
#: purpose: it is a non-passing finding about the strength of a bound, not about whether
#: the test has standing to judge its subject.
MEMBERSHIP_RULES: Final[frozenset[str]] = frozenset(
    {
        "oracle-subject-undeclared",
        "oracle-subject-not-invoked",
        "oracle-reference-not-independent",
        "oracle-claim-unearned",
    }
)

#: Exit status per verdict. ``2`` is non-passing just as ``1`` is (I-7).
EXPECTED_EXIT: Final[dict[str, int]] = {"pass": 0, "fail": 1, "unavailable": 2}

#: Verdicts that are not a pass, named so the assertions can say what they mean.
NON_PASSING: Final[tuple[str, ...]] = ("fail", "unavailable")


# ---------------------------------------------------------------------------
# One generated oracle-suite module
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubjectDraft:
    """One generated test, and the ground truth of what it does.

    Every ``expected_*`` property below is computed from the knobs alone - never from the
    auditor - so the assertions compare the derivation against the module's actual
    behaviour rather than against itself. The ``effective_*`` properties exist because a
    bare ``@pytest.mark.oracle`` carries no keywords at all: they keep the ground truth
    and the rendering in step even after a ``dataclasses.replace``.
    """

    index: int = 0
    marker: MarkerKind = "oracle"
    marker_called: bool = True
    declares_subject: bool = True
    layer_kwarg: int | None = None
    imports_subject_module: bool = True
    invocation: InvocationKind = "asserted"
    reference: ReferenceKind = "independent"
    tolerance_bound: float | None = CONSTRAINING_BOUND
    tolerance_in_assert: bool = True
    title_claims_oracle: bool = True
    file_name_claims_oracle: bool = True
    marker_on_class: bool = True

    # -- identity -----------------------------------------------------------

    @property
    def module_name(self) -> str:
        suffix = "_oracle" if self.file_name_claims_oracle else ""
        return f"test_case_{self.index}{suffix}.py"

    @property
    def class_name(self) -> str:
        return f"TestGeneratedCase{self.index}"

    @property
    def test_name(self) -> str:
        return "test_generated_case"

    @property
    def node_id(self) -> str:
        return f"{GENERATED_DIR}/{self.module_name}::{self.class_name}::{self.test_name}"

    # -- what the rendered decorator actually carries ------------------------

    @property
    def renders_oracle_keywords(self) -> bool:
        """A bare ``@pytest.mark.oracle`` declares neither a subject nor a layer."""
        return self.marker != "oracle" or self.marker_called

    @property
    def effective_layer_kwarg(self) -> int | None:
        if self.marker == "none" or not self.renders_oracle_keywords:
            return None
        return self.layer_kwarg

    # -- the four predicates, as ground truth -------------------------------

    @property
    def declared_subject(self) -> str:
        """A subject is declared only by ``@pytest.mark.oracle(subject=...)``."""
        if self.marker != "oracle" or not self.renders_oracle_keywords:
            return ""
        return SUBJECT if self.declares_subject else ""

    @property
    def expected_layer(self) -> int | None:
        """The layer the registration declares; ``None`` when nothing registers it."""
        if self.marker == "none":
            return None
        kwarg = self.effective_layer_kwarg
        if kwarg is not None:
            return kwarg
        return ORACLE_LAYER if self.marker == "oracle" else METAMORPHIC_LAYER

    @property
    def registered_oracle(self) -> bool:
        return self.expected_layer == ORACLE_LAYER

    @property
    def expected_imports(self) -> bool:
        """R12.1's first half: the named subject is actually brought into scope."""
        return bool(self.declared_subject) and self.imports_subject_module

    @property
    def expected_invokes(self) -> bool:
        """R12.1's second half: a value from *calling* the subject reaches an assert."""
        return self.expected_imports and self.invocation == "asserted"

    @property
    def expected_reference_independent(self) -> bool:
        """R12.2: the reference is neither the subject's own output nor an admitted
        closed-form restatement of the quantity being compared."""
        return self.reference == "independent"

    @property
    def expected_tolerance_constraining(self) -> bool | None:
        """R12.7, three-valued: ``None`` means no bound was declared *and* asserted."""
        if self.tolerance_bound is None or not self.tolerance_in_assert:
            return None
        return 0.0 < self.tolerance_bound < CEILING

    @property
    def expected_tolerance_name(self) -> str | None:
        return TOLERANCE_SYMBOL if self.expected_tolerance_constraining is not None else None

    @property
    def expected_tolerance_bound(self) -> float | None:
        return self.tolerance_bound if self.expected_tolerance_constraining is not None else None

    @property
    def expected_earned(self) -> bool:
        """Membership, restated from design Property 37: three predicates, no title."""
        return (
            bool(self.declared_subject)
            and self.expected_imports
            and self.expected_invokes
            and self.expected_reference_independent
        )

    @property
    def expected_member(self) -> bool:
        """Earned *and* registered in the Oracle layer."""
        return self.expected_earned and self.registered_oracle

    # -- rendering ----------------------------------------------------------

    def marker_line(self) -> str | None:
        """The registration decorator, in the shape the committed suite uses."""
        if self.marker == "none":
            return None
        if self.marker == "metamorphic":
            keywords = "" if self.layer_kwarg is None else f"layer={self.layer_kwarg}"
            return f"@pytest.mark.metamorphic({keywords})"
        if not self.marker_called:
            return "@pytest.mark.oracle"
        parts: list[str] = []
        if self.declares_subject:
            parts.append(f'subject="{SUBJECT}"')
        if self.layer_kwarg is not None:
            parts.append(f"layer={self.layer_kwarg}")
        return f"@pytest.mark.oracle({', '.join(parts)})"

    def body_lines(self) -> list[str]:
        """The test body: a subject half, a reference half, and one assertion."""
        lines: list[str] = []
        renders_subject = self.imports_subject_module and self.invocation != "imported-unused"
        if renders_subject:
            lines.append("model = LinearElasticityModel(weights=[0.1], bias=0.2)")
            lines.append("predicted = float(model.estimate_elasticity(0.5))")

        if self.reference == "literal-only":
            lines.append("computed_gap = 0.25")
            compared = "computed_gap"
        else:
            if self.reference == "closed-form-admission":
                # The specimen R12.2 was written from: a test admitting, in its own
                # words, that its reference is the compared quantity restated.
                lines.append("# The reference is the twin's own behaviour in closed form.")
            lines.append("observed_ratio = twin_batch()")
            compared = "observed_ratio"

        bound = TOLERANCE_SYMBOL if self.tolerance_in_assert else "0.10"
        if renders_subject and self.invocation == "asserted":
            lines.append(f"assert abs(predicted - {compared}) <= {bound}")
        else:
            lines.append(f"assert abs({compared} - 1.0) <= {bound}")
        return lines

    def render(self) -> str:
        """The whole module, as text the auditor parses and never imports."""
        title = (
            f"Oracle Layer {ORACLE_LAYER}: generated case {self.index} vs the twin."
            if self.title_claims_oracle
            else f"Generated case {self.index}: a comparison against the twin."
        )
        lines: list[str] = [
            f'"""{title}"""',
            "from __future__ import annotations",
            "",
            "import pytest",
            "",
            SUBJECT_IMPORT if self.imports_subject_module else DECOY_IMPORT,
            "",
        ]
        if self.tolerance_bound is not None:
            lines += [f"{TOLERANCE_SYMBOL} = {self.tolerance_bound!r}", ""]
        lines += [
            "",
            "def twin_batch() -> float:",
            '    """The reference side. This module is parsed, never executed."""',
            "    return 1.0",
            "",
            "",
        ]
        marker = self.marker_line()
        if marker is not None and self.marker_on_class:
            lines.append(marker)
        lines.append(f"class {self.class_name}:")
        if marker is not None and not self.marker_on_class:
            lines.append(f"    {marker}")
        lines.append(f"    def {self.test_name}(self) -> None:")
        lines.append(f'        """Generated case {self.index}."""')
        lines += [f"        {statement}" for statement in self.body_lines()]
        lines.append("")
        return "\n".join(lines)


@st.composite
def subject_drafts(
    draw: st.DrawFn,
    *,
    markers: Sequence[MarkerKind] = MARKERS,
    declares_subject: bool | None = None,
    imports_subject: bool | None = None,
    invocations: Sequence[InvocationKind] = INVOCATIONS,
    references: Sequence[ReferenceKind] = REFERENCES,
    tolerance: Literal["drawn", "in-assert", "absent"] = "drawn",
) -> SubjectDraft:
    """One generated oracle-suite test.

    Every knob is a *pin*, not a filter: pinning is how a property isolates one clause
    (``markers=("oracle",)`` for the registered-oracle clauses, ``invocations`` for
    R12.1) without a ``.filter`` that would reject most draws and trip Hypothesis'
    ``filter_too_much`` health check.
    """
    marker = draw(st.sampled_from(tuple(markers)))
    declares = draw(st.booleans()) if declares_subject is None else declares_subject
    layer_kwarg = (
        draw(st.sampled_from((None, ORACLE_LAYER, METAMORPHIC_LAYER))) if marker != "none" else None
    )
    imports = draw(st.booleans()) if imports_subject is None else imports_subject
    invocation = draw(st.sampled_from(tuple(invocations)))
    if not imports:
        # Nothing was brought into scope, so there is nothing to call: keep the draft's
        # ground truth and its rendering in step.
        invocation = "imported-unused"

    bound = draw(
        threshold_sequences(min_size=1, max_size=1, low=TOLERANCE_LOW, high=TOLERANCE_HIGH)
    )[0]
    if tolerance == "absent":
        declared_bound: float | None = None
        in_assert = False
    elif tolerance == "in-assert":
        declared_bound, in_assert = bound, True
    else:
        declared_bound = bound if draw(st.booleans()) else None
        in_assert = declared_bound is not None and draw(st.booleans())

    return SubjectDraft(
        marker=marker,
        marker_called=declares or layer_kwarg is not None or draw(st.booleans()),
        declares_subject=declares,
        layer_kwarg=layer_kwarg,
        imports_subject_module=imports,
        invocation=invocation,
        reference=draw(st.sampled_from(tuple(references))),
        tolerance_bound=declared_bound,
        tolerance_in_assert=in_assert,
        title_claims_oracle=draw(st.booleans()),
        file_name_claims_oracle=draw(st.booleans()),
        marker_on_class=draw(st.booleans()),
    )


def earning_drafts() -> st.SearchStrategy[SubjectDraft]:
    """Drafts that earn membership: registered Oracle, subject imported and invoked."""
    return subject_drafts(
        markers=("oracle",),
        declares_subject=True,
        imports_subject=True,
        invocations=("asserted",),
        references=("independent",),
        tolerance="in-assert",
    ).map(lambda draft: dataclasses.replace(draft, layer_kwarg=ORACLE_LAYER, marker_called=True))


# ---------------------------------------------------------------------------
# The hermetic suite
# ---------------------------------------------------------------------------


def numbered(drafts: Sequence[SubjectDraft]) -> tuple[SubjectDraft, ...]:
    """Re-index *drafts* so every generated module lands on its own file name."""
    return tuple(
        dataclasses.replace(draft, index=position) for position, draft in enumerate(drafts)
    )


@contextlib.contextmanager
def synthetic_suite(drafts: Sequence[SubjectDraft]) -> Iterator[Path]:
    """Render *drafts* into a throwaway suite and point the auditor's roots at it.

    ``derive_module_subjects`` resolves node ids with ``path.relative_to(ROOT)`` and
    ``derive_subjects`` discovers modules by globbing ``ORACLE_DIR``. Neither is a
    parameter, so the only way to evaluate generated modules *without* writing into the
    working tree is to rebind those two globals for one example. They are restored in a
    ``finally``, so a failing example cannot leak a root into the next test, and the
    directory is removed on the way out.
    """
    with tempfile.TemporaryDirectory(prefix="oracle-membership-") as tmp:
        root = Path(tmp)
        directory = root / GENERATED_DIR
        directory.mkdir(parents=True)
        for draft in drafts:
            (directory / draft.module_name).write_text(draft.render(), encoding="utf-8")
        previous_root, previous_dir = ot.ROOT, ot.ORACLE_DIR
        ot.ROOT, ot.ORACLE_DIR = root, directory
        try:
            yield directory
        finally:
            ot.ROOT, ot.ORACLE_DIR = previous_root, previous_dir


def subject_for(subjects: tuple[ot.OracleSubject, ...], node_id: str) -> ot.OracleSubject:
    """The single classification for *node_id*; the derivation must emit exactly one."""
    matching = [subject for subject in subjects if subject.node_id == node_id]
    assert len(matching) == 1, f"expected one classification for {node_id}, got {len(matching)}"
    return matching[0]


def rules_for(findings: tuple[ot.Finding, ...], node_id: str) -> frozenset[str]:
    """The rules the auditor reported against *node_id*."""
    return frozenset(finding.rule for finding in findings if finding.node_id == node_id)


def detail_for(findings: tuple[ot.Finding, ...], node_id: str, rule: str) -> str:
    """The finding text for one (node, rule) pair - where the naming obligation lands."""
    for finding in findings:
        if finding.node_id == node_id and finding.rule == rule:
            return finding.detail
    raise AssertionError(f"{node_id} carries no {rule} finding: {findings}")


# ---------------------------------------------------------------------------
# The independent recompute of R12
# ---------------------------------------------------------------------------


def expected_rules(draft: SubjectDraft) -> frozenset[str]:
    """Every finding R12 mandates for one draft, restated from ``requirements.md``.

    Written out here rather than imported from the auditor, so a disagreement means one of
    two implementations of the same requirement is wrong.
    """
    rules: set[str] = set()
    # R12.6: registered in the layer while naming nothing to be an oracle *of*.
    if draft.registered_oracle and not draft.declared_subject:
        rules.add("oracle-subject-undeclared")
    # R12.1: names a subject it does not import, or imports one it never invokes on the
    # path producing the asserted value. Both spellings, one rule.
    if draft.declared_subject and not draft.expected_invokes:
        rules.add("oracle-subject-not-invoked")
    # R12.2: registered in the layer while its reference is not independent.
    if draft.registered_oracle and not draft.expected_reference_independent:
        rules.add("oracle-reference-not-independent")
    # R12.6: the title claims the layer the derivation refuses.
    if draft.title_claims_oracle and not draft.expected_earned:
        rules.add("oracle-claim-unearned")
    # R12.7: a declared bound at or beyond the committed ceiling constrains nothing.
    if draft.expected_tolerance_constraining is False:
        rules.add("tolerance-unconstraining")
    return frozenset(rules)


def assert_classification(subject: ot.OracleSubject, draft: SubjectDraft) -> None:
    """The derivation rediscovered every fact about the module it was never told."""
    assert subject.declared_subject == draft.declared_subject
    assert subject.declared_layer == draft.expected_layer
    assert subject.title_claims_oracle is draft.title_claims_oracle
    assert subject.imports_subject is draft.expected_imports
    assert subject.invokes_subject_on_asserted_path is draft.expected_invokes
    assert subject.reference_independent is draft.expected_reference_independent
    assert subject.tolerance_constraining is draft.expected_tolerance_constraining
    assert subject.tolerance_name == draft.expected_tolerance_name
    assert subject.tolerance_bound == draft.expected_tolerance_bound
    assert subject.earned is draft.expected_earned


def predicate_tuple(subject: ot.OracleSubject) -> tuple[object, ...]:
    """Everything the derivation observed, with the node id deliberately left out."""
    return (
        subject.declared_subject,
        subject.declared_layer,
        subject.imports_subject,
        subject.invokes_subject_on_asserted_path,
        subject.reference_independent,
        subject.tolerance_constraining,
        subject.tolerance_name,
        subject.tolerance_bound,
        subject.earned,
    )


# ---------------------------------------------------------------------------
# Property 37
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 37: Oracle-layer membership is earned, not
# declared
@given(draft=subject_drafts())
def test_membership_is_granted_only_when_the_derivation_earns_it(draft: SubjectDraft) -> None:
    """R12.1, R12.2, R12.6: the derivation is the only thing that grants membership.

    Every field of the classification is compared against what the generated module
    actually does. Getting any one of them wrong would leave the layer decided by
    something other than evidence, which is the whole finding.
    """
    with synthetic_suite((draft,)):
        subjects = ot.derive_subjects(CONFIG)
        assert len(subjects) == 1, "one generated test must yield exactly one classification"
        subject = subject_for(subjects, draft.node_id)
        assert_classification(subject, draft)

        findings = ot.membership_findings(subjects, CONFIG)
        report = ot.evaluate_membership(CONFIG)

    assert rules_for(findings, draft.node_id) == expected_rules(draft)
    for finding in findings:
        # Naming is half the contract: a finding nobody can locate repairs nothing.
        assert finding.node_id == draft.node_id
        assert draft.node_id in finding.detail
        assert finding.requirement.startswith("R12.")
        # A gate that cannot print its own finding on Windows reports nothing (E-S13-07).
        assert finding.detail.isascii()

    assert (draft.node_id in report.oracle_members) is draft.expected_member
    assert rules_for(report.unresolved, draft.node_id) == expected_rules(draft)
    assert report.verdict == ("fail" if report.unresolved else "pass")
    assert report.exit_code == EXPECTED_EXIT[report.verdict]
    assert report.reason


@given(draft=earning_drafts())
def test_a_test_that_earns_every_predicate_is_admitted_and_fails_nothing(
    draft: SubjectDraft,
) -> None:
    """The converse guard: without it, a gate that rejected everything would pass above.

    The bound is pinned strictly inside the committed ceiling, so this draft is the
    genuine article: subject imported, invoked, asserted, judged against a reference the
    subject never touched, inside a tolerance that can still fail.
    """
    admitted = dataclasses.replace(draft, tolerance_bound=CONSTRAINING_BOUND)
    assert ot.allowlist_findings() == (), "the committed allowlist is malformed; see R12.5"

    with synthetic_suite((admitted,)):
        report = ot.evaluate_membership(CONFIG)

    assert report.findings == ()
    assert report.unresolved == ()
    assert report.verdict == "pass"
    assert report.exit_code == EXPECTED_EXIT["pass"]
    assert report.oracle_members == (admitted.node_id,)
    subject = subject_for(report.subjects, admitted.node_id)
    assert subject.earned is True
    assert subject.tolerance_constraining is True


@given(
    draft=subject_drafts(
        markers=("oracle",),
        declares_subject=True,
        invocations=("called-unasserted", "imported-unused"),
        references=("independent",),
    )
)
def test_naming_a_subject_it_never_invokes_cannot_claim_membership(draft: SubjectDraft) -> None:
    """R12.1: a title plus a subject keyword is not standing to judge that subject.

    Two failure modes, one rule. Either the subject is never imported - the audit's
    specimen, a test named for the pricing agent that imports only the twin - or it is
    imported and never reaches an assertion, and a value the assertion does not depend on
    cannot be the thing the assertion checks. The detail must distinguish them, because
    the repairs are different.
    """
    with synthetic_suite((draft,)):
        subjects = ot.derive_subjects(CONFIG)
        findings = ot.membership_findings(subjects, CONFIG)
        report = ot.evaluate_membership(CONFIG)

    subject = subject_for(subjects, draft.node_id)
    assert subject.declared_subject == SUBJECT
    assert subject.invokes_subject_on_asserted_path is False
    assert subject.earned is False
    assert "oracle-subject-not-invoked" in rules_for(findings, draft.node_id)
    assert draft.node_id not in report.oracle_members
    assert report.verdict in NON_PASSING

    detail = detail_for(findings, draft.node_id, "oracle-subject-not-invoked")
    assert SUBJECT in detail
    if draft.imports_subject_module:
        assert subject.imports_subject is True
        assert "reaches an assertion" in detail
    else:
        assert subject.imports_subject is False
        assert "imports no module under it" in detail


@given(draft=subject_drafts(markers=("oracle",), declares_subject=False))
def test_a_registered_oracle_naming_no_subject_is_named_not_defaulted(
    draft: SubjectDraft,
) -> None:
    """R12.6: registration with nothing to derive from is a finding, not a free pass.

    This is where a silent default would hide. The test *is* in the layer and there is no
    subject to check, so a gate with a permissive fallback would report nothing at all -
    which is how eight of the committed oracle tests came to be Layer 6.
    """
    registered = dataclasses.replace(draft, marker_called=True, layer_kwarg=ORACLE_LAYER)
    with synthetic_suite((registered,)):
        findings = ot.membership_findings(ot.derive_subjects(CONFIG), CONFIG)
        report = ot.evaluate_membership(CONFIG)

    assert "oracle-subject-undeclared" in rules_for(findings, registered.node_id)
    detail = detail_for(findings, registered.node_id, "oracle-subject-undeclared")
    assert "@pytest.mark.oracle(subject=" in detail
    assert registered.node_id not in report.oracle_members
    assert report.verdict in NON_PASSING


@given(draft=earning_drafts(), reference=st.sampled_from(REFERENCES))
def test_a_reference_the_subject_produced_or_restated_is_rejected_from_the_layer(
    draft: SubjectDraft, reference: ReferenceKind
) -> None:
    """R12.2: comparing a mechanism to a model of itself is not evidence.

    Both dependence modes are generated: a reference that is only a literal beside the
    subject's own output, and a module that *admits* its reference is the compared
    quantity restated - the self-admission the audit quoted out of the pricing test. The
    finding must also say where the test belongs instead, which is the difference between
    a gate that rejects and a gate that redirects.
    """
    case = dataclasses.replace(draft, reference=reference, tolerance_bound=CONSTRAINING_BOUND)
    with synthetic_suite((case,)):
        subjects = ot.derive_subjects(CONFIG)
        findings = ot.membership_findings(subjects, CONFIG)
        report = ot.evaluate_membership(CONFIG)

    subject = subject_for(subjects, case.node_id)
    independent = reference == "independent"
    assert subject.reference_independent is independent
    assert subject.earned is independent
    assert (case.node_id in report.oracle_members) is independent

    if independent:
        assert report.unresolved == ()
        assert report.verdict == "pass"
        return

    assert "oracle-reference-not-independent" in rules_for(findings, case.node_id)
    detail = detail_for(findings, case.node_id, "oracle-reference-not-independent")
    assert CONFIG.layer_name(METAMORPHIC_LAYER) in detail
    assert report.verdict == "fail"
    assert report.exit_code == EXPECTED_EXIT["fail"]


@given(
    draft=earning_drafts(),
    bound=threshold_sequences(min_size=1, max_size=1, low=TOLERANCE_LOW, high=TOLERANCE_HIGH),
)
def test_an_unconstraining_tolerance_is_non_passing_even_when_membership_is_earned(
    draft: SubjectDraft, bound: tuple[float, ...]
) -> None:
    """R12.7 with I-7: earning the layer is not the same as passing the gate.

    This draft earns membership on all three derivation predicates, so the *only* thing
    that can turn the run red is the width of the bound. A bound at or beyond the
    committed ceiling admits an error large enough that agreement distinguishes nothing,
    and the gate must say so while still listing the test as a member - collapsing the two
    would let a wide bound ride in on a genuine oracle's membership.
    """
    case = dataclasses.replace(draft, tolerance_bound=bound[0], tolerance_in_assert=True)
    constrains = 0.0 < bound[0] < CEILING

    with synthetic_suite((case,)):
        subjects = ot.derive_subjects(CONFIG)
        findings = ot.membership_findings(subjects, CONFIG)
        report = ot.evaluate_membership(CONFIG)

    subject = subject_for(subjects, case.node_id)
    assert subject.tolerance_constraining is constrains
    assert subject.tolerance_name == TOLERANCE_SYMBOL
    assert subject.tolerance_bound == bound[0]
    # Membership is untouched by the width of the bound.
    assert subject.earned is True
    assert case.node_id in report.oracle_members

    if constrains:
        assert rules_for(findings, case.node_id) == frozenset()
        assert report.verdict == "pass"
        return

    assert rules_for(findings, case.node_id) == frozenset({"tolerance-unconstraining"})
    detail = detail_for(findings, case.node_id, "tolerance-unconstraining")
    assert f"{TOLERANCE_SYMBOL}={bound[0]}" in detail
    assert str(CEILING) in detail
    assert report.verdict == "fail"
    assert report.verdict in NON_PASSING


@given(draft=subject_drafts())
def test_a_title_claiming_the_layer_never_grants_it_and_is_itself_a_finding(
    draft: SubjectDraft,
) -> None:
    """R12.6: a rename cannot restore membership, and claiming it unearned is a failure.

    The same module is rendered twice, differing only in whether its docstring calls
    itself an Oracle-layer test. Every derived predicate must be identical across the pair
    - that is the clause - and the claim must cost the run a finding whenever the
    derivation refuses it. Without the second half, retitling would be a free way to
    silence the gate; without the first, a title would still be worth membership.
    """
    claiming = dataclasses.replace(draft, title_claims_oracle=True)
    silent = dataclasses.replace(draft, title_claims_oracle=False)

    with synthetic_suite((claiming,)):
        claiming_subject = subject_for(ot.derive_subjects(CONFIG), claiming.node_id)
        claiming_findings = ot.membership_findings((claiming_subject,), CONFIG)
        claiming_members = ot.evaluate_membership(CONFIG).oracle_members
    with synthetic_suite((silent,)):
        silent_subject = subject_for(ot.derive_subjects(CONFIG), silent.node_id)
        silent_members = ot.evaluate_membership(CONFIG).oracle_members

    assert predicate_tuple(claiming_subject) == predicate_tuple(silent_subject), (
        "the title changed what the derivation observed; membership would be declarable"
    )
    assert claiming_subject.title_claims_oracle is True
    assert silent_subject.title_claims_oracle is False
    assert bool(claiming_members) is draft.expected_member
    assert bool(silent_members) is draft.expected_member

    claimed = rules_for(claiming_findings, claiming.node_id)
    assert ("oracle-claim-unearned" in claimed) is not draft.expected_earned
    if not draft.expected_earned:
        detail = detail_for(claiming_findings, claiming.node_id, "oracle-claim-unearned")
        assert "membership is derived, not titled" in detail


@given(draft=subject_drafts())
def test_membership_is_invariant_under_the_file_name_and_the_registration_site(
    draft: SubjectDraft,
) -> None:
    """R12.6's path clause, plus the class-versus-function registration site.

    A module called ``test_..._oracle.py`` must derive exactly what the same module called
    ``test_case_0.py`` derives - the path was the audit's original grant of membership.
    The marker site travels with it because the committed suite registers on the *class*:
    a derivation that read only function decorators would silently unregister every test
    in the suite and then report nothing at all.
    """
    observed: set[tuple[object, ...]] = set()
    for named, on_class in ((True, True), (True, False), (False, True), (False, False)):
        variant = dataclasses.replace(
            draft, file_name_claims_oracle=named, marker_on_class=on_class
        )
        with synthetic_suite((variant,)):
            subject = subject_for(ot.derive_subjects(CONFIG), variant.node_id)
        observed.add(predicate_tuple(subject))

    assert len(observed) == 1, (
        f"membership moved with the file name or the decorator site: {sorted(map(str, observed))}"
    )


@given(drafts=st.lists(subject_drafts(), min_size=1, max_size=4))
def test_classification_is_total_and_never_silently_admits_a_test(
    drafts: list[SubjectDraft],
) -> None:
    """R12.6 as totality: no test is dropped, and none is admitted without evidence.

    A gate that quietly skipped a module it could not classify would satisfy every naming
    assertion above while measuring nothing - which is the state the audit found. So: one
    classification per test, a declared layer drawn only from the committed vocabulary,
    and every registered oracle landing on exactly one side of the membership question.
    """
    suite = numbered(drafts)
    with synthetic_suite(suite):
        subjects = ot.derive_subjects(CONFIG)
        findings = ot.membership_findings(subjects, CONFIG)
        report = ot.evaluate_membership(CONFIG)

    assert len(subjects) == len(suite)
    assert {subject.node_id for subject in subjects} == {draft.node_id for draft in suite}

    for draft in suite:
        subject = subject_for(subjects, draft.node_id)
        assert_classification(subject, draft)
        assert subject.declared_layer in (None, ORACLE_LAYER, METAMORPHIC_LAYER)

        membership = rules_for(findings, draft.node_id) & MEMBERSHIP_RULES
        is_member = draft.node_id in report.oracle_members
        assert is_member is draft.expected_member

        if draft.registered_oracle:
            # Exactly one side, always: admitted, or named. Never neither.
            assert is_member is not bool(membership)
        else:
            # Nothing about proximity to the suite promotes a test into the layer.
            assert not is_member

    assert all(finding.node_id for finding in report.unresolved)
    assert report.verdict == ("fail" if report.unresolved else "pass")
    assert report.exit_code == EXPECTED_EXIT[report.verdict]
    assert len(report.oracle_members) == sum(1 for draft in suite if draft.expected_member)


def test_a_suite_with_no_test_modules_is_unavailable_and_never_a_pass() -> None:
    """I-7: a derivation that classified nothing has established membership for nothing."""
    with synthetic_suite(()):
        assert ot.derive_subjects(CONFIG) == ()
        report = ot.evaluate_membership(CONFIG)

    assert report.verdict == "unavailable"
    assert report.verdict in NON_PASSING
    assert report.exit_code == EXPECTED_EXIT["unavailable"]
    assert report.oracle_members == ()
    assert "no oracle-suite test modules" in report.reason


# ---------------------------------------------------------------------------
# The committed layer configuration: read, never invented (I-7)
# ---------------------------------------------------------------------------


@given(ceiling=threshold_sequences(min_size=1, max_size=1, low=-1.0, high=2.0))
def test_a_ceiling_outside_the_admissible_range_is_unavailable_not_defaulted(
    ceiling: tuple[float, ...],
) -> None:
    """A gate running on an invented threshold reports a verdict it did not earn.

    The ceiling bounds a *relative* tolerance, so only ``(0, 1]`` can bound anything.
    Anything else must raise rather than fall back on a number nobody reviewed; the caller
    maps that to ``unavailable``, which is not a pass.
    """
    value = ceiling[0]
    document: dict[str, object] = {
        "version": CONFIG.version,
        "oracle_layer": ORACLE_LAYER,
        "layer_names": dict(CONFIG.layer_names),
        "tolerance_ceiling": value,
    }
    with tempfile.TemporaryDirectory(prefix="oracle-config-") as tmp:
        path = Path(tmp) / "oracle-layers.yaml"
        path.write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8")

        if 0.0 < value <= 1.0:
            loaded = ot.load_config(path)
            assert loaded.tolerance_ceiling == value
            assert loaded.oracle_layer == ORACLE_LAYER
            return
        with pytest.raises(ot.ConfigUnavailable):
            ot.load_config(path)


def test_an_absent_or_unusable_layer_configuration_raises_rather_than_defaulting() -> None:
    """The three ways the configuration can fail, and none of them yields a ceiling."""
    with tempfile.TemporaryDirectory(prefix="oracle-config-") as tmp:
        root = Path(tmp)
        with pytest.raises(ot.ConfigUnavailable):
            ot.load_config(root / "absent.yaml")

        not_a_mapping = root / "sequence.yaml"
        not_a_mapping.write_text(yaml.safe_dump([1, 2, 3]), encoding="utf-8")
        with pytest.raises(ot.ConfigUnavailable):
            ot.load_config(not_a_mapping)

        incomplete = root / "incomplete.yaml"
        incomplete.write_text(yaml.safe_dump({"version": 1}), encoding="utf-8")
        with pytest.raises(ot.ConfigUnavailable):
            ot.load_config(incomplete)


def test_the_committed_configuration_pins_the_layer_vocabulary_it_is_read_for() -> None:
    """The layer numbers and the ceiling this file uses are the committed ones."""
    assert CONFIG.layer_names[str(ORACLE_LAYER)] == "Oracle"
    assert CONFIG.layer_names[str(METAMORPHIC_LAYER)] == "Metamorphic"
    assert CONFIG.layer_name(ORACLE_LAYER) == "Oracle"
    assert CONFIG.layer_name(None) == "(unregistered)"
    assert 0.0 < CEILING <= 1.0
    assert 0.0 < CONSTRAINING_BOUND < CEILING < TOLERANCE_HIGH


# ---------------------------------------------------------------------------
# R12.5 - the allowlist is a label on debt, never an exemption from measurement
# ---------------------------------------------------------------------------

#: Date strings a generated entry may carry. Two parse, three do not; ``None`` is the
#: entry that records a rationale nobody dated.
DATE_SAMPLES: Final[tuple[str | None, ...]] = (
    None,
    "2026-06-17",
    "2027-01-05",
    "17-06-2026",
    "not-a-date",
    "",
)


@dataclass(frozen=True)
class EntryDraft:
    """One raw allowlist entry, and whether it is reviewable.

    R12.5 requires **both** a dated rationale and a stated removal condition. Either alone
    leaves an entry nobody can review: a rationale with no date cannot be aged out, and a
    date with no removal condition never expires.
    """

    node_id: str = "generated/test_case_0.py::TestGeneratedCase0::test_generated_case"
    rules: tuple[str, ...] = ("oracle-claim-unearned",)
    has_node_id: bool = True
    has_rules: bool = True
    unknown_rule: bool = False
    has_rationale: bool = True
    date_text: str | None = "2026-06-17"
    has_removal_condition: bool = True

    @property
    def declared_rules(self) -> tuple[str, ...]:
        if not self.has_rules:
            return ()
        return (*self.rules, "not-a-rule") if self.unknown_rule else self.rules

    @property
    def date_is_iso(self) -> bool:
        """Whether the rationale is dated, recomputed with the stdlib, not the gate."""
        if self.date_text is None:
            return False
        try:
            date.fromisoformat(self.date_text)
        except ValueError:
            return False
        return True

    @property
    def well_formed(self) -> bool:
        return (
            self.has_node_id
            and bool(self.declared_rules)
            and not self.unknown_rule
            and self.has_rationale
            and self.date_is_iso
            and self.has_removal_condition
        )

    def as_raw(self) -> dict[str, object]:
        raw: dict[str, object] = {"rules": self.declared_rules}
        if self.has_node_id:
            raw["node_id"] = self.node_id
        if self.has_rationale:
            raw["rationale"] = "generated entry recorded by the property test"
        if self.date_text is not None:
            raw["dated"] = self.date_text
        if self.has_removal_condition:
            raw["removal_condition"] = "delete when the generated case earns the layer"
        return raw

    def reviewable(self) -> EntryDraft:
        """The same entry with every R12.5 defect repaired."""
        return dataclasses.replace(
            self,
            has_node_id=True,
            has_rules=True,
            unknown_rule=False,
            has_rationale=True,
            date_text="2026-06-17",
            has_removal_condition=True,
        )


@st.composite
def entry_drafts(draw: st.DrawFn) -> EntryDraft:
    """One allowlist entry, defective in any combination of the reviewable ways."""
    return EntryDraft(
        rules=draw(
            st.lists(
                st.sampled_from(sorted(ot.ALLOWLISTABLE_RULES)),
                min_size=1,
                max_size=3,
                unique=True,
            ).map(tuple)
        ),
        has_node_id=draw(st.booleans()),
        has_rules=draw(st.booleans()),
        unknown_rule=draw(st.booleans()),
        has_rationale=draw(st.booleans()),
        date_text=draw(st.sampled_from(DATE_SAMPLES)),
        has_removal_condition=draw(st.booleans()),
    )


@given(entry=entry_drafts())
def test_an_allowlist_entry_without_a_dated_rationale_and_a_removal_condition_fails(
    entry: EntryDraft,
) -> None:
    """R12.5: the auditor fails on the entry itself, and the entry excuses nothing.

    The second half is the one that matters. If a malformed entry still suppressed the
    findings it named, a broken exception would be *more* powerful than a reviewed one,
    and the allowlist would become the easiest place in the repository to hide a failure.
    """
    raw = (entry.as_raw(),)
    schema = ot.allowlist_findings(raw)
    entries = ot.allowlist_entries(raw)

    assert bool(schema) is not entry.well_formed
    assert len(entries) == (1 if entry.well_formed else 0)
    for finding in schema:
        assert finding.rule == "allowlist-entry-incomplete"
        assert finding.requirement == "R12.5"
        assert finding.detail.isascii()
        assert finding.node_id == (entry.node_id if entry.has_node_id else "(entry 0)")

    # A finding the entry names is excused only when the entry is reviewable.
    named = ot.Finding(
        rule=entry.declared_rules[0] if entry.declared_rules else "oracle-claim-unearned",
        requirement="R12.6",
        node_id=entry.node_id,
        detail="generated finding",
    )
    excused = entry.well_formed and named.rule in entry.declared_rules
    assert (ot.unresolved_findings((named,), entries) == ()) is excused

    # And the schema check can never be excused by the thing it checks.
    assert "allowlist-entry-incomplete" not in ot.ALLOWLISTABLE_RULES


@given(entry=entry_drafts(), rule=st.sampled_from(sorted(ot.ALLOWLISTABLE_RULES)))
def test_a_well_formed_entry_excuses_only_the_rules_it_names(
    entry: EntryDraft, rule: str
) -> None:
    """R12.5: an exception covers what somebody reviewed, and nothing adjacent.

    An entry that silently widened to cover a finding nobody looked at would turn one
    reviewed exception into a blanket one, which is how allowlists rot.
    """
    reviewable = entry.reviewable()
    raw = (reviewable.as_raw(),)
    assert ot.allowlist_findings(raw) == ()
    entries = ot.allowlist_entries(raw)
    assert len(entries) == 1

    names_rule = rule in reviewable.declared_rules
    assert entries[0].excuses(rule) is names_rule

    named = ot.Finding(
        rule=rule, requirement="R12.6", node_id=reviewable.node_id, detail="generated finding"
    )
    assert (ot.unresolved_findings((named,), entries) == ()) is names_rule

    # A finding about a different test is never excused by this entry.
    elsewhere = ot.Finding(
        rule=rule,
        requirement="R12.6",
        node_id="generated/other_case.py::TestOther::test_other",
        detail="generated finding",
    )
    assert ot.unresolved_findings((elsewhere,), entries) == (elsewhere,)


@given(entry=entry_drafts())
def test_the_same_test_listed_twice_is_reported_rather_than_merged_silently(
    entry: EntryDraft,
) -> None:
    """Two entries for one test are two reviews nobody reconciled (R12.5)."""
    reviewable = entry.reviewable()
    schema = ot.allowlist_findings((reviewable.as_raw(), reviewable.as_raw()))

    assert schema, "a duplicated allowlist entry was accepted"
    assert any("twice" in finding.detail for finding in schema)
    assert all(finding.requirement == "R12.5" for finding in schema)
    assert all(finding.node_id == reviewable.node_id for finding in schema)


def test_the_committed_allowlist_carries_a_dated_rationale_and_a_removal_condition() -> None:
    """R12.5 over the real file: every recorded exception is reviewable today.

    A static read of the committed tuple - no suite, no execution. C61's docstring
    baseline is derived from these same entries, so the two cannot drift apart.
    """
    assert ot.allowlist_findings() == (), "the committed allowlist is not reviewable"
    entries = ot.allowlist_entries()
    assert entries, "the committed allowlist records no exception at all"

    for entry in entries:
        assert entry.node_id.startswith("tests/oracle/")
        assert entry.rules
        assert set(entry.rules) <= ot.ALLOWLISTABLE_RULES
        assert entry.rationale.strip()
        assert entry.removal_condition.strip()
        assert entry.dated.year >= 2026

    node_ids = [entry.node_id for entry in entries]
    assert len(node_ids) == len(set(node_ids))
    assert ot.KNOWN_BASELINE == {
        entry.node_id for entry in entries if entry.excuses("docstring-body-mismatch")
    }


# ---------------------------------------------------------------------------
# The committed oracle suite, read statically
# ---------------------------------------------------------------------------

ELASTICITY_ORACLE: Final[str] = (
    "tests/oracle/test_pricing_elasticity_oracle.py"
    "::TestPricingElasticityOracle::test_agent_elasticity_predicts_twin_demand_response"
)

IMPACT_METAMORPHIC: Final[str] = (
    "tests/oracle/test_pricing_impact_oracle.py"
    "::TestPricingImpactOracle::test_price_change_revenue_within_predicted"
)


def _test_function_count(directory: Path) -> int:
    """Count ``test*`` functions in *directory* with an independent AST walk.

    Independent of ``oracle_truth``'s own walker on purpose: the count the auditor
    classifies must be the count the suite contains, and a walker that skipped a nesting
    shape would under-report while every other assertion still held.
    """
    total = 0
    for path in sorted(directory.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            named_test = isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and (
                node.name.startswith("test")
            )
            if named_test:
                total += 1
    return total


def test_the_committed_suite_classifies_every_test_and_earns_one_membership() -> None:
    """R12.1, R12.2, R12.6 against the real files: a static read, no twin, no run.

    What must hold today is the audit's repair. ``test_pricing_elasticity_oracle.py``
    imports ``agents.pricing_oracle``, invokes its elasticity path and is judged against
    the twin, so it earns the layer. ``test_pricing_impact_oracle.py`` compares the twin
    to an algebraic restatement of the twin, so it is registered Metamorphic and is *not*
    a member however its file is named. Every remaining test in the suite is honest debt:
    it carries a finding, and that finding is allowlisted with a dated rationale and a
    removal condition. Repairing one of them changes the numbers here deliberately rather
    than by drift.
    """
    report = ot.evaluate_membership()

    assert len(report.subjects) == _test_function_count(ot.ORACLE_DIR)
    assert report.unresolved == (), f"unresolved oracle-layer findings: {report.unresolved}"
    assert report.verdict == "pass"
    assert report.exit_code == EXPECTED_EXIT["pass"]

    elasticity = subject_for(report.subjects, ELASTICITY_ORACLE)
    assert elasticity.declared_subject == SUBJECT
    assert elasticity.declared_layer == ORACLE_LAYER
    assert elasticity.imports_subject is True
    assert elasticity.invokes_subject_on_asserted_path is True
    assert elasticity.reference_independent is True
    assert elasticity.tolerance_constraining is True
    assert elasticity.tolerance_bound is not None
    assert 0.0 < elasticity.tolerance_bound < CEILING
    assert elasticity.earned is True

    # One earned member is the honest state of the layer today, and it is the whole point
    # of the finding: the top rung of the topology had none before this feature.
    assert report.oracle_members == (ELASTICITY_ORACLE,)

    impact = subject_for(report.subjects, IMPACT_METAMORPHIC)
    assert impact.declared_layer == METAMORPHIC_LAYER
    assert impact.declared_subject == ""
    assert impact.earned is False
    assert impact.node_id not in report.oracle_members

    allowlisted = {entry.node_id for entry in ot.allowlist_entries()}
    for finding in report.findings:
        assert finding.node_id in allowlisted, f"unlabelled oracle debt: {finding.detail}"
        assert finding.detail.isascii()
