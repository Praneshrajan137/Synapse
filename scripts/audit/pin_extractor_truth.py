"""Every declared pin's extractor RESOLVES -- verified by running it (AD-13; R5.2, R5.12).

Feature: decision-quality-proof, task 8.3.

**The one-word addition to AD-13: extractors are verified by *running* them.**

A pin is a triple -- (document anchor, mechanical source, extractor). The predecessor spec's
Property 5 asserts that the extracted values *agree* and that extraction is *idempotent*. It
does **not** assert that the extractor *resolves*. Those are different claims, and the gap
between them is a silent one:

    a `yaml_path:` naming a key that no longer exists  ->  yields nothing
    a `json_path:` into a restructured file            ->  yields nothing
    an `anchor` regex whose document prose was reworded ->  matches nothing

...and *nothing compared against nothing agrees*. `None == None`. A pin that compares two
absences reports green, having established precisely nothing about the number it was written
to protect. This is the same failure shape as `published_checkpoint_truth.evaluate` letting an
`UNAVAILABLE` outcome fall through to `ok`, and as a property passing over a stub that returns
`[]`: the mechanism runs, reports success, and measures nothing.

**Why this cannot be left to `doc_truth`.** `doc_truth` evaluates pins and reports per-claim
statuses, and task 8.3 hardened it so that an unresolvable extractor lands on a non-passing
status rather than an `ok`. But `doc_truth` only reaches an extractor when the *document* side
resolved first: if the anchor regex fails, the source extractor is never invoked at all, so a
long-dead `yaml_path:` can sit in the table indefinitely without ever being exercised. This
module inverts that -- it runs **every declared extractor against its declared source
unconditionally**, independent of whether the document anchor matched, and fails on any that
resolves to nothing.

**Three clauses, and the second is the one with teeth.**

1. ``pin-table-unreadable`` -> ``unavailable``. The table itself could not be parsed, so no
   pin was checked. Non-passing, and never a pass (I-7).
2. ``source-extractor-unresolved`` -> ``fail``, naming the pin, the side, the source file and
   the extractor expression. This is the clause that closes the hole. A declared extractor
   that yields nothing is a **defect in this tree**, fixable in the change that broke it --
   not an absence to be tolerated.
3. ``document-anchor-unresolved`` -> ``fail``, naming the pin and the anchor. The document
   half of the same hole: an anchor that matches no line means the pin is guarding a sentence
   that no longer exists.

**Two deliberate non-findings**, because a gate that reports non-defects trains its readers to
ignore it:

* ``kind: generated`` pins are **skipped by design**. Their document side is a projection of
  their source side, so comparing them compares a mechanism to itself -- the shape AD-21
  rejects. Their generator's own ``--check`` mode owns them. Skipped pins are *counted and
  named* in the report, so the exemption is visible rather than silent.
* A **missing source or document file** is reported as ``unavailable`` for that pin rather
  than ``fail``. The distinction matters and mirrors ``anchor_truth``'s recorded reasoning:
  "the file is gone" and "the file is there and the expression no longer matches it" are
  different repairs, and only the second is evidence that a pin has silently stopped
  measuring.

**Nothing here compares values.** Whether the two sides *agree* is `doc_truth`'s job and
Property 5's subject. This module answers the strictly prior question that nobody was asking:
*did either side produce a value at all?*

Run::

    python -m scripts.audit.pin_extractor_truth            # human summary
    python -m scripts.audit.pin_extractor_truth --json     # canonical machine JSON
    python -m scripts.audit.pin_extractor_truth --check    # exit-code only mode

Exit codes: ``0`` pass, ``1`` fail, ``2`` unavailable. ``2`` is non-passing.
Cheap by construction: pure file reads plus regex/YAML/JSON walks, no subprocess, so this is
a category-5 workload under I-0 and is safe to run locally.
Every file is read with ``encoding='utf-8'`` (E-S13-07) and all console output is ASCII.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Final, Literal

import structlog
from pydantic import BaseModel, ConfigDict

ROOT: Final[Path] = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:  # importable when run as a bare script
    sys.path.insert(0, str(ROOT))

from scripts.audit.doc_truth import (  # noqa: E402 - after the sys.path guard
    PIN_TABLE,
    NumericPin,
    documented_value,
    extract_source_values,
    load_pins,
)
from scripts.audit.doc_truth import _Unresolvable as PinUnresolvable  # noqa: E402

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 1
EXIT_UNAVAILABLE: Final[int] = 2

Verdict = Literal["pass", "fail", "unavailable"]

_EXIT_CODES: Final[dict[str, int]] = {
    "pass": EXIT_PASS,
    "fail": EXIT_FAIL,
    "unavailable": EXIT_UNAVAILABLE,
}
_SYMBOLS: Final[dict[str, str]] = {"pass": "[OK]", "fail": "[XX]", "unavailable": "[--]"}

#: Rule -> verdict contribution, as a table rather than inline branches so the
#: fail-versus-unavailable split is auditable at a glance and cannot drift per call site.
_RULE_VERDICTS: Final[dict[str, Verdict]] = {
    "pin-table-unreadable": "unavailable",
    "source-file-missing": "unavailable",
    "document-file-missing": "unavailable",
    "source-extractor-unresolved": "fail",
    "document-anchor-unresolved": "fail",
}

_LOG = structlog.get_logger(__name__)

__all__ = [
    "EXIT_FAIL",
    "EXIT_PASS",
    "EXIT_UNAVAILABLE",
    "ROOT",
    "ExtractorFinding",
    "ExtractorProbe",
    "PinExtractorReport",
    "assess",
    "main",
    "probe_pin",
    "run",
]


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _ascii(text: str) -> str:
    """Escape non-ASCII for the Windows console (ASCII-only output contract)."""
    return text if text.isascii() else text.encode("unicode_escape").decode("ascii")


def _read(path: Path) -> str | None:
    """Read one file as UTF-8 (E-S13-07), or ``None`` when it cannot be read."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ExtractorFinding(BaseModel):
    """One finding, naming its rule, the pin it is about, and the side that failed."""

    model_config = ConfigDict(frozen=True)

    rule: str
    requirement: str
    pin_id: str
    side: Literal["document", "source", "table"]
    subject: str
    detail: str

    @property
    def verdict_contribution(self) -> Verdict:
        return _RULE_VERDICTS.get(self.rule, "fail")

    @property
    def fatal(self) -> bool:
        """A defect in this tree, as opposed to an absence. See the module docstring."""
        return self.verdict_contribution == "fail"


class ExtractorProbe(BaseModel):
    """What running one pin's two extractors actually produced.

    ``source_values`` is recorded, not just its length, because a failure detail should be
    able to quote the source byte-for-byte -- ``0.70``, not ``0.7``.
    """

    model_config = ConfigDict(frozen=True)

    pin_id: str
    kind: str
    required: bool
    document: str
    source: str
    extractor: str
    skipped: bool
    skip_reason: str | None
    document_resolved: bool
    documented_value: str | None
    document_line: int | None
    source_resolved: bool
    source_values: tuple[str, ...]


class PinExtractorReport(BaseModel):
    """Everything one execution of this gate observed."""

    model_config = ConfigDict(frozen=True)

    pin_table: str
    pins_declared: int
    pins_probed: int
    pins_skipped: int
    both_sides_resolved: int
    probes: tuple[ExtractorProbe, ...]
    findings: tuple[ExtractorFinding, ...]
    notes: tuple[str, ...]
    verdict: Verdict
    reason: str

    @property
    def exit_code(self) -> int:
        return _EXIT_CODES[self.verdict]

    @property
    def passing(self) -> bool:
        """``unavailable`` is not a pass (I-7)."""
        return self.verdict == "pass"


def _verdict_of(findings: tuple[ExtractorFinding, ...]) -> Verdict:
    """``fail`` outranks ``unavailable`` outranks ``pass``.

    An extractor that stopped resolving is a worse fact than a file that is absent, because
    the absent file is visible and the dead extractor was reporting green.
    """
    contributions = {finding.verdict_contribution for finding in findings}
    if "fail" in contributions:
        return "fail"
    if "unavailable" in contributions:
        return "unavailable"
    return "pass"


# ---------------------------------------------------------------------------
# Probing
# ---------------------------------------------------------------------------


def probe_pin(
    pin: NumericPin, *, root: Path = ROOT
) -> tuple[ExtractorProbe, tuple[ExtractorFinding, ...]]:
    """Run both of one pin's extractors and report whether each produced anything.

    Deliberately does **not** compare the two sides. Agreement is ``doc_truth``'s subject;
    this answers the strictly prior question of whether either side produced a value.

    The two sides are probed **independently**: unlike ``doc_truth.resolve_pin_texts``, a
    document anchor that fails to match does not prevent the source extractor from running.
    That independence is the whole point -- a dead ``yaml_path:`` behind a reworded sentence
    is exactly the case that was never being exercised.
    """
    findings: list[ExtractorFinding] = []
    document_path = root / pin.document
    source_path = root / pin.source

    if pin.kind == "generated":
        reason = (
            f"kind: generated -- {pin.document}'s value is a projection of {pin.source}, so "
            "pinning them compares a mechanism to itself (AD-21). The generator's --check "
            "mode owns this claim"
        )
        return (
            ExtractorProbe(
                pin_id=pin.id,
                kind=pin.kind,
                required=pin.required,
                document=pin.document,
                source=pin.source,
                extractor=pin.extractor,
                skipped=True,
                skip_reason=reason,
                document_resolved=False,
                documented_value=None,
                document_line=None,
                source_resolved=False,
                source_values=(),
            ),
            (),
        )

    # --- source side, probed unconditionally -----------------------------------------
    source_text = _read(source_path)
    source_values: tuple[str, ...] = ()
    source_resolved = False
    if source_text is None:
        findings.append(
            ExtractorFinding(
                rule="source-file-missing",
                requirement="R5.2, R5.12",
                pin_id=pin.id,
                side="source",
                subject=pin.source,
                detail=(
                    "the mechanical source is missing or unreadable, so the extractor could "
                    "not be run at all; that is an absence, not a dead extractor"
                ),
            )
        )
    else:
        try:
            source_values = extract_source_values(pin.extractor, source_text)
        except PinUnresolvable as error:
            findings.append(
                ExtractorFinding(
                    rule="source-extractor-unresolved",
                    requirement="R5.2, R5.11, R5.12",
                    pin_id=pin.id,
                    side="source",
                    subject=f"{pin.source} :: {pin.extractor}",
                    detail=(
                        f"the declared extractor could not be resolved: {_ascii(str(error))}. "
                        "An extractor that yields nothing makes the pin compare an absence, "
                        "and two absences agree -- so this pin was reporting green while "
                        "measuring nothing"
                    ),
                )
            )
        else:
            source_resolved = bool(source_values)
            if not source_resolved:
                findings.append(
                    ExtractorFinding(
                        rule="source-extractor-unresolved",
                        requirement="R5.2, R5.11, R5.12",
                        pin_id=pin.id,
                        side="source",
                        subject=f"{pin.source} :: {pin.extractor}",
                        detail=(
                            "the declared extractor resolved to an EMPTY set of values. The "
                            "expression parsed but matched nothing in the source, which is "
                            "the silent case: the pin compares nothing and reports agreement"
                        ),
                    )
                )

    # --- document side, probed independently ------------------------------------------
    document_text = _read(document_path)
    documented: str | None = None
    document_line: int | None = None
    document_resolved = False
    if document_text is None:
        findings.append(
            ExtractorFinding(
                rule="document-file-missing",
                requirement="R5.2, R5.12",
                pin_id=pin.id,
                side="document",
                subject=pin.document,
                detail="the governance document is missing or unreadable",
            )
        )
    else:
        try:
            documented, document_line = documented_value(pin, document_text)
        except PinUnresolvable as error:
            findings.append(
                ExtractorFinding(
                    rule="document-anchor-unresolved",
                    requirement="R5.2, R5.12",
                    pin_id=pin.id,
                    side="document",
                    subject=f"{pin.document} :: {pin.anchor}",
                    detail=(
                        f"the declared anchor did not resolve: {_ascii(str(error))}. The pin "
                        "is guarding a sentence that no longer exists in the document"
                    ),
                )
            )
        else:
            document_resolved = True

    return (
        ExtractorProbe(
            pin_id=pin.id,
            kind=pin.kind,
            required=pin.required,
            document=pin.document,
            source=pin.source,
            extractor=pin.extractor,
            skipped=False,
            skip_reason=None,
            document_resolved=document_resolved,
            documented_value=documented,
            document_line=document_line,
            source_resolved=source_resolved,
            source_values=source_values,
        ),
        tuple(findings),
    )


def assess(pin_table: Path = PIN_TABLE, *, root: Path = ROOT) -> PinExtractorReport:
    """Run every declared pin's extractors. Total over every malformed input; never raises."""
    table_rel = _relative(pin_table)

    table_text = _read(pin_table)
    if table_text is None:
        findings = (
            ExtractorFinding(
                rule="pin-table-unreadable",
                requirement="R5.2",
                pin_id="<table>",
                side="table",
                subject=table_rel,
                detail="the pin table is missing or unreadable, so no extractor was run",
            ),
        )
        return PinExtractorReport(
            pin_table=table_rel,
            pins_declared=0,
            pins_probed=0,
            pins_skipped=0,
            both_sides_resolved=0,
            probes=(),
            findings=findings,
            notes=(),
            verdict="unavailable",
            reason=f"{table_rel} could not be read, so no pin's extractor was exercised",
        )

    try:
        pins = load_pins(table_text)
    except PinUnresolvable as error:
        findings = (
            ExtractorFinding(
                rule="pin-table-unreadable",
                requirement="R5.2",
                pin_id="<table>",
                side="table",
                subject=table_rel,
                detail=_ascii(str(error)),
            ),
        )
        return PinExtractorReport(
            pin_table=table_rel,
            pins_declared=0,
            pins_probed=0,
            pins_skipped=0,
            both_sides_resolved=0,
            probes=(),
            findings=findings,
            notes=(),
            verdict="unavailable",
            reason=f"{table_rel} is not a readable pin table, so no extractor was exercised",
        )

    probes: list[ExtractorProbe] = []
    collected: list[ExtractorFinding] = []
    for pin in pins:
        probe, findings_for_pin = probe_pin(pin, root=root)
        probes.append(probe)
        collected.extend(findings_for_pin)

    ordered = tuple(collected)
    verdict = _verdict_of(ordered)
    skipped = tuple(probe for probe in probes if probe.skipped)
    probed = tuple(probe for probe in probes if not probe.skipped)
    both = tuple(
        probe for probe in probed if probe.document_resolved and probe.source_resolved
    )

    notes = [
        f"pin table: {len(pins)} pin(s) declared in {table_rel}",
        (
            f"probed: {len(probed)} pin(s); {len(both)} resolved on BOTH sides "
            f"(a pin resolving on one side only compares a value against an absence)"
        ),
    ]
    for probe in skipped:
        notes.append(f"skipped {probe.pin_id}: {probe.skip_reason}")
    if not probed:
        notes.append(
            "no pin was probed at all, so this gate established nothing about any extractor"
        )

    if verdict == "pass":
        reason = (
            f"every declared extractor resolved: {len(both)} of {len(probed)} probed pin(s) "
            f"produced a value on both sides, {len(skipped)} skipped as generated "
            "projections (AD-21). Each was verified by RUNNING it, not by assuming it"
        )
    elif verdict == "fail":
        dead = sorted({finding.pin_id for finding in ordered if finding.fatal})
        reason = (
            f"{len(dead)} pin(s) declare an extractor or anchor that no longer resolves "
            f"({', '.join(dead)}): each was comparing an absence and reporting agreement"
        )
    else:
        reason = (
            "no extractor could be exercised for at least one pin because a declared file is "
            "absent; that is an absence rather than a dead extractor, and it is non-passing"
        )

    _LOG.info(
        "pin_extractor.assessed",
        verdict=verdict,
        declared=len(pins),
        probed=len(probed),
        skipped=len(skipped),
        both_sides_resolved=len(both),
        findings=len(ordered),
    )

    return PinExtractorReport(
        pin_table=table_rel,
        pins_declared=len(pins),
        pins_probed=len(probed),
        pins_skipped=len(skipped),
        both_sides_resolved=len(both),
        probes=tuple(probes),
        findings=ordered,
        notes=tuple(notes),
        verdict=verdict,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_report(report: PinExtractorReport) -> None:
    symbol = _SYMBOLS[report.verdict]
    print(f"{symbol} pin-extractors: {report.verdict.upper()} - {_ascii(report.reason)}")
    for note in report.notes:
        print(f"     - {_ascii(note)}")
    for finding in report.findings:
        print(
            f"  {_SYMBOLS[finding.verdict_contribution]} {finding.rule} "
            f"[{finding.requirement}] {finding.pin_id} ({finding.side}) "
            f"{_ascii(finding.subject)}: {_ascii(finding.detail)}"
        )


def run(*, as_json: bool = False, check: bool = False) -> int:
    """Evaluate and report. Returns ``0`` / ``1`` / ``2`` in both modes."""
    report = assess()

    if as_json:
        print(json.dumps(report.model_dump(mode="json"), sort_keys=True, separators=(",", ":")))
        return report.exit_code

    _print_report(report)
    if not check:
        print(
            "(a pin is only evidence if its extractor resolves; two absences agree, so an "
            "unresolved extractor reports green while measuring nothing.)"
        )
    return report.exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pin_extractor_truth",
        description=(
            "Run every declared pin's extractor against its declared source and fail on any "
            "that resolves to nothing."
        ),
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return run(as_json=bool(args.as_json), check=bool(args.check))


if __name__ == "__main__":
    sys.exit(main())
