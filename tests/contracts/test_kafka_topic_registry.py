"""Kafka topic-registry contract test (WS-2 §7, ADR-029).

AST-walks the entire repository for ``.produce(`` calls and asserts that
every literal topic argument is present in ``infrastructure/kafka/topics.json``.
This is the mechanical guard that keeps code and registry in sync after the
freeze exception introduced by ADR-029.

Failure modes covered:
    - bare ``confluent_kafka.Producer().produce("synapse.foo.bar", ...)``
    - ``SynapseProducer().produce(topic="synapse.foo.bar", ...)``
    - keyword-only ``.produce(topic="synapse.foo.bar", value=...)``

Computed topics (variables, f-strings, function calls) are skipped — the
test is deliberately conservative; only string literals are checked.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOPICS_JSON = REPO_ROOT / "infrastructure" / "kafka" / "topics.json"
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "frontend",
    "dist",
    "build",
    ".claude",
    "__pycache__",
}


def _registered_topics() -> set[str]:
    data = json.loads(TOPICS_JSON.read_text(encoding="utf-8"))
    return {entry["name"] for entry in data["topics"]}


def _extract_topic_literal(call: ast.Call) -> str | None:
    if not call.args and not call.keywords:
        return None
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    for kw in call.keywords:
        if (
            kw.arg == "topic"
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)
        ):
            return kw.value.value
    return None


def _walk_python_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def _produce_topic_literals(path: Path) -> list[tuple[int, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        attr_name: str | None
        attr_name = func.attr if isinstance(func, ast.Attribute) else None
        if attr_name != "produce":
            continue
        topic = _extract_topic_literal(node)
        if topic is None:
            continue
        if not topic.startswith("synapse."):
            continue
        found.append((node.lineno, topic))
    return found


@pytest.mark.contract
def test_every_produced_topic_is_registered() -> None:
    registered = _registered_topics()
    offenders: list[str] = []
    for path in _walk_python_files():
        for lineno, topic in _produce_topic_literals(path):
            if topic not in registered:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno} → {topic}")
    assert not offenders, (
        "Unregistered Kafka topics found in producer calls. Register them in "
        "infrastructure/kafka/topics.json (with an ADR for any freeze exception):\n"
        + "\n".join(offenders)
    )


@pytest.mark.contract
def test_orders_demand_topic_present() -> None:
    """Guard against accidental removal of the ADR-029 freeze exception."""
    assert "synapse.orders.demand" in _registered_topics()
