#!/usr/bin/env python3
"""
SYNAPSE SLO -> Prometheus alert generator (Sprint 8, WS-4).

Reads ``infrastructure/observability/slos/*.slo.yaml`` (synapse-slo/v1
format) and emits Prometheus rule files implementing the Google SRE
workbook's multi-window-multi-burn-rate alerting pattern.

For each SLO with target ``T%`` (so error budget ``B = 1 - T/100``), each
``burn_rates`` entry produces ONE alert that fires only when *both* the
short and long window error rates exceed ``burn * B``. The two-window
form is what makes burn-rate alerts robust against single-spike noise:
the long window ensures sustained badness, the short window ensures the
operator hears about it within minutes.

Usage
-----
    python scripts/slo_to_alerts.py
        # Reads infrastructure/observability/slos/*.slo.yaml,
        # writes infrastructure/prometheus/rules/synapse_slo.alerts.yml.

    python scripts/slo_to_alerts.py path/to/single.slo.yaml --stdout
        # Emits the rules to stdout for inspection.
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SLO_DIR = REPO_ROOT / "infrastructure" / "observability" / "slos"
RULES_OUT = REPO_ROOT / "infrastructure" / "prometheus" / "rules" / "synapse_slo.alerts.yml"

VERSION = "synapse-slo/v1"


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BurnRate:
    severity: str
    long_window: str
    short_window: str
    burn: float


@dataclass(frozen=True)
class Slo:
    service: str
    name: str
    description: str
    target_sli: float  # percent, e.g. 99.5
    window_days: int
    metric: dict[str, Any]
    burn_rates: tuple[BurnRate, ...]
    labels: dict[str, str]

    @property
    def error_budget(self) -> float:
        """Allowed bad-event ratio. 99.5% target -> 0.005 budget."""
        return max(0.0, 1.0 - (self.target_sli / 100.0))


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_slo_file(path: Path) -> list[Slo]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level must be a mapping")
    if raw.get("version") != VERSION:
        raise ValueError(
            f"{path}: unsupported version {raw.get('version')!r}; "
            f"expected {VERSION!r}"
        )
    service = str(raw.get("service") or path.stem)
    common_labels = {str(k): str(v) for k, v in (raw.get("labels") or {}).items()}
    slos: list[Slo] = []
    for entry in raw.get("slos") or []:
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: slo entry must be a mapping")
        burn_rates = tuple(
            BurnRate(
                severity=str(b["severity"]),
                long_window=str(b["long_window"]),
                short_window=str(b["short_window"]),
                burn=float(b["burn"]),
            )
            for b in entry.get("burn_rates") or []
        )
        slos.append(
            Slo(
                service=service,
                name=str(entry["name"]),
                description=str(entry.get("description", "")),
                target_sli=float(entry["target_sli"]),
                window_days=int(entry.get("window_days", 28)),
                metric=dict(entry.get("metric") or {}),
                burn_rates=burn_rates,
                labels=common_labels,
            )
        )
    return slos


# ---------------------------------------------------------------------------
# Rule generation
# ---------------------------------------------------------------------------


def _label_selector(labels: dict[str, str]) -> str:
    """Render a PromQL ``{k="v", ...}`` selector with a stable key order."""
    if not labels:
        return ""
    pairs = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return "{" + pairs + "}"


def _bad_ratio_query(slo: Slo, window: str) -> str:
    """Return a PromQL expression for ``bad_events / total_events`` over ``window``."""
    metric = slo.metric
    mtype = metric.get("type")
    if mtype == "latency_bucket":
        bucket = metric["bucket_metric"]
        threshold = float(metric["threshold_seconds"])
        bucket_labels = dict(metric.get("labels") or {})
        below = dict(bucket_labels)
        below["le"] = f"{threshold}"
        total = dict(bucket_labels)
        total["le"] = "+Inf"
        return (
            f"1 - (\n"
            f"  sum(rate({bucket}{_label_selector(below)}[{window}]))\n"
            f"  /\n"
            f"  sum(rate({bucket}{_label_selector(total)}[{window}]))\n"
            f")"
        )
    if mtype == "availability_ratio":
        good = str(metric["good_query"]).strip().replace("{{.window}}", window)
        total = str(metric["total_query"]).strip().replace("{{.window}}", window)
        return f"1 - (\n  ({good})\n  /\n  ({total})\n)"
    raise ValueError(f"unsupported SLO metric type: {mtype!r}")


def _alert_for_burn(slo: Slo, br: BurnRate) -> dict[str, Any]:
    """Build a single multi-window-multi-burn alert rule."""
    threshold = br.burn * slo.error_budget
    long_q = _bad_ratio_query(slo, br.long_window)
    short_q = _bad_ratio_query(slo, br.short_window)
    expr = (
        f"(\n  {long_q}\n) > {threshold}\n"
        f"and\n"
        f"(\n  {short_q}\n) > {threshold}"
    )
    safe_name = slo.name.replace("-", "_")
    alert_name = f"Synapse_{safe_name}_BurnRate_{br.long_window}"
    labels = {
        "severity": br.severity,
        "service": slo.service,
        "slo": slo.name,
        "burn_window": br.long_window,
        **slo.labels,
    }
    annotations = {
        "summary": f"{slo.name} burning error budget {br.burn:.1f}x over {br.long_window}",
        "description": (
            f"{slo.description}\n"
            f"Target: {slo.target_sli}% over {slo.window_days}d "
            f"(error budget {slo.error_budget:.4f}). "
            f"Both {br.long_window} and {br.short_window} bad-event ratios "
            f"exceed {threshold:.4f} ({br.burn}x burn)."
        ),
        "runbook_url": (
            f"https://github.com/synapse-ai/synapse/blob/main/docs/runbooks/slo-{slo.name}.md"
        ),
    }
    return {
        "alert": alert_name,
        "expr": expr,
        "for": "2m",
        "labels": labels,
        "annotations": annotations,
    }


def render_rules_yaml(slos: Iterable[Slo]) -> str:
    """Render every SLO's burn-rate alerts as a single Prometheus rules YAML."""
    groups: list[dict[str, Any]] = []
    by_service: dict[str, list[Slo]] = {}
    for slo in slos:
        by_service.setdefault(slo.service, []).append(slo)
    for service in sorted(by_service):
        rules: list[dict[str, Any]] = []
        for slo in sorted(by_service[service], key=lambda s: s.name):
            for br in slo.burn_rates:
                rules.append(_alert_for_burn(slo, br))
        groups.append({"name": f"{service}-slo-burn", "rules": rules})
    return yaml.safe_dump({"groups": groups}, sort_keys=False, width=10000)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def discover_slo_files() -> list[Path]:
    return sorted(SLO_DIR.glob("*.slo.yaml"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="slo-to-alerts", description=__doc__)
    parser.add_argument(
        "slo",
        nargs="?",
        help="Path to a single SLO YAML; default: every file in infrastructure/observability/slos",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Emit to stdout instead of writing a rules file",
    )
    parser.add_argument(
        "--out",
        default=str(RULES_OUT),
        help=f"Output path (default: {RULES_OUT})",
    )
    args = parser.parse_args(argv)

    slo_files = [Path(args.slo)] if args.slo else discover_slo_files()
    if not slo_files:
        print("No SLO files found.", file=sys.stderr)
        return 1
    slos: list[Slo] = []
    for path in slo_files:
        slos.extend(load_slo_file(path))
    if not slos:
        print("No SLO entries to render.", file=sys.stderr)
        return 1
    text = render_rules_yaml(slos)
    if args.stdout:
        sys.stdout.write(text)
        return 0
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    rule_count = sum(len(slo.burn_rates) for slo in slos)
    print(f"WROTE {out_path}: {len(slos)} SLO(s), {rule_count} alert(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BurnRate",
    "Slo",
    "discover_slo_files",
    "load_slo_file",
    "main",
    "render_rules_yaml",
]
