"""SLO → Prometheus burn-rate rules generator (WS-7).

Reads ``infrastructure/observability/slos/*.slo.yaml`` (Pyrra/sloth-style) and
emits multi-window multi-burn-rate alert rules per the SRE Workbook chapter 5
recipe.

Two paired alerts per SLO:
  * Fast burn: 1h window AND 5m window both above 14.4× budget burn → page
  * Slow burn: 6h window AND 1h window both above 6× budget burn → ticket

The rules already shipped in
``infrastructure/prometheus/rules/orchestrator_burn.yml`` were hand-rolled;
this generator re-derives the same shape from the SLO YAMLs and makes the
chain enforceable: ``slo_to_rules.py --check`` fails CI if the YAMLs and
the rules drift.

Usage::

    python -m scripts.observability.slo_to_rules           # write rules
    python -m scripts.observability.slo_to_rules --check   # exit 1 on drift
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    print("PyYAML not installed; install with `pip install pyyaml`", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[2]
SLO_DIR = ROOT / "infrastructure" / "observability" / "slos"
OUT_FILE = ROOT / "infrastructure" / "prometheus" / "rules" / "orchestrator_burn.generated.yml"

# Multi-window multi-burn-rate (Google SRE Workbook ch5):
#   short_burn × short_window AND long_burn × long_window above threshold.
WINDOWS = [
    # (alert_suffix, long_window, short_window, multiplier, severity, for_clause)
    ("1h-5m", "1h", "5m", 14.4, "page", "2m"),
    ("6h-1h", "6h", "1h", 6.0, "ticket", "15m"),
]


def _render_query(query: str, window: str) -> str:
    """Substitute the SLO ``{{.window}}`` placeholder with a concrete window."""
    return query.replace("{{.window}}", window)


def _burn_threshold(objective: float, multiplier: float) -> float:
    """SLO 99.5 → error budget 0.005 → burn-rate threshold = 0.005 * multiplier."""
    budget = 1.0 - (objective / 100.0)
    return round(budget * multiplier, 5)


def _alert_for_slo(slo: dict[str, Any], slo_name: str, service: str) -> list[dict[str, Any]]:
    error_q = slo["sli"]["events"]["error_query"]
    total_q = slo["sli"]["events"]["total_query"]
    objective = float(slo["objective"])
    alerting_meta = slo.get("alerting", {})
    runbook = (
        alerting_meta.get("annotations", {}).get("runbook_url")
        or "https://github.com/Praneshrajan137/synapse/blob/main/docs/runbooks/README.md"
    )
    alerts: list[dict[str, Any]] = []
    for suffix, long_w, short_w, multiplier, severity, for_clause in WINDOWS:
        thr = _burn_threshold(objective, multiplier)
        long_expr = (
            f"(1 - ({_render_query(error_q, long_w)} / "
            f"{_render_query(total_q, long_w)})) > {thr:.5f}"
        )
        short_expr = (
            f"(1 - ({_render_query(error_q, short_w)} / "
            f"{_render_query(total_q, short_w)})) > {thr:.5f}"
        )
        # Mimic the existing hand-rolled file's whitespace conventions so the
        # generator output stays close to a clean diff vs. the committed file.
        expr = f"({long_expr}) and ({short_expr})"
        alerts.append(
            {
                "alert": f"{slo_name}-burn-{suffix}",
                "expr": expr,
                "for": for_clause,
                "labels": {
                    "severity": severity,
                    "slo": slo_name,
                    "service": service,
                },
                "annotations": {
                    "summary": f"{slo_name} burning at {multiplier:.1f}x over {long_w}/{short_w}",
                    "runbook_url": runbook,
                },
            }
        )
    return alerts


def generate() -> str:
    out: dict[str, Any] = {
        "groups": [{"name": "synapse-burn-rate", "interval": "30s", "rules": []}]
    }
    rules = out["groups"][0]["rules"]
    for path in sorted(SLO_DIR.glob("*.slo.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        service = doc.get("service", path.stem)
        for slo in doc.get("slos", []):
            name = slo["name"]
            rules.extend(_alert_for_slo(slo, name, service))
    # width=10_000 prevents PyYAML from wrapping the long Prometheus
    # expressions; sort_keys=False keeps the canonical alert/expr/for/labels
    # ordering which is what humans expect when scanning the diff.
    return yaml.safe_dump(out, sort_keys=False, default_flow_style=False, width=10_000)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if regenerating would change the committed file.",
    )
    args = p.parse_args()
    content = generate()
    if args.check:
        if not OUT_FILE.exists():
            print(f"FAIL: {OUT_FILE} missing; run without --check to create it.")
            return 1
        existing = OUT_FILE.read_text(encoding="utf-8")
        if existing.strip() != content.strip():
            print(
                "FAIL: generated rules differ from committed rules. "
                "Rerun `python -m scripts.observability.slo_to_rules` "
                "and commit the result."
            )
            return 1
        print("OK: generated rules match committed file.")
        return 0
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(content, encoding="utf-8")
    print(f"Wrote {OUT_FILE} ({len(content.splitlines())} lines).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
