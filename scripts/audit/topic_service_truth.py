"""R4.7 - a topic recorded with real consumers must have a deployed consuming service.

purpose-achievement-audit R4 found two halves of one gap. Real operator orders have
reached ``synapse.orders.demand`` (``api/routers/orders.py``) since ADR-029 and
nothing turned them into features, because the consumer that would
(``data_fabric/feast/stream_materialization.py``) had no service in
``docker/docker-compose.gcp.yml`` until task 10.14 added one. And the gate that
holds the ``consumers`` / ``consumers_planned`` distinction -
``scripts/audit/topic_consumer_truth.py`` - was reachable from ``Makefile:22`` and
from nothing else: no workflow, no Check_Registry row, so its verdict could not
fail anything.

This module is the registry-facing half (task 10.14). It is deliberately thin:

  * The **source leg** stays owned by ``topic_consumer_truth`` and is consumed
    through that module's public ``run`` entry point. A second copy of the
    subscribe-site scan would be free to disagree with the first, so there isn't
    one.
  * The **deployment leg** is what this module adds, and it is what R4.7 actually
    asks for: a recorded consumer must resolve to a service in the deployed GCP
    compose file. A subscribe call site in a module that nothing deploys is code,
    not a consumer.

Honest scope, stated here so a PASS cannot be read as more than it is (I-7):

  * ``consumers_planned`` is never enforced. That field is the registry being
    truthful about intent; promoting it to a requirement would punish the honesty.
  * ``topic_consumer_truth.HONEST_ABSENCES`` - the consumers the repository
    documents as not-yet-built - are exempt from the deployment leg and are named,
    with their count, in every verdict detail. This gate proves nothing about
    those bindings and says so; a declared absence is a first-class state, never a
    pass.
  * The service a consumer resolves to is **derived** from that consumer's own
    source globs (``topic_consumer_truth.CONSUMER_LOCATIONS``), never from a
    second hand-maintained table. Every hand-maintained mirror of machine state in
    this repository has drifted at least once.

Run::

    python -m scripts.audit.topic_service_truth          # human output
    python -m scripts.audit.topic_service_truth --json   # machine JSON

Exit codes match the other gates: ``0`` pass, ``1`` fail, ``2`` unavailable - and
``2`` is non-passing. An unreadable compose file or an unexecutable sub-check
establishes nothing about the deployment, so it degrades rather than passing (I-7).
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from scripts.audit.topic_consumer_truth import CONSUMER_LOCATIONS, HONEST_ABSENCES

if TYPE_CHECKING:
    from collections.abc import Sequence

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
TOPICS_FILE: Final[Path] = ROOT / "infrastructure" / "kafka" / "topics.json"
COMPOSE_FILE: Final[Path] = ROOT / "docker" / "docker-compose.gcp.yml"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 1
EXIT_UNAVAILABLE: Final[int] = 2

#: How many unresolved bindings (or resolved examples) a one-line detail names
#: before it summarises the remainder. The detail is read in a registry row, not
#: in a report file.
_DETAIL_EXAMPLES: Final[int] = 3


class TopicRecord(BaseModel):
    """One row of ``infrastructure/kafka/topics.json``.

    Only the two consumer fields matter here, and the distinction between them is
    the whole point: ``consumers`` is enforced, ``consumers_planned`` is intent.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str
    consumers: tuple[str, ...] = ()
    consumers_planned: tuple[str, ...] = ()


class TopicRegistry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    topics: tuple[TopicRecord, ...] = ()


class ConsumerBinding(BaseModel):
    """One (topic, recorded consumer) pair and how it resolved against the stack."""

    model_config = ConfigDict(frozen=True)

    topic: str
    consumer: str
    #: Compose service names derived for this consumer, in the order tried.
    services_considered: tuple[str, ...]
    #: The first considered service present in the deployed compose file.
    resolved_service: str | None
    #: True when ``topic_consumer_truth`` documents this consumer as not-yet-built.
    declared_absence: bool


class SourceLeg(BaseModel):
    """``topic_consumer_truth``'s own verdict, carried rather than re-derived."""

    model_config = ConfigDict(frozen=True)

    exit_code: int
    topics_with_missing: tuple[str, ...]


class TopicServiceProbe(BaseModel):
    """The verdict. ``unavailable`` is distinct from ``ok`` and from ``fail``."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "fail", "unavailable"]
    detail: str
    bindings: tuple[ConsumerBinding, ...] = ()
    unresolved: tuple[ConsumerBinding, ...] = ()

    @property
    def exit_code(self) -> int:
        return {"ok": EXIT_PASS, "fail": EXIT_FAIL, "unavailable": EXIT_UNAVAILABLE}[self.status]


def _service_name(raw: str) -> str:
    """Registry/source spelling -> compose spelling (``_`` -> ``-``)."""
    return raw.replace("_", "-")


def candidate_services(consumer: str, globs: Sequence[str]) -> tuple[str, ...]:
    """Compose services that could host ``consumer``, derived from its source globs.

    ``agents/<name>/**`` yields ``<name>``; any other glob yields its first path
    segment (``orchestrator/**`` -> ``orchestrator``, ``api/routers/**`` -> ``api``,
    ``digital_twin/**`` -> ``digital-twin``). The consumer's own name is a candidate
    too, so a consumer named after its service (``stream_materialization`` ->
    ``stream-materialization``) resolves without anyone maintaining a table.
    """
    candidates: list[str] = [_service_name(consumer)]
    for glob in globs:
        parts = [p for p in glob.split("/") if p and p not in {"*", "**"}]
        if not parts:
            continue
        if parts[0] == "agents" and len(parts) >= 2:
            candidates.append(_service_name(parts[1]))
        else:
            candidates.append(_service_name(parts[0]))
    seen: dict[str, None] = {}
    for candidate in candidates:
        seen.setdefault(candidate, None)
    return tuple(seen)


def compose_services() -> tuple[str, ...] | None:
    """Service names declared in the deployed GCP compose file.

    ``None`` means the deployment could not be read - file missing, PyYAML absent,
    or YAML that does not parse. The caller maps that to ``unavailable`` rather
    than to an empty stack: an unreadable deployment proves nothing about it (I-7).
    """
    if not COMPOSE_FILE.is_file():
        return None
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        doc = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(doc, dict):
        return None
    services = doc.get("services")
    if not isinstance(services, dict):
        return None
    return tuple(sorted(str(name) for name in services))


def source_leg() -> SourceLeg | None:
    """Run ``topic_consumer_truth`` and carry its verdict.

    Called through its public ``run(as_json=True)``, whose payload goes to stdout -
    hence the capture. This is the registration the audit asked for: from here the
    check is reachable from the Check_Registry instead of from ``Makefile:22``
    alone. ``None`` means it could not be executed at all -> ``unavailable``.
    """
    try:
        from scripts.audit.topic_consumer_truth import run as run_source
    except ImportError:
        return None
    stream = io.StringIO()
    try:
        with contextlib.redirect_stdout(stream):
            code = run_source(as_json=True)
    except Exception:  # noqa: BLE001 - a sub-check that crashed is unavailable, not a pass
        return None
    try:
        payload = json.loads(stream.getvalue())
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    missing: list[str] = []
    truths = payload.get("truths")
    if isinstance(truths, list):
        for entry in truths:
            if isinstance(entry, dict) and entry.get("missing"):
                missing.append(str(entry.get("topic", "<unnamed>")))
    return SourceLeg(exit_code=int(code), topics_with_missing=tuple(missing))


def _summarise(items: Sequence[str]) -> str:
    """Name up to ``_DETAIL_EXAMPLES`` items, then count the rest."""
    head = list(items[:_DETAIL_EXAMPLES])
    rest = len(items) - len(head)
    joined = "; ".join(head)
    return f"{joined} (+{rest} more)" if rest > 0 else joined


def evaluate() -> TopicServiceProbe:
    """Both legs: recorded consumers exist in code AND run in the deployed stack."""
    try:
        registry = TopicRegistry.model_validate_json(TOPICS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        return TopicServiceProbe(status="unavailable", detail=f"topic registry unreadable: {exc}")

    services = compose_services()
    if services is None:
        return TopicServiceProbe(
            status="unavailable",
            detail=(
                f"deployed compose file unreadable ({COMPOSE_FILE.name}: missing, "
                "unparseable, or PyYAML not installed)"
            ),
        )

    source = source_leg()
    if source is None:
        return TopicServiceProbe(
            status="unavailable",
            detail="topic_consumer_truth could not be executed; its source leg is unproven",
        )

    bindings: list[ConsumerBinding] = []
    for topic in registry.topics:
        for consumer in topic.consumers:
            candidates = candidate_services(consumer, CONSUMER_LOCATIONS.get(consumer, ()))
            bindings.append(
                ConsumerBinding(
                    topic=topic.name,
                    consumer=consumer,
                    services_considered=candidates,
                    resolved_service=next((c for c in candidates if c in services), None),
                    # Exemption is applied BEFORE resolution on purpose. A declared
                    # absence resolving to some service it merely lives inside would
                    # overstate the stack: topic_consumer_truth records that no such
                    # consumer process exists, and this gate must not contradict it.
                    declared_absence=consumer in HONEST_ABSENCES,
                )
            )

    enforced = tuple(b for b in bindings if not b.declared_absence)
    unresolved = tuple(b for b in enforced if b.resolved_service is None)
    absences = tuple(sorted({b.consumer for b in bindings if b.declared_absence}))
    absence_note = (
        f"{len(bindings) - len(enforced)} declared-absence binding(s) exempt and unproven "
        f"({', '.join(absences)})"
        if absences
        else "no declared-absence bindings"
    )

    if unresolved:
        named = _summarise(
            [
                f"{b.topic} recorded consumer '{b.consumer}' has no deployed service "
                f"(considered: {', '.join(b.services_considered)})"
                for b in unresolved
            ]
        )
        return TopicServiceProbe(
            status="fail",
            detail=(
                f"{len(unresolved)} recorded consumer binding(s) with no consuming service "
                f"in the deployed stack: {named}"
            ),
            bindings=tuple(bindings),
            unresolved=unresolved,
        )

    if source.exit_code != EXIT_PASS:
        return TopicServiceProbe(
            status="fail",
            detail=(
                f"topic_consumer_truth exit {source.exit_code}: "
                f"{len(source.topics_with_missing)} topic(s) record a consumer with no "
                f"subscribe site: {_summarise(source.topics_with_missing)}"
            ),
            bindings=tuple(bindings),
        )

    resolved_examples = _summarise(
        [f"{b.topic} -> {b.consumer} -> {b.resolved_service}" for b in enforced]
    )
    return TopicServiceProbe(
        status="ok",
        detail=(
            f"{len(registry.topics)} topic(s), {len(enforced)} enforced binding(s) resolve "
            f"to a deployed service ({resolved_examples}); {absence_note}; "
            "consumers_planned not enforced (recorded intent)"
        ),
        bindings=tuple(bindings),
    )


def run(as_json: bool = False) -> int:
    """Print the verdict and return its exit code (``0`` / ``1`` / ``2``)."""
    probe = evaluate()
    if as_json:
        print(
            json.dumps(
                {
                    "detail": probe.detail,
                    "exit_code": probe.exit_code,
                    "status": probe.status,
                    "unresolved": [b.model_dump(mode="json") for b in probe.unresolved],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    else:
        symbol = {"ok": "[OK]", "fail": "[XX]", "unavailable": "[--]"}[probe.status]
        print(f"{symbol} topic->service truth: {probe.detail}")
    return probe.exit_code


__all__ = [
    "COMPOSE_FILE",
    "EXIT_FAIL",
    "EXIT_PASS",
    "EXIT_UNAVAILABLE",
    "TOPICS_FILE",
    "ConsumerBinding",
    "SourceLeg",
    "TopicRecord",
    "TopicRegistry",
    "TopicServiceProbe",
    "candidate_services",
    "compose_services",
    "evaluate",
    "run",
    "source_leg",
]


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv))
