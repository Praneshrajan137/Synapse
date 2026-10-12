"""The external-dataset licence register is schema-total, and an absent term is named (R8.1, R8.2).

Feature: decision-quality-proof, task 7.2. Design section E4a.2.

There is **no dataset-licence gate anywhere in the tree** before this module, so this is the
whole of the mechanism R8.2 asks for. It reads
``infrastructure/data/dataset-licences.yaml``, validates it against
``infrastructure/data/schemas/dataset-licences.schema.json``, and reports a non-passing
result naming any field that is absent or schema-invalid.

**The distinction this module exists to preserve.** R8.1 names six fields. Three of them are
properties of a licence *text* that sits behind an acceptance gate, and reading it is an
operator act. So the honest state of this register on the day it lands is "the identity and
the location are established; the terms are not". That state must be **reportable**, and it
must be reportable as *non-passing* without being reportable as *broken*. Hence the split
below, which mirrors ``anchor_truth``'s recorded reasoning that "we are not anchored" and
"the anchor we have is broken" are two different repairs:

* ``unavailable`` (exit 2, -> SKIP in the registry) — the register is well-formed and is
  telling the truth about what it does not know. ``register-absent``, ``field-absent``,
  ``redistribution-unestablished``, ``schema-version-unrecognised``, ``schema-absent``,
  ``register-unparseable``.
* ``fail`` (exit 1) — the register is making a **false statement about itself**.
  ``schema-invalid`` and ``flag-disagreement``.

``flag-disagreement`` is the clause worth reading twice. An entry whose
``confirmation.confirmed`` is ``true`` while an R8.1 field is still ``null`` is not merely
incomplete: it asserts a confirmation that its own fields contradict. That is a fail, not a
skip. The reverse — every field populated with the flag still ``false`` — is **not** a
finding, because it is the ordinary state of an operator mid-procedure, and failing it would
punish the honest half of the work. ``DatasetLicence.confirmed`` is therefore **derived from
the fields** and the flag is only ever compared against it, never trusted
(``data_fabric/licence.py``). A boolean that can disagree with its own subject is a claim,
not evidence — the same shape that let ``published_checkpoint_truth.evaluate`` fall through
from ``UNAVAILABLE`` to ``ok``.

**What this module must never do.** It must never treat a ``null`` field as permissive, and
it must never be "helped" by populating one. An invented ``licence_id`` — ``CC-BY-4.0`` is
the tempting one — would make this gate green, would be indistinguishable from a confirmed
value to every downstream reader, and would be a fabricated fact about a legal instrument.
I-7: absence of proof is never a pass, and a fabricated pass is worse than a visible gap.

**Why registration matters more than placement.** R8.16's "before the first ingestion" is
enforceable only on the change that performs the ingestion, so the check is registered in the
Check_Registry, which ``truth-gates.yml::truth-gates`` runs on every push and every pull
request — including Markdown-only ones, since that workflow deliberately carries no
``paths-ignore``.

Run::

    python -m scripts.audit.dataset_licence_truth            # human summary
    python -m scripts.audit.dataset_licence_truth --json     # canonical machine JSON
    python -m scripts.audit.dataset_licence_truth --check    # exit-code only mode

Exit codes: ``0`` pass, ``1`` fail, ``2`` unavailable. ``2`` is non-passing.
Every file is read with ``encoding='utf-8'`` (E-S13-07) and all console output is ASCII.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final, Literal

import structlog
import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

ROOT: Final[Path] = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:  # importable when run as a bare script
    sys.path.insert(0, str(ROOT))

from data_fabric.licence import (  # noqa: E402 - after the sys.path guard
    R8_1_FIELDS,
    DatasetLicence,
    LicenceRegister,
)

REGISTER_FILE: Final[Path] = ROOT / "infrastructure" / "data" / "dataset-licences.yaml"
SCHEMA_FILE: Final[Path] = (
    ROOT / "infrastructure" / "data" / "schemas" / "dataset-licences.schema.json"
)

#: The one schema version this reader understands. An unrecognised version is
#: ``unavailable`` rather than a best-effort parse: a reader that guesses at a shape it does
#: not know reports on a document it did not understand.
SUPPORTED_SCHEMA_VERSION: Final[int] = 1

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 1
EXIT_UNAVAILABLE: Final[int] = 2

Verdict = Literal["pass", "fail", "unavailable"]

_EXIT_CODES: Final[Mapping[str, int]] = {
    "pass": EXIT_PASS,
    "fail": EXIT_FAIL,
    "unavailable": EXIT_UNAVAILABLE,
}
_SYMBOLS: Final[Mapping[str, str]] = {"pass": "[OK]", "fail": "[XX]", "unavailable": "[--]"}

#: Rule -> verdict contribution. Stated as a table rather than inline branches so the
#: fail-versus-unavailable split is auditable at a glance and cannot drift per call site.
_RULE_VERDICTS: Final[Mapping[str, Verdict]] = {
    "register-absent": "unavailable",
    "register-unparseable": "unavailable",
    "schema-absent": "unavailable",
    "schema-not-draft07": "unavailable",
    "schema-version-unrecognised": "unavailable",
    "declaration-empty": "unavailable",
    "field-absent": "unavailable",
    "redistribution-unestablished": "unavailable",
    "schema-invalid": "fail",
    "flag-disagreement": "fail",
}

_LOG = structlog.get_logger(__name__)

__all__ = [
    "EXIT_FAIL",
    "EXIT_PASS",
    "EXIT_UNAVAILABLE",
    "REGISTER_FILE",
    "ROOT",
    "SCHEMA_FILE",
    "SUPPORTED_SCHEMA_VERSION",
    "LicenceFinding",
    "LicenceTruthReport",
    "assess",
    "load_schema",
    "main",
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


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class LicenceFinding(BaseModel):
    """One finding, naming its rule, its requirement and the subject it is about."""

    model_config = ConfigDict(frozen=True)

    rule: str
    requirement: str
    subject: str
    detail: str

    @property
    def verdict_contribution(self) -> Verdict:
        return _RULE_VERDICTS.get(self.rule, "fail")

    @property
    def fatal(self) -> bool:
        """True for a finding that is somebody's **defect**, false for an **absence**.

        The distinction a reader acts on: a fatal finding is fixable in the change that
        introduced it ("the value you wrote is wrong"), while a non-fatal one is work for
        somebody else entirely ("go and read the terms"). Both are non-passing, so R8.2 holds
        either way; the flag is what makes the report actionable rather than merely correct.
        """
        return self.verdict_contribution == "fail"


class LicenceTruthReport(BaseModel):
    """Everything one execution of this gate observed."""

    model_config = ConfigDict(frozen=True)

    register_path: str
    schema_path: str
    register_present: bool
    schema_present: bool
    schema_validated: bool
    schema_version: int | None
    datasets_declared: int
    confirmed_datasets: tuple[str, ...]
    unconfirmed_datasets: tuple[str, ...]
    absent_fields_by_dataset: tuple[tuple[str, tuple[str, ...]], ...]
    findings: tuple[LicenceFinding, ...]
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


def _verdict_of(findings: tuple[LicenceFinding, ...]) -> Verdict:
    """``fail`` outranks ``unavailable`` outranks ``pass``.

    A false self-statement is a worse fact than an unread term, and reporting the milder of
    the two when both hold would understate the defect.
    """
    contributions = {finding.verdict_contribution for finding in findings}
    if "fail" in contributions:
        return "fail"
    if "unavailable" in contributions:
        return "unavailable"
    return "pass"


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


def load_schema(schema_path: Path = SCHEMA_FILE) -> dict[str, object]:
    """Read the committed schema as JSON. Raises ``OSError``/``JSONDecodeError`` on failure.

    Exposed because the schema is a committed artifact in its own right, and a test that
    wants to assert something about it should read it through the same path the gate does
    rather than re-implementing the read.
    """
    loaded: dict[str, object] = json.loads(schema_path.read_text(encoding="utf-8"))
    return loaded


def _validate_schema(
    payload: object, schema_path: Path
) -> tuple[bool, bool, tuple[LicenceFinding, ...]]:
    """``(schema_present, validated, findings)``.

    ``jsonschema`` is imported inside the function and its absence is ``unavailable`` rather
    than an exception: several registry checks import an optional dependency in a
    ``try/except`` and SKIP when it is missing, and a gate that crashes on a thin environment
    reports nothing, which is not a pass either.

    Note the ``schema-not-draft07`` clause. A schema that is not itself a valid schema means
    the gate has **no yardstick**, which is an ``unavailable`` state and emphatically not a
    pass - the same shape as an absent schema, reported separately because "the file is
    missing" and "the file is not a schema" are different repairs.
    """
    if not schema_path.is_file():
        return (
            False,
            False,
            (
                LicenceFinding(
                    rule="schema-absent",
                    requirement="R8.1",
                    subject=_relative(schema_path),
                    detail=(
                        "the committed schema is absent, so the register was not validated; "
                        "an unvalidated register is not a validated one (I-7)"
                    ),
                ),
            ),
        )
    try:
        import jsonschema
    except ImportError as error:  # pragma: no cover - environment-dependent
        return (
            True,
            False,
            (
                LicenceFinding(
                    rule="schema-absent",
                    requirement="R8.1",
                    subject="jsonschema",
                    detail=f"jsonschema is unavailable, so no validation ran: {_ascii(str(error))}",
                ),
            ),
        )

    try:
        schema = load_schema(schema_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return (
            True,
            False,
            (
                LicenceFinding(
                    rule="schema-not-draft07",
                    requirement="R8.1",
                    subject=_relative(schema_path),
                    detail=f"the schema could not be read as JSON: {_ascii(str(error))}",
                ),
            ),
        )

    try:
        jsonschema.Draft7Validator.check_schema(schema)
    except jsonschema.exceptions.SchemaError as error:
        return (
            True,
            False,
            (
                LicenceFinding(
                    rule="schema-not-draft07",
                    requirement="R8.1",
                    subject=_relative(schema_path),
                    detail=(
                        "the committed schema is not a valid draft-07 schema, so the gate has "
                        f"no yardstick and has measured nothing: {_ascii(error.message)}"
                    ),
                ),
            ),
        )

    validator = jsonschema.Draft7Validator(
        schema,
        # WITHOUT this, `format` is annotation-only in draft-07 and `read_date: "banana"`
        # would VALIDATE. That is the difference between a field being absent (nobody read
        # the terms -> unavailable/SKIP) and a field being present and wrong (somebody wrote
        # that value in this tree -> fail). Collapsing the two would let a malformed date
        # read as an established one, which is the direction I-7 forbids.
        format_checker=jsonschema.Draft7Validator.FORMAT_CHECKER,
    )
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.absolute_path))
    if not errors:
        return True, True, ()
    findings = tuple(
        LicenceFinding(
            rule="schema-invalid",
            requirement="R8.1",
            subject="$." + ".".join(str(part) for part in error.absolute_path) or "$",
            detail=_ascii(error.message),
        )
        for error in errors
    )
    return True, False, findings


def _assess_entry(entry: DatasetLicence, index: int) -> tuple[LicenceFinding, ...]:
    """Findings for one declared dataset."""
    subject = entry.dataset_id or f"$.datasets[{index}]"
    findings: list[LicenceFinding] = []

    absent = entry.absent_fields
    if absent:
        findings.append(
            LicenceFinding(
                rule="field-absent",
                requirement="R8.1, R8.2",
                subject=subject,
                detail=(
                    f"{len(absent)} of {len(R8_1_FIELDS)} declared field(s) are not "
                    f"established: {', '.join(absent)}. Each is named rather than defaulted, "
                    "so a missing term cannot read as a permissive one"
                ),
            )
        )

    if entry.flag_disagrees():
        findings.append(
            LicenceFinding(
                rule="flag-disagreement",
                requirement="R8.1",
                subject=subject,
                detail=(
                    "confirmation.confirmed is true while "
                    f"{', '.join(entry.absent_fields)} is/are still null: the entry asserts a "
                    "confirmation its own fields contradict, which is a false self-statement "
                    "rather than an incomplete one"
                ),
            )
        )

    if not entry.redistribution_established:
        findings.append(
            LicenceFinding(
                rule="redistribution-unestablished",
                requirement="R8.1",
                subject=subject,
                detail=(
                    "the redistribution disposition is null, meaning the terms were not read; "
                    "note that `unknown` would be a different claim - that they WERE read and "
                    "are silent - and neither is `permitted`"
                ),
            )
        )

    return tuple(findings)


def assess(
    register_path: Path = REGISTER_FILE, schema_path: Path = SCHEMA_FILE
) -> LicenceTruthReport:
    """Read, validate and report. Total over every malformed input; never raises."""
    register_rel = _relative(register_path)
    schema_rel = _relative(schema_path)

    def _unavailable(
        findings: tuple[LicenceFinding, ...],
        reason: str,
        *,
        register_present: bool = True,
        schema_present: bool = False,
        schema_version: int | None = None,
    ) -> LicenceTruthReport:
        return LicenceTruthReport(
            register_path=register_rel,
            schema_path=schema_rel,
            register_present=register_present,
            schema_present=schema_present,
            schema_validated=False,
            schema_version=schema_version,
            datasets_declared=0,
            confirmed_datasets=(),
            unconfirmed_datasets=(),
            absent_fields_by_dataset=(),
            findings=findings,
            notes=(),
            verdict=_verdict_of(findings),
            reason=reason,
        )

    if not register_path.is_file():
        return _unavailable(
            (
                LicenceFinding(
                    rule="register-absent",
                    requirement="R8.1, R8.2",
                    subject=register_rel,
                    detail=(
                        "no licence register exists, so no dataset's terms are recorded; "
                        "an absent register is not a permissive one"
                    ),
                ),
            ),
            f"{register_rel} does not exist, so nothing is licensed as far as this gate knows",
            register_present=False,
        )

    try:
        raw = yaml.safe_load(register_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        return _unavailable(
            (
                LicenceFinding(
                    rule="register-unparseable",
                    requirement="R8.1",
                    subject=register_rel,
                    detail=f"the register could not be parsed: {_ascii(str(error))}",
                ),
            ),
            f"{register_rel} is not parseable, so no field could be read",
        )

    if not isinstance(raw, Mapping):
        return _unavailable(
            (
                LicenceFinding(
                    rule="register-unparseable",
                    requirement="R8.1",
                    subject=register_rel,
                    detail=f"the register is {type(raw).__name__}, not a mapping",
                ),
            ),
            f"{register_rel} does not contain a mapping",
        )

    schema_present, schema_validated, schema_findings = _validate_schema(raw, schema_path)

    declared_version = raw.get("schema_version")
    if declared_version != SUPPORTED_SCHEMA_VERSION:
        findings = schema_findings + (
            LicenceFinding(
                rule="schema-version-unrecognised",
                requirement="R8.1",
                subject=register_rel,
                detail=(
                    f"schema_version is {declared_version!r}, and this reader understands "
                    f"only {SUPPORTED_SCHEMA_VERSION}; a reader that guesses at a shape it "
                    "does not know reports on a document it did not understand"
                ),
            ),
        )
        return _unavailable(
            findings,
            f"{register_rel} declares an unrecognised schema_version",
            schema_present=schema_present,
            schema_version=declared_version if isinstance(declared_version, int) else None,
        )

    try:
        register = LicenceRegister.model_validate(raw)
    except ValidationError as error:
        findings = schema_findings + (
            LicenceFinding(
                rule="schema-invalid",
                requirement="R8.1",
                subject=register_rel,
                detail=_ascii(str(error).replace("\n", "; ")),
            ),
        )
        return _unavailable(
            findings,
            f"{register_rel} does not satisfy the register model",
            schema_present=schema_present,
            schema_version=SUPPORTED_SCHEMA_VERSION,
        )

    collected: list[LicenceFinding] = list(schema_findings)
    confirmed: list[str] = []
    unconfirmed: list[str] = []
    absent_map: list[tuple[str, tuple[str, ...]]] = []

    if not register.datasets:
        collected.append(
            LicenceFinding(
                rule="declaration-empty",
                requirement="R8.1, R8.2",
                subject=register_rel,
                detail=(
                    "the register declares no dataset at all: nobody wrote a wrong term, "
                    "there are simply no terms. That is absence of proof, not proof of "
                    "permission, and it is reported as unavailable rather than as a defect"
                ),
            )
        )

    for index, entry in enumerate(register.datasets):
        label = entry.dataset_id or f"$.datasets[{index}]"
        collected.extend(_assess_entry(entry, index))
        if entry.confirmed:
            confirmed.append(label)
        else:
            unconfirmed.append(label)
            absent_map.append((label, entry.absent_fields))

    ordered = tuple(collected)
    verdict = _verdict_of(ordered)

    notes = [
        f"register: {len(register.datasets)} dataset(s) declared in {register_rel}",
        (
            "schema: validated against " + schema_rel
            if schema_validated
            else "schema: NOT validated (see findings) - an unvalidated register is not a "
            "validated one"
        ),
    ]
    for label, absent in absent_map:
        declared_entry = register.entry(label)
        blocked = (
            declared_entry.confirmation.blocked_on if declared_entry is not None else None
        )
        notes.append(
            f"{label}: {len(absent)} field(s) unestablished ({', '.join(absent)})"
            + (f"; blocked on: {blocked.strip().splitlines()[0]}" if blocked else "")
        )

    if verdict == "pass":
        reason = (
            f"every one of {len(R8_1_FIELDS)} declared field(s) is established for all "
            f"{len(register.datasets)} dataset(s), and the register validates against its "
            "committed schema"
        )
    elif verdict == "fail":
        rules = sorted(
            {finding.rule for finding in ordered if finding.verdict_contribution == "fail"}
        )
        reason = (
            f"the register makes a statement its own contents contradict ({', '.join(rules)}); "
            "this is a false self-statement, not an incomplete one"
        )
    else:
        reason = (
            f"{len(unconfirmed)} of {len(register.datasets)} dataset(s) carry unestablished "
            "licence terms, each named in the findings; the terms sit behind an operator "
            "acceptance gate, so this reports SKIP rather than PASS - absence of proof is "
            "never a pass (I-7)"
        )

    _LOG.info(
        "dataset_licence.assessed",
        verdict=verdict,
        datasets=len(register.datasets),
        confirmed=len(confirmed),
        unconfirmed=len(unconfirmed),
        findings=len(ordered),
    )

    return LicenceTruthReport(
        register_path=register_rel,
        schema_path=schema_rel,
        register_present=True,
        schema_present=schema_present,
        schema_validated=schema_validated,
        schema_version=register.schema_version,
        datasets_declared=len(register.datasets),
        confirmed_datasets=tuple(confirmed),
        unconfirmed_datasets=tuple(unconfirmed),
        absent_fields_by_dataset=tuple(absent_map),
        findings=ordered,
        notes=tuple(notes),
        verdict=verdict,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_report(report: LicenceTruthReport) -> None:
    symbol = _SYMBOLS[report.verdict]
    print(f"{symbol} dataset-licence: {report.verdict.upper()} - {_ascii(report.reason)}")
    for note in report.notes:
        print(f"     - {_ascii(note)}")
    for finding in report.findings:
        print(
            f"  {_SYMBOLS[finding.verdict_contribution]} {finding.rule} "
            f"[{finding.requirement}] {_ascii(finding.subject)}: {_ascii(finding.detail)}"
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
            "(a null field is an assertion of ignorance, not a permission; this gate reports "
            "SKIP until an operator reads the terms, and never invents a licence identifier.)"
        )
    return report.exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dataset_licence_truth",
        description=(
            "Validate the external-dataset licence register against its committed schema and "
            "name every R8.1 field that is not established."
        ),
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return run(as_json=bool(args.as_json), check=bool(args.check))


if __name__ == "__main__":
    sys.exit(main())
