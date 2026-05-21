"""
Kafka topic registry contract test (Sprint 7, WS-2).

Walks the AST of every Python file under ``api/``, ``agents/``,
``orchestrator/``, ``digital_twin/``, and ``data_fabric/`` and finds every
call that produces to Kafka. For each, extracts the topic argument
(literal string) and asserts it is registered in
``infrastructure/kafka/topics.json``.

Detects the following call shapes:
    confluent_kafka.Producer().produce("topic.name", ...)
    Producer(...).produce("topic.name", ...)
    SynapseProducer(...).produce(topic="topic.name", value=...)
    self._producer.produce("topic.name", ...)

When the topic argument is a *variable* (not a literal), the call is
recorded but skipped from the strict check; we only fail on literals that
miss the registry. The intention is to catch the *easy* class of bugs
(typos, freeze violations) without producing false positives on legit
runtime-resolved topic names.

Failure mode is human-readable:
    AssertionError: Producer call at agents/x/y.py:42 publishes to topic
    'synapse.orders.legacy', which is NOT registered in
    infrastructure/kafka/topics.json. Either register the topic (with an
    ADR for freeze-class topics) or correct the typo.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOPICS_FILE = REPO_ROOT / "infrastructure" / "kafka" / "topics.json"

SCAN_DIRS: tuple[str, ...] = (
    "api",
    "agents",
    "orchestrator",
    "digital_twin",
    "data_fabric",
    "packages",
)

# Producer-call attribute names we should inspect.
PRODUCE_ATTR_NAMES: frozenset[str] = frozenset({"produce"})


class ProduceCall(NamedTuple):
    file: str
    line: int
    topic: str | None  # None when the topic arg isn't a literal


def _registered_topics() -> set[str]:
    with TOPICS_FILE.open("r", encoding="utf-8") as fh:
        registry = json.load(fh)
    return {entry["name"] for entry in registry["topics"]}


def _extract_topic(call: ast.Call) -> str | None:
    """Return the topic literal from a ``.produce(...)`` call, or None."""
    # First positional arg
    if call.args:
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
        return None
    # Keyword arg ``topic=...``
    for kw in call.keywords:
        if kw.arg == "topic":
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                return kw.value.value
            return None
    return None


def _looks_like_kafka_producer_call(call: ast.Call) -> bool:
    """Heuristic: ``something.produce(...)`` where 'something' looks like a producer.

    We require an attribute access (``foo.produce(...)``) so we don't pick
    up unrelated functions named ``produce``. We don't try to resolve the
    type — file-scanned callers reach this code only via a fixture that
    skips false-positives.
    """
    func = call.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr not in PRODUCE_ATTR_NAMES:
        return False
    # The receiver name often signals intent. We accept any of:
    #   producer, _producer, self._producer, kafka_producer, app.state.producer
    receiver_name = _attr_root_name(func.value)
    return receiver_name is not None and (
        "producer" in receiver_name.lower() or "kafka" in receiver_name.lower()
    )


def _attr_root_name(node: ast.AST) -> str | None:
    """Walk down attribute chains to find the rooted Name."""
    cur = node
    while isinstance(cur, ast.Attribute):
        cur = cur.value
    if isinstance(cur, ast.Name):
        return cur.id
    if isinstance(cur, ast.Call):
        # Producer(...).produce(...) — root is the Call's func name
        if isinstance(cur.func, ast.Name):
            return cur.func.id
        if isinstance(cur.func, ast.Attribute):
            return cur.func.attr
    return None


def _scan_file(path: Path) -> list[ProduceCall]:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    found: list[ProduceCall] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _looks_like_kafka_producer_call(node):
            topic = _extract_topic(node)
            found.append(
                ProduceCall(file=str(path.relative_to(REPO_ROOT)), line=node.lineno, topic=topic)
            )
    return found


def _all_python_files() -> list[Path]:
    files: list[Path] = []
    for d in SCAN_DIRS:
        root = REPO_ROOT / d
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if any(part in {"tests", "training"} for part in path.parts):
                continue
            files.append(path)
    return files


def _all_produce_calls() -> list[ProduceCall]:
    return [
        call
        for path in _all_python_files()
        for call in _scan_file(path)
    ]


@pytest.mark.contract
def test_topics_json_loads() -> None:
    """Smoke check: the registry file is valid JSON with required fields."""
    assert TOPICS_FILE.exists(), f"missing {TOPICS_FILE}"
    with TOPICS_FILE.open("r", encoding="utf-8") as fh:
        registry = json.load(fh)
    assert "topics" in registry
    for entry in registry["topics"]:
        assert "name" in entry, entry
        assert "partitions" in entry, entry
        assert "retention_hours" in entry, entry
        assert "producer" in entry, entry


@pytest.mark.contract
def test_every_kafka_produce_targets_a_registered_topic() -> None:
    """No producer.produce() call may target an unregistered topic literal."""
    registered = _registered_topics()
    offending: list[ProduceCall] = []
    for call in _all_produce_calls():
        if call.topic is None:
            continue
        if call.topic not in registered:
            offending.append(call)
    if offending:
        details = "\n".join(
            f"  - {c.file}:{c.line} -> '{c.topic}'" for c in offending
        )
        msg = (
            "The following producer.produce(...) calls target topics not in "
            "infrastructure/kafka/topics.json. Either register the topic "
            "(with an ADR if it changes the freeze) or fix the typo:\n"
            f"{details}"
        )
        raise AssertionError(msg)


@pytest.mark.contract
def test_at_least_one_produce_call_was_scanned() -> None:
    """Sanity guard: if the scanner finds zero calls, the test is a no-op."""
    calls = _all_produce_calls()
    assert calls, (
        "Scanner found no producer.produce() calls anywhere; either the "
        "scanner regressed or the codebase no longer publishes to Kafka."
    )
