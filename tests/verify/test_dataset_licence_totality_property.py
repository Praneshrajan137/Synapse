# Feature: decision-quality-proof, Property 68: The licence artifact is schema-total and every
# absent field is named
"""Property 68 -- the licence artifact is schema-total and every absent field is named.

Feature: decision-quality-proof, task 19.2. Requirements **R8.1**, **R8.2**.

**The gap this closes, and why it was left open deliberately.** Task 7.5 shipped E4a with unit
tests and recorded that Properties 68 and 69 belong to E4's numbering block, so they land here.
The unit layer (``tests/verify/test_feed_licence_admission.py``) removes each of R8.1's six
fields *one at a time*. That is six of the sixty-four possible absence patterns. This file
quantifies over **all** of them, plus the two ways a field can be missing, plus the flag, which
is what turns "the six cases we thought of are named" into "no absence pattern escapes".

What each property would have to do to fail
-------------------------------------------

1. :func:`test_absent_fields_is_exactly_the_set_of_unestablished_terms` fails if any R8.1 field
   is null and ``absent_fields`` omits it, or is populated and ``absent_fields`` includes it.
   That is *totality*: every one of the six is classified, and nothing else is. A defaulted
   field would be the interesting failure -- it would be populated without anybody establishing
   it, and R8.1's "an absent field is named rather than defaulted" is exactly that prohibition.

2. :func:`test_a_dropped_key_and_a_null_key_produce_the_same_verdict` fails if the gate reports
   different verdicts for the same fact expressed two ways. This is the property the schema's
   ``required`` list would break: a dropped key would be ``schema-invalid`` -> FAIL while a null
   key was ``field-absent`` -> SKIP, two verdicts for "nobody established this term", decided by
   whichever mechanism noticed first.

3. :func:`test_every_absent_field_is_named_in_the_report` fails if the report counts absences
   without naming them. Naming is the assertion that matters: "1 field absent" tells an operator
   to go looking; "``permitted_use`` is absent" tells them what to read. **Non-emptiness is
   asserted**: whenever the absent set is non-empty the findings must be non-empty, so this
   property cannot be satisfied by a gate that reports nothing at all.

4. :func:`test_no_absence_ever_reads_as_a_pass` fails if any absence pattern yields ``pass``.
   A SKIP is not a PASS and absence of proof is never a pass (I-7). This is the clause that
   stops a missing term reading as a permissive one.

5. :func:`test_an_overclaiming_flag_is_a_fail_and_never_a_skip` fails if a ``confirmed: true``
   entry carrying a null term is reported as merely incomplete. It is not incomplete -- it is
   making a false statement about itself, which is somebody's defect in this tree and a
   different repair from "go and read the terms".

Budget and locus
----------------

``max_examples`` is **inherited from the root** ``conftest.py`` profile and appears nowhere in
this file (I-0's authoring rule). Locus: ``ci.yml::uplift-verify`` fast step -- every example is
a handful of dictionary operations plus one small YAML write into ``tmp_path``. No dataset is
read, no bulk work runs, and there is no ``@pytest.mark.slow`` here.

**Validates: Requirements 8.1, 8.2.**
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import yaml
from hypothesis import given
from hypothesis import strategies as st

from data_fabric.licence import (
    R8_1_FIELDS,
    Confirmation,
    DatasetLicence,
)
from scripts.audit import dataset_licence_truth as gate

if TYPE_CHECKING:  # annotation-only
    from pathlib import Path

#: One establishable value per R8.1 field. Deliberately fictional: the point of the fixture is
#: to exercise the *established* branch, and borrowing a real dataset's identity to do that
#: would put a plausible licence record in the test tree where a future reader could mistake it
#: for the real one.
ESTABLISHED: Final[dict[str, str]] = {
    "dataset_id": "fixture-dataset",
    "licence_id": "FIXTURE-LICENCE-1.0",
    "licence_text_uri": "https://example.invalid/fixture/licence.txt",
    "read_date": "2026-09-01",
    "permitted_use": "fixture use only; this entry describes no real dataset",
    "dataset_revision": "rev-1",
}

#: The four redistribution dispositions. ``None`` is excluded on purpose: a null
#: redistribution is its own ``unavailable`` finding, and including it here would make every
#: property below measure that rule instead of R8.1's. It gets its own property at the end.
DISPOSITIONS: Final[tuple[str, ...]] = (
    "permitted",
    "prohibited",
    "permitted-with-attribution",
    "unknown",
)

#: How a term can fail to be established. Both mean "nobody established this", and the whole
#: point of property 2 is that the gate must not be able to tell them apart.
ABSENCE_MODES: Final[tuple[str, ...]] = ("dropped", "nulled")

_absent_fields = st.sets(st.sampled_from(R8_1_FIELDS))
_absence_mode = st.sampled_from(ABSENCE_MODES)
_disposition = st.sampled_from(DISPOSITIONS)


def _entry(
    absent: set[str],
    *,
    mode: str = "nulled",
    flag: bool = False,
    redistribution: str | None = "permitted",
) -> dict[str, Any]:
    """One declaration with ``absent`` unestablished, expressed via ``mode``."""
    payload: dict[str, Any] = {}
    for field in R8_1_FIELDS:
        if field not in absent:
            payload[field] = ESTABLISHED[field]
        elif mode == "nulled":
            payload[field] = None
        # mode == "dropped": the key simply does not appear.
    payload["redistribution"] = redistribution
    payload["confirmation"] = {
        "confirmed": flag,
        "confirmed_by": "fixture-operator" if flag else None,
        "procedure": "fixture: no terms were read; this entry describes no real dataset",
        "blocked_on": None if flag else "fixture: the terms sit behind an acceptance gate",
    }
    return payload


def _write(path: Path, entries: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"schema_version": 1, "datasets": entries}, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _model(payload: dict[str, Any]) -> DatasetLicence:
    """The typed record for one declaration, through the same model the runtime path uses.

    Fields are named explicitly rather than splatted from the dictionary: a ``**payload`` would
    let a renamed field silently stop being exercised, which is the drift the model exists to
    prevent.
    """
    confirmation = payload["confirmation"]
    return DatasetLicence(
        dataset_id=payload.get("dataset_id"),
        licence_id=payload.get("licence_id"),
        licence_text_uri=payload.get("licence_text_uri"),
        read_date=payload.get("read_date"),
        permitted_use=payload.get("permitted_use"),
        dataset_revision=payload.get("dataset_revision"),
        redistribution=payload["redistribution"],
        confirmation=Confirmation(
            confirmed=confirmation["confirmed"],
            confirmed_by=confirmation["confirmed_by"],
            procedure=confirmation["procedure"],
            blocked_on=confirmation["blocked_on"],
        ),
    )


# ---------------------------------------------------------------------------
# 1. Totality: every R8.1 field is classified, and nothing else is
# ---------------------------------------------------------------------------


@given(absent=_absent_fields, mode=_absence_mode, disposition=_disposition)
def test_absent_fields_is_exactly_the_set_of_unestablished_terms(
    absent: set[str], mode: str, disposition: str
) -> None:
    """``absent_fields`` equals the unestablished set exactly, in requirement order.

    Both directions, because either one alone is satisfiable by a broken implementation: a
    subset would let a term escape the report, and a superset would name a term somebody did
    establish. Equality over the powerset is the totality claim R8.1 needs.
    """
    entry = _model(_entry(absent, mode=mode, redistribution=disposition))

    assert set(entry.absent_fields) == absent
    assert entry.absent_fields == tuple(
        name for name in R8_1_FIELDS if name in absent
    ), "the report's order is the requirement's order, so a reader can follow R8.1 down it"
    assert entry.confirmed is (not absent)
    assert entry.unconfirmed_fields() == entry.absent_fields


@given(absent=_absent_fields, mode=_absence_mode)
def test_no_r8_1_field_is_ever_defaulted_to_a_value_nobody_established(
    absent: set[str], mode: str
) -> None:
    """An unestablished term reads as ``None``, never as a permissive string.

    The failure this forbids is the one R8.1 names in its own words: a default would make a
    missing term readable as an unrestricted one, and every downstream reader would treat it as
    a fact. ``None`` is a positive assertion of ignorance.
    """
    entry = _model(_entry(absent, mode=mode))

    for field in absent:
        assert getattr(entry, field) is None, f"{field} was defaulted rather than left absent"
    for field in set(R8_1_FIELDS) - absent:
        assert getattr(entry, field) == ESTABLISHED[field]


# ---------------------------------------------------------------------------
# 2. One fact, one verdict
# ---------------------------------------------------------------------------


@given(absent=_absent_fields, disposition=_disposition)
def test_a_dropped_key_and_a_null_key_produce_the_same_verdict(
    tmp_path: Path, absent: set[str], disposition: str
) -> None:
    """Two spellings of "nobody established this term" cannot yield two verdicts.

    Completeness has exactly one owner. Were the six fields in the schema's ``required`` list,
    a dropped key would surface as ``schema-invalid`` -> FAIL while a null key surfaced as
    ``field-absent`` -> SKIP -- one fact, two verdicts, decided by whichever mechanism noticed
    first. The rules are compared as sets, not just the verdicts, so a gate that reached the
    same verdict by a different route still fails this.
    """
    dropped = gate.assess(
        _write(
            tmp_path / "dropped.yaml",
            [_entry(absent, mode="dropped", redistribution=disposition)],
        ),
        gate.SCHEMA_FILE,
    )
    nulled = gate.assess(
        _write(
            tmp_path / "nulled.yaml",
            [_entry(absent, mode="nulled", redistribution=disposition)],
        ),
        gate.SCHEMA_FILE,
    )

    assert dropped.verdict == nulled.verdict
    assert {item.rule for item in dropped.findings} == {item.rule for item in nulled.findings}
    assert dropped.absent_fields_by_dataset == nulled.absent_fields_by_dataset


# ---------------------------------------------------------------------------
# 3. Naming, with non-emptiness asserted
# ---------------------------------------------------------------------------


@given(absent=_absent_fields, mode=_absence_mode, disposition=_disposition)
def test_every_absent_field_is_named_in_the_report(
    tmp_path: Path, absent: set[str], mode: str, disposition: str
) -> None:
    """Each unestablished term appears **by name** in the gate's own output.

    The non-emptiness clause is load-bearing. "No absence went unnamed" is trivially true of a
    gate that emits nothing at all, which is the vacuity that lets a property pass over a stub;
    so a non-empty absent set is required to produce a non-empty findings tuple, and only then
    is the naming checked. The complementary direction is checked too: a term that WAS
    established must not be named as absent, or the report sends an operator to read something
    they already recorded.
    """
    report = gate.assess(
        _write(
            tmp_path / "dataset-licences.yaml",
            [_entry(absent, mode=mode, redistribution=disposition)],
        ),
        gate.SCHEMA_FILE,
    )
    named = " ".join(
        (report.reason, *report.notes, *(item.detail for item in report.findings))
    )

    if absent:
        assert report.findings, "an absence with no finding is an absence nobody was told about"
        assert any(item.rule == "field-absent" for item in report.findings)
        for field in absent:
            assert field in named, f"the report must NAME {field}, not merely count it"
    else:
        assert not [item for item in report.findings if item.rule == "field-absent"]
    for field in set(R8_1_FIELDS) - absent:
        assert field not in {
            name for _label, names in report.absent_fields_by_dataset for name in names
        }, f"{field} was established but reported absent"


# ---------------------------------------------------------------------------
# 4. No absence ever reads as a pass
# ---------------------------------------------------------------------------


@given(absent=_absent_fields, mode=_absence_mode, disposition=_disposition)
def test_no_absence_ever_reads_as_a_pass(
    tmp_path: Path, absent: set[str], mode: str, disposition: str
) -> None:
    """R8.2: any absent declared field yields a non-passing result, over the whole powerset.

    Stated as an equivalence rather than an implication, so the pass branch is exercised too: a
    gate that never passed would satisfy the one-directional reading while being useless. The
    exit code is asserted alongside the verdict because that is what a CI step consumes -- a
    verdict nobody can act on is not a gate.
    """
    report = gate.assess(
        _write(
            tmp_path / "dataset-licences.yaml",
            [_entry(absent, mode=mode, redistribution=disposition)],
        ),
        gate.SCHEMA_FILE,
    )

    assert report.passing is (not absent)
    assert (report.verdict == "pass") is (not absent)
    assert report.exit_code == (gate.EXIT_PASS if not absent else gate.EXIT_UNAVAILABLE)
    if absent:
        assert report.verdict == "unavailable", (
            "an unestablished term is an absence, not a defect: nobody wrote a wrong value, "
            f"so the honest verdict is unavailable, got {report.verdict}"
        )


# ---------------------------------------------------------------------------
# 5. A flag that outruns its subject is a defect, not an absence
# ---------------------------------------------------------------------------


@given(absent=_absent_fields, mode=_absence_mode, disposition=_disposition)
def test_an_overclaiming_flag_is_a_fail_and_never_a_skip(
    tmp_path: Path, absent: set[str], mode: str, disposition: str
) -> None:
    """``confirmed: true`` beside an unestablished term is a FAIL, and names the term.

    The asymmetry is the point and it is asserted in both directions. Over-claiming is a false
    self-statement -- somebody wrote ``true`` in this tree -- so it must not sit in the same
    SKIP bucket as the honestly-unread entries, or the one document that is wrong about itself
    becomes indistinguishable from the ones that are merely incomplete. Under-claiming (every
    field populated, flag still false) is an operator mid-procedure and is not a finding at all.
    """
    report = gate.assess(
        _write(
            tmp_path / "dataset-licences.yaml",
            [_entry(absent, mode=mode, flag=True, redistribution=disposition)],
        ),
        gate.SCHEMA_FILE,
    )
    entry = _model(_entry(absent, mode=mode, flag=True, redistribution=disposition))

    assert entry.flag_disagrees() is bool(absent)
    assert (report.verdict == "fail") is bool(absent)
    if absent:
        assert report.exit_code == gate.EXIT_FAIL
        disagreements = [i for i in report.findings if i.rule == "flag-disagreement"]
        assert disagreements, "an over-claimed confirmation must produce its own finding"
        assert all(item.fatal for item in disagreements)
        detail = " ".join(item.detail for item in disagreements)
        for field in absent:
            assert field in detail, f"the disagreement must name {field}"
    else:
        assert not [i for i in report.findings if i.rule == "flag-disagreement"]
        assert report.verdict == "pass", report.reason


# ---------------------------------------------------------------------------
# The disposition the properties above deliberately held constant
# ---------------------------------------------------------------------------


@given(absent=_absent_fields, mode=_absence_mode)
def test_an_unestablished_redistribution_is_never_a_pass_either(
    tmp_path: Path, absent: set[str], mode: str
) -> None:
    """A null redistribution is non-passing whatever the six R8.1 fields say.

    Held constant in every property above so those measured R8.1's rule rather than this one;
    asserted here so holding it constant is a scoping decision rather than a blind spot. Note
    what the two values mean: ``unknown`` asserts the terms were read and found silent, ``null``
    asserts they were not read. Neither is ``permitted``, and collapsing them would lose the
    difference between an answered question and an unasked one.
    """
    report = gate.assess(
        _write(
            tmp_path / "dataset-licences.yaml",
            [_entry(absent, mode=mode, redistribution=None)],
        ),
        gate.SCHEMA_FILE,
    )

    assert not report.passing, "an unread redistribution disposition is not a permissive one"
    unestablished = [
        item for item in report.findings if item.rule == "redistribution-unestablished"
    ]
    assert unestablished, "a null disposition must produce its own named finding"
    assert not any(item.fatal for item in unestablished), (
        "an unread disposition is an absence, not a defect: nobody wrote a wrong value, so it "
        "must not be reported as fatal"
    )
