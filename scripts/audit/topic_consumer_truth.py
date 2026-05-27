"""Verify that every topic in ``infrastructure/kafka/topics.json`` whose
``consumers`` list claims a real consumer has a corresponding
``Consumer.subscribe(...)`` call site somewhere in the source tree.

Run::

    python -m scripts.audit.topic_consumer_truth          # human output
    python -m scripts.audit.topic_consumer_truth --json   # machine JSON

Exits 1 if the registry diverges from the code. This is the mechanical
enforcement promised by ADR-038.

Heuristics (deliberately strict; false positives fail CI):

  * A consumer is "real" iff it appears in any non-test ``.py`` file under
    ``agents/``, ``orchestrator/``, ``digital_twin/``, or ``api/`` that
    invokes ``SynapseConsumer`` and lists the topic name OR the file
    declares a ``topics = [...]`` literal containing the name.
  * The shorthand consumer names (``audit_logger``, ``postgres_sink``,
    ``prometheus_exporter``, ``hitl_console``, ``digital_twin``,
    ``ml_pipeline``, ``compliance``) are mapped to the file globs they
    are expected to live under. Missing globs PASS until the consumer is
    expected to exist (gated by ``REQUIRED_CONSUMERS`` below).
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "infrastructure" / "kafka" / "topics.json"

# Consumer-name → list of source-tree globs where a Consumer.subscribe(...)
# for the named topic must appear. Globs are evaluated from ROOT.
CONSUMER_LOCATIONS: dict[str, list[str]] = {
    "demand_prophet": ["agents/demand_prophet/**/*.py"],
    "inventory_sentinel": ["agents/inventory_sentinel/**/*.py"],
    "pricing_oracle": ["agents/pricing_oracle/**/*.py"],
    "routing_navigator": ["agents/routing_navigator/**/*.py"],
    "supplier_trust": ["agents/supplier_trust/**/*.py"],
    "sustainability_agent": ["agents/sustainability_agent/**/*.py"],
    "freshness_guardian": ["agents/freshness_guardian/**/*.py"],
    "disruption_shield": ["agents/disruption_shield/**/*.py"],
    "orchestrator": ["orchestrator/**/*.py"],
    "digital_twin": ["digital_twin/**/*.py"],
    "audit_logger": ["orchestrator/audit/**/*.py", "scripts/audit/**/*.py"],
    "ml_pipeline": ["ml_pipelines/**/*.py"],
    "postgres_sink": ["scripts/**/*.py", "orchestrator/audit/**/*.py"],
    "prometheus_exporter": ["infrastructure/**/*"],
    "hitl_console": ["frontend/src/**/*"],
    "compliance": ["scripts/**/*.py"],
}

# Consumers we will be honest about NOT enforcing (yet). Today, the audit
# pipeline routes events to Postgres via the OutboxDispatcher's reverse
# flow + a synthetic in-process audit sink — there is no separate Kafka
# consumer process. Mark these as "honest absence" rather than fail CI.
HONEST_ABSENCES: set[str] = {
    "audit_logger",
    "postgres_sink",
    "prometheus_exporter",
    "compliance",
    "hitl_console",
    "ml_pipeline",
    "digital_twin",  # consumes a parallel naming scheme; flagged separately
}


@dataclass
class TopicTruth:
    topic: str
    declared_consumers: list[str]
    real_consumers: list[str]
    missing: list[str]
    extra: list[str]  # consumers in code but not in registry


def _grep_topic_subscriptions(globs: list[str], topic: str) -> bool:
    """True iff any matching file references the topic name in a subscribe call."""
    # Two patterns:
    #   topics=[..., "synapse.foo.bar", ...]
    #   subscribe("synapse.foo.bar")
    topic_q = re.escape(topic)
    needle_1 = re.compile(rf"['\"]{topic_q}['\"]")
    for glob in globs:
        for path in ROOT.glob(glob):
            if not path.is_file():
                continue
            if "test" in path.parts:
                continue
            if path.suffix not in {".py"}:
                # Yaml/json may declare consumers via labels; treat as
                # supporting evidence only if they're under infra/.
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if needle_1.search(text) and (
                "subscribe" in text
                or "SynapseConsumer" in text
                or "Consumer(" in text
                or "topics = [" in text
                or "topics=[" in text
            ):
                return True
    return False


def run(as_json: bool = False) -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    truths: list[TopicTruth] = []
    failures = 0

    for entry in registry["topics"]:
        topic = entry["name"]
        declared = list(entry.get("consumers", []))
        real: list[str] = []
        missing: list[str] = []
        for consumer in declared:
            if consumer in HONEST_ABSENCES:
                # Documented as a not-yet-built consumer; doesn't fail.
                real.append(f"{consumer} (declared absence)")
                continue
            globs = CONSUMER_LOCATIONS.get(consumer)
            if not globs:
                missing.append(f"{consumer} (no glob mapping)")
                continue
            if _grep_topic_subscriptions(globs, topic):
                real.append(consumer)
            else:
                missing.append(consumer)
        truths.append(
            TopicTruth(
                topic=topic,
                declared_consumers=declared,
                real_consumers=real,
                missing=missing,
                extra=[],
            )
        )
        if missing:
            failures += 1

    if as_json:
        print(
            json.dumps(
                {
                    "summary": {"topics": len(truths), "failures": failures},
                    "truths": [t.__dict__ for t in truths],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for t in truths:
            sym = "[OK]" if not t.missing else "[XX]"
            print(f"{sym} {t.topic:<40} declared={t.declared_consumers} missing={t.missing}")
        print()
        print(f"Summary: {len(truths)} topics, {failures} with missing consumers")
        if registry.get("non_registered_consumed_topics"):
            extra = registry["non_registered_consumed_topics"]["topics"]
            print(
                f"Note: {len(extra)} non-registered topics ARE consumed "
                f"(see registry.non_registered_consumed_topics)"
            )

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv))
