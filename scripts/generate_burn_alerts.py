#!/usr/bin/env python
"""Generate Prometheus multi-window multi-burn-rate alert rules from SLO YAMLs.

WS-4 §2 — Each ``infrastructure/observability/slos/*.slo.yaml`` produces
two paired burn-rate alerts: a fast 1h/5m page-grade alert (14.4x burn)
and a slower 6h/1h ticket-grade alert (6x burn), following the Google
SRE workbook's multi-window pattern.

This generator is Python-only and produces output that ``promtool`` can
validate; we do not require the ``sloth`` binary to be present at CI
time. The output is deterministically sorted so the generated file is
diff-stable and can be byte-compared against the checked-in
``orchestrator_burn.yml``.

Usage::

    python scripts/generate_burn_alerts.py \
        --slos infrastructure/observability/slos \
        --out infrastructure/prometheus/rules/orchestrator_burn.yml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

WINDOW_PAIRS: list[tuple[str, str, float, str]] = [
    # (long_window, short_window, burn_rate_factor, severity)
    ("1h", "5m", 14.4, "page"),
    ("6h", "1h", 6.0, "ticket"),
]


def _render_query(query_template: str, window: str) -> str:
    return query_template.replace("{{.window}}", window).strip()


def _alert_for_slo(slo: dict[str, Any], slo_doc: dict[str, Any]) -> list[dict[str, Any]]:
    name = slo["name"]
    objective = float(slo["objective"]) / 100.0
    error_template = slo["sli"]["events"]["error_query"]
    total_template = slo["sli"]["events"]["total_query"]
    runbook_url = slo.get("alerting", {}).get("annotations", {}).get("runbook_url", "")
    service = slo_doc.get("service", "")

    rules: list[dict[str, Any]] = []
    for long_w, short_w, burn, severity in WINDOW_PAIRS:
        expr_long = (
            f"(1 - ({_render_query(error_template, long_w)} / "
            f"{_render_query(total_template, long_w)})) > "
            f"{burn * (1 - objective):.5f}"
        )
        expr_short = (
            f"(1 - ({_render_query(error_template, short_w)} / "
            f"{_render_query(total_template, short_w)})) > "
            f"{burn * (1 - objective):.5f}"
        )
        expr = f"({expr_long}) and ({expr_short})"
        rule: dict[str, Any] = {
            "alert": f"{name}-burn-{long_w}-{short_w}",
            "expr": expr,
            "for": "2m" if severity == "page" else "15m",
            "labels": {
                "severity": severity,
                "slo": name,
                "service": service,
            },
            "annotations": {
                "summary": f"{name} burning at {burn}x over {long_w}/{short_w}",
                "runbook_url": runbook_url,
            },
        }
        rules.append(rule)
    return rules


def _load_slos(slo_dir: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in sorted(slo_dir.glob("*.slo.yaml")):
        with path.open(encoding="utf-8") as fp:
            docs.append(yaml.safe_load(fp))
    return docs


def generate(slo_dir: Path) -> dict[str, Any]:
    rules: list[dict[str, Any]] = []
    for doc in _load_slos(slo_dir):
        for slo in doc.get("slos", []):
            rules.extend(_alert_for_slo(slo, doc))
    return {
        "groups": [
            {
                "name": "synapse-burn-rate",
                "interval": "30s",
                "rules": sorted(rules, key=lambda r: r["alert"]),
            }
        ]
    }


def _emit_yaml(payload: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)
    out_path.write_text(rendered, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--slos",
        type=Path,
        default=Path("infrastructure/observability/slos"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("infrastructure/prometheus/rules/orchestrator_burn.yml"),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the generated rules diverge from the file at --out.",
    )
    args = parser.parse_args(argv)

    payload = generate(args.slos)
    rendered = yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)

    if args.check:
        if not args.out.exists():
            print(f"missing {args.out}", file=sys.stderr)
            return 1
        existing = args.out.read_text(encoding="utf-8")
        if existing != rendered:
            print(
                "burn-rate rules out of sync — run scripts/generate_burn_alerts.py",
                file=sys.stderr,
            )
            print("--- expected (generated) ---")
            print(rendered[:2000])
            print("--- actual (on disk) ---")
            print(existing[:2000])
            return 1
        return 0

    _emit_yaml(payload, args.out)
    print(f"wrote {args.out} with {len(payload['groups'][0]['rules'])} rules")
    print(json.dumps({"rules": len(payload["groups"][0]["rules"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
