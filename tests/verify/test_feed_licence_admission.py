"""Feed admission: the licence gate's totality, and the ingestion record's digest binding.

Feature: decision-quality-proof, task 7.5. Requirements **R8.1**, **R8.2**, **R8.16**,
**R8.17**.

Three things are established here, and each closes a way the E4a mechanism could report
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

**3. The ingestion record binds to the licence artifact by digest.** The record carries the
SHA-256 of the artifact bytes in force at ingestion, so "we had permission" stays checkable
after the artifact is edited. The test edits the artifact and asserts the digest moves --
a binding that did not move under an edit would be decoration.

Alongside those: the committed artifact's real state is pinned (M5 unconfirmed -> SKIP, which
is what stops an invented ``licence_id`` from creeping in later), the marker-versus-fields
disagreement is pinned as a FAIL rather than a SKIP, ``record_ingestion``'s three refusals
are each asserted to name their subject, first-versus-subsequent ingestion is asserted to be
recorded rather than inferred, and the three aggregate shapes are exercised on a
seven-column fixture -- including the assertion that the intra-day shape reports
``unavailable`` and carries **no values**, since a plausible intra-day curve derived from
daily data is exactly the invented literal R5.11 forbids.

**Plain assertions, no Hypothesis.** E4a's properties are 68 (licence schema totality) and
69 (provenanced ingestion, slow); both are numbered inside E4's block and land with task 19.
This file is the unit layer, so there is no example budget to inherit and no ``max_examples``
anywhere in it (I-0's authoring rule).

**No dataset is read and no bulk work runs.** Every fixture is a handful of rows in
``tmp_path``. ``extract_statistics`` over the real M5 files is a category-3/4 workload whose
locus is ``ci.yml::training-smoke``; this file proves the extractor's logic, not its scale.

**Validates: Requirements 8.1, 8.2, 8.16, 8.17.**
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

import pytest
import yaml
from pydantic import ValidationError

from data_fabric.ingest.m5 import (
    IngestionRefusedError,
    M5Columns,
    digest_file,
    extract_statistics,
    record_ingestion,
)
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

#: The dataset the committed artifact declares. Read from the artifact rather than restated,
#: so a rename in the YAML cannot leave this file asserting against a dataset nobody
#: declares (AD-13). `dataset_id` is nullable, so an unnamed entry is tolerated here.
COMMITTED_DATASET_IDS: Final[tuple[str, ...]] = tuple(
    entry.dataset_id
    for entry in load_licence_document(ARTIFACT_PATH).datasets
    if entry.dataset_id is not None
)

_FIXED_TIME: Final[datetime] = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


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

    ``load_licence_document`` does not run JSON-Schema validation, so without this the
    runtime ingestion path could read a malformed date that the gate would have caught. Null
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
# 3. The ingestion record's digest binding (R8.16, R8.17)
# ---------------------------------------------------------------------------


def _csv(path: Path, rows: list[list[str]]) -> Path:
    path.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8")
    return path


def test_ingestion_record_pins_the_licence_artifact_digest(tmp_path: Path) -> None:
    """R8.17: identity, revision, rows, per-file digests, and the licence digest in force."""
    artifact = _write_artifact(tmp_path / "dataset-licences.yaml", [_confirmed_entry()])
    data = _csv(tmp_path / "sales.csv", [["id", "d_1"], ["a", "1"], ["b", "2"]])

    record = record_ingestion(
        dataset_id="fixture-dataset",
        dataset_revision="rev-1",
        files=[data],
        ingested_at=_FIXED_TIME,
        licence_path=artifact,
    )

    assert record.dataset_id == "fixture-dataset"
    assert record.dataset_revision == "rev-1"
    assert record.rows == 2, "two data rows behind one header"
    assert record.licence_artifact_digest == artifact_digest(artifact)
    assert record.licence_artifact_digest.startswith("sha256:")
    assert record.files[0].sha256 == digest_file(data).sha256
    assert record.licence_id == "FIXTURE-LICENCE-1.0"
    assert record.ingested_at == _FIXED_TIME.isoformat()
    # Canonical JSON, so two records over the same facts are byte-identical.
    assert record.canonical_json() == json.dumps(
        json.loads(record.canonical_json()), sort_keys=True, separators=(",", ":")
    )


def test_digest_binding_moves_when_the_artifact_changes(tmp_path: Path) -> None:
    """A binding that survived an edit to the thing it binds would be decoration."""
    entries = [_confirmed_entry()]
    artifact = _write_artifact(tmp_path / "dataset-licences.yaml", entries)
    data = _csv(tmp_path / "sales.csv", [["id", "d_1"], ["a", "1"]])
    before = record_ingestion(
        dataset_id="fixture-dataset",
        dataset_revision="rev-1",
        files=[data],
        ingested_at=_FIXED_TIME,
        licence_path=artifact,
    )

    edited = copy.deepcopy(entries)
    edited[0]["permitted_use"] = "fixture use only; terms re-read and widened"
    _write_artifact(artifact, edited)
    after = record_ingestion(
        dataset_id="fixture-dataset",
        dataset_revision="rev-1",
        files=[data],
        ingested_at=_FIXED_TIME,
        licence_path=artifact,
    )

    assert before.licence_artifact_digest != after.licence_artifact_digest
    assert before.files[0].sha256 == after.files[0].sha256, "the data did not change"


def test_first_ingestion_is_recorded_as_such(tmp_path: Path) -> None:
    """R8.16: a first ingestion is reported, not folded into the steady-state path."""
    artifact = _write_artifact(tmp_path / "dataset-licences.yaml", [_confirmed_entry()])
    data = _csv(tmp_path / "sales.csv", [["id", "d_1"], ["a", "1"]])

    first = record_ingestion(
        dataset_id="fixture-dataset",
        dataset_revision="rev-1",
        files=[data],
        ingested_at=_FIXED_TIME,
        licence_path=artifact,
    )
    later = record_ingestion(
        dataset_id="fixture-dataset",
        dataset_revision="rev-1",
        files=[data],
        ingested_at=_FIXED_TIME,
        licence_path=artifact,
        previously_ingested=("fixture-dataset",),
    )

    assert first.first_ingestion is True
    assert later.first_ingestion is False


def test_unconfirmed_licence_refuses_ingestion_and_names_the_fields(tmp_path: Path) -> None:
    """The committed artifact's own state: an unconfirmed entry cannot be ingested."""
    data = _csv(tmp_path / "sales.csv", [["id", "d_1"], ["a", "1"]])

    with pytest.raises(IngestionRefusedError) as raised:
        record_ingestion(
            dataset_id=COMMITTED_DATASET_IDS[0],
            dataset_revision="any-revision-at-all",
            files=[data],
            ingested_at=_FIXED_TIME,
            licence_path=ARTIFACT_PATH,
        )

    message = str(raised.value)
    assert "not confirmed" in message
    assert "licence_id" in message and "permitted_use" in message


def test_undeclared_dataset_refuses_ingestion(tmp_path: Path) -> None:
    artifact = _write_artifact(tmp_path / "dataset-licences.yaml", [_confirmed_entry()])
    data = _csv(tmp_path / "sales.csv", [["id", "d_1"], ["a", "1"]])

    with pytest.raises(IngestionRefusedError, match="declares no licence entry"):
        record_ingestion(
            dataset_id="some-other-dataset",
            dataset_revision="rev-1",
            files=[data],
            ingested_at=_FIXED_TIME,
            licence_path=artifact,
        )


def test_revision_mismatch_refuses_ingestion(tmp_path: Path) -> None:
    """Terms are read against a revision; a different revision has no recorded permission."""
    artifact = _write_artifact(tmp_path / "dataset-licences.yaml", [_confirmed_entry()])
    data = _csv(tmp_path / "sales.csv", [["id", "d_1"], ["a", "1"]])

    with pytest.raises(IngestionRefusedError, match="rev-1"):
        record_ingestion(
            dataset_id="fixture-dataset",
            dataset_revision="rev-2",
            files=[data],
            ingested_at=_FIXED_TIME,
            licence_path=artifact,
        )


def test_naive_timestamp_refuses_ingestion(tmp_path: Path) -> None:
    artifact = _write_artifact(tmp_path / "dataset-licences.yaml", [_confirmed_entry()])
    data = _csv(tmp_path / "sales.csv", [["id", "d_1"], ["a", "1"]])

    with pytest.raises(IngestionRefusedError, match="timezone-naive"):
        record_ingestion(
            dataset_id="fixture-dataset",
            dataset_revision="rev-1",
            files=[data],
            ingested_at=datetime(2026, 9, 1, 12, 0),  # the subject of this test
            licence_path=artifact,
        )


def test_unreadable_licence_artifact_refuses_ingestion(tmp_path: Path) -> None:
    with pytest.raises(IngestionRefusedError, match="could not be read"):
        record_ingestion(
            dataset_id="fixture-dataset",
            dataset_revision="rev-1",
            files=[],
            ingested_at=_FIXED_TIME,
            licence_path=tmp_path / "absent.yaml",
        )


def test_artifact_digest_refuses_an_absent_file(tmp_path: Path) -> None:
    with pytest.raises(LicenceArtifactError, match="could not be read for digesting"):
        artifact_digest(tmp_path / "absent.yaml")


# ---------------------------------------------------------------------------
# The three aggregate shapes, on a fixture (R5.11, R8.17)
# ---------------------------------------------------------------------------

#: A 14-day, two-week fixture. Two series, seven observation columns per week, so one week
#: is complete and the other is complete too -- the partial-week guard is exercised
#: separately.
_CALENDAR: Final[list[list[str]]] = [
    ["d", "wm_yr_wk", "wday", "weekday"],
    *[
        [f"d_{day}", f"w{1 + (day - 1) // 7}", str(1 + (day - 1) % 7), f"day{1 + (day - 1) % 7}"]
        for day in range(1, 15)
    ],
]


def _sales_rows(week_one: list[str], week_two: list[str]) -> list[list[str]]:
    header = ["id", *[f"d_{day}" for day in range(1, 15)]]
    return [header, ["series-a", *week_one, *week_two]]


def test_day_of_week_shape_is_derived_and_normalised(tmp_path: Path) -> None:
    """The multipliers' cell-count-weighted mean is 1.0 by construction."""
    calendar = _csv(tmp_path / "calendar.csv", _CALENDAR)
    sales = _csv(
        tmp_path / "sales.csv",
        _sales_rows(
            ["1", "2", "3", "4", "5", "6", "7"], ["3", "4", "5", "6", "7", "8", "9"]
        ),
    )

    statistics = extract_statistics(
        dataset_id="fixture-dataset",
        dataset_revision="rev-1",
        sales_csv=sales,
        calendar_csv=calendar,
    )

    shape = statistics.day_of_week
    assert shape.status == "derived", shape.detail
    assert len(shape.values) == 7
    assert len(shape.labels) == 7
    assert shape.labels[0] == "day1", "labels are read from the calendar, never asserted"
    assert shape.rows_consumed == 1
    assert sum(shape.values) / len(shape.values) == pytest.approx(1.0)
    assert shape.values[6] > shape.values[0], "the fixture rises across the week"


def test_intra_day_shape_is_unavailable_and_carries_no_values(tmp_path: Path) -> None:
    """R5.11: the shape a daily dataset cannot support is reported, never invented.

    The structural half matters as much as the status: an ``unavailable`` estimate carrying
    numbers would be picked up by the first consumer that read ``values``.
    """
    calendar = _csv(tmp_path / "calendar.csv", _CALENDAR)
    sales = _csv(
        tmp_path / "sales.csv",
        _sales_rows(["1"] * 7, ["1"] * 7),
    )

    statistics = extract_statistics(
        dataset_id="fixture-dataset",
        dataset_revision="rev-1",
        sales_csv=sales,
        calendar_csv=calendar,
    )

    shape = statistics.intra_day_intensity
    assert shape.status == "unavailable"
    assert shape.values == ()
    assert shape.labels == ()
    assert "daily" in shape.basis
    assert "intra_day_intensity" in statistics.unavailable_shapes


def test_promotion_uplift_is_unavailable_without_a_price_file(tmp_path: Path) -> None:
    calendar = _csv(tmp_path / "calendar.csv", _CALENDAR)
    sales = _csv(tmp_path / "sales.csv", _sales_rows(["1"] * 7, ["1"] * 7))

    statistics = extract_statistics(
        dataset_id="fixture-dataset",
        dataset_revision="rev-1",
        sales_csv=sales,
        calendar_csv=calendar,
    )

    assert statistics.promotion_uplift.status == "unavailable"
    assert statistics.promotion_uplift.values == ()
    assert "no promotion flag" in statistics.promotion_uplift.detail


def test_promotion_uplift_needs_enough_weeks_to_split(tmp_path: Path) -> None:
    """Two weeks is below the declared minimum, so the estimate is unavailable, not weak."""
    calendar = _csv(tmp_path / "calendar.csv", _CALENDAR)
    sales = _csv(tmp_path / "sales.csv", _sales_rows(["1"] * 7, ["4"] * 7))
    prices = _csv(
        tmp_path / "prices.csv",
        [
            ["store_id", "item_id", "wm_yr_wk", "sell_price"],
            ["s1", "i1", "w1", "10.0"],
            ["s1", "i1", "w2", "5.0"],
        ],
    )

    statistics = extract_statistics(
        dataset_id="fixture-dataset",
        dataset_revision="rev-1",
        sales_csv=sales,
        calendar_csv=calendar,
        sell_prices_csv=prices,
    )

    shape = statistics.promotion_uplift
    assert shape.status == "unavailable"
    assert str(4) in shape.detail, "the declared minimum must be named"
    assert "PROXY" in shape.basis, "the proxy nature travels with the estimate"


def test_promotion_uplift_is_derived_over_enough_weeks(tmp_path: Path) -> None:
    """Six weeks, discounted in the back half, with units following. Ratio > 1."""
    weeks = 6
    days = weeks * 7
    calendar = _csv(
        tmp_path / "calendar.csv",
        [
            ["d", "wm_yr_wk", "wday", "weekday"],
            *[
                [
                    f"d_{day}",
                    f"w{1 + (day - 1) // 7}",
                    str(1 + (day - 1) % 7),
                    f"day{1 + (day - 1) % 7}",
                ]
                for day in range(1, days + 1)
            ],
        ],
    )
    # Weeks 1-3 sell 1 unit a day, weeks 4-6 sell 4 -- and weeks 4-6 are the discounted ones.
    units = ["1"] * 21 + ["4"] * 21
    sales = _csv(
        tmp_path / "sales.csv",
        [
            ["id", *[f"d_{day}" for day in range(1, days + 1)]],
            ["series-a", *units],
        ],
    )
    prices = _csv(
        tmp_path / "prices.csv",
        [
            ["store_id", "item_id", "wm_yr_wk", "sell_price"],
            *[["s1", "i1", f"w{week}", "10.0"] for week in range(1, 4)],
            *[["s1", "i1", f"w{week}", "6.0"] for week in range(4, 7)],
        ],
    )

    statistics = extract_statistics(
        dataset_id="fixture-dataset",
        dataset_revision="rev-1",
        sales_csv=sales,
        calendar_csv=calendar,
        sell_prices_csv=prices,
    )

    shape = statistics.promotion_uplift
    assert shape.status == "derived", shape.detail
    assert shape.values[0] == pytest.approx(4.0)
    assert len(shape.labels) == 1
    assert "PROXY" in shape.basis
    assert statistics.canonical_json().startswith("{")


def test_missing_calendar_column_is_named_not_silently_empty(tmp_path: Path) -> None:
    """A wrong column expectation surfaces as a named absence, never as a zero shape."""
    calendar = _csv(
        tmp_path / "calendar.csv",
        [["d", "wm_yr_wk", "weekday"], ["d_1", "w1", "day1"]],
    )
    sales = _csv(tmp_path / "sales.csv", [["id", "d_1"], ["series-a", "1"]])

    statistics = extract_statistics(
        dataset_id="fixture-dataset",
        dataset_revision="rev-1",
        sales_csv=sales,
        calendar_csv=calendar,
    )

    assert statistics.day_of_week.status == "unavailable"
    assert "'wday'" in statistics.day_of_week.detail
    assert statistics.day_of_week.values == ()


def test_non_numeric_observation_is_named_not_treated_as_zero(tmp_path: Path) -> None:
    """An unreadable cell is not a zero observation -- defaulting it would flatten the shape."""
    calendar = _csv(tmp_path / "calendar.csv", _CALENDAR)
    sales = _csv(
        tmp_path / "sales.csv",
        _sales_rows(["1", "", "3", "4", "5", "6", "7"], ["1"] * 7),
    )

    statistics = extract_statistics(
        dataset_id="fixture-dataset",
        dataset_revision="rev-1",
        sales_csv=sales,
        calendar_csv=calendar,
    )

    assert statistics.day_of_week.status == "unavailable"
    assert "not a number" in statistics.day_of_week.detail


def test_custom_columns_are_honoured(tmp_path: Path) -> None:
    """The column names are parameters, so a differently shaped export is readable."""
    calendar = _csv(
        tmp_path / "calendar.csv",
        [
            ["day", "week", "dow"],
            *[[f"obs_{n}", "w1", str(n)] for n in range(1, 8)],
        ],
    )
    sales = _csv(
        tmp_path / "sales.csv",
        [["id", *[f"obs_{n}" for n in range(1, 8)]], ["a", *["2"] * 7]],
    )

    statistics = extract_statistics(
        dataset_id="fixture-dataset",
        dataset_revision="rev-1",
        sales_csv=sales,
        calendar_csv=calendar,
        columns=M5Columns(
            day_prefix="obs_",
            calendar_day="day",
            calendar_week="week",
            calendar_wday="dow",
            calendar_weekday_name="absent-on-purpose",
        ),
    )

    shape = statistics.day_of_week
    assert shape.status == "derived", shape.detail
    assert shape.labels == tuple(f"wday={n}" for n in range(1, 8))
    assert all(value == pytest.approx(1.0) for value in shape.values)
