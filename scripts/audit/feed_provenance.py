"""Make the SYNAPSE *world provenance* mechanically checkable (audit R4.2/R4.5/R4.8, AD-11).

The audit's Requirement 4 finding was that the closed autonomy loop had only ever run on
its own simulation, and that the honesty flag which should have said so
(``WorldState.is_synthetic``) was **pinned** ``True`` rather than derived. AD-11 makes the
flag derive from the active ``WorldSource``'s declared class. A declaration, though, is
just a claim: nothing stops a class called ``ExternalFeedSource`` from declaring
``EXTERNAL`` while its ``poll_arrivals`` unconditionally returns ``[]``. That is exactly
the state this repository was in before task 10.11, and it is what this gate exists to
make impossible to re-enter.

What it checks
--------------

For every ``WorldSource`` implementation in the production tree (a class that defines
``poll_arrivals``; the ``Protocol`` itself is not an implementation), it derives a class
from the **body** and compares it to the **declaration**:

* ``STUB`` — every ``return`` in ``poll_arrivals`` yields an empty list (or nothing). This
  is R4.8 verbatim: an unconditionally empty arrival list is a stub *regardless of what the
  class is called* and regardless of what ``provenance()`` returns.
* ``EXTERNAL`` — the body reaches an external-feed seam (a drain/poll/consume/fetch call).
* ``SEEDED`` — the body draws from a random generator and reaches no external seam.
* ``UNCLASSIFIED`` — neither. Reported as a violation rather than silently omitted, so no
  implementation can land in *neither* list (the totality discipline of design AD-5).

Three violations are fatal beyond a mere mismatch:

* ``seeded_fallback_in_feed`` — one ``poll_arrivals`` both reads a feed **and** draws from a
  generator. R4.5 forbids a configured-but-unreachable feed from advancing demand from a
  seeded generator; a body that can do both is that fallback, whether or not it is reached
  today.
* ``seeded_fallback_reachable`` — a feed-reading class references ``SimWorldSource`` or the
  ``random`` module anywhere in its body. The same rule, one scope wider.
* ``undeclared_provenance`` — an implementation with no constant ``provenance()``. An
  undeclared source cannot derive ``is_synthetic``, so it must not exist.

And the headline the requirement cares about: ``externally_driven`` is true only when some
implementation's **body** derives ``EXTERNAL``. A repository whose only feed class is a stub
reports ``externally_driven: false``, so CI can never report the loop as externally driven
on the strength of a class name (R4.8).

Run::

    python -m scripts.audit.feed_provenance            # human table
    python -m scripts.audit.feed_provenance --json     # machine JSON
    python -m scripts.audit.feed_provenance --check    # exit 1 on any violation
    python -m scripts.audit.feed_provenance --external-decisions 12   # with DB evidence

``--external-decisions`` is the count of ``decision_data_provenance`` rows carrying
``source_class = 'EXTERNAL'``, supplied by the job that has the database in front of it. It
defaults to zero, so a static run reports ``externally_driven: no`` rather than inferring
from a class that a decision was ever taken on real data.

ASCII-only output, ``encoding='utf-8'`` on every read (E-S13-07), stdlib only (I-1).
"""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: Production roots scanned for implementations. Test trees are excluded on purpose: a
#: fixture that returns ``[]`` to simulate an unreachable feed is a legitimate fake, and
#: failing the gate on it would punish the very tests that prove the degradation path.
#: The obligation R4.8 places is on what the *system* ships.
SCAN_ROOTS: tuple[str, ...] = (
    "packages",
    "digital_twin",
    "orchestrator",
    "agents",
    "api",
    "data_fabric",
    "uplift",
    "scripts",
)

_SKIP_DIR_PARTS = frozenset(
    {"tests", "test", "__pycache__", ".venv", "venv", "node_modules", "site-packages"}
)

#: The method that makes a class a ``WorldSource`` implementation.
POLL_METHOD = "poll_arrivals"
PROVENANCE_METHOD = "provenance"

#: Substrings that mark a call as reaching an external feed. Deliberately behavioural
#: (what the body *does*) rather than nominal (what the class is *called*).
_FEED_TOKENS: tuple[str, ...] = (
    "drain",
    "consume",
    "reachable_topics",
    "kafka",
    "fetch",
    "subscribe",
    "read_records",
    "poll_records",
)

#: Substrings that mark a body as drawing from a generator.
_RNG_TOKENS: tuple[str, ...] = ("_rng", "random", "poisson", "default_rng", "seed")

#: Substrings that mark a *class* as holding a seeded generator it could fall back to.
#: Narrower than :data:`_RNG_TOKENS` because this is checked over the whole class body,
#: where a token like "seed" appears innocently (a ``seed`` argument threaded through).
_FALLBACK_TOKENS: tuple[str, ...] = ("simworldsource", "default_rng", "_rng")

SEEDED = "SEEDED"
EXTERNAL = "EXTERNAL"
STUB = "STUB"
UNCLASSIFIED = "UNCLASSIFIED"

#: Mirrors ``orchestrator.audit.models.SOURCE_CLASSES`` and the migration's CHECK
#: constraint. A fourth declared class is a violation, not a new category.
DECLARABLE: tuple[str, ...] = (SEEDED, EXTERNAL, STUB)


@dataclass
class Violation:
    file: str
    line: int
    kind: str
    detail: str


@dataclass
class SourceReport:
    """One classified ``WorldSource`` implementation."""

    file: str
    line: int
    class_name: str
    declared: str | None
    derived: str
    evidence: str
    violations: list[Violation] = field(default_factory=list)


# ── AST helpers ─────────────────────────────────────────────────────────────


def _is_protocol(node: ast.ClassDef) -> bool:
    """Whether the class is the ``WorldSource`` Protocol rather than an implementation."""
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "Protocol":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "Protocol":
            return True
        if isinstance(base, ast.Subscript):  # Protocol[T]
            inner = base.value
            if isinstance(inner, ast.Name) and inner.id == "Protocol":
                return True
    return False


def _method(node: ast.ClassDef, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name:
            return item
    return None


def _is_empty_arrivals(value: ast.expr | None) -> bool:
    """Whether a ``return`` value can only be an empty arrival list."""
    if value is None:
        return True
    if isinstance(value, ast.List) and not value.elts:
        return True
    if isinstance(value, ast.Constant) and value.value is None:
        return True
    if isinstance(value, ast.Call):  # list()
        func = value.func
        if isinstance(func, ast.Name) and func.id == "list" and not value.args:
            return True
    return False


def _returns_unconditionally_empty(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """R4.8: every return path yields an empty list, and nothing is yielded.

    A body with no ``return`` at all (``...``, a bare log, ``pass``) also qualifies: it
    produces no arrivals either. This is what makes the check independent of naming - the
    pre-10.11 ``ExternalFeedSource``, whose body logged ``external_feed_not_wired`` and
    returned ``[]``, is a ``STUB`` under this rule however it is labelled.
    """
    for node in ast.walk(fn):
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            return False
        if isinstance(node, ast.Return) and not _is_empty_arrivals(node.value):
            return False
    return True


def _names_in(fn: ast.AST) -> set[str]:
    """Every identifier-ish token in a subtree: names, attributes, and call targets."""
    found: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
    return found


def _matches(tokens: set[str], needles: tuple[str, ...]) -> str | None:
    """First ``token`` containing one of ``needles``, else ``None``."""
    for token in sorted(tokens):
        lowered = token.lower()
        for needle in needles:
            if needle in lowered:
                return token
    return None


def _declared_provenance(node: ast.ClassDef) -> tuple[str | None, list[str]]:
    """The constant class ``provenance()`` declares, plus every distinct value it returns."""
    fn = _method(node, PROVENANCE_METHOD)
    if fn is None:
        return None, []
    values: list[str] = []
    for sub in ast.walk(fn):
        if not isinstance(sub, ast.Return) or sub.value is None:
            continue
        value = sub.value
        if isinstance(value, ast.Attribute):
            values.append(value.attr)
        elif isinstance(value, ast.Constant) and isinstance(value.value, str):
            values.append(value.value)
    unique = sorted(set(values))
    return (unique[0] if len(unique) == 1 else None), unique


# ── classification ──────────────────────────────────────────────────────────


def classify(rel: str, node: ast.ClassDef) -> SourceReport:
    """Classify one implementation from its body, then compare with its declaration."""
    poll = _method(node, POLL_METHOD)
    assert poll is not None  # callers only pass classes that define it
    declared, declared_values = _declared_provenance(node)
    poll_tokens = _names_in(poll)
    class_tokens = _names_in(node)
    feed_hit = _matches(poll_tokens, _FEED_TOKENS)
    rng_hit = _matches(poll_tokens, _RNG_TOKENS)
    violations: list[Violation] = []

    if _returns_unconditionally_empty(poll):
        derived, evidence = STUB, f"{POLL_METHOD} returns an empty arrival list on every path"
    elif feed_hit and rng_hit:
        derived = UNCLASSIFIED
        evidence = f"reads a feed via '{feed_hit}' AND draws from '{rng_hit}'"
        violations.append(
            Violation(
                rel,
                poll.lineno,
                "seeded_fallback_in_feed",
                f"{node.name}.{POLL_METHOD} both reads a feed ('{feed_hit}') and draws from "
                f"a generator ('{rng_hit}'); R4.5 forbids advancing demand from a seeded "
                f"generator when a configured feed is unreachable",
            )
        )
    elif feed_hit:
        derived, evidence = EXTERNAL, f"{POLL_METHOD} reads a feed via '{feed_hit}'"
        fallback = _matches(class_tokens, _FALLBACK_TOKENS)
        if fallback:
            violations.append(
                Violation(
                    rel,
                    node.lineno,
                    "seeded_fallback_reachable",
                    f"{node.name} references '{fallback}': a feed source must hold no seeded "
                    f"generator to fall back to (R4.5)",
                )
            )
    elif rng_hit:
        derived, evidence = SEEDED, f"{POLL_METHOD} draws from '{rng_hit}'"
    else:
        derived = UNCLASSIFIED
        evidence = f"{POLL_METHOD} reaches no feed seam and draws from no generator"
        violations.append(
            Violation(
                rel,
                poll.lineno,
                "unclassifiable_source",
                f"{node.name}.{POLL_METHOD} could not be classified as seeded, external, or "
                f"stub; every implementation must be classifiable (R4.8)",
            )
        )

    if declared is None:
        violations.append(
            Violation(
                rel,
                node.lineno,
                "undeclared_provenance",
                f"{node.name} declares no constant {PROVENANCE_METHOD}()"
                + (f" (returns {declared_values})" if declared_values else ""),
            )
        )
    elif declared not in DECLARABLE:
        violations.append(
            Violation(
                rel,
                node.lineno,
                "unknown_declared_class",
                f"{node.name} declares '{declared}', not one of {list(DECLARABLE)}",
            )
        )
    elif declared != derived:
        violations.append(
            Violation(
                rel,
                node.lineno,
                "declaration_contradicts_body",
                f"{node.name} declares '{declared}' but its body is '{derived}' ({evidence})",
            )
        )

    return SourceReport(
        file=rel,
        line=node.lineno,
        class_name=node.name,
        declared=declared,
        derived=derived,
        evidence=evidence,
        violations=violations,
    )


def _candidate_files() -> list[Path]:
    """Production ``.py`` files that mention ``poll_arrivals`` (cheap pre-filter)."""
    files: list[Path] = []
    for root in SCAN_ROOTS:
        base = ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            parts = set(path.parts)
            if parts & _SKIP_DIR_PARTS:
                continue
            if path.name.startswith("test_") or path.name == "conftest.py":
                continue
            try:
                if POLL_METHOD in path.read_text(encoding="utf-8"):
                    files.append(path)
            except OSError:  # pragma: no cover - unreadable file is reported by collect()
                files.append(path)
    return files


def collect() -> tuple[list[SourceReport], list[Violation]]:
    """Classify every production implementation. Returns ``(reports, scan_errors)``."""
    reports: list[SourceReport] = []
    errors: list[Violation] = []
    for path in _candidate_files():
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:
            errors.append(Violation(rel, 0, "parse_error", f"could not parse: {exc}"))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or _is_protocol(node):
                continue
            if _method(node, POLL_METHOD) is None:
                continue
            reports.append(classify(rel, node))
    return reports, errors


def external_implementation_present(reports: list[SourceReport]) -> bool:
    """Whether any implementation's **body** reads an external feed, violation-free.

    The R4.8 half this gate can settle statically: a stub can never make this true, so no
    amount of naming makes a shipped tree feed-capable.
    """
    return any(r.derived == EXTERNAL and not r.violations for r in reports)


def externally_driven(reports: list[SourceReport], external_decisions: int) -> bool:
    """Whether the **loop** ran on external data - capability AND evidence.

    Deliberately two-part, and deliberately false by default. A body-verified
    ``EXTERNAL`` implementation proves the loop *can* be externally driven; it proves
    nothing about whether it *was*. The evidence is rows in ``decision_data_provenance``
    (AD-10) carrying ``source_class = 'EXTERNAL'``, which only a job with the database in
    front of it can count - so this gate takes that count as an argument and defaults it to
    zero. A static run therefore reports ``externally_driven: no``, which is the honest
    reading of "nobody measured it" (I-7: absence of proof is not a pass), and exactly the
    over-claim R4.8 forbids CI from making.
    """
    return external_implementation_present(reports) and external_decisions > 0


def run(*, as_json: bool = False, check: bool = False, external_decisions: int = 0) -> int:
    reports, errors = collect()
    violations = [v for r in reports for v in r.violations] + errors
    classes = (*DECLARABLE, UNCLASSIFIED)
    counts = {cls: sum(1 for r in reports if r.derived == cls) for cls in classes}
    capable = external_implementation_present(reports)
    driven = externally_driven(reports, external_decisions)

    if as_json:
        payload = {
            "summary": {
                "implementations": len(reports),
                "counts": counts,
                "external_implementation_present": capable,
                "external_decisions_recorded": external_decisions,
                "externally_driven": driven,
                "total_violations": len(violations),
            },
            "sources": [asdict(r) for r in reports],
            "scan_errors": [asdict(v) for v in errors],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for r in reports:
            mark = "[XX]" if r.violations else "[OK]"
            print(f"{mark} {r.file}:{r.line}  {r.class_name}")
            print(f"        declared={r.declared or '-':<13} derived={r.derived:<13} {r.evidence}")
            for v in r.violations:
                print(f"        {v.kind:<30} {v.detail}")
        for v in errors:
            print(f"[XX] {v.file}:{v.line}  {v.kind:<30} {v.detail}")
        print()
        summary = ", ".join(f"{cls}={counts[cls]}" for cls in classes)
        print(f"Feed-provenance audit: {len(reports)} implementation(s) -- {summary}")
        print(f"External implementation present: {'yes' if capable else 'no'}")
        print(f"Decisions recorded from an external source: {external_decisions}")
        print(f"Loop externally driven: {'yes' if driven else 'no'}")
        print(f"Violations: {len(violations)}")

    if check:
        return 1 if violations else 0
    return 0


def _external_decisions_arg(argv: list[str]) -> int:
    """Parse ``--external-decisions N``; anything unparseable counts as no evidence.

    Supplied by the job that can read ``decision_data_provenance``. A malformed value is
    read as zero rather than trusted, so a typo cannot promote the loop to
    externally driven.
    """
    flag = "--external-decisions"
    for index, arg in enumerate(argv):
        raw: str | None = None
        if arg.startswith(f"{flag}="):
            raw = arg.split("=", 1)[1]
        elif arg == flag and index + 1 < len(argv):
            raw = argv[index + 1]
        if raw is None:
            continue
        try:
            return max(0, int(raw))
        except ValueError:
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(
        run(
            as_json="--json" in sys.argv,
            check="--check" in sys.argv,
            external_decisions=_external_decisions_arg(sys.argv[1:]),
        )
    )
