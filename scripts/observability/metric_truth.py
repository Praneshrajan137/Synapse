"""Verify that every metric referenced by an alert rule is actually defined
somewhere in the source tree (WS-7).

Walks ``infrastructure/prometheus/rules/*.yml``, extracts metric names from
the alert ``expr`` fields, and asserts each name appears in at least one
Python source file under ``orchestrator/``, ``agents/``, ``api/``,
``packages/``, or ``digital_twin/``.

This is the cheap, mechanical version of the "metrics emitted = metrics
alerted" invariant — it cannot catch a metric defined but never `.inc()`'d,
but it does catch the common drift case: an alert that references a metric
nobody emits any more.

Run::

    python -m scripts.observability.metric_truth          # human output
    python -m scripts.observability.metric_truth --json   # CI ingestion
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES_DIR = ROOT / "infrastructure" / "prometheus" / "rules"
SOURCE_GLOBS = [
    "orchestrator/**/*.py",
    "agents/**/*.py",
    "api/**/*.py",
    "packages/**/*.py",
    "digital_twin/**/*.py",
]

# Match `synapse_*` metric names — the convention in this repo. Anything
# that doesn't start with `synapse_` is an upstream metric (Prometheus
# default, FastAPI instrumentator, KEDA, etc.) and is exempt.
METRIC_RE = re.compile(r"\b(synapse_[a-zA-Z0-9_]+)\b")
SUFFIX_STRIP = ("_total", "_count", "_sum", "_bucket")


def _all_source_text() -> str:
    chunks: list[str] = []
    for glob in SOURCE_GLOBS:
        for path in ROOT.glob(glob):
            if not path.is_file():
                continue
            try:
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
    return "\n".join(chunks)


def _extract_metrics(rules_text: str) -> set[str]:
    found = set(METRIC_RE.findall(rules_text))
    out: set[str] = set()
    for m in found:
        for suf in SUFFIX_STRIP:
            if m.endswith(suf):
                out.add(m[: -len(suf)])
                break
        else:
            out.add(m)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    rules_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(RULES_DIR.glob("*.yml"))
        if path.is_file()
    )
    metrics = _extract_metrics(rules_text)
    sources = _all_source_text()

    missing: list[str] = []
    present: list[str] = []
    for m in sorted(metrics):
        if m in sources:
            present.append(m)
        else:
            missing.append(m)

    if args.json:
        print(
            json.dumps(
                {
                    "summary": {
                        "total": len(metrics),
                        "present": len(present),
                        "missing": len(missing),
                    },
                    "missing": missing,
                    "present": present,
                },
                indent=2,
            )
        )
    else:
        print(f"Metrics referenced by alert rules: {len(metrics)}")
        print(f"  present in source: {len(present)}")
        print(f"  missing from source: {len(missing)}")
        for m in missing:
            print(f"    - {m}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
