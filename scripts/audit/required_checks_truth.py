"""Required-status-check declaration truth and live reconciliation (design E1.7).

Feature: purpose-achievement-audit, task 2.14. Requirements R14.1, R14.2, R14.4,
R14.5, R14.6.

R14's finding is a boundary, not a divergence. A job that fails turns its run red;
whether a red run *blocks a merge* lives in GitHub branch-protection settings, which
are not in this working tree. Every "blocking" claim in `CLAUDE.md` and the
Truth_Ledger therefore rests on a fact the repository's own honesty apparatus cannot
check. This module is both halves of the fix:

* **The in-repo half (R14.1, R14.2).** `infrastructure/quality/required-checks.yaml`
  is the committed declaration. This gate validates it against
  `infrastructure/quality/schemas/required-checks.schema.json` (draft-07; the dialect
  keyword is deliberately omitted from the schema so nothing is fetched over the
  network, so ``Draft7Validator`` is selected explicitly) and then resolves every
  declared job to a job actually defined in the named workflow, comparing
  ``check_name`` byte-for-byte against the job's ``name:`` - or against the job id
  when the job is unnamed, because that is what GitHub matches. A rename or removal
  FAILs naming the job.
* **The live half (R14.4-R14.6).** ``--reconcile`` compares the declared set against
  a branch-protection response that
  `.github/workflows/required-checks-reconcile.yml` read **during the reporting
  run**, recorded with that run's timestamp. Any difference is a non-passing
  conclusion naming each difference (R14.4). An unreadable response is also
  non-passing and is reported as ``UNVERIFIED``, never as a match (R14.5). Under I-7
  absence of a read is not a verified set.

Two deliberate non-behaviours, both load-bearing:

1. **``pending:`` job names are never resolved.** Resolving a job that has not landed
   would fail the gate for the honest reason that it does not exist yet, which would
   make the declaration unable to record a future obligation at all. Pending entries
   are counted and named in the report and contribute no verdict. The section is empty
   as of task 2.17: its one entry, ``truth-gates``, was created by that task - in its
   own workflow file, ``.github/workflows/truth-gates.yml``, because ``paths-ignore``
   is a property of ``on.push`` and a job cannot opt out of its workflow's filter -
   and promoted into ``required:``. The exemption is a property of the section, not of
   that entry, so it outlives it.
2. **Nothing here ever writes ``status: verified`` into the committed file.** The
   reconciliation outcome lives in the run's artifact, timestamped with that run's
   read. A committed or cached copy is not a read (R14.6), so ``--reconcile``
   additionally refuses a ``--read-at`` equal to the value already committed in
   ``reconciliation.live_read.read_at``.

Ineligibility is reported in two kinds, because the declaration mixes them. A
**trigger** reason (``path-filtered``, ``branch-push-only``,
``conditioned-off-pull-request``, ``post-merge``, ``path-filtered-and-conditioned``)
is a mechanical fact about ``on:``/``if:``: the job produces no check on a pull
request, so branch protection cannot cover it. A **policy** reason
(``self-labelled-informational``) is a judgement: the job does report on every pull
request and could be required. ``gate_surface.py`` (task 2.12) reports exactly that
disagreement for ``ci.yml::v4-compliance``. This gate records it as a note and does
not resolve it - relabelling or promoting that job is an operator decision, not an
audit finding.

Run::

    python -m scripts.audit.required_checks_truth              # in-repo consistency
    python -m scripts.audit.required_checks_truth --json       # machine-readable
    python -m scripts.audit.required_checks_truth --reconcile \
        --read-at "$READ_AT" --live-protection live-protection.json \
        --read-exit-code 0 --artifact artifacts/required-checks/live.json

Exit codes: ``0`` pass, ``1`` fail, ``2`` unavailable. ``2`` is non-passing (I-7: a
SKIP is not a PASS, and neither is an unread configuration).

Reuse: every workflow read goes through `scripts.audit.workflow_shape_truth`'s shared
reader (`iter_workflow_paths`, `load_workflow`, `iter_jobs`, `job_display_names`,
`workflow_relative_path`). There is one workflow parser in this repository and it is
not here. Every file read uses ``encoding='utf-8'`` (E-S13-07) and all console output
is ASCII - a non-ASCII ``check_name`` (``ci.yml``'s em dash) is escaped for display
and compared unescaped.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final, Literal

import yaml
from jsonschema import Draft7Validator  # type: ignore[import-untyped]
from jsonschema.exceptions import SchemaError  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict

from scripts.audit.workflow_shape_truth import (
    ROOT,
    WORKFLOW_DIR,
    iter_workflow_paths,
    job_display_names,
    load_workflow,
    workflow_relative_path,
    workflow_triggers,
)

DECLARATION_FILE: Final[Path] = ROOT / "infrastructure" / "quality" / "required-checks.yaml"
SCHEMA_FILE: Final[Path] = (
    ROOT / "infrastructure" / "quality" / "schemas" / "required-checks.schema.json"
)

#: Sections whose ``job`` must resolve to a real job. ``pending`` is absent by design.
RESOLVED_SECTIONS: Final[tuple[str, ...]] = ("required", "candidates", "ineligible")

#: Ineligibility reasons that are mechanical facts about the job's trigger.
TRIGGER_INELIGIBILITY: Final[frozenset[str]] = frozenset(
    {
        "path-filtered",
        "path-filtered-and-conditioned",
        "branch-push-only",
        "conditioned-off-pull-request",
        "post-merge",
    }
)

#: Ineligibility reasons that are policy judgements rather than trigger facts.
POLICY_INELIGIBILITY: Final[frozenset[str]] = frozenset({"self-labelled-informational"})

#: Rule ids, in report order (strongest first).
RULES: Final[tuple[str, ...]] = (
    "schema-invalid",
    "workflow-missing",
    "job-unresolved",
    "check-name-mismatch",
    "reconciliation-workflow-shape",
    "reconciliation-status-unread",
)

#: The `gh api` error text that means the branch is definitively not protected. A
#: 404 of this shape is a readable answer, so it is a mismatch (R14.4) rather than an
#: unreadable response (R14.5).
NOT_PROTECTED_MARKER: Final[str] = "branch not protected"

_EXIT_CODES: Final[dict[str, int]] = {"pass": 0, "fail": 1, "unavailable": 2}
_SYMBOLS: Final[dict[str, str]] = {"pass": "[OK]", "fail": "[XX]", "unavailable": "[--]"}

__all__ = [
    "DECLARATION_FILE",
    "NOT_PROTECTED_MARKER",
    "POLICY_INELIGIBILITY",
    "RESOLVED_SECTIONS",
    "RULES",
    "SCHEMA_FILE",
    "TRIGGER_INELIGIBILITY",
    "DeclarationLoadError",
    "DeclaredJob",
    "Difference",
    "LiveRead",
    "ReconcileInputs",
    "ReconciliationOutcome",
    "RequiredChecksFinding",
    "RequiredChecksReport",
    "artifact_payload",
    "collect_declared_jobs",
    "evaluate",
    "live_contexts",
    "load_declaration",
    "load_schema",
    "main",
    "reconcile",
    "resolve_declared_jobs",
    "run",
    "schema_findings",
]


# ---------------------------------------------------------------------------
# ASCII display
# ---------------------------------------------------------------------------


def _ascii(text: str) -> str:
    """Escape non-ASCII for the Windows console; comparison always uses the original."""
    if text.isascii():
        return text
    return text.encode("unicode_escape").decode("ascii")


# ---------------------------------------------------------------------------
# Roots
# ---------------------------------------------------------------------------
#
# Every root this gate reads is a parameter with a production default, so a property
# test can point the whole gate at a temporary tree and get back the same
# ``.github/workflows/x.yml`` keys the committed declaration writes. Without that the
# only way to test resolution hermetically would be to monkeypatch ``ROOT``, and a gate
# whose roots are module globals is a gate that can only be tested against the tree it
# happens to live in.


def _workflow_key(path: Path, root: Path) -> str:
    """POSIX path of ``path`` relative to ``root``, as the declaration writes it.

    With the production ``root`` this is exactly
    :func:`~scripts.audit.workflow_shape_truth.workflow_relative_path`, which is the
    fallback for a path that lies outside ``root`` (the committed schema, when the
    declaration under test is a generated one).
    """
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return workflow_relative_path(path)


def _display_names(directory: Path, root: Path) -> dict[tuple[str, str], str]:
    """``(workflow, job_id) -> display name`` for every job, keyed relative to ``root``.

    The parse stays in ``workflow_shape_truth.job_display_names`` - there is one
    workflow parser in this repository and it is not here. Only the key is rewritten,
    from the repository-root-relative form to the ``root``-relative one, which is a
    no-op under the production root.
    """
    translation = {
        workflow_relative_path(path): _workflow_key(path, root)
        for path in iter_workflow_paths(directory)
    }
    return {
        (translation.get(workflow, workflow), job_id): display
        for (workflow, job_id), display in job_display_names(directory).items()
    }


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class DeclaredJob(BaseModel):
    """One ``job``/``workflow`` pair the declaration names."""

    model_config = ConfigDict(frozen=True)

    section: str
    index: int
    job: str
    workflow: str
    check_name: str | None
    reason: str | None


class RequiredChecksFinding(BaseModel):
    """One violation, naming the job (R14.2's naming obligation)."""

    model_config = ConfigDict(frozen=True)

    rule: str
    requirement: str
    section: str
    workflow: str
    job: str
    detail: str


class LiveRead(BaseModel):
    """What the reporting run was able to read from the hosting platform."""

    model_config = ConfigDict(frozen=True)

    read_at: str | None
    contexts: tuple[str, ...] | None
    strict: bool | None
    readable: bool
    not_protected: bool
    detail: str


class Difference(BaseModel):
    """One difference between the declared set and the live set (R14.4)."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["declared-not-live", "live-not-declared"]
    context: str


class ReconciliationOutcome(BaseModel):
    """The live half's conclusion. ``verified`` requires a read performed this run."""

    model_config = ConfigDict(frozen=True)

    branch: str
    api_path: str
    declared_contexts: tuple[str, ...]
    live: LiveRead
    differences: tuple[Difference, ...]
    status: Literal["verified", "mismatch", "unverified"]
    verdict: Literal["pass", "fail", "unavailable"]
    reason: str


class ReconcileInputs(BaseModel):
    """Everything the reconciliation step hands to this gate."""

    model_config = ConfigDict(frozen=True)

    read_at: str | None
    response_path: Path | None
    read_exit_code: int
    read_error: str


class RequiredChecksReport(BaseModel):
    """Everything one execution of this gate observed."""

    model_config = ConfigDict(frozen=True)

    declaration: str
    schema_file: str
    declared: tuple[DeclaredJob, ...]
    resolved: tuple[str, ...]
    pending: tuple[str, ...]
    trigger_ineligible: tuple[str, ...]
    policy_ineligible: tuple[str, ...]
    committed_status: str | None
    findings: tuple[RequiredChecksFinding, ...]
    notes: tuple[str, ...]
    reconciliation: ReconciliationOutcome | None
    verdict: Literal["pass", "fail", "unavailable"]
    reason: str


class DeclarationLoadError(Exception):
    """The declaration or its schema is absent or unusable - the gate is unavailable."""


# ---------------------------------------------------------------------------
# Loading the declaration and its schema
# ---------------------------------------------------------------------------


def load_declaration(path: Path = DECLARATION_FILE) -> dict[str, object]:
    """Read the committed declaration into a plain mapping."""
    if not path.is_file():
        raise DeclarationLoadError(f"declaration not found: {workflow_relative_path(path)}")
    try:
        raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:  # pragma: no cover - malformed committed file
        raise DeclarationLoadError(
            f"declaration is not parseable YAML: {workflow_relative_path(path)}: {error}"
        ) from error
    if not isinstance(raw, dict):
        raise DeclarationLoadError(
            f"declaration is not a mapping: {workflow_relative_path(path)}"
        )
    return {str(key): value for key, value in raw.items()}


def load_schema(path: Path = SCHEMA_FILE) -> dict[str, object]:
    """Read the draft-07 schema and confirm it is itself a valid schema."""
    if not path.is_file():
        raise DeclarationLoadError(f"schema not found: {workflow_relative_path(path)}")
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise DeclarationLoadError(
            f"schema is not parseable JSON: {workflow_relative_path(path)}: {error}"
        ) from error
    if not isinstance(raw, dict):
        raise DeclarationLoadError(f"schema is not a mapping: {workflow_relative_path(path)}")
    schema = {str(key): value for key, value in raw.items()}
    try:
        Draft7Validator.check_schema(schema)
    except SchemaError as error:
        raise DeclarationLoadError(
            f"schema is not a valid draft-07 schema: {workflow_relative_path(path)}: "
            f"{error.message}"
        ) from error
    return schema


def _pointer(path: Sequence[object]) -> str:
    if not path:
        return "(document root)"
    return "/" + "/".join(str(part) for part in path)


def _locate(document: dict[str, object], path: Sequence[object]) -> tuple[str, str, str]:
    """``(section, workflow, job)`` for a schema error, best effort.

    A schema error carries a path, not a job name. Recovering the job from the
    document is what turns "``/required/0/check_name`` is wrong" into a finding a
    reader can act on.
    """
    parts = list(path)
    section = str(parts[0]) if parts else "(document)"
    if len(parts) >= 2 and isinstance(parts[1], int):
        block = document.get(section)
        if isinstance(block, list) and 0 <= parts[1] < len(block):
            entry = block[parts[1]]
            if isinstance(entry, dict):
                return (
                    section,
                    str(entry.get("workflow", "(no workflow)")),
                    str(entry.get("job", "(no job)")),
                )
    return section, "(n/a)", "(n/a)"


def schema_findings(
    document: dict[str, object], schema: dict[str, object]
) -> tuple[RequiredChecksFinding, ...]:
    """Every draft-07 violation of the declaration, in document order (R14.1).

    Structural validity is a precondition of the consistency check, not a substitute
    for it: a schema-valid file whose jobs do not resolve still FAILs, and an invalid
    file FAILs here rather than being reported unavailable - the declaration is
    committed to this tree, so a malformed one is a repository defect.
    """
    validator = Draft7Validator(schema)
    findings: list[RequiredChecksFinding] = []
    for error in validator.iter_errors(document):
        section, workflow, job = _locate(document, error.absolute_path)
        findings.append(
            RequiredChecksFinding(
                rule="schema-invalid",
                requirement="R14.1",
                section=section,
                workflow=workflow,
                job=job,
                detail=(
                    f"{_pointer(list(error.absolute_path))} violates the declaration "
                    f"schema: {_ascii(error.message)}"
                ),
            )
        )
    return tuple(
        sorted(findings, key=lambda item: (item.section, item.job, item.detail))
    )


# ---------------------------------------------------------------------------
# Resolution against the workflow tree (R14.2)
# ---------------------------------------------------------------------------


def collect_declared_jobs(document: dict[str, object]) -> tuple[DeclaredJob, ...]:
    """Every entry of the three resolved sections, in document order.

    ``pending`` is excluded deliberately: those jobs do not exist yet, and a
    declaration that can record a future obligation is the point of the section.
    """
    declared: list[DeclaredJob] = []
    for section in RESOLVED_SECTIONS:
        block = document.get(section)
        if not isinstance(block, list):
            continue
        for index, entry in enumerate(block):
            if not isinstance(entry, dict):
                continue
            check_name = entry.get("check_name")
            reason = entry.get("reason")
            declared.append(
                DeclaredJob(
                    section=section,
                    index=index,
                    job=str(entry.get("job", "")),
                    workflow=str(entry.get("workflow", "")),
                    check_name=(
                        str(check_name) if isinstance(check_name, str) and check_name else None
                    ),
                    reason=str(reason) if isinstance(reason, str) and reason else None,
                )
            )
    return tuple(declared)


def _pending_labels(document: dict[str, object]) -> tuple[str, ...]:
    block = document.get("pending")
    if not isinstance(block, list):
        return ()
    labels: list[str] = []
    for entry in block:
        if not isinstance(entry, dict):
            continue
        labels.append(f"{entry.get('workflow', '(no workflow)')}::{entry.get('job', '(no job)')}")
    return tuple(labels)


def resolve_declared_jobs(
    declared: tuple[DeclaredJob, ...],
    *,
    directory: Path = WORKFLOW_DIR,
    root: Path = ROOT,
) -> tuple[tuple[str, ...], tuple[RequiredChecksFinding, ...]]:
    """Resolve each declared job against the workflow tree (R14.2).

    Three failures, all naming the job:

    * ``workflow-missing`` - the named workflow file is not in the tree.
    * ``job-unresolved`` - the workflow exists but defines no such job id. This is
      the removal half of R14.2.
    * ``check-name-mismatch`` - the job exists but its display name is not the
      declared ``check_name``, byte for byte. This is the rename half: GitHub matches
      a required status check by that exact string, so a one-character drift means
      branch protection waits for a check that never reports.

    ``job_display_names`` already yields the job's ``name:`` when present and the job
    id otherwise, which is precisely GitHub's rule.
    """
    names = _display_names(directory, root)
    known = {_workflow_key(path, root) for path in iter_workflow_paths(directory)}

    resolved: list[str] = []
    findings: list[RequiredChecksFinding] = []
    for entry in declared:
        requirement = "R14.2"
        label = f"{entry.workflow}::{entry.job}"
        if entry.workflow not in known:
            findings.append(
                RequiredChecksFinding(
                    rule="workflow-missing",
                    requirement=requirement,
                    section=entry.section,
                    workflow=entry.workflow,
                    job=entry.job,
                    detail=(
                        "declared workflow file is not in the workflow tree, so the "
                        "declared job cannot resolve"
                    ),
                )
            )
            continue
        display = names.get((entry.workflow, entry.job))
        if display is None:
            findings.append(
                RequiredChecksFinding(
                    rule="job-unresolved",
                    requirement=requirement,
                    section=entry.section,
                    workflow=entry.workflow,
                    job=entry.job,
                    detail=(
                        "declared job is not defined in that workflow: it was renamed "
                        "or removed"
                    ),
                )
            )
            continue
        resolved.append(label)
        if entry.check_name is not None and entry.check_name != display:
            findings.append(
                RequiredChecksFinding(
                    rule="check-name-mismatch",
                    requirement=requirement,
                    section=entry.section,
                    workflow=entry.workflow,
                    job=entry.job,
                    detail=(
                        f"declared check_name '{_ascii(entry.check_name)}' does not "
                        f"byte-match the job's display name '{_ascii(display)}'; GitHub "
                        "matches a required status check by that exact string"
                    ),
                )
            )
    return tuple(resolved), tuple(findings)


# ---------------------------------------------------------------------------
# The committed reconciliation block (in-repo half of R14.4-R14.6)
# ---------------------------------------------------------------------------


def _reconciliation_block(document: dict[str, object]) -> dict[str, object]:
    block = document.get("reconciliation")
    if not isinstance(block, dict):
        return {}
    return {str(key): value for key, value in block.items()}


def _committed_read_at(document: dict[str, object]) -> str | None:
    live = _reconciliation_block(document).get("live_read")
    if not isinstance(live, dict):
        return None
    value = live.get("read_at")
    return value if isinstance(value, str) and value else None


def _reconciliation_findings(
    document: dict[str, object],
    *,
    root: Path = ROOT,
) -> tuple[RequiredChecksFinding, ...]:
    """The reconciliation declaration must name a workflow that performs the read.

    Two checks, both mechanical:

    * ``reconciliation-status-unread`` - a committed ``verified``/``mismatch`` status
      with a null ``read_at`` or null ``contexts`` claims a conclusion no read
      supports. The schema's ``allOf`` also rejects this; the rule is kept here so the
      claim stays refused even if the schema is loosened (I-7).
    * ``reconciliation-workflow-shape`` - the named workflow must exist, must be
      scheduled, and must contain a ``gh api`` read of the declared ``api_path``.
      Without that, nothing reads the live configuration during a run (R14.6) and the
      declaration would describe a reconciliation that cannot happen.
    """
    block = _reconciliation_block(document)
    if not block:
        return ()

    findings: list[RequiredChecksFinding] = []
    status = str(block.get("status", ""))
    api_path = str(block.get("api_path", ""))
    workflow = str(block.get("workflow", ""))

    live = block.get("live_read")
    live_map = {str(k): v for k, v in live.items()} if isinstance(live, dict) else {}
    if status in {"verified", "mismatch"} and (
        not isinstance(live_map.get("read_at"), str) or not isinstance(live_map.get("contexts"), list)
    ):
        findings.append(
            RequiredChecksFinding(
                rule="reconciliation-status-unread",
                requirement="R14.5",
                section="reconciliation",
                workflow=workflow,
                job="(reconciliation)",
                detail=(
                    f"status '{status}' is recorded with no live read (read_at or "
                    "contexts is null); absence of a read is UNVERIFIED, never a match"
                ),
            )
        )

    path = root / workflow if workflow else root
    if not workflow or not path.is_file():
        findings.append(
            RequiredChecksFinding(
                rule="reconciliation-workflow-shape",
                requirement="R14.6",
                section="reconciliation",
                workflow=workflow or "(unset)",
                job="(reconciliation)",
                detail="declared reconciliation workflow is not in the workflow tree",
            )
        )
        return tuple(findings)

    text = path.read_text(encoding="utf-8")
    # `repos/{owner}/{repo}/branches/main/protection` -> the resource half, which is
    # what the workflow writes once the repository is interpolated at run time.
    resource = api_path.rsplit("}/", 1)[-1] if "}/" in api_path else api_path
    if "gh api" not in text or (resource and resource not in text):
        findings.append(
            RequiredChecksFinding(
                rule="reconciliation-workflow-shape",
                requirement="R14.6",
                section="reconciliation",
                workflow=workflow,
                job="(reconciliation)",
                detail=(
                    f"reconciliation workflow does not read '{resource}' with `gh api`, "
                    "so no run reads the live configuration"
                ),
            )
        )
    if "schedule" not in workflow_triggers(load_workflow(path)):
        findings.append(
            RequiredChecksFinding(
                rule="reconciliation-workflow-shape",
                requirement="R14.6",
                section="reconciliation",
                workflow=workflow,
                job="(reconciliation)",
                detail="reconciliation workflow is not scheduled, so the read never recurs",
            )
        )
    return tuple(findings)


# ---------------------------------------------------------------------------
# The live half (R14.4-R14.6)
# ---------------------------------------------------------------------------


def live_contexts(payload: object) -> tuple[tuple[str, ...] | None, bool | None]:
    """``(contexts, strict)`` from a branch-protection response.

    ``contexts`` is ``None`` when the response carries no required-status-check block
    at all - an error body, a truncated write, or a shape this gate does not
    understand. That is unreadable, not "zero required checks". An empty tuple is the
    readable answer "the branch is protected and requires nothing", which is a
    difference from a non-empty declaration, not an unreadable response.

    Both the legacy ``contexts`` array and the newer ``checks[].context`` form are
    read, because a repository may return either.
    """
    if not isinstance(payload, dict):
        return None, None
    block = payload.get("required_status_checks")
    if not isinstance(block, dict):
        return None, None

    contexts = block.get("contexts")
    checks = block.get("checks")
    if not isinstance(contexts, list) and not isinstance(checks, list):
        return None, None

    found: list[str] = []
    if isinstance(contexts, list):
        found.extend(str(item) for item in contexts)
    if isinstance(checks, list):
        for item in checks:
            if isinstance(item, dict) and isinstance(item.get("context"), str):
                found.append(str(item["context"]))

    strict = block.get("strict")
    return tuple(sorted(dict.fromkeys(found))), strict if isinstance(strict, bool) else None


def _read_live(inputs: ReconcileInputs) -> LiveRead:
    """Interpret the reporting run's read attempt. Never invents a set."""
    read_at = inputs.read_at
    error = inputs.read_error.strip()

    if inputs.read_exit_code != 0:
        not_protected = NOT_PROTECTED_MARKER in error.lower()
        return LiveRead(
            read_at=read_at,
            contexts=None,
            strict=None,
            readable=False,
            not_protected=not_protected,
            detail=(
                "the hosting platform reports the branch is not protected, so no "
                "required status check is enforced"
                if not_protected
                else (
                    f"branch-protection read failed with exit code "
                    f"{inputs.read_exit_code}: {_ascii(error) or 'no error text captured'}"
                )
            ),
        )

    path = inputs.response_path
    if path is None or not path.is_file():
        return LiveRead(
            read_at=read_at,
            contexts=None,
            strict=None,
            readable=False,
            not_protected=False,
            detail="no branch-protection response was written by the reporting run",
        )
    body = path.read_text(encoding="utf-8").strip()
    if not body:
        return LiveRead(
            read_at=read_at,
            contexts=None,
            strict=None,
            readable=False,
            not_protected=False,
            detail=f"branch-protection response is empty: {path.name}",
        )
    try:
        payload: object = json.loads(body)
    except json.JSONDecodeError as decode_error:
        return LiveRead(
            read_at=read_at,
            contexts=None,
            strict=None,
            readable=False,
            not_protected=False,
            detail=f"branch-protection response is not JSON: {decode_error}",
        )

    contexts, strict = live_contexts(payload)
    if contexts is None:
        message = payload.get("message") if isinstance(payload, dict) else None
        detail = (
            "branch-protection response carries no required_status_checks block"
            f"{f': {_ascii(str(message))}' if isinstance(message, str) else ''}"
        )
        return LiveRead(
            read_at=read_at,
            contexts=None,
            strict=None,
            readable=False,
            not_protected=(
                isinstance(message, str) and NOT_PROTECTED_MARKER in message.lower()
            ),
            detail=detail,
        )
    return LiveRead(
        read_at=read_at,
        contexts=contexts,
        strict=strict,
        readable=True,
        not_protected=False,
        detail=f"{len(contexts)} live required context(s) read during this run",
    )


def reconcile(
    document: dict[str, object],
    inputs: ReconcileInputs,
) -> ReconciliationOutcome:
    """Compare the declared required set against the live configuration.

    The mapping from situation to conclusion, which is the whole of R14.4-R14.6:

    ===============================================  ==========  =============
    situation                                        status      verdict
    ===============================================  ==========  =============
    declared set equals the live contexts            verified    pass
    declared set differs from the live contexts      mismatch    fail
    the branch is definitively not protected         mismatch    fail
    the response could not be read or understood     unverified  unavailable
    no read timestamp for this run was supplied      unverified  unavailable
    the timestamp equals the committed (cached) one   unverified  unavailable
    ===============================================  ==========  =============

    Only the first row is a pass. ``fail`` and ``unavailable`` are both non-passing
    conclusions, and the difference between them is the honest label: ``mismatch``
    says what the live set is, ``unverified`` says the live set is unknown.
    """
    block = _reconciliation_block(document)
    branch = str(document.get("branch", "main"))
    api_path = str(block.get("api_path", ""))
    declared_contexts = tuple(
        sorted(
            entry.check_name
            for entry in collect_declared_jobs(document)
            if entry.section == "required" and entry.check_name is not None
        )
    )

    def _outcome(
        live: LiveRead,
        differences: tuple[Difference, ...],
        status: Literal["verified", "mismatch", "unverified"],
        verdict: Literal["pass", "fail", "unavailable"],
        reason: str,
    ) -> ReconciliationOutcome:
        return ReconciliationOutcome(
            branch=branch,
            api_path=api_path,
            declared_contexts=declared_contexts,
            live=live,
            differences=differences,
            status=status,
            verdict=verdict,
            reason=reason,
        )

    if inputs.read_at is None or not inputs.read_at.strip():
        return _outcome(
            LiveRead(
                read_at=None,
                contexts=None,
                strict=None,
                readable=False,
                not_protected=False,
                detail="no read timestamp was supplied",
            ),
            (),
            "unverified",
            "unavailable",
            "the reporting run supplied no read timestamp, so no read can be recorded (R14.6)",
        )

    committed = _committed_read_at(document)
    if committed is not None and inputs.read_at == committed:
        return _outcome(
            LiveRead(
                read_at=inputs.read_at,
                contexts=None,
                strict=None,
                readable=False,
                not_protected=False,
                detail="supplied timestamp equals the committed one",
            ),
            (),
            "unverified",
            "unavailable",
            (
                f"read timestamp '{inputs.read_at}' equals the committed "
                "reconciliation.live_read.read_at; a cached or committed copy is not a "
                "read (R14.6)"
            ),
        )

    live = _read_live(inputs)

    if live.contexts is None:
        if live.not_protected:
            differences = tuple(
                Difference(kind="declared-not-live", context=context)
                for context in declared_contexts
            )
            return _outcome(
                live,
                differences,
                "mismatch",
                "fail",
                (
                    f"branch '{branch}' is not protected: all {len(declared_contexts)} "
                    "declared required check(s) are unenforced"
                ),
            )
        return _outcome(
            live,
            (),
            "unverified",
            "unavailable",
            f"live required-check set is UNVERIFIED: {live.detail}",
        )

    declared_set = set(declared_contexts)
    live_set = set(live.contexts)
    differences = tuple(
        [
            Difference(kind="declared-not-live", context=context)
            for context in sorted(declared_set - live_set)
        ]
        + [
            Difference(kind="live-not-declared", context=context)
            for context in sorted(live_set - declared_set)
        ]
    )
    if differences:
        return _outcome(
            live,
            differences,
            "mismatch",
            "fail",
            (
                f"{len(differences)} difference(s) between the declared required set and "
                f"the live configuration read at {inputs.read_at}"
            ),
        )
    return _outcome(
        live,
        (),
        "verified",
        "pass",
        (
            f"{len(declared_contexts)} declared required check(s) match the live "
            f"configuration read at {inputs.read_at}"
        ),
    )


def artifact_payload(
    outcome: ReconciliationOutcome,
    *,
    repository: str,
    run_id: str,
) -> str:
    """The artifact's canonical bytes: the read, its timestamp, and the conclusion.

    Canonical ``sort_keys=True, separators=(',',':')`` so two runs that read the same
    configuration produce byte-comparable payloads apart from the timestamp and run
    identity that R14.6 requires be recorded.
    """
    obj: dict[str, object] = {
        "api_path": outcome.api_path,
        "branch": outcome.branch,
        "declared_contexts": list(outcome.declared_contexts),
        "detail": outcome.live.detail,
        "differences": [
            {"context": difference.context, "kind": difference.kind}
            for difference in outcome.differences
        ],
        "live_contexts": (
            list(outcome.live.contexts) if outcome.live.contexts is not None else None
        ),
        "live_strict": outcome.live.strict,
        "read_at": outcome.live.read_at,
        "readable": outcome.live.readable,
        "reason": outcome.reason,
        "repository": repository,
        "run_id": run_id,
        "status": outcome.status,
        "verdict": outcome.verdict,
    }
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


def _ineligibility_notes(
    declared: tuple[DeclaredJob, ...],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Split ineligibility into trigger facts and policy judgements.

    A trigger reason is re-derivable from ``on:``/``if:``; a policy reason is not.
    Keeping them apart is what stops the declaration from reading as though every
    ineligible job were mechanically unable to report on a pull request.
    """
    trigger: list[str] = []
    policy: list[str] = []
    notes: list[str] = []
    for entry in declared:
        if entry.section != "ineligible" or entry.reason is None:
            continue
        label = f"{entry.workflow}::{entry.job}"
        if entry.reason in TRIGGER_INELIGIBILITY:
            trigger.append(label)
        elif entry.reason in POLICY_INELIGIBILITY:
            policy.append(label)
            notes.append(
                f"policy-ineligible: {label} is filed under '{entry.reason}', which is a "
                "policy judgement rather than a trigger fact - the job does report on "
                "every pull request (gate_surface, task 2.12, reports the same "
                "disagreement). Recorded, not resolved: promoting or relabelling it is an "
                "operator decision."
            )
        else:  # pragma: no cover - the schema enum forbids any other value
            trigger.append(label)
    return tuple(trigger), tuple(policy), tuple(notes)


def evaluate(
    *,
    declaration_path: Path = DECLARATION_FILE,
    schema_path: Path = SCHEMA_FILE,
    directory: Path = WORKFLOW_DIR,
    root: Path = ROOT,
    reconcile_inputs: ReconcileInputs | None = None,
) -> RequiredChecksReport:
    """Validate the declaration, resolve it, and optionally reconcile it.

    An unreadable declaration or schema is ``unavailable`` - nothing was checked, and
    under I-7 that is not a pass. Everything else is a ``fail`` naming the job.

    ``root`` is the tree the declared ``.github/workflows/...`` paths are resolved
    against, and ``directory`` is the workflow directory inside it. Both default to the
    repository, so the CLI reads the committed tree and nothing else changes.
    """

    def _unavailable(reason: str) -> RequiredChecksReport:
        return RequiredChecksReport(
            declaration=_workflow_key(declaration_path, root),
            schema_file=_workflow_key(schema_path, root),
            declared=(),
            resolved=(),
            pending=(),
            trigger_ineligible=(),
            policy_ineligible=(),
            committed_status=None,
            findings=(),
            notes=(),
            reconciliation=None,
            verdict="unavailable",
            reason=reason,
        )

    try:
        document = load_declaration(declaration_path)
        schema = load_schema(schema_path)
    except DeclarationLoadError as error:
        return _unavailable(f"required-check declaration could not be checked: {error}")

    findings: list[RequiredChecksFinding] = list(schema_findings(document, schema))
    declared = collect_declared_jobs(document)
    resolved, resolution_findings = resolve_declared_jobs(
        declared, directory=directory, root=root
    )
    findings.extend(resolution_findings)
    findings.extend(_reconciliation_findings(document, root=root))

    trigger_ineligible, policy_ineligible, policy_notes = _ineligibility_notes(declared)
    notes: list[str] = list(policy_notes)
    pending = _pending_labels(document)
    if pending:
        notes.append(
            f"pending: {len(pending)} entry/entries deliberately not resolved "
            f"({', '.join(pending)}) - those jobs do not exist yet and contribute no "
            "required check"
        )

    committed_status = str(_reconciliation_block(document).get("status", "")) or None
    if committed_status == "unverified":
        notes.append(
            "reconciliation.status is 'unverified': this gate checks in-repo consistency "
            "only and makes no claim about the live branch-protection configuration. Only "
            "a run of the reconciliation workflow can change that (R14.5, R14.6)."
        )

    outcome = reconcile(document, reconcile_inputs) if reconcile_inputs is not None else None

    ordered = tuple(
        sorted(
            findings,
            key=lambda item: (
                RULES.index(item.rule) if item.rule in RULES else len(RULES),
                item.section,
                item.workflow,
                item.job,
            ),
        )
    )

    verdict: Literal["pass", "fail", "unavailable"]
    reasons: list[str] = []
    if ordered:
        counts = {rule: sum(1 for item in ordered if item.rule == rule) for rule in RULES}
        verdict = "fail"
        reasons.append(", ".join(f"{rule}={counts[rule]}" for rule in RULES if counts[rule]))
    else:
        verdict = "pass"
        reasons.append(
            f"{len(resolved)} declared job(s) resolve to a defined job with a byte-matching "
            f"check name across {len(RESOLVED_SECTIONS)} section(s); "
            f"{len(pending)} pending entry/entries not resolved by design"
        )

    if outcome is not None:
        reasons.append(f"reconciliation {outcome.status}: {outcome.reason}")
        if outcome.verdict == "fail":
            verdict = "fail"
        elif outcome.verdict == "unavailable" and verdict != "fail":
            verdict = "unavailable"

    return RequiredChecksReport(
        declaration=_workflow_key(declaration_path, root),
        schema_file=_workflow_key(schema_path, root),
        declared=declared,
        resolved=resolved,
        pending=pending,
        trigger_ineligible=trigger_ineligible,
        policy_ineligible=policy_ineligible,
        committed_status=committed_status,
        findings=ordered,
        notes=tuple(notes),
        reconciliation=outcome,
        verdict=verdict,
        reason="; ".join(reasons),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run(
    *,
    as_json: bool = False,
    reconcile_inputs: ReconcileInputs | None = None,
    artifact: Path | None = None,
    repository: str = "",
    run_id: str = "",
) -> int:
    """CLI entry point. ``print`` is acceptable here and nowhere else in this module."""
    report = evaluate(reconcile_inputs=reconcile_inputs)

    if artifact is not None and report.reconciliation is not None:
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            artifact_payload(report.reconciliation, repository=repository, run_id=run_id),
            encoding="utf-8",
        )

    if as_json:
        print(json.dumps(report.model_dump(mode="json"), sort_keys=True, indent=2))
        return _EXIT_CODES[report.verdict]

    required = sum(1 for entry in report.declared if entry.section == "required")
    candidates = sum(1 for entry in report.declared if entry.section == "candidates")
    print("Required-check declaration truth (E1.7 - R14.1, R14.2, R14.4, R14.5, R14.6)")
    print(f"  declaration     : {report.declaration}")
    print(f"  schema          : {report.schema_file}")
    print(
        f"  declared jobs   : required={required} candidates={candidates} "
        f"ineligible={len(report.trigger_ineligible) + len(report.policy_ineligible)} "
        f"pending={len(report.pending)} (pending not resolved by design)"
    )
    print(
        f"  resolved        : {len(report.resolved)} of {len(report.declared)} "
        "declared job(s) resolve to a defined job"
    )
    print(
        f"  ineligible kind : trigger={len(report.trigger_ineligible)} "
        f"policy={len(report.policy_ineligible)}"
    )
    print(f"  committed status: {report.committed_status or '(none)'}")
    print()

    if report.findings:
        for rule in RULES:
            rule_findings = [item for item in report.findings if item.rule == rule]
            if not rule_findings:
                continue
            print(f"{rule} ({len(rule_findings)}):")
            for item in rule_findings:
                print(f"  [XX] {item.workflow} :: {item.job} [{item.section}]")
                print(f"       {item.requirement} - {item.detail}")
            print()
    else:
        print("Every declared job resolves and every check name byte-matches.")
        print()

    outcome = report.reconciliation
    if outcome is not None:
        print(f"Reconciliation ({outcome.api_path}):")
        print(f"  read_at        : {outcome.live.read_at or '(none)'}")
        print(f"  readable       : {'yes' if outcome.live.readable else 'no'}")
        print(f"  live strict    : {outcome.live.strict}")
        print(f"  declared       : {len(outcome.declared_contexts)} context(s)")
        for context in outcome.declared_contexts:
            print(f"      - {_ascii(context)}")
        if outcome.live.contexts is None:
            print("  live           : UNVERIFIED (not read)")
        else:
            print(f"  live           : {len(outcome.live.contexts)} context(s)")
            for context in outcome.live.contexts:
                print(f"      - {_ascii(context)}")
        for difference in outcome.differences:
            print(f"  [XX] {difference.kind}: {_ascii(difference.context)}")
        print(f"  status         : {outcome.status.upper()} - {outcome.reason}")
        print(f"  detail         : {outcome.live.detail}")
        print()

    for note in report.notes:
        print(f"  note: {note}")
    if report.notes:
        print()

    print(f"{_SYMBOLS[report.verdict]} verdict={report.verdict} reason={report.reason}")
    return _EXIT_CODES[report.verdict]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.audit.required_checks_truth",
        description=(
            "Validate infrastructure/quality/required-checks.yaml and resolve every "
            "declared job against the workflow tree (R14.1, R14.2); with --reconcile, "
            "compare the declared set against a branch-protection response read during "
            "this run (R14.4-R14.6)."
        ),
    )
    parser.add_argument("--json", action="store_true", help="emit the machine-readable record")
    parser.add_argument(
        "--check",
        action="store_true",
        help="explicit form of the default in-repo consistency check",
    )
    parser.add_argument(
        "--reconcile",
        action="store_true",
        help="also reconcile against the live branch-protection configuration",
    )
    parser.add_argument(
        "--read-at",
        default=None,
        help="ISO-8601 UTC timestamp of the read performed by THIS run (R14.6)",
    )
    parser.add_argument(
        "--live-protection",
        default=None,
        help="path to the branch-protection response body this run wrote",
    )
    parser.add_argument(
        "--read-exit-code",
        type=int,
        default=0,
        help="exit code of the branch-protection read (non-zero means unreadable)",
    )
    parser.add_argument(
        "--read-error",
        default=None,
        help="path to the captured stderr of the branch-protection read",
    )
    parser.add_argument(
        "--artifact",
        default=None,
        help="path to write the canonical reconciliation payload to",
    )
    parser.add_argument("--repository", default="", help="owner/repo of the reporting run")
    parser.add_argument("--run-id", default="", help="identifier of the reporting run")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)

    inputs: ReconcileInputs | None = None
    if args.reconcile:
        error_text = ""
        if args.read_error is not None:
            error_path = Path(args.read_error)
            if error_path.is_file():
                error_text = error_path.read_text(encoding="utf-8")
        inputs = ReconcileInputs(
            read_at=args.read_at,
            response_path=Path(args.live_protection) if args.live_protection else None,
            read_exit_code=args.read_exit_code,
            read_error=error_text,
        )

    return run(
        as_json=bool(args.json),
        reconcile_inputs=inputs,
        artifact=Path(args.artifact) if args.artifact else None,
        repository=str(args.repository),
        run_id=str(args.run_id),
    )


if __name__ == "__main__":
    sys.exit(main())
