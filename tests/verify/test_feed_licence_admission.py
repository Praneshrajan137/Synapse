"""Feed admission: the licence gate's totality and refusal shapes (unit layer).

Feature: decision-quality-proof, task 7.5. Requirements **R8.1**, **R8.2**.

Two things are established here, and each closes a way the E4a mechanism could report
green while proving nothing.

**1. Every absent field is NAMED, and absence never passes.** The suite removes each of
R8.1's six fields in turn from an otherwise perfect artifact and asserts that the verdict is
``unavailable`` *and* that the removed field's name appears in the report. Naming is the
assertion that matters: "1 field absent" tells an operator to go looking, while
"``permitted_use`` is absent" tells them what to read. It is also the difference between a
missing term and a permissive one -- a defaulted field would read as "no restriction
recorded", which is the failure mode the sentinel and this test exist to prevent (I-7).

**2. An unparseable artifact yields ``unavailable``, never a pass and never a crash.** Three
shapes are covered: an absent file, malformed YAML, and a document whose root is not a
mapping. All three are ``unavailable``, because "could not be read" must never collapse into
"no restriction found".

Alongside those: the committed artifact's real state is pinned (M5 unconfirmed -> SKIP, which
is what stops an invented ``licence_id`` from creeping in later), the marker-versus-fields
disagreement is pinned as a FAIL rather than a SKIP, and ``artifact_digest`` is asserted to
refuse an unreadable file rather than digest nothing.

**The ingestion-record half was retired on 2026-10-01.** M5 was declined on 2026-09-29, so
``data_fabric/ingest/m5.py`` -- the ingestion record, its digest binding to this artifact
(R8.17), its three refusals (R8.16) and the aggregate-shape extraction (R5.11) -- was removed
as dead code (C44), and the tests that exercised it went with it. The design withdraws
Property 69's R8.17 clause for the same reason. ``artifact_digest`` stays covered here because
it lives in ``data_fabric/licence.py``, which the gate still reads.

**Plain assertions, no Hypothesis.** E4a's licence-totality property is 68, in
``tests/verify/test_dataset_licence_totality_property.py``. This file is the unit layer, so
there is no example budget to inherit and no ``max_examples`` anywhere in it (I-0's authoring
rule).

**No dataset is read and no bulk work runs.** Every fixture is a handful of rows in
``tmp_path``.

**Validates: Requirements 8.1, 8.2.**
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

import pytest
import yaml
from pydantic import ValidationError

from data_fabric.licence import (
    ARTIFACT_PATH,
    R8_1_FIELDS,
    Confirmation,
    DatasetLicence,
    LicenceArtifactError,
    artifact_digest,
    load_licence_document,
)
from scripts.audit import dataset_licence_truth as gate

if TYPE_CHECKING:  # annotation-only
    from pathlib import Path

#: Alias kept at the name these tests read it under. Single source: the model module.
LICENCE_FIELDS: Final[tuple[str, ...]] = R8_1_FIELDS
SCHEMA_PATH: Final = gate.SCHEMA_FILE


def _confirmed_entry(dataset_id: str = "fixture-dataset") -> dict[str, Any]:
    """A fully confirmed entry: every one of R8.1's six fields established.

    Deliberately fictional. The point of the fixture is to exercise the *pass* branch, and
    borrowing a real dataset's identity to do that would put a plausible licence record in
    the test tree where a future reader could mistake it for the real one.
    """
    return {
        "dataset_id": dataset_id,
        "licence_id": "FIXTURE-LICENCE-1.0",
        "licence_text_uri": "https://example.invalid/fixture/licence.txt",
        "read_date": "2026-09-01",
        "permitted_use": "fixture use only; this entry describes no real dataset",
        "dataset_revision": "rev-1",
        "redistribution": "permitted",
        "confirmation": {
            "confirmed": True,
            "confirmed_by": "fixture-operator",
            "procedure": "fixture: no terms were read; this entry describes no real dataset",
        },
    }


def _write_artifact(path: Path, entries: list[dict[str, Any]], version: int = 1) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"schema_version": version, "datasets": entries}, sort_keys=True),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# The committed artifact's real state (I-7: recorded, not aspirational)
# ---------------------------------------------------------------------------


def test_committed_artifact_is_schema_valid_and_reports_unavailable() -> None:
    """The M5 entry is unconfirmed, so C74's verdict today is ``unavailable`` -> SKIP.

    This is the state of the repository, asserted rather than described. If somebody later
    fills in a plausible ``licence_id`` without an operator having read the terms, this test
    still passes -- nothing here can detect a lie -- but the test that follows pins the
    sentinel itself, so the fabrication would have to be accompanied by deleting an
    assertion that says why it must not happen.
    """
    report = gate.assess()
    assert report.verdict == "unavailable"
    assert not report.passing, "unavailable is not a pass (I-7)"
    assert report.exit_code == gate.EXIT_UNAVAILABLE
    assert report.datasets_declared >= 1
    # No schema violation and no flag disagreement: the artifact is well-formed and
    # honest about being unread.
    assert not [item for item in report.findings if item.fatal]
    assert {item.rule for item in report.findings} == {
        "field-absent",
        "redistribution-unestablished",
    }


def test_committed_m5_entry_records_every_term_as_unestablished() -> None:
    """Not one of the term fields carries an invented value.

    The strongest single guard in this file. An entry whose ``licence_id`` reads
    ``CC-BY-4.0`` would be indistinguishable from a fact for every downstream reader, and
    would be quoted by the first generated document that touched it.
    """
    document = load_licence_document(ARTIFACT_PATH)
    assert document.datasets, "the artifact must declare at least one dataset"
    for entry in document.datasets:
        assert not entry.confirmed
        assert entry.confirmation.confirmed is False
        assert entry.confirmation.procedure, "an unconfirmed entry must name the operator steps"
        assert entry.confirmation.blocked_on, "it must also say why it cannot be automated"
        # The terms are unread; identity and the location of the text are establishable
        # without reading them, so those two may legitimately be populated.
        assert "licence_id" in entry.absent_fields
        assert "read_date" in entry.absent_fields
        assert "permitted_use" in entry.absent_fields
        assert entry.redistribution is None
        # And the flag does not outrun its subject.
        assert not entry.flag_disagrees()


def test_committed_schema_is_a_valid_draft07_schema() -> None:
    schema = gate.load_schema(SCHEMA_PATH)
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert schema["additionalProperties"] is False


# ---------------------------------------------------------------------------
# 1. Every absent field is NAMED, and absence is unavailable, never a pass
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", LICENCE_FIELDS)
def test_absent_field_is_named_and_yields_unavailable(tmp_path: Path, field: str) -> None:
    """R8.1/R8.2: removing any one of the six fields yields ``unavailable`` naming it.

    The fixture's flag is set to ``false`` first, deliberately. An entry that still claimed
    ``confirmed: true`` with a term removed would trip ``flag-disagreement`` -> FAIL, and this
    test would then be measuring the over-claim rule rather than the absence rule. Isolating
    one rule per test is what makes a failure here mean what it says.
    """
    entry = _confirmed_entry()
    del entry[field]
    entry["confirmation"]["confirmed"] = False
    artifact = _write_artifact(tmp_path / "dataset-licences.yaml", [entry])

    report = gate.assess(artifact, SCHEMA_PATH)

    assert report.verdict == "unavailable", f"absent {field} must not pass or fail"
    assert not report.passing
    assert report.exit_code == gate.EXIT_UNAVAILABLE
    rules = {item.rule for item in report.findings}
    assert rules == {"field-absent"}, f"absent {field} is an absence, not a defect: {rules}"
    blob = report.reason + " " + " ".join(item.detail for item in report.findings)
    assert field in blob, f"the report must NAME {field}, not merely count it: {blob}"


def test_a_null_field_and_an_absent_key_are_the_same_fact(tmp_path: Path) -> None:
    """One fact, one verdict. Completeness has exactly one owner.

    If the schema required the six fields, a dropped key would surface as ``schema-invalid``
    -> FAIL while a null key surfaced as ``field-absent`` -> SKIP: two verdicts for "nobody
    established this term", decided by whichever mechanism noticed first. The keys are
    therefore optional in the schema and :attr:`DatasetLicence.absent_fields` owns the rule.
    """
    dropped = _confirmed_entry()
    del dropped["permitted_use"]
    dropped["confirmation"]["confirmed"] = False
    nulled = _confirmed_entry()
    nulled["permitted_use"] = None
    nulled["confirmation"]["confirmed"] = False

    a = gate.assess(_write_artifact(tmp_path / "a.yaml", [dropped]), SCHEMA_PATH)
    b = gate.assess(_write_artifact(tmp_path / "b.yaml", [nulled]), SCHEMA_PATH)

    assert a.verdict == b.verdict == "unavailable"
    assert {i.rule for i in a.findings} == {i.rule for i in b.findings} == {"field-absent"}


def test_present_but_malformed_value_is_a_fail_not_a_skip(tmp_path: Path) -> None:
    """A value somebody wrote and got wrong is a repository defect -> FAIL.

    The split from the absence clause is this module's one interpretive decision, so it is
    pinned here: ``read_date: "soon"`` is present, wrong, and fixable in this change, which
    is different work from "an operator must go and read the terms". This only holds because
    the validator is constructed WITH a format checker - ``format`` is annotation-only in
    draft-07 by default, and without it ``"soon"`` would validate.
    """
    entry = _confirmed_entry()
    entry["read_date"] = "soon"
    artifact = _write_artifact(tmp_path / "dataset-licences.yaml", [entry])

    report = gate.assess(artifact, SCHEMA_PATH)

    assert report.verdict == "fail"
    assert report.exit_code == gate.EXIT_FAIL
    assert {item.rule for item in report.findings} == {"schema-invalid"}
    assert all(item.fatal for item in report.findings)


def test_empty_declaration_is_unavailable(tmp_path: Path) -> None:
    """An artifact that licences nothing is absence of proof, not proof of permission.

    Owned by the gate's ``declaration-empty`` rule rather than by a schema ``minItems``,
    deliberately: nobody wrote a wrong term here, there are no terms, and "nothing declared"
    is the canonical ``unavailable`` shape rather than a document defect.
    """
    artifact = tmp_path / "dataset-licences.yaml"
    artifact.write_text(
        yaml.safe_dump({"schema_version": 1, "datasets": []}), encoding="utf-8"
    )

    report = gate.assess(artifact, SCHEMA_PATH)

    assert report.verdict == "unavailable"
    assert not report.passing
    assert {item.rule for item in report.findings} == {"declaration-empty"}
    assert not any(item.fatal for item in report.findings)


def test_confirmed_entry_passes(tmp_path: Path) -> None:
    """The pass branch exists and is reachable -- a gate that can never pass is not a gate."""
    artifact = _write_artifact(tmp_path / "dataset-licences.yaml", [_confirmed_entry()])

    report = gate.assess(artifact, SCHEMA_PATH)

    assert report.verdict == "pass", report.reason
    assert report.passing
    assert report.exit_code == gate.EXIT_PASS
    assert report.findings == ()
    assert len(report.confirmed_datasets) == 1


# ---------------------------------------------------------------------------
# 2. An unparseable artifact yields unavailable
# ---------------------------------------------------------------------------


def test_absent_artifact_is_unavailable(tmp_path: Path) -> None:
    report = gate.assess(tmp_path / "nope.yaml", SCHEMA_PATH)

    assert report.verdict == "unavailable"
    assert {item.rule for item in report.findings} == {"register-absent"}


def test_unparseable_yaml_is_unavailable(tmp_path: Path) -> None:
    """Malformed YAML is unavailable, and the gate does not raise through its caller.

    C74 calls ``assess`` directly, so an exception escaping here would be coerced to a FAIL
    naming a crash rather than reporting the honest unavailable state.
    """
    artifact = tmp_path / "dataset-licences.yaml"
    artifact.write_text("schema_version: 1\ndatasets: [unclosed\n", encoding="utf-8")

    report = gate.assess(artifact, SCHEMA_PATH)

    assert report.verdict == "unavailable"
    assert {item.rule for item in report.findings} == {"register-unparseable"}
    assert not report.passing


def test_non_mapping_root_is_unavailable(tmp_path: Path) -> None:
    artifact = tmp_path / "dataset-licences.yaml"
    artifact.write_text("- just\n- a\n- list\n", encoding="utf-8")

    report = gate.assess(artifact, SCHEMA_PATH)

    assert report.verdict == "unavailable"
    assert {item.rule for item in report.findings} == {"register-unparseable"}


def test_absent_schema_is_unavailable(tmp_path: Path) -> None:
    """Without its yardstick the gate has measured nothing, so it must not report a pass."""
    artifact = _write_artifact(tmp_path / "dataset-licences.yaml", [_confirmed_entry()])

    report = gate.assess(artifact, tmp_path / "no-schema.json")

    assert report.verdict == "unavailable"
    assert {item.rule for item in report.findings} == {"schema-absent"}


def test_schema_that_is_not_a_schema_is_unavailable(tmp_path: Path) -> None:
    artifact = _write_artifact(tmp_path / "dataset-licences.yaml", [_confirmed_entry()])
    broken = tmp_path / "broken.schema.json"
    broken.write_text(json.dumps({"type": "not-a-type"}), encoding="utf-8")

    report = gate.assess(artifact, broken)

    assert report.verdict == "unavailable"
    assert {item.rule for item in report.findings} == {"schema-not-draft07"}


# ---------------------------------------------------------------------------
# The confirmation flag must agree with the fields it describes
# ---------------------------------------------------------------------------


def test_flag_true_beside_an_unestablished_term_is_a_fail(tmp_path: Path) -> None:
    """A document wrong about itself is a FAIL, not a SKIP.

    An entry claiming ``confirmed: true`` while a term is still null is not merely
    incomplete -- it asserts a confirmation its own fields contradict. What must never
    happen is this document reading as a SKIP alongside the honestly-unread ones.
    """
    entry = _confirmed_entry()
    entry["licence_id"] = None
    artifact = _write_artifact(tmp_path / "dataset-licences.yaml", [entry])

    report = gate.assess(artifact, SCHEMA_PATH)

    assert report.verdict == "fail"
    assert any(item.rule == "flag-disagreement" for item in report.findings)
    detail = " ".join(item.detail for item in report.findings)
    assert "licence_id" in detail


def test_flag_false_beside_established_terms_is_not_a_finding(tmp_path: Path) -> None:
    """The honest half of the procedure is not punished.

    Every field populated with the flag still ``false`` is an operator mid-procedure, not a
    defect. Only the *over-claiming* direction is a fail.
    """
    entry = _confirmed_entry()
    entry["confirmation"]["confirmed"] = False
    artifact = _write_artifact(tmp_path / "dataset-licences.yaml", [entry])

    report = gate.assess(artifact, SCHEMA_PATH)

    assert not any(item.rule == "flag-disagreement" for item in report.findings)
    assert report.verdict == "pass", report.reason


def test_unestablished_entry_reports_unavailable_and_names_the_operator_steps(
    tmp_path: Path,
) -> None:
    """The SKIP branch carries the work list, not just the verdict."""
    entry = _confirmed_entry()
    entry["permitted_use"] = None
    entry["confirmation"] = {
        "confirmed": False,
        "procedure": "read the terms at the URI and record permitted_use verbatim",
        "blocked_on": "terms sit behind an acceptance gate",
    }
    artifact = _write_artifact(tmp_path / "dataset-licences.yaml", [entry])

    report = gate.assess(artifact, SCHEMA_PATH)

    assert report.verdict == "unavailable"
    assert not report.passing
    blob = " ".join(report.notes) + " ".join(item.detail for item in report.findings)
    assert "permitted_use" in blob
    assert "acceptance gate" in blob


def test_read_date_must_be_a_date_when_present(tmp_path: Path) -> None:
    """Null is admitted; a present non-date is not.

    Two different facts, and the format checker is what keeps them apart.
    """
    nulled = _confirmed_entry()
    nulled["read_date"] = None
    ok = gate.assess(_write_artifact(tmp_path / "n.yaml", [nulled]), SCHEMA_PATH)
    assert ok.verdict == "fail"  # flag says confirmed, field is null -> over-claim
    assert any(i.rule == "flag-disagreement" for i in ok.findings)

    bad = _confirmed_entry()
    bad["read_date"] = "2026-13-45"
    broken = gate.assess(_write_artifact(tmp_path / "b.yaml", [bad]), SCHEMA_PATH)
    assert broken.verdict == "fail"
    assert any(i.rule == "schema-invalid" for i in broken.findings)


def test_model_refuses_a_malformed_read_date_even_bypassing_the_schema() -> None:
    """The typed record refuses a date it cannot parse, on the path that skips the schema.

    ``load_licence_document`` does not run JSON-Schema validation, so without this a reader
    that loads through it could accept a malformed date that the gate would have caught. Null
    is admitted; present-and-unparseable is not.
    """
    with pytest.raises(ValidationError, match="ISO YYYY-MM-DD"):
        DatasetLicence(
            dataset_id="fixture",
            licence_id="X",
            licence_text_uri="https://example.invalid",
            read_date="whenever",
            permitted_use="fixture",
            dataset_revision="rev-1",
            redistribution="permitted",
            confirmation=Confirmation(confirmed=True, procedure="fixture"),
        )

    admitted = DatasetLicence(
        read_date=None, confirmation=Confirmation(confirmed=False, procedure="fixture")
    )
    assert admitted.read_date is None
    assert "read_date" in admitted.absent_fields


# ---------------------------------------------------------------------------
# The artifact digest refuses an unreadable file rather than digesting nothing
# ---------------------------------------------------------------------------


def test_artifact_digest_refuses_an_absent_file(tmp_path: Path) -> None:
    with pytest.raises(LicenceArtifactError, match="could not be read for digesting"):
        artifact_digest(tmp_path / "absent.yaml")
