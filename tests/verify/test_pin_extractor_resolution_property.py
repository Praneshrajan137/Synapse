"""Feature: decision-quality-proof, Property 48: Every declared pin's extractor resolves.

Task 8.4. Subject: ``scripts/audit/pin_extractor_truth``.

**What this property is really about.** A pin is a triple -- document anchor, mechanical
source, extractor. The predecessor spec's Property 5 asserts that the two extracted values
*agree* and that extraction is *idempotent*. Neither clause asserts that the extractor
*resolves*, and that gap is silent in the worst way: a ``yaml_path:`` naming a key that no
longer exists yields nothing, and **nothing compared against nothing agrees**. ``None ==
None``. The pin reports green having established nothing about the number it guards.

So the property under test is not "the values match" -- it is the strictly prior question
*did either side produce a value at all*, and the load-bearing clauses are the negative ones:

* an unresolved source extractor is **never** a pass, on any input;
* an **empty** extraction is a fail, not a silent success -- the expression parsed and matched
  nothing, which is exactly the case that used to report agreement;
* the two sides are probed **independently**, so a dead document anchor cannot hide a dead
  source extractor behind it. That is the specific behaviour that distinguishes this gate from
  ``doc_truth``, which only reaches the source extractor once the document anchor matched, and
  therefore never exercises an extractor sitting behind a reworded sentence.

Budget inherited from the root ``conftest.py`` profile via ``HYPOTHESIS_PROFILE``
(``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000). **No ``max_examples``
literal appears in this file** -- a hardcoded value overrides the profile in *both*
directions, which is what amplified the original I-0 incident.

Locus: ``ci.yml::uplift-verify`` fast step (``-m "not slow"``). Not slow-marked: every case
here is a temporary-directory file write plus a pure regex/YAML walk, with no subprocess, no
twin and no network.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit.doc_truth import NumericPin
from scripts.audit.pin_extractor_truth import (
    EXIT_FAIL,
    EXIT_PASS,
    EXIT_UNAVAILABLE,
    assess,
    probe_pin,
)

if TYPE_CHECKING:  # annotation-only
    from pathlib import Path

#: Pin identifiers: short, safe, and never empty, because an id is what every finding is
#: attributed to and an anonymous finding is unactionable.
_IDS: Final = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Nd"), whitelist_characters="-"),
    min_size=1,
    max_size=12,
).filter(lambda value: value.strip("-") != "")

#: The four non-generated kinds. `generated` is exercised separately, because its whole
#: contract is to be skipped rather than probed.
_PROBED_KINDS: Final = st.sampled_from(["threshold", "flag", "blocking-gate", "required-job"])


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _pin(
    *,
    pin_id: str = "fixture-pin",
    kind: str = "threshold",
    document: str = "DOC.md",
    anchor: str = r"target (?P<value>[\d.]+) percent",
    source: str = "src.yaml",
    extractor: str = "yaml_path:target",
    compare: str = "numeric",
) -> NumericPin:
    return NumericPin(
        id=pin_id,
        kind=kind,  # type: ignore[arg-type]
        required=True,
        document=document,
        anchor=anchor,
        source=source,
        extractor=extractor,
        compare=compare,  # type: ignore[arg-type]
    )


def _table(pins: list[dict[str, Any]]) -> str:
    return yaml.safe_dump({"version": 1, "pins": pins}, sort_keys=True)


def _pin_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": "fixture-pin",
        "kind": "threshold",
        "required": True,
        "document": "DOC.md",
        "anchor": r"target (?P<value>[\d.]+) percent",
        "source": "src.yaml",
        "extractor": "yaml_path:target",
        "compare": "numeric",
        "scale": "identity",
    }
    row.update(overrides)
    return row


def _tree(
    tmp_path: Path,
    *,
    document: str = "target 80 percent\n",
    source: str = "target: 80\n",
) -> Path:
    _write(tmp_path / "DOC.md", document)
    _write(tmp_path / "src.yaml", source)
    return tmp_path


# ---------------------------------------------------------------------------
# 1. The negative clauses -- an unresolved extractor is NEVER a pass
# ---------------------------------------------------------------------------


@given(pin_id=_IDS, kind=_PROBED_KINDS)
def test_a_source_extractor_resolving_to_nothing_is_never_a_pass(
    tmp_path_factory: pytest.TempPathFactory, pin_id: str, kind: str
) -> None:
    """The whole point. An extractor that yields nothing must fail, for every id and kind.

    This is the ``None == None`` hole stated as a property: the expression parses, matches
    nothing, and the pin would otherwise compare an absence against an absence and agree.
    """
    root = _tree(tmp_path_factory.mktemp("nothing"))
    # `target` exists; `absent_key` does not. The expression is well-formed either way.
    table = _write(
        root / "pins.yaml",
        _table([_pin_row(id=pin_id, kind=kind, extractor="yaml_path:absent_key")]),
    )

    report = assess(table, root=root)

    assert report.verdict == "fail", report.reason
    assert not report.passing, "an unresolved extractor is never a pass (I-7)"
    assert report.exit_code == EXIT_FAIL
    assert any(
        finding.rule == "source-extractor-unresolved" and finding.pin_id == pin_id
        for finding in report.findings
    ), report.findings
    # The finding must name the pin, the file AND the expression -- a report that merely
    # counts failures cannot be acted on.
    blob = " ".join(f"{f.subject} {f.detail}" for f in report.findings)
    assert "absent_key" in blob
    assert "src.yaml" in blob


@given(kind=_PROBED_KINDS)
def test_a_dead_document_anchor_does_not_hide_a_dead_source_extractor(
    tmp_path_factory: pytest.TempPathFactory, kind: str
) -> None:
    """The clause that distinguishes this gate from ``doc_truth``.

    ``doc_truth.resolve_pin_texts`` resolves the document side FIRST and returns early when
    the anchor fails, so the source extractor is never invoked -- meaning a long-dead
    ``yaml_path:`` sitting behind a reworded sentence is never exercised at all. Here both
    sides are probed independently, so BOTH findings appear.
    """
    root = _tree(tmp_path_factory.mktemp("both_dead"), document="nothing pinned here\n")
    table = _write(
        root / "pins.yaml",
        _table([_pin_row(kind=kind, extractor="yaml_path:absent_key")]),
    )

    report = assess(table, root=root)

    rules = {finding.rule for finding in report.findings}
    assert "document-anchor-unresolved" in rules
    assert "source-extractor-unresolved" in rules, (
        "the source extractor must be probed even though the document anchor failed; "
        "otherwise a dead extractor hides behind a reworded sentence"
    )
    assert report.verdict == "fail"


def test_an_empty_extraction_is_a_fail_not_a_silent_success(tmp_path: Path) -> None:
    """An expression that parses and matches nothing is the silent case, so it must be loud."""
    root = _tree(tmp_path, source="other: 1\n")
    table = _write(root / "pins.yaml", _table([_pin_row(extractor="regex:no-such-text")]))

    report = assess(table, root=root)

    assert report.verdict == "fail"
    finding = next(f for f in report.findings if f.rule == "source-extractor-unresolved")
    assert "EMPTY" in finding.detail or "empty" in finding.detail


# ---------------------------------------------------------------------------
# 2. The fail-versus-unavailable split
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["document", "source"])
def test_a_missing_file_is_unavailable_not_a_dead_extractor(
    tmp_path: Path, missing: str
) -> None:
    """"The file is gone" and "the expression stopped matching" are different repairs.

    Only the second is evidence that a pin silently stopped measuring, so only the second is
    a fail. Both are non-passing.
    """
    root = _tree(tmp_path)
    (root / ("DOC.md" if missing == "document" else "src.yaml")).unlink()
    table = _write(root / "pins.yaml", _table([_pin_row()]))

    report = assess(table, root=root)

    assert report.verdict == "unavailable", report.reason
    assert not report.passing, "unavailable is not a pass (I-7)"
    assert report.exit_code == EXIT_UNAVAILABLE
    assert {f.rule for f in report.findings} == {f"{missing}-file-missing"}
    assert not any(f.fatal for f in report.findings), (
        "an absent file is an absence, not a defect in this tree"
    )


def test_an_unreadable_pin_table_is_unavailable_and_probes_nothing(tmp_path: Path) -> None:
    """No pin was exercised, so the gate established nothing -- and must say so."""
    report = assess(tmp_path / "no-such-table.yaml", root=tmp_path)

    assert report.verdict == "unavailable"
    assert not report.passing
    assert report.pins_probed == 0
    assert {f.rule for f in report.findings} == {"pin-table-unreadable"}


# ---------------------------------------------------------------------------
# 3. `kind: generated` is skipped, counted, and never evaluated (AD-21)
# ---------------------------------------------------------------------------


def test_a_generated_pin_is_skipped_named_and_never_probed(tmp_path: Path) -> None:
    """Comparing a generated region against its own source compares a mechanism to itself.

    AD-21 rejects that shape, so the pin is skipped -- but **counted and named**, because a
    silent exemption is indistinguishable from an oversight.
    """
    root = _tree(tmp_path, document="nothing here\n", source="other: 1\n")
    table = _write(
        root / "pins.yaml",
        _table([_pin_row(id="generated-pin", kind="generated", extractor="yaml_path:absent")]),
    )

    report = assess(table, root=root)

    # Both sides are broken, yet there is no finding: the pin was never evaluated.
    assert report.findings == (), "a generated pin must not be probed at all"
    assert report.verdict == "pass"
    assert report.pins_skipped == 1
    assert report.pins_probed == 0
    probe = report.probes[0]
    assert probe.skipped is True
    assert probe.skip_reason is not None and "generated" in probe.skip_reason
    # And the exemption is visible in the human-readable notes, not only in the model.
    assert any("skipped generated-pin" in note for note in report.notes)


# ---------------------------------------------------------------------------
# 4. Totality and the verdict lattice
# ---------------------------------------------------------------------------


@given(
    body=st.one_of(
        st.just(""),
        st.just("- not a mapping\n"),
        st.just("version: 1\n"),
        st.just("version: 1\npins: []\n"),
        st.just("pins: [unclosed\n"),
        st.text(max_size=40),
    )
)
def test_assess_is_total_over_malformed_pin_tables(
    tmp_path_factory: pytest.TempPathFactory, body: str
) -> None:
    """The gate never raises through its caller.

    C75 calls ``assess`` directly, so an escaping exception would be coerced into a FAIL
    naming a crash rather than reporting the honest state. Every malformed table must produce
    a report with a verdict in the closed three-value vocabulary.
    """
    root = tmp_path_factory.mktemp("total")
    table = _write(root / "pins.yaml", body)

    report = assess(table, root=root)

    assert report.verdict in {"pass", "fail", "unavailable"}
    assert report.exit_code in {EXIT_PASS, EXIT_FAIL, EXIT_UNAVAILABLE}
    assert report.passing is (report.verdict == "pass")


def test_fail_outranks_unavailable_when_both_hold(tmp_path: Path) -> None:
    """An extractor that stopped resolving is a worse fact than a file that is absent.

    The absent file is visible; the dead extractor was reporting green. So a table carrying
    both must report ``fail``, not the milder verdict.
    """
    root = _tree(tmp_path)
    (root / "src2.yaml")  # deliberately not created
    table = _write(
        root / "pins.yaml",
        _table(
            [
                _pin_row(id="dead-extractor", extractor="yaml_path:absent_key"),
                _pin_row(id="absent-source", source="src2.yaml"),
            ]
        ),
    )

    report = assess(table, root=root)

    rules = {f.rule for f in report.findings}
    assert "source-extractor-unresolved" in rules
    assert "source-file-missing" in rules
    assert report.verdict == "fail", "fail outranks unavailable"


def test_a_fully_resolving_table_passes(tmp_path: Path) -> None:
    """The pass branch is reachable -- a gate that can never pass is not a gate."""
    root = _tree(tmp_path)
    table = _write(root / "pins.yaml", _table([_pin_row()]))

    report = assess(table, root=root)

    assert report.verdict == "pass", report.reason
    assert report.passing
    assert report.exit_code == EXIT_PASS
    assert report.findings == ()
    assert report.pins_probed == 1
    assert report.both_sides_resolved == 1


# ---------------------------------------------------------------------------
# 5. probe_pin's own contract, independent of the table reader
# ---------------------------------------------------------------------------


@given(extractor=st.sampled_from(["yaml_path:target", "regex:target: (?P<value>[\\d.]+)"]))
def test_probe_pin_reports_the_raw_extracted_values(
    tmp_path_factory: pytest.TempPathFactory, extractor: str
) -> None:
    """Values are recorded raw, so a failure detail can quote the source byte-for-byte.

    ``0.70`` and ``0.7`` are the same number and different bytes, and a pin failure that
    normalises them cannot show a reader what the file actually says.
    """
    root = _tree(
        tmp_path_factory.mktemp("raw"),
        source="target: 0.70\n",
        document="target 0.70 percent\n",
    )
    pin = _pin(extractor=extractor, anchor=r"target (?P<value>[\d.]+) percent")

    probe, findings = probe_pin(pin, root=root)

    if probe.source_resolved:
        assert findings == ()
        assert probe.source_values, "a resolved probe must carry the values it resolved"
        assert any("0.70" in value for value in probe.source_values), probe.source_values


def test_the_committed_pin_table_resolves_on_both_sides() -> None:
    """The real tree, not a fixture: every committed pin's extractor is exercised.

    This is the clause that makes the gate a gate rather than a well-tested library. It is
    also the one that will fail the moment somebody reorganises a source file and leaves a
    pin behind -- which is precisely the event that used to be silent.
    """
    report = assess()

    assert report.pins_declared > 0, "the committed pin table must declare at least one pin"
    assert report.verdict == "pass", report.reason
    assert report.both_sides_resolved == report.pins_probed, (
        "every probed pin must resolve on BOTH sides; a pin resolving on one side compares a "
        f"value against an absence: {report.reason}"
    )


def test_the_report_is_canonically_serialisable() -> None:
    """The report is consumed as JSON by ``--json``, so it must round-trip deterministically."""
    report = assess()

    blob = json.dumps(report.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    again = json.dumps(report.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    assert blob == again, "serialisation must be deterministic"
    assert json.loads(blob)["verdict"] == report.verdict
