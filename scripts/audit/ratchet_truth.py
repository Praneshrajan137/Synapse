"""Keep every ratcheted threshold monotone and equal to the config it guards (R2.10, R7.4, R7.8).

Audit findings this gate closes:

  * **R7.4** -- nothing in the repository stops a committed threshold from being
    quietly moved to a weaker value. ``infrastructure/quality/ratchets.json``
    records the *highest-ever committed value* for every ratcheted threshold
    (coverage floors, the frontend Stryker ``break``, the mutation-survival
    ceilings, ``UPLIFT_FLOOR``, the dead-module baseline, the actuation-stub
    ceiling). A committed value on the wrong side of that bound FAILs here,
    naming the threshold, the recorded bound (**previous**) and the committed
    value (**proposed**).
  * **R7.8** -- a ratchet constant frozen below the configuration it claims to
    guard converts a floor into a no-op. ``frontend/stryker.conf.json`` ships
    ``thresholds.break = 50`` while ``verify_claims.py::STRYKER_BREAK_NOW`` is
    still ``26``, so a regression 50 -> 26 currently PASSES C16. This gate FAILs
    naming **both** files and **both** values. It does not repair either value --
    remediation is task 12.1; the gate's job is to make the hole bite.
  * **R2.10** -- ``UPLIFT_FLOOR`` is *data-gated*: a raise above ``0.0`` is
    admissible only through ``uplift.uplift_floor.ratchet_to_measured`` against a
    same-run :class:`~uplift.uplift_floor.PoweredProof`. A raise with no such
    proof is rejected here. (Wiring that admission path into the C60 gate is task
    10.3; this gate only refuses to let an unproven raise through.)

Every number is read from a committed file. Each row's ``shipped.value`` is
**re-extracted** from the real configuration it names, so a record that has rotted
away from the tree it describes is itself a FAIL rather than a quiet fiction. Three
extractor forms are implemented, matching the vocabulary already used by
``infrastructure/quality/doc-number-pins.yaml``:

  * ``yaml_path:packages['agents/supplier_trust'].line``
  * ``json_path:$.thresholds.break``
  * ``regex:^UPLIFT_FLOOR: float = (?P<value>[\\d.]+)$`` (evaluated multi-line;
    the value is group ``value`` when named, else group 1)

**I-7 honest degradation.** A row with ``status: unmeasured`` or
``measured_at: null`` has no measurement behind it. It is reported ``skip`` -- a
state distinct from ``pass`` -- and no measurement is ever fabricated to stand in
for one. A row whose shipped file cannot be read or whose extractor matches
nothing is reported ``unavailable``. Neither is a pass. A real regression outranks
both, so an absence can never mask a breach.

Outcome mapping::

    any row fails a clause      -> exit 1  (fail)
    else any row unavailable    -> exit 2  (unavailable; never a pass)
    else any row unmeasured     -> exit 2  (skip; never a pass)
    else every row clean        -> exit 0  (pass)

``--apply`` is the operator maintenance step: it raises a recorded bound to the
committed value when the commit moved in the ratcheting direction, never the other
way, and never for a data-gated row without a supporting proof. It never writes
``status``, ``measured_at``, or ``source_run`` -- only a run that took a
measurement may record one (CF-3).

I-0: this gate reads files. It runs no suite, no mutation sweep, and no coverage.

Run::

    python -m scripts.audit.ratchet_truth             # human summary
    python -m scripts.audit.ratchet_truth --json      # canonical JSON report
    python -m scripts.audit.ratchet_truth --check     # exit 0/1/2 per the mapping
    python -m scripts.audit.ratchet_truth --apply     # bump bounds that improved
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

ROOT = Path(__file__).resolve().parents[2]

# Ensure the repo root is importable when run as a bare script (not -m).
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RATCHETS_FILE = ROOT / "infrastructure" / "quality" / "ratchets.json"

# Distinct exit codes, mirroring scripts/audit/replay_metrics.py and uplift_truth.py.
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNAVAILABLE = 2

#: ``bound`` is the highest-ever committed value; a lower commit is the regression.
DIRECTION_UP = "up"
#: ``bound`` is a ceiling that only tightens; a higher commit is the regression.
DIRECTION_DOWN = "down"
DIRECTIONS = (DIRECTION_UP, DIRECTION_DOWN)

STATUS_MEASURED = "measured"
STATUS_UNMEASURED = "unmeasured"

# Float comparison tolerance. Every committed threshold is an exact short decimal,
# so this only absorbs YAML/JSON round-trip representation, never a real delta.
_TOLERANCE = 1e-9


class Outcome(str, Enum):
    """Four-state row/aggregate outcome. Only ``PASS`` is a pass (I-7)."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    UNAVAILABLE = "unavailable"


class Clause(str, Enum):
    """The clause a finding belongs to, so a failure names its own rule."""

    MONOTONICITY = "monotonicity"
    CONFIG_AGREEMENT = "config-agreement"
    RECORD_DRIFT = "record-drift"
    DATA_GATE = "data-gate"


class Shipped(BaseModel):
    """The configuration a ratchet guards, and how to read its value."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    file: str
    extractor: str
    value: float


class GuardConstant(BaseModel):
    """The in-code constant that claims to guard a shipped configuration value."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    file: str
    symbol: str
    value: float


class RatchetRecord(BaseModel):
    """One row of ``infrastructure/quality/ratchets.json``.

    Monotone by construction: ``bound`` is only ever moved in the direction the
    row declares, and only by the ``--apply`` operator step.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    kind: str
    direction: str
    bound: float
    unit: str | None = None
    shipped: Shipped
    guard_constant: GuardConstant | None = None
    agrees_with_shipped: bool
    status: str
    measured_at: str | None = None
    source_run: str | None = None
    data_gated: bool = False
    admission: str | None = None
    note: str | None = None

    @property
    def measured(self) -> bool:
        """True only when a measurement is actually recorded (I-7)."""
        return self.status == STATUS_MEASURED and self.measured_at is not None


class Finding(BaseModel):
    """One clause violation, carrying the message that names its subjects."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    clause: Clause
    detail: str


class RatchetReport(BaseModel):
    """The verdict for one ratchet id."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    kind: str | None = None
    direction: str | None = None
    bound: float | None = None
    committed: float | None = None
    shipped_file: str | None = None
    guard_file: str | None = None
    guard_symbol: str | None = None
    guard_value: float | None = None
    status: str | None = None
    outcome: Outcome
    findings: tuple[Finding, ...] = ()
    detail: str


class RatchetTruthReport(BaseModel):
    """The full ratchet verdict, persisted canonically."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ratchets_file: str
    version: int | None = None
    ratchets: tuple[RatchetReport, ...] = ()
    outcome: Outcome
    exit_code: int

    def canonical_json(self) -> str:
        """Canonical serialisation for a persisted payload."""
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )


class _Unavailable(Exception):
    """Raised when a committed value could not be read. Never a pass."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


# ---------------------------------------------------------------------------
# Value extraction -- three forms, all reading committed files
# ---------------------------------------------------------------------------

_SEGMENT_RE = re.compile(
    r"""\[\s*(?P<quote>['"])(?P<quoted>.*?)(?P=quote)\s*\]"""  # ['key with /']
    r"""|\[\s*(?P<index>\d+)\s*\]"""  # [0]
    r"""|(?P<name>[^.\[\]]+)"""  # dotted.name
)


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _as_finite_float(value: object) -> float | None:
    """Coerce a scalar to a finite float. Booleans are never numbers here."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    if isinstance(value, str):
        try:
            numeric = float(value.strip())
        except ValueError:
            return None
        return numeric if math.isfinite(numeric) else None
    return None


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=_TOLERANCE, abs_tol=_TOLERANCE)


def _fmt(value: float) -> str:
    """Render a threshold the way it is committed: ``50`` not ``50.0``, ``83.5`` as-is."""
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _read_text(path: Path) -> str:
    """Read a committed file with ``encoding='utf-8'`` (E-S13-07)."""
    if not path.is_file():
        raise _Unavailable(f"shipped file missing: {_rel(path)}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise _Unavailable(f"shipped file unreadable: {_rel(path)}: {exc}") from exc


def path_segments(expression: str) -> tuple[str | int, ...]:
    """Split a ``yaml_path``/``json_path`` expression into walkable segments.

    Supports dotted names, bracketed quoted keys (needed for the coverage-floor
    keys, which contain ``/``), and integer list indices. A leading ``$`` is the
    JSONPath root and is dropped.
    """
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
            raise _Unavailable(f"unparseable path expression: {expression!r}")
        if match.group("quoted") is not None:
            segments.append(match.group("quoted"))
        elif match.group("index") is not None:
            segments.append(int(match.group("index")))
        else:
            segments.append(match.group("name").strip())
        position = match.end()
    if not segments:
        raise _Unavailable(f"empty path expression: {expression!r}")
    return tuple(segments)


def _walk(document: object, segments: tuple[str | int, ...], expression: str) -> object:
    current = document
    for segment in segments:
        if isinstance(segment, int):
            if not isinstance(current, list) or segment >= len(current):
                raise _Unavailable(f"path {expression!r} has no index {segment}")
            current = current[segment]
            continue
        if not isinstance(current, dict) or segment not in current:
            raise _Unavailable(f"path {expression!r} has no key {segment!r}")
        current = current[segment]
    return current


def _extract_yaml_path(path: Path, expression: str) -> float:
    try:
        document = yaml.safe_load(_read_text(path))
    except yaml.YAMLError as exc:
        raise _Unavailable(f"unparseable YAML: {_rel(path)}: {exc}") from exc
    value = _as_finite_float(_walk(document, path_segments(expression), expression))
    if value is None:
        raise _Unavailable(f"{_rel(path)} path {expression!r} is not a finite number")
    return value


def _extract_json_path(path: Path, expression: str) -> float:
    try:
        document = json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise _Unavailable(f"unparseable JSON: {_rel(path)}: {exc}") from exc
    value = _as_finite_float(_walk(document, path_segments(expression), expression))
    if value is None:
        raise _Unavailable(f"{_rel(path)} path {expression!r} is not a finite number")
    return value


def _extract_regex(path: Path, expression: str) -> float:
    try:
        pattern = re.compile(expression, re.MULTILINE)
    except re.error as exc:
        raise _Unavailable(f"unusable extractor regex {expression!r}: {exc}") from exc
    match = pattern.search(_read_text(path))
    if match is None:
        raise _Unavailable(f"{_rel(path)} has no match for regex {expression!r}")
    group = match.groupdict().get("value")
    raw = group if group is not None else (match.group(1) if match.re.groups else match.group(0))
    value = _as_finite_float(raw)
    if value is None:
        raise _Unavailable(f"{_rel(path)} regex {expression!r} captured non-numeric {raw!r}")
    return value


def extract(extractor: str, path: Path) -> float:
    """Read one committed numeric value from ``path`` per ``extractor``.

    Raises :class:`_Unavailable` for every failure mode -- missing file, bad
    syntax, absent path, non-numeric capture -- so an unreadable value degrades
    honestly instead of defaulting to something that could pass.
    """
    kind, separator, expression = extractor.partition(":")
    if not separator or not expression:
        raise _Unavailable(f"malformed extractor {extractor!r} (expected 'kind:expression')")
    if kind == "yaml_path":
        return _extract_yaml_path(path, expression)
    if kind == "json_path":
        return _extract_json_path(path, expression)
    if kind == "regex":
        return _extract_regex(path, expression)
    raise _Unavailable(
        f"unsupported extractor kind {kind!r} (expected yaml_path, json_path, or regex)"
    )


def extract_guard_constant(guard: GuardConstant, root: Path) -> float | None:
    """Re-read a simple ``SYMBOL = <number>`` guard constant from its own file.

    Returns ``None`` when the symbol is not a numeric module-level assignment (the
    ``UPLIFT_FLOOR`` guard names a *test function*, not a constant). ``None`` means
    "not independently verifiable here" -- it is never treated as agreement, and no
    value is invented in its place.
    """
    path = root / guard.file
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    match = re.search(
        rf"^{re.escape(guard.symbol)}(?:\s*:\s*[A-Za-z_][\w.\[\], ]*)?\s*=\s*(-?[\d.]+)\s*(?:#.*)?$",
        text,
        re.MULTILINE,
    )
    if match is None:
        return None
    return _as_finite_float(match.group(1))


# ---------------------------------------------------------------------------
# Clause evaluation
# ---------------------------------------------------------------------------


class ProofLike:
    """Structural stand-in for :class:`uplift.uplift_floor.PoweredProof`.

    Declared as a protocol-shaped base rather than imported so this gate does not
    become the production call site of the uplift admission path -- wiring
    ``ratchet_to_measured`` / ``is_proven_uplift`` into C60 is task 10.3. Anything
    exposing ``supports(proposed) -> bool`` (the real ``PoweredProof`` does) is
    accepted here.
    """

    def supports(self, proposed: float) -> bool:  # pragma: no cover - interface only
        raise NotImplementedError


def is_regression(direction: str, bound: float, committed: float) -> bool:
    """True when ``committed`` sits on the wrong side of ``bound`` (R7.4).

    ``up``: ``bound`` is the highest-ever committed value, so a *lower* commit is
    the regression. ``down``: ``bound`` is a ceiling that only tightens, so a
    *higher* commit is the regression.
    """
    if _same(bound, committed):
        return False
    if direction == DIRECTION_UP:
        return committed < bound
    if direction == DIRECTION_DOWN:
        return committed > bound
    raise _Unavailable(f"unsupported ratchet direction {direction!r} (expected one of {DIRECTIONS})")


def is_improvement(direction: str, bound: float, committed: float) -> bool:
    """True when ``committed`` strictly tightens the ratchet past ``bound``."""
    if _same(bound, committed):
        return False
    return committed > bound if direction == DIRECTION_UP else committed < bound


def judge_ratchet(
    identifier: str,
    record: RatchetRecord,
    *,
    root: Path = ROOT,
    proof: ProofLike | None = None,
) -> RatchetReport:
    """Evaluate every clause for one ratchet id against the real tree.

    Clause order is deliberate: a real breach (``fail``) outranks an unmeasured
    row (``skip``), so an absent measurement can never mask a regression.
    """
    shipped_path = root / record.shipped.file
    if record.direction not in DIRECTIONS:
        return RatchetReport(
            id=identifier,
            kind=record.kind,
            direction=record.direction,
            bound=record.bound,
            shipped_file=record.shipped.file,
            status=record.status,
            outcome=Outcome.UNAVAILABLE,
            detail=(
                f"unsupported direction {record.direction!r}; expected "
                f"{DIRECTION_UP!r} or {DIRECTION_DOWN!r}"
            ),
        )

    try:
        committed = extract(record.shipped.extractor, shipped_path)
    except _Unavailable as exc:
        return RatchetReport(
            id=identifier,
            kind=record.kind,
            direction=record.direction,
            bound=record.bound,
            shipped_file=record.shipped.file,
            guard_file=None if record.guard_constant is None else record.guard_constant.file,
            guard_symbol=None if record.guard_constant is None else record.guard_constant.symbol,
            guard_value=None if record.guard_constant is None else record.guard_constant.value,
            status=record.status,
            outcome=Outcome.UNAVAILABLE,
            detail=f"no committed value could be read: {exc.detail}",
        )

    findings: list[Finding] = []

    # -- the record itself must still describe the tree it names -----------------
    if not _same(committed, record.shipped.value):
        findings.append(
            Finding(
                clause=Clause.RECORD_DRIFT,
                detail=(
                    f"{identifier}: recorded shipped.value {_fmt(record.shipped.value)} has "
                    f"drifted from {record.shipped.file}, which now ships {_fmt(committed)} "
                    f"(extractor {record.shipped.extractor!r}); re-record the ratchet"
                ),
            )
        )

    # -- clause 1: monotonicity (R7.4, R2.10) -----------------------------------
    if is_regression(record.direction, record.bound, committed):
        relation = "below" if record.direction == DIRECTION_UP else "above"
        findings.append(
            Finding(
                clause=Clause.MONOTONICITY,
                detail=(
                    f"{identifier}: committed value {relation} its recorded bound -- "
                    f"previous {_fmt(record.bound)}, proposed {_fmt(committed)} "
                    f"(direction {record.direction}, from {record.shipped.file})"
                ),
            )
        )

    # -- clause 1b: a data-gated raise needs a same-run powered proof (R2.10) ----
    if record.data_gated and is_improvement(record.direction, record.bound, committed):
        admission = record.admission or (
            "uplift.uplift_floor.ratchet_to_measured against a same-run PoweredProof"
        )
        if proof is None or not proof.supports(committed):
            reason = (
                "no powered proof was supplied"
                if proof is None
                else "the supplied proof does not support it"
            )
            findings.append(
                Finding(
                    clause=Clause.DATA_GATE,
                    detail=(
                        f"{identifier}: raise from {_fmt(record.bound)} to {_fmt(committed)} in "
                        f"{record.shipped.file} is not backed by a measurement -- {reason}; "
                        f"a raise is admissible only through {admission}"
                    ),
                )
            )

    # -- clause 2: the guard constant must equal the shipped value (R7.8) -------
    guard = record.guard_constant
    guard_source_value: float | None = None
    if guard is not None:
        guard_source_value = extract_guard_constant(guard, root)
        if guard_source_value is not None and not _same(guard_source_value, guard.value):
            findings.append(
                Finding(
                    clause=Clause.RECORD_DRIFT,
                    detail=(
                        f"{identifier}: recorded guard_constant.value {_fmt(guard.value)} has "
                        f"drifted from {guard.file}::{guard.symbol}, which now holds "
                        f"{_fmt(guard_source_value)}; re-record the ratchet"
                    ),
                )
            )
        effective_guard = guard.value if guard_source_value is None else guard_source_value
        if not _same(effective_guard, committed):
            findings.append(
                Finding(
                    clause=Clause.CONFIG_AGREEMENT,
                    detail=(
                        f"{identifier}: ratchet constant disagrees with the configuration it "
                        f"guards -- {guard.file}::{guard.symbol} = {_fmt(effective_guard)} but "
                        f"{record.shipped.file} ships {_fmt(committed)} "
                        f"({record.shipped.extractor!r}); a gate comparing against the constant "
                        f"cannot catch a regression to it"
                    ),
                )
            )

    computed_agreement = guard is None or _same(
        guard.value if guard_source_value is None else guard_source_value, committed
    )
    if computed_agreement != record.agrees_with_shipped:
        agreement_word = "agree" if computed_agreement else "disagree"
        findings.append(
            Finding(
                clause=Clause.RECORD_DRIFT,
                detail=(
                    f"{identifier}: agrees_with_shipped records "
                    f"{record.agrees_with_shipped} but the guard constant and the shipped "
                    f"value {agreement_word}"
                ),
            )
        )

    if findings:
        outcome = Outcome.FAIL
        detail = findings[0].detail
    elif not record.measured:
        outcome = Outcome.SKIP
        detail = (
            f"{identifier}: no measurement recorded (status {record.status}, "
            f"measured_at {record.measured_at}); bound {_fmt(record.bound)} is a declared value "
            f"only"
        )
    else:
        outcome = Outcome.PASS
        detail = (
            f"{identifier}: committed {_fmt(committed)} holds the {record.direction} ratchet at "
            f"{_fmt(record.bound)}; measured {record.measured_at}"
        )

    return RatchetReport(
        id=identifier,
        kind=record.kind,
        direction=record.direction,
        bound=record.bound,
        committed=committed,
        shipped_file=record.shipped.file,
        guard_file=None if guard is None else guard.file,
        guard_symbol=None if guard is None else guard.symbol,
        guard_value=None if guard is None else guard.value,
        status=record.status,
        outcome=outcome,
        findings=tuple(findings),
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Whole-file evaluation
# ---------------------------------------------------------------------------


def load_ratchets(ratchets_file: Path = RATCHETS_FILE) -> dict[str, Any]:
    """Read ``ratchets.json``. A file that cannot be read is never a pass."""
    if not ratchets_file.is_file():
        raise _Unavailable(f"ratchets file missing: {_rel(ratchets_file)}")
    try:
        document = json.loads(ratchets_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise _Unavailable(f"ratchets file unreadable: {_rel(ratchets_file)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise _Unavailable(f"ratchets file is not valid JSON: {_rel(ratchets_file)}: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("ratchets"), dict):
        raise _Unavailable(f"{_rel(ratchets_file)} has no `ratchets` mapping")
    return document


def _aggregate(rows: tuple[RatchetReport, ...]) -> Outcome:
    """FAIL > UNAVAILABLE > SKIP > PASS. A skip is never a pass (I-7)."""
    if any(row.outcome is Outcome.FAIL for row in rows):
        return Outcome.FAIL
    if any(row.outcome is Outcome.UNAVAILABLE for row in rows):
        return Outcome.UNAVAILABLE
    if any(row.outcome is Outcome.SKIP for row in rows):
        return Outcome.SKIP
    return Outcome.PASS


_EXIT_BY_OUTCOME = {
    Outcome.PASS: EXIT_PASS,
    Outcome.FAIL: EXIT_FAIL,
    Outcome.UNAVAILABLE: EXIT_UNAVAILABLE,
    Outcome.SKIP: EXIT_UNAVAILABLE,
}


def evaluate(
    ratchets_file: Path = RATCHETS_FILE,
    *,
    root: Path = ROOT,
    proof: ProofLike | None = None,
) -> RatchetTruthReport:
    """Evaluate every recorded ratchet against the committed tree."""
    try:
        document = load_ratchets(ratchets_file)
    except _Unavailable as exc:
        return RatchetTruthReport(
            ratchets_file=_rel(ratchets_file),
            ratchets=(
                RatchetReport(id="<file>", outcome=Outcome.UNAVAILABLE, detail=exc.detail),
            ),
            outcome=Outcome.UNAVAILABLE,
            exit_code=EXIT_UNAVAILABLE,
        )

    version = document.get("version")
    rows: list[RatchetReport] = []
    for identifier, raw in document["ratchets"].items():
        try:
            record = RatchetRecord.model_validate(raw)
        except ValidationError as exc:
            rows.append(
                RatchetReport(
                    id=identifier,
                    outcome=Outcome.UNAVAILABLE,
                    detail=f"{identifier}: malformed ratchet record: {exc.error_count()} error(s)",
                )
            )
            continue
        rows.append(judge_ratchet(identifier, record, root=root, proof=proof))

    outcome = _aggregate(tuple(rows))
    return RatchetTruthReport(
        ratchets_file=_rel(ratchets_file),
        version=version if isinstance(version, int) else None,
        ratchets=tuple(rows),
        outcome=outcome,
        exit_code=_EXIT_BY_OUTCOME[outcome],
    )


# ---------------------------------------------------------------------------
# Maintenance: raise a bound the tree has already improved on
# ---------------------------------------------------------------------------


def apply_improvements(
    ratchets_file: Path = RATCHETS_FILE,
    *,
    root: Path = ROOT,
    proof: ProofLike | None = None,
    write: bool = True,
) -> tuple[str, ...]:
    """Move each recorded ``bound`` to the committed value when it improved.

    Only ever tightens: a regression is reported by :func:`evaluate` and is never
    written. A data-gated row is skipped unless ``proof`` supports the raise
    (R2.10). ``status``, ``measured_at``, and ``source_run`` are never touched --
    only a run that took a measurement may record one (CF-3, I-7).
    """
    document = load_ratchets(ratchets_file)
    messages: list[str] = []
    changed = False
    for identifier, raw in document["ratchets"].items():
        try:
            record = RatchetRecord.model_validate(raw)
        except ValidationError:
            continue
        if record.direction not in DIRECTIONS:
            continue
        try:
            committed = extract(record.shipped.extractor, root / record.shipped.file)
        except _Unavailable:
            continue
        if not is_improvement(record.direction, record.bound, committed):
            continue
        if record.data_gated and (proof is None or not proof.supports(committed)):
            messages.append(
                f"[--] {identifier}: {_fmt(record.bound)} -> {_fmt(committed)} withheld; a "
                f"data-gated "
                f"raise needs a supporting powered proof (R2.10)"
            )
            continue
        raw["bound"] = committed
        raw["shipped"]["value"] = committed
        changed = True
        messages.append(
            f"[OK] {identifier}: bound ratcheted {_fmt(record.bound)} -> {_fmt(committed)}"
        )
    if changed and write:
        ratchets_file.write_text(
            json.dumps(document, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
    if not messages:
        messages.append("[OK] no bound improved on; nothing to ratchet")
    return tuple(messages)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

_MARKER = {
    Outcome.PASS: "[OK]",
    Outcome.FAIL: "[XX]",
    Outcome.SKIP: "[--]",
    Outcome.UNAVAILABLE: "[??]",
}


def format_report(report: RatchetTruthReport) -> list[str]:
    """ASCII-only human summary; every failure names its subjects."""
    lines = [
        f"ratchet-truth: {len(report.ratchets)} ratchet(s) from {report.ratchets_file}"
        f" (version {report.version})"
    ]
    for row in report.ratchets:
        lines.append(f"{_MARKER[row.outcome]} {row.detail}")
        for finding in row.findings[1:]:
            lines.append(f"     + {finding.clause.value}: {finding.detail}")
    counts = {outcome: 0 for outcome in Outcome}
    for row in report.ratchets:
        counts[row.outcome] += 1
    lines.append(
        f"ratchet-truth: PASS {counts[Outcome.PASS]} / FAIL {counts[Outcome.FAIL]} / "
        f"SKIP {counts[Outcome.SKIP]} / UNAVAILABLE {counts[Outcome.UNAVAILABLE]}"
    )
    if report.outcome is Outcome.FAIL:
        lines.append(
            "[XX] ratchet-truth: FAIL - a committed threshold regressed, drifted from its "
            "record, or disagrees with the configuration it guards."
        )
    elif report.outcome is Outcome.UNAVAILABLE:
        lines.append(
            "[??] ratchet-truth: UNAVAILABLE - a committed value could not be read. "
            "Absence of proof is not a pass (I-7)."
        )
    elif report.outcome is Outcome.SKIP:
        lines.append(
            "[--] ratchet-truth: SKIP - every clause holds, but at least one ratchet has no "
            "measurement behind it. A skip is not a pass (I-7)."
        )
    else:
        lines.append("[OK] ratchet-truth: every ratchet is monotone and agrees with its config.")
    return lines


def run(
    *,
    as_json: bool = False,
    check: bool = False,
    out: Path | None = None,
    apply: bool = False,
) -> int:
    if apply:
        try:
            for message in apply_improvements():
                print(message)
        except _Unavailable as exc:
            print(f"[??] ratchet-truth: {exc.detail}")
            return EXIT_UNAVAILABLE
    report = evaluate()
    if as_json:
        print(report.canonical_json())
    else:
        for line in format_report(report):
            print(line)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.canonical_json(), encoding="utf-8")
    return report.exit_code if check else EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synapse-ratchet-truth")
    parser.add_argument("--json", action="store_true", help="Emit the canonical JSON report.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 pass / 1 regression or disagreement / 2 unavailable-or-unmeasured.",
    )
    parser.add_argument("--out", type=Path, default=None, help="Persist the canonical report.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Operator step: raise each bound the tree has already improved on.",
    )
    args = parser.parse_args(argv)
    return run(as_json=args.json, check=args.check, out=args.out, apply=args.apply)


if __name__ == "__main__":
    sys.exit(main())
