"""scripts/audit/doc_truth.py - narrative-truth gate (C56; design E1.3 / AD-3).

Pins the load-bearing NUMBERS and cadence claims that CLAUDE.md / `docs/state/*`
/ the workflow headers assert to their mechanical source of truth, and FAILs on
drift.

Why this gate exists: the single biggest risk in this repo is the *narrative*
(CLAUDE.md, in-file comments) silently diverging from the *mechanical reality*
the gates enforce - which re-introduces the exact claim-vs-reality gap the whole
verification apparatus was built to kill. CLAUDE.md's own rule: "a fact worth
discovering twice is worth a gate."

Two structural properties, both added by task 2.5:

* **Data-driven pins (AD-3).** Every numeric/flag/blocking-gate/required-job pin
  lives in `infrastructure/quality/doc-number-pins.yaml`, not in a bespoke claim
  function. Adding a pin is a data edit, which is what makes Requirement 7's
  eight-number sweep affordable and R7.5 / R7.10 total rather than per-number.
  Extraction is a pure regex / YAML / JSON read, so it is idempotent by
  construction (design Property 5's round-trip clause).
* **Non-maskable aggregate (R1.4, R1.6).** A claim carries `required`. If a
  required claim cannot be evaluated - the README headline claim's 900s suite
  timeout, an unparseable summary, a missing pin table, the recursion guard
  firing - the aggregate verdict is `unavailable`, and no number of `ok`
  siblings can supply a passing verdict. Before this, `evaluate()` returned `ok`
  when *any* claim was ok, so a skipped headline claim was absorbed by the
  unrelated spec-threshold pin passing. The recursion guard itself was always
  correct and is unchanged; what changed is that a guarded skip is now reported
  instead of masked (I-7: absence of proof is never a pass).

The README-headline claim executes the `verify_claims` suite as a subprocess and
pins the advertised PASS/FAIL/PARTIAL/SKIP/TOTAL counts to what the suite
actually reports. It stays a *narrative* pin: since AD-1 it is no longer the only
path by which a FAIL turns CI red - `scripts/audit/registry_gate.py` runs the
registry in-process and gates on its verdict.

Never fabricates a pass: a claim whose document or mechanical source is missing,
unreadable, or ambiguous reports `skip` naming the cause.

Run::

    python -m scripts.audit.doc_truth            # human lines
    python -m scripts.audit.doc_truth --json     # canonical machine JSON
    python -m scripts.audit.doc_truth --check     # same exit code, no operator note
    python -m scripts.audit.doc_truth --check --emit-nested-json PATH

``--emit-nested-json`` keeps the nested ``verify_claims`` payload this evaluation
already executed, so ``scripts/audit/readme_gen.py --counts-json PATH`` can project the
README's generated region from the **same** execution this gate compares against
instead of spawning a second 900s suite (feature decision-quality-proof, AD-21). That is
why the two steps in ``truth-gates.yml`` are ordered and why the ordering is
load-bearing: this one is the producer.

Exit codes (both modes - a gate whose default invocation cannot fail is the hole
this feature exists to close): ``0`` all claims hold, ``1`` drift, ``2`` a
required claim could not be evaluated. ``2`` is non-passing.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

ROOT = Path(__file__).resolve().parents[2]
CLAUDE_MD = ROOT / "CLAUDE.md"
CD_GCP_YML = ROOT / ".github" / "workflows" / "cd-gcp.yml"
README_MD = ROOT / "README.md"
VERIFY_CLAIMS_PY = ROOT / "scripts" / "audit" / "verify_claims.py"
PIN_TABLE = ROOT / "infrastructure" / "quality" / "doc-number-pins.yaml"

ClaimStatus = Literal["ok", "fail", "skip"]
ProbeStatus = Literal["ok", "fail", "unavailable"]


class ClaimResult(BaseModel):
    """One narrative claim's verdict.

    ``required`` is what makes the aggregate non-maskable: a required claim that
    cannot be evaluated forces ``unavailable`` regardless of how many siblings
    report ``ok`` (R1.6).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    status: ClaimStatus
    required: bool
    detail: str


class NumericPin(BaseModel):
    """One row of ``infrastructure/quality/doc-number-pins.yaml`` (AD-3).

    ``kind`` records which mechanical source family the pin resolves against and
    is reported with the verdict; it never changes the comparison. Comparison is
    driven by ``compare`` alone, so a pin's verdict is readable from its own row.

    ``kind: generated`` is the one exception, and it is a *reachability* exception rather
    than a comparison one (decision-quality-proof task 8.3): a pin whose DOCUMENT side sits
    inside a generated region compares a projection against the very source that projected
    it, which is comparing a mechanism to itself. AD-21 rejects that shape, so such a pin is
    skipped with the reason named rather than evaluated into a tautological ``ok``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    kind: Literal[
        "threshold", "flag", "blocking-gate", "required-job", "generated"
    ]
    required: bool
    document: str
    anchor: str
    source: str
    extractor: str
    compare: Literal["numeric", "string", "count"] = "numeric"
    scale: Literal["identity", "percent_of_fraction"] = "identity"


class DocProbe(BaseModel):
    """The aggregate verdict, as ``verify_claims`` C56 and the CLI both see it."""

    model_config = ConfigDict(frozen=True)

    status: ProbeStatus
    detail: str
    claims: tuple[ClaimResult, ...] = ()

    @property
    def passing(self) -> bool:
        """True only for ``ok``. ``unavailable`` is not a pass (I-7)."""
        return self.status == "ok"


class _Unresolvable(Exception):
    """A claim could not be evaluated. Always becomes a ``skip``, never a pass."""


def _read(path: Path) -> str | None:
    """Read one file as UTF-8 (E-S13-07), or ``None`` when it cannot be read."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _rel(path: Path) -> str:
    """Repo-relative POSIX path, for details that must be greppable on any OS."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------------
# The declarative pin table (AD-3). One data row replaces one claim function.
# ---------------------------------------------------------------------------

#: Governance prose spells small counts as words ("two BLOCKING verify steps"),
#: so a `count` pin accepts either spelling on the document side.
_NUMBER_WORDS: Final[dict[str, int]] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}

#: Relative tolerance for numeric agreement. Wide enough that 80/100 == 0.80
#: survives binary floating point, narrow enough that 0.70 != 0.7001.
_REL_TOL: Final[float] = 1e-9


def load_pins(text: str) -> tuple[NumericPin, ...]:
    """Parse the pin table body into validated rows.

    Only the ``pins:`` list is read. ``pending_pins:`` (rows whose activating task
    has not landed) and ``drift:`` (a work record of known, attributable failures)
    are deliberately NOT evaluated and NOT suppressive - nothing here reads either
    section as a pass.

    Raises :class:`_Unresolvable` for every malformed-table mode, so a broken table
    becomes an unavailable required claim instead of zero silently-skipped pins.
    """
    try:
        raw: object = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise _Unresolvable(f"{_rel(PIN_TABLE)} is not parseable YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise _Unresolvable(f"{_rel(PIN_TABLE)} does not contain a mapping")
    rows = raw.get("pins")
    if not isinstance(rows, list) or not rows:
        raise _Unresolvable(f"{_rel(PIN_TABLE)} declares no pins")
    pins: list[NumericPin] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise _Unresolvable(f"{_rel(PIN_TABLE)} pin #{index} is not a mapping")
        try:
            pins.append(NumericPin.model_validate(row))
        except ValidationError as exc:
            named = row.get("id", f"#{index}")
            problems = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            )
            raise _Unresolvable(f"{_rel(PIN_TABLE)} pin {named!r} is invalid: {problems}") from exc
    seen: set[str] = set()
    duplicates: set[str] = set()
    for pin in pins:
        if pin.id in seen:
            duplicates.add(pin.id)
        seen.add(pin.id)
    if duplicates:
        raise _Unresolvable(
            f"{_rel(PIN_TABLE)} declares duplicate pin id(s): {', '.join(sorted(duplicates))}"
        )
    return tuple(pins)


# ---------------------------------------------------------------------------
# Extraction. Every extractor yields an ORDERED SET of RAW source strings - raw,
# so a failure detail can quote the source byte-for-byte (`0.70`, never `0.7`).
# ---------------------------------------------------------------------------

#: A `[]` path segment fans out over a sequence. A plain name can never be `[]`,
#: so the literal doubles as the sentinel.
_EACH: Final[str] = "[]"

_SEGMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"""
      \['(?P<quoted>[^']*)'\]   # ['packages/synapse_common'] - keys containing dots or slashes
    | \[(?P<index>\d+)\]        # [0]
    | (?P<each>\[\])            # []  - every element of this sequence
    | (?P<name>[^.\[\]]+)       # plain dotted name
    """,
    re.VERBOSE,
)


def path_segments(expression: str) -> tuple[str | int, ...]:
    """Split a ``yaml_path`` / ``json_path`` expression into walkable segments."""
    expression = expression.strip()
    if expression.startswith("$"):
        expression = expression[1:].lstrip(".")
    segments: list[str | int] = []
    position = 0
    while position < len(expression):
        if expression[position] == ".":
            position += 1
            continue
        match = _SEGMENT_RE.match(expression, position)
        if match is None:
            raise _Unresolvable(f"unparseable path expression: {expression!r}")
        if match.group("quoted") is not None:
            segments.append(match.group("quoted"))
        elif match.group("index") is not None:
            segments.append(int(match.group("index")))
        elif match.group("each") is not None:
            segments.append(_EACH)
        else:
            segments.append(match.group("name").strip())
        position = match.end()
    if not segments:
        raise _Unresolvable(f"empty path expression: {expression!r}")
    return tuple(segments)


def _mapping_child(node: MappingNode, key: str) -> Node | None:
    for key_node, value_node in node.value:
        if isinstance(key_node, ScalarNode) and key_node.value == key:
            return value_node
    return None


def _walk_yaml_nodes(root: Node, expression: str) -> tuple[str, ...]:
    """Walk the composed YAML node tree, returning the raw text of each leaf.

    Working on nodes rather than ``safe_load`` output is what preserves the source
    spelling: ``0.70`` stays ``0.70`` instead of becoming the float ``0.7``, so the
    failure detail quotes what is actually committed.
    """
    current: list[Node] = [root]
    for segment in path_segments(expression):
        nxt: list[Node] = []
        for node in current:
            if segment == _EACH:
                if not isinstance(node, SequenceNode):
                    raise _Unresolvable(f"path {expression!r} applies [] to a non-sequence")
                nxt.extend(node.value)
            elif isinstance(segment, int):
                if not isinstance(node, SequenceNode) or segment >= len(node.value):
                    raise _Unresolvable(f"path {expression!r} has no index {segment}")
                nxt.append(node.value[segment])
            else:
                if not isinstance(node, MappingNode):
                    raise _Unresolvable(
                        f"path {expression!r} applies key {segment!r} to a non-mapping"
                    )
                child = _mapping_child(node, segment)
                if child is None:
                    raise _Unresolvable(f"path {expression!r} has no key {segment!r}")
                nxt.append(child)
        current = nxt
    leaves: list[str] = []
    for node in current:
        if not isinstance(node, ScalarNode):
            raise _Unresolvable(f"path {expression!r} does not end at a scalar")
        leaves.append(str(node.value))
    return tuple(leaves)


def _extract_yaml_path(text: str, expression: str) -> tuple[str, ...]:
    try:
        root = yaml.compose(text)
    except yaml.YAMLError as exc:
        raise _Unresolvable(f"source is not parseable YAML: {exc}") from exc
    if root is None:
        raise _Unresolvable("source YAML is empty")
    return _walk_yaml_nodes(root, expression)


def _render_json_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    raise _Unresolvable(f"JSON value {value!r} is not a scalar")


def _extract_json_path(text: str, expression: str) -> tuple[str, ...]:
    try:
        document: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _Unresolvable(f"source is not parseable JSON: {exc}") from exc
    current: list[object] = [document]
    for segment in path_segments(expression):
        nxt: list[object] = []
        for node in current:
            if segment == _EACH:
                if not isinstance(node, list):
                    raise _Unresolvable(f"path {expression!r} applies [] to a non-array")
                nxt.extend(node)
            elif isinstance(segment, int):
                if not isinstance(node, list) or segment >= len(node):
                    raise _Unresolvable(f"path {expression!r} has no index {segment}")
                nxt.append(node[segment])
            else:
                if not isinstance(node, dict) or segment not in node:
                    raise _Unresolvable(f"path {expression!r} has no key {segment!r}")
                nxt.append(node[segment])
        current = nxt
    return tuple(_render_json_scalar(value) for value in current)


def _extract_regex(text: str, expression: str) -> tuple[str, ...]:
    """Every match of ``expression``: the ``value`` group, else group 1, else the match."""
    try:
        pattern = re.compile(expression, re.MULTILINE)
    except re.error as exc:
        raise _Unresolvable(f"unusable extractor regex {expression!r}: {exc}") from exc
    found: list[str] = []
    for match in pattern.finditer(text):
        captured = match.groupdict().get("value")
        if captured is None:
            captured = match.group(1) if match.re.groups else match.group(0)
        found.append(captured)
    return tuple(found)


def extract_source_values(extractor: str, text: str) -> tuple[str, ...]:
    """Read the mechanical source per ``extractor``, as raw strings in order.

    Raises :class:`_Unresolvable` for every failure mode - malformed extractor,
    bad syntax, absent path, non-scalar leaf - so an unreadable source degrades
    honestly instead of defaulting to a value that could pass.
    """
    kind, separator, expression = extractor.partition(":")
    if not separator or not expression:
        raise _Unresolvable(f"malformed extractor {extractor!r} (expected 'kind:expression')")
    if kind == "yaml_path":
        return _extract_yaml_path(text, expression)
    if kind == "json_path":
        return _extract_json_path(text, expression)
    if kind == "regex":
        return _extract_regex(text, expression)
    raise _Unresolvable(
        f"unsupported extractor kind {kind!r} (expected yaml_path, json_path, or regex)"
    )


# ---------------------------------------------------------------------------
# Comparison. `compare` alone decides; `kind` is reported, never branched on.
# ---------------------------------------------------------------------------


def _as_number(raw: str, side: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise _Unresolvable(f"{side} value {raw!r} is not numeric") from exc
    if not math.isfinite(value):
        raise _Unresolvable(f"{side} value {raw!r} is not finite")
    return value


def _as_count(raw: str) -> int:
    word = _NUMBER_WORDS.get(raw.strip().lower())
    if word is not None:
        return word
    try:
        return int(raw)
    except ValueError as exc:
        raise _Unresolvable(
            f"documented count {raw!r} is neither digits nor a number word"
        ) from exc


def documented_value(pin: NumericPin, document_text: str) -> tuple[str, int]:
    """The raw value the document asserts, plus its 1-based line number.

    The anchor must carry a ``(?P<value>...)`` group and must match **exactly one
    line** (the pin table's row contract). Zero matches means the governance
    sentence was reworded; more than one means the pin is ambiguous about which
    line it guards. Both are unresolvable, never a pass.
    """
    try:
        pattern = re.compile(pin.anchor)
    except re.error as exc:
        raise _Unresolvable(f"unusable anchor regex {pin.anchor!r}: {exc}") from exc
    if "value" not in pattern.groupindex:
        raise _Unresolvable(f"anchor {pin.anchor!r} has no (?P<value>...) group")
    hits: list[tuple[int, str]] = []
    for number, line in enumerate(document_text.splitlines(), start=1):
        match = pattern.search(line)
        if match is not None:
            hits.append((number, match.group("value")))
    if not hits:
        raise _Unresolvable(f"{pin.document} has no line matching anchor {pin.anchor!r}")
    if len(hits) > 1:
        lines = ", ".join(str(number) for number, _value in hits)
        raise _Unresolvable(
            f"{pin.document} anchor {pin.anchor!r} matches {len(hits)} lines ({lines}); "
            "a pin must anchor to exactly one"
        )
    number, value = hits[0]
    return value, number


def _distinct(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _single_source_value(pin: NumericPin, values: tuple[str, ...]) -> str:
    if not values:
        raise _Unresolvable(
            f"{pin.source} has no value for extractor {pin.extractor!r}, so the "
            f"{pin.document} claim has nothing to be pinned to"
        )
    distinct = _distinct(values)
    if len(distinct) > 1:
        raise _Unresolvable(
            f"{pin.source} yields {len(distinct)} disagreeing values for extractor "
            f"{pin.extractor!r} ({', '.join(distinct)}); the pin cannot say which is the gate"
        )
    return distinct[0]


def compare_pin(
    pin: NumericPin,
    documented: str,
    document_line: int,
    source_values: tuple[str, ...],
) -> ClaimResult:
    """Compare the documented value against the extracted source value(s).

    Every failure names the document line, the source, and both values (design
    Property 5; R7.5, R7.10, R11.8, R14.3).
    """
    location = f"{pin.document}:{document_line}"

    def result(status: ClaimStatus, detail: str) -> ClaimResult:
        return ClaimResult(name=pin.id, status=status, required=pin.required, detail=detail)

    if pin.compare == "count":
        expected = _as_count(documented)
        distinct = _distinct(source_values)
        if not source_values and expected == 0:
            # THE `None == None` HOLE (decision-quality-proof task 8.3). An empty extraction
            # against a documented zero is not agreement -- it is two absences matching. A
            # `yaml_path:` naming a key that no longer exists resolves to nothing, and a pin
            # comparing nothing to a claim of nothing reports green while establishing
            # nothing. Everywhere else an empty extraction is the honest count `0` and FAILs
            # a non-zero claim (that is the pin table's documented contract and it stays);
            # this one case cannot distinguish "the source genuinely declares none" from
            # "the extractor no longer resolves", so it refuses to guess.
            raise _Unresolvable(
                f"{pin.source} yields no value at all for extractor {pin.extractor!r} while "
                f"{location} claims {documented}: an empty extraction agreeing with a zero "
                "claim compares nothing to nothing, so the extractor cannot be shown to "
                "resolve. Give the pin a non-zero subject, or correct the extractor"
            )
        if len(distinct) != expected:
            listed = ", ".join(distinct) if distinct else "<none>"
            return result(
                "fail",
                f"{location} claims {documented} ({expected}) but {pin.source} shows "
                f"{len(distinct)} matching entr{'y' if len(distinct) == 1 else 'ies'} "
                f"for {pin.extractor!r}: {listed}",
            )
        return result(
            "ok",
            f"{location} claims {documented} and {pin.source} shows {expected}: "
            + ", ".join(distinct),
        )

    if pin.compare == "string":
        if not source_values:
            raise _Unresolvable(
                f"{pin.source} has no value for extractor {pin.extractor!r}, so the "
                f"{pin.document} claim has nothing to be pinned to"
            )
        distinct = _distinct(source_values)
        if documented not in distinct:
            return result(
                "fail",
                f"{location} names {documented!r} but {pin.source} declares "
                f"{', '.join(repr(value) for value in distinct)}",
            )
        return result("ok", f"{location} names {documented!r} and {pin.source} declares it")

    source_raw = _single_source_value(pin, source_values)
    document_number = _as_number(documented, f"{location} documented")
    source_number = _as_number(source_raw, f"{pin.source} source")
    scaled = document_number / 100.0 if pin.scale == "percent_of_fraction" else document_number
    note = f" ({documented} percent == {scaled} as a fraction)" if pin.scale != "identity" else ""
    if not math.isclose(scaled, source_number, rel_tol=_REL_TOL, abs_tol=0.0):
        return result(
            "fail",
            f"{location} states {documented} but {pin.source} has {source_raw}{note}",
        )
    return result("ok", f"{location} and {pin.source} agree: {documented} == {source_raw}{note}")


def resolve_pin_texts(pin: NumericPin, document_text: str, source_text: str) -> ClaimResult:
    """Resolve one pin against two in-memory file bodies.

    Pure: no file read, no process state. This is the seam design Property 5 drives,
    and it is why extraction can be shown idempotent without touching the real tree.
    """
    try:
        documented, line_number = documented_value(pin, document_text)
        if pin.kind == "generated":
            # AD-21: the document side is a PROJECTION of the source side, so comparing them
            # compares a mechanism to itself and can only ever agree. Skipped with the reason
            # named, never evaluated into a tautological `ok`. The generator's own `--check`
            # mode is what actually guards these, by diffing the rendered region.
            raise _Unresolvable(
                f"{pin.document}:{line_number} sits inside a generated region "
                f"(kind: generated), so pinning it against {pin.source} would compare that "
                "region against the source it is projected from -- a mechanism against "
                "itself. The generator's --check mode owns this claim"
            )
        try:
            values = extract_source_values(pin.extractor, source_text)
        except _Unresolvable as exc:
            # Extractor failures describe the shape they could not read ("source is not
            # parseable JSON", "path ... has no key 'break'") but not WHICH source, so
            # attribute them here. Matches the convention the sibling gates already use
            # (required_checks_truth, gate_fault_injection): every unresolved read names
            # its file, so a CI log line stands alone.
            raise _Unresolvable(f"{pin.source}: {exc}") from exc
        return compare_pin(pin, documented, line_number, values)
    except _Unresolvable as exc:
        return ClaimResult(name=pin.id, status="skip", required=pin.required, detail=str(exc))


def resolve_pin(pin: NumericPin, *, root: Path = ROOT) -> ClaimResult:
    """Resolve one pin against the committed tree."""
    document_text = _read(root / pin.document)
    if document_text is None:
        return ClaimResult(
            name=pin.id,
            status="skip",
            required=pin.required,
            detail=f"document {pin.document} is missing or unreadable",
        )
    source_text = _read(root / pin.source)
    if source_text is None:
        return ClaimResult(
            name=pin.id,
            status="skip",
            required=pin.required,
            detail=f"mechanical source {pin.source} is missing or unreadable",
        )
    return resolve_pin_texts(pin, document_text, source_text)


def _pin_claims() -> tuple[ClaimResult, ...]:
    """Every pin in the table, resolved. A broken table is one required skip."""
    text = _read(PIN_TABLE)
    if text is None:
        return (
            ClaimResult(
                name="pin-table",
                status="skip",
                required=True,
                detail=f"pin table {_rel(PIN_TABLE)} is missing or unreadable",
            ),
        )
    try:
        pins = load_pins(text)
    except _Unresolvable as exc:
        return (ClaimResult(name="pin-table", status="skip", required=True, detail=str(exc)),)
    return tuple(resolve_pin(pin) for pin in pins)


# ---------------------------------------------------------------------------
# CLAIM: cd-gcp.yml must not re-assert per-merge auto-deploy.
#
# Not a numeric pin, so it stays a bespoke claim function: it asserts the ABSENCE
# of a phrase, which has no `document value == source value` shape for AD-3's table
# to express. `_claim_spec_threshold` had that shape and is gone - it now lives as
# the `spec-coverage-threshold` row of doc-number-pins.yaml.
# ---------------------------------------------------------------------------

#: Phrases that assert continuous per-merge freshness of the live VM. They are FALSE:
#: the deploy-to-vm `if:` skips plain pushes; the VM deploys weekly (ADR-049). This is
#: a regression guard for the exact drift fixed in Phase 0.
_STALE_DEPLOY_PHRASES: Final[tuple[str, ...]] = ("never more than one workflow run behind HEAD",)


def _claim_deploy_cadence() -> ClaimResult:
    """The deploy cadence claim (ADR-049).

    Required: an unreadable ``cd-gcp.yml`` means the cadence claim cannot be checked,
    and an unchecked cadence claim must not be reported as holding (I-7).
    """
    name = "deploy-cadence"
    cd = _read(CD_GCP_YML)
    if cd is None:
        return ClaimResult(
            name=name,
            status="skip",
            required=True,
            detail=f"{_rel(CD_GCP_YML)} is missing or unreadable",
        )
    hits = [phrase for phrase in _STALE_DEPLOY_PHRASES if phrase in cd]
    if hits:
        return ClaimResult(
            name=name,
            status="fail",
            required=True,
            detail=(
                f"{_rel(CD_GCP_YML)} re-asserts a stale per-merge-deploy claim: {hits!r} - the "
                "deploy-to-vm `if:` skips plain pushes (weekly / tag / dispatch only)"
            ),
        )
    return ClaimResult(
        name=name,
        status="ok",
        required=True,
        detail=f"{_rel(CD_GCP_YML)} carries no stale per-merge-deploy claim",
    )


# ---------------------------------------------------------------------------
# CLAIM: the README headline counts are pinned to the LIVE verify_claims summary.
# The suite is executed at evaluation time and every "actual" count is derived from
# its emitted summary - nothing here is hardcoded, so the pin cannot rot the way the
# numbers it guards did.
#
# This claim is REQUIRED (task 2.5). Every way it can fail to reach a verdict - the
# 900s timeout, an unparseable summary, a missing README, the recursion guard firing -
# now forces the aggregate to `unavailable` instead of being absorbed by an unrelated
# passing pin. The guard itself is unchanged and still correct; what changed is that a
# guarded skip is reported rather than masked (I-7, R1.4, R1.6).
# ---------------------------------------------------------------------------
_HEADLINE_CATEGORIES: Final[tuple[str, ...]] = ("PASS", "FAIL", "PARTIAL", "SKIP", "TOTAL")

#: Recursion guard: verify_claims' own C56 check calls :func:`evaluate` here, and this
#: claim executes verify_claims. The spawned suite carries this marker so its nested C56
#: skips *this* claim only (every other claim still runs), bounding the recursion at
#: depth 1 instead of forking forever.
_NESTED_ENV: Final[str] = "SYNAPSE_DOC_TRUTH_NESTED"

#: The suite shells out to git/docker probes; generous but finite. A timeout is an
#: honest unresolved claim ("suite could not run"), never a pass.
_SUITE_TIMEOUT_S: Final[float] = 900.0

_VERIFY_CLAIMS_MENTION: Final[re.Pattern[str]] = re.compile(r"verify[-_]claims", re.IGNORECASE)


def _extract_count(text: str, category: str) -> int | None:
    """Pull one headline count out of a doc line: ``16 PASS`` or ``PASS=16``."""
    prefixed = re.search(rf"(\d+)\s*{category}\b", text)
    if prefixed is not None:
        return int(prefixed.group(1))
    suffixed = re.search(rf"\b{category}\s*[=:]\s*(\d+)", text)
    if suffixed is not None:
        return int(suffixed.group(1))
    return None


def _readme_headline_line(md: str) -> str | None:
    """The README line that states the ``verify-claims`` headline counts.

    A candidate must both name the suite and carry at least one extractable count, so
    prose like "a SKIP is not a PASS" cannot be mistaken for the headline. When several
    lines qualify, the richest one wins.
    """
    best: tuple[int, str] | None = None
    for raw in md.splitlines():
        if _VERIFY_CLAIMS_MENTION.search(raw) is None:
            continue
        found = sum(1 for cat in _HEADLINE_CATEGORIES if _extract_count(raw, cat) is not None)
        if found and (best is None or found > best[0]):
            best = (found, raw.strip())
    return None if best is None else best[1]


class NestedCheck(BaseModel):
    """One row of a nested ``verify_claims --json`` payload's ``checks`` list.

    Mirrors ``verify_claims.CheckResult``'s four fields, which is what that payload
    serialises (``[r.__dict__ for r in results]``). It is a separate declaration on
    purpose: this is the *parse* of another process's output, and validating it here
    means a payload shape change surfaces as an unresolved claim rather than as an
    attribute error deep inside a consumer.
    """

    model_config = ConfigDict(frozen=True)

    cid: str
    title: str
    status: str
    detail: str = ""


class NestedVerdict(BaseModel):
    """One nested ``verify_claims`` execution, as its ``--json`` payload reports it.

    ``counts`` is the five-category summary the README headline is pinned to.
    ``checks`` is the per-check row list, and it exists so a consumer can read the
    status the *nested* run reported for a specific identifier - which is the whole
    of what `scripts/audit/readme_gen.py` needs to state the recursion-guard
    compensation (R4.8) without modelling the guard a second time (AD-21).

    ``checks`` is empty when the human ``Summary:`` fallback was parsed instead of the
    JSON payload, or when the payload's ``checks`` list could not be validated. Empty
    means "not read", never "no checks ran": a consumer that needs a row reports
    ``unavailable`` naming the identifier it could not find (I-7).
    """

    model_config = ConfigDict(frozen=True)

    counts: Mapping[str, int]
    checks: tuple[NestedCheck, ...] = ()

    def status_of(self, cid: str) -> str | None:
        """The status this execution reported for ``cid``, or ``None`` if no row."""
        for check in self.checks:
            if check.cid == cid:
                return check.status
        return None


def _parse_nested_checks(payload: Mapping[str, object]) -> tuple[NestedCheck, ...]:
    """Validate the payload's ``checks`` list, or return empty on any problem.

    Returning empty rather than raising is deliberate and bounded: the counts are what
    C56 compares against, and an unreadable row list must not turn a readable summary
    into an unresolved claim. The cost lands on the only consumer that needs a row -
    :mod:`scripts.audit.readme_gen`, which reports ``unavailable`` when the identifier
    it needs is absent. Nothing infers a status from an absent row.
    """
    rows = payload.get("checks")
    if not isinstance(rows, list):
        return ()
    parsed: list[NestedCheck] = []
    for row in rows:
        if not isinstance(row, dict):
            return ()
        try:
            parsed.append(NestedCheck.model_validate(row))
        except ValidationError:
            return ()
    return tuple(parsed)


def _parse_suite_summary(stdout: str) -> NestedVerdict | None:
    """Parse one nested execution out of the suite output.

    Prefers the machine-readable ``--json`` payload (which carries the per-check rows
    as well as the summary); falls back to the human ``Summary: PASS=..`` line, which
    carries counts only. Returns ``None`` when neither can be read, which the caller
    turns into an unresolved required claim.
    """
    text = stdout.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            payload = json.loads(text[start : end + 1])
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            summary = payload.get("summary")
            if isinstance(summary, dict):
                counts: dict[str, int] = {}
                for cat in _HEADLINE_CATEGORIES:
                    value = summary.get(cat.lower())
                    if isinstance(value, bool) or not isinstance(value, int):
                        counts = {}
                        break
                    counts[cat] = value
                if counts:
                    return NestedVerdict(counts=counts, checks=_parse_nested_checks(payload))
    line = re.search(r"^Summary:.*$", text, re.MULTILINE)
    if line is None:
        return None
    human: dict[str, int] = {}
    for cat in _HEADLINE_CATEGORIES:
        parsed = _extract_count(line.group(0), cat)
        if parsed is None:
            return None
        human[cat] = parsed
    return NestedVerdict(counts=human)


def nested_suite_counts(*, emit_to: Path | None = None) -> tuple[NestedVerdict | None, str]:
    """Execute the verify_claims suite now and return that one nested execution.

    Public since feature decision-quality-proof task 4.1 (AD-21). It was
    ``_suite_counts`` and private, which forced any second consumer of the nested
    counts to model the recursion guard again - the exact defect AD-21 removes:
    ``ledger_gen`` renders the README headline from the **top-level** verdict, in which
    C56 is PASS, while this claim enforces the **nested** one, in which the guard makes
    C56 self-exclude. Two executions, one published number. There is now one function
    that performs the guarded execution and one execution semantics behind it.

    The 900s budget is deliberate and unchanged: the suite shells out to git and docker
    probes. Exhausting it, or emitting a summary that cannot be parsed, makes a
    *required* claim unresolved and therefore makes the aggregate ``unavailable``
    (R1.4).

    Args:
        emit_to: when given, the payload this execution emitted is written there so a
            following step can consume the *same* execution instead of spawning a
            second 900s suite (``readme_gen --counts-json``). A write failure returns
            no verdict, naming the path: the caller asked for the payload, the ordered
            pair of steps cannot function without it, and reporting the required claim
            unresolved is the honest outcome rather than silently dropping the request.

    Returns:
        ``(verdict, "")`` on success, or ``(None, reason)`` naming what could not be
        done. ``None`` is never a zero-count verdict - absence of a summary is not a
        summary of zero.
    """
    env = dict(os.environ)
    env[_NESTED_ENV] = "1"
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-m", "scripts.audit.verify_claims", "--json"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=_SUITE_TIMEOUT_S,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"verify_claims suite could not be executed: {exc!r}"
    verdict = _parse_suite_summary(proc.stdout)
    if verdict is None:
        tail = (proc.stderr.strip() or proc.stdout.strip() or "<no output>").splitlines()[-1]
        return None, f"verify_claims summary could not be parsed (exit {proc.returncode}): {tail}"
    if emit_to is not None:
        try:
            emit_to.parent.mkdir(parents=True, exist_ok=True)
            emit_to.write_text(proc.stdout, encoding="utf-8", newline="\n")
        except OSError as exc:
            return None, f"nested verify_claims payload could not be written to {emit_to}: {exc!r}"
    return verdict, ""


#: The claim name the guarded verdict and the headline verdict share. One literal, so a
#: test can assert on the guarded claim by name without restating it.
HEADLINE_CLAIM_NAME: Final[str] = "headline-counts"


def headline_claim_under_guard(env: Mapping[str, str]) -> ClaimResult | None:
    """The headline claim's verdict when the recursion guard is set, else ``None``.

    Factored out of :func:`_claim_readme_headline_counts` by feature
    decision-quality-proof task 4.4 (R4.9). The guard branch was previously reachable
    only by evaluating the whole claim, which reads ``README.md`` and - if the guard is
    *not* set - spawns the 900s suite. There was therefore no way to assert the guarded
    status without either executing the Check_Registry or trusting a reading of the
    source, and R4.9 requires exactly that assertion. A grep for ``_NESTED_ENV`` across
    the test tree finds two property tests that ``delenv`` it to keep the guard *out* of
    their scope, and none that assert what it does.

    Pure: a total function of the mapping it is handed. No file read, no subprocess, no
    process state - so the test that drives it costs nothing under I-0.

    Returns:
        A ``skip`` :class:`ClaimResult` naming the guard, or ``None`` when the guard is
        not set (in which case the claim proceeds to its real evaluation). ``required``
        is ``True`` on the guarded result, which is what makes the aggregate
        ``unavailable`` rather than letting a passing sibling supply a verdict for it
        (R4.6, R4.7, I-7).
    """
    if not env.get(_NESTED_ENV):
        return None
    return ClaimResult(
        name=HEADLINE_CLAIM_NAME,
        status="skip",
        required=True,
        detail=(
            f"nested inside a verify_claims run ({_NESTED_ENV} is set) - recursion guard; "
            "this claim self-excludes so the suite it executes cannot fork, and the pin "
            "is checked by the outer doc_truth evaluation"
        ),
    )


def _claim_readme_headline_counts(*, emit_nested_to: Path | None = None) -> ClaimResult:
    """Every README headline count must equal the count the suite actually reports.

    Required (task 2.5): a timeout, an unparseable summary, an absent README, or the
    recursion guard firing can no longer be masked by an unrelated passing pin.

    ``emit_nested_to`` is forwarded to :func:`nested_suite_counts` so a caller can keep
    the payload this execution produced (``--emit-nested-json``). It changes nothing
    about the verdict except that a payload the caller asked for and could not get makes
    the claim unresolved, which is the honest outcome for an incomplete request.
    """
    name = HEADLINE_CLAIM_NAME

    def result(status: ClaimStatus, detail: str) -> ClaimResult:
        return ClaimResult(name=name, status=status, required=True, detail=detail)

    guarded = headline_claim_under_guard(os.environ)
    if guarded is not None:
        return guarded
    md = _read(README_MD)
    if md is None:
        return result("skip", "README.md missing or unreadable")
    if not VERIFY_CLAIMS_PY.is_file():
        return result("skip", "scripts/audit/verify_claims.py missing")
    headline = _readme_headline_line(md)
    if headline is None:
        return result("skip", "no verify-claims headline count line found in README.md")
    verdict, error = nested_suite_counts(emit_to=emit_nested_to)
    if verdict is None:
        return result("skip", error)
    actual = verdict.counts
    claimed = {cat: _extract_count(headline, cat) for cat in _HEADLINE_CATEGORIES}
    drifts = [
        f"{cat} (README claims {'absent' if claimed[cat] is None else claimed[cat]}, "
        f"suite reports {actual[cat]})"
        for cat in _HEADLINE_CATEGORIES
        if claimed[cat] != actual[cat]
    ]
    if drifts:
        return result(
            "fail",
            "README headline drifted from the live verify_claims summary: " + "; ".join(drifts),
        )
    return result(
        "ok",
        "README headline matches the live verify_claims summary: "
        + " ".join(f"{cat}={actual[cat]}" for cat in _HEADLINE_CATEGORIES),
    )


# ---------------------------------------------------------------------------
# Aggregation. The non-maskable part (R1.4, R1.6).
# ---------------------------------------------------------------------------

#: Bespoke claims that take no argument - only the shapes AD-3's table cannot express.
#: Everything with a `document value == source value` shape is a row in
#: doc-number-pins.yaml. The headline claim is NOT here: it is invoked last and by name
#: in :func:`collect_claims` because it is the only claim that spawns a process and the
#: only one that can be asked to keep that process's payload.
_CLAIMS: Final[tuple[Callable[[], ClaimResult], ...]] = (_claim_deploy_cadence,)

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 1
EXIT_UNAVAILABLE: Final[int] = 2

_EXIT_CODES: Mapping[ProbeStatus, int] = {
    "ok": EXIT_PASS,
    "fail": EXIT_FAIL,
    "unavailable": EXIT_UNAVAILABLE,
}

_CLAIM_SYMBOLS: Mapping[ClaimStatus, str] = {"ok": "[OK]", "fail": "[XX]", "skip": "[--]"}
_PROBE_SYMBOLS: Mapping[ProbeStatus, str] = {"ok": "[OK]", "fail": "[XX]", "unavailable": "[??]"}


def collect_claims(*, emit_nested_to: Path | None = None) -> tuple[ClaimResult, ...]:
    """Evaluate every claim: the declarative pin table, then the bespoke claims.

    The headline claim is evaluated last and unchanged in position - it is the only one
    that spawns a process, so a failure in a cheap claim is reported before the 900s
    budget is spent.
    """
    return (
        _pin_claims()
        + tuple(claim() for claim in _CLAIMS)
        + (_claim_readme_headline_counts(emit_nested_to=emit_nested_to),)
    )


def _named(results: tuple[ClaimResult, ...]) -> str:
    return "; ".join(f"{result.name}: {result.detail}" for result in results)


def evaluate_claims(claims: tuple[ClaimResult, ...]) -> DocProbe:
    """Aggregate a claim multiset into the gate's verdict.

    Pure: no file read, no subprocess, no process state, so the verdict is a total
    function of its argument and design Property 2 can drive it without executing the
    900s suite (I-0).

    Rules, in order - first match wins:

    1. no claims at all              -> ``unavailable``: nothing was evaluated, so
       nothing was proven.
    2. any claim reports ``fail``    -> ``fail``, naming each drift. A proven falsehood
       is strictly more actionable than an unknown, so drift keeps exit ``1``; any
       unresolved *required* claim is named in the same detail so it is not hidden.
    3. any REQUIRED claim reports
       ``skip``                      -> ``unavailable``, naming each. This is the
       non-maskable clause (R1.6): the count of ``ok`` siblings is irrelevant.
    4. no claim reports ``ok``       -> ``unavailable``: an all-skip run proves nothing.
    5. otherwise                     -> ``ok``.

    Rule 3 is the defect this task removes. The previous aggregate returned ``ok`` as
    soon as *any* claim was ``ok``, so a headline claim skipped by a suite timeout was
    absorbed by an unrelated pin passing - absence of proof reported as proof (I-7).
    """
    fails = tuple(claim for claim in claims if claim.status == "fail")
    unresolved_required = tuple(
        claim for claim in claims if claim.status == "skip" and claim.required
    )
    oks = tuple(claim for claim in claims if claim.status == "ok")

    if not claims:
        return DocProbe(
            status="unavailable",
            detail="no doc claims were evaluated, so no narrative claim was verified",
            claims=claims,
        )
    if fails:
        detail = f"{len(fails)} doc claim(s) drifted from source - {_named(fails)}"
        if unresolved_required:
            detail += (
                f"; additionally {len(unresolved_required)} required claim(s) could not be "
                f"evaluated - {_named(unresolved_required)}"
            )
        return DocProbe(status="fail", detail=detail, claims=claims)
    if unresolved_required:
        return DocProbe(
            status="unavailable",
            detail=(
                f"{len(unresolved_required)} required doc claim(s) could not be evaluated - "
                f"{_named(unresolved_required)}"
                f" ({len(oks)} other claim(s) passed; a passing sibling does not supply a "
                "verdict for an unevaluated required claim)"
            ),
            claims=claims,
        )
    if not oks:
        return DocProbe(
            status="unavailable",
            detail=f"no doc claim could be evaluated - {_named(claims)}",
            claims=claims,
        )
    return DocProbe(
        status="ok",
        detail=(
            f"{len(oks)}/{len(claims)} doc claims match source ("
            + ", ".join(claim.name for claim in oks)
            + ")"
        ),
        claims=claims,
    )


def evaluate(*, emit_nested_to: Path | None = None) -> DocProbe:
    """Evaluate every claim against the committed tree and aggregate the verdict.

    ``emit_nested_to`` is optional and defaults to off, so ``verify_claims``' C56 call
    site (``evaluate()``) is unchanged.
    """
    return evaluate_claims(collect_claims(emit_nested_to=emit_nested_to))


# ---------------------------------------------------------------------------
# CLI. `print` here is the entry-point reporting style shared with verify_claims and
# registry_gate; nothing in the library path above prints.
# ---------------------------------------------------------------------------


def run(*, as_json: bool = False, check: bool = False, emit_nested_json: Path | None = None) -> int:
    """Evaluate and report. Returns ``0`` / ``1`` / ``2`` in **both** modes.

    ``--check`` only suppresses the trailing operator note. A gate whose default
    invocation cannot fail is the hole this feature exists to close (R1.8).

    ``emit_nested_json`` writes the nested ``verify_claims`` payload this evaluation
    executed, so a following step can consume the same execution rather than spawning a
    second 900s suite. That is what makes the ``doc_truth --check`` ->
    ``readme_gen --check`` pair in ``truth-gates.yml`` ordered and its ordering
    load-bearing (AD-21's cost note): the earlier step is the producer.
    """
    probe = evaluate(emit_nested_to=emit_nested_json)

    if as_json:
        print(
            json.dumps(
                probe.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return _EXIT_CODES[probe.status]

    for claim in probe.claims:
        flag = "required" if claim.required else "optional"
        print(f"{_CLAIM_SYMBOLS[claim.status]} doc-truth/{claim.name:<32} [{flag}] {claim.detail}")
    print(f"{_PROBE_SYMBOLS[probe.status]} doc-truth: {probe.status.upper()} - {probe.detail}")
    if not check:
        print()
        print(
            "(this gate's exit status is its verdict - it must not be wrapped in "
            "`|| true` or `continue-on-error`. 2 means a required claim could not be "
            "evaluated, which is not a pass.)"
        )
    return _EXIT_CODES[probe.status]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="doc_truth",
        description="Pin governance-document claims to their mechanical source (C56).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the verdict as canonical JSON instead of human lines",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="suppress the operator note; the exit code is verdict-derived either way",
    )
    parser.add_argument(
        "--emit-nested-json",
        metavar="PATH",
        default=None,
        help=(
            "write the nested verify_claims --json payload this evaluation executed, so a "
            "following step (readme_gen --counts-json) consumes the same execution instead "
            "of spawning a second 900s suite"
        ),
    )
    args = parser.parse_args(argv)
    emit = Path(args.emit_nested_json) if args.emit_nested_json else None
    return run(as_json=bool(args.as_json), check=bool(args.check), emit_nested_json=emit)


if __name__ == "__main__":
    sys.exit(main())
