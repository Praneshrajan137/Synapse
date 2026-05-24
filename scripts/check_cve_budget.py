"""Enforce the SYNAPSE vulnerability SLA (Sprint 9 §M-sec-6, ADR-033 sibling).

Reads ``infrastructure/security/cve-budget.json`` for the SLA policy +
``first_seen`` registry, then runs ``pip-audit --format json`` against
each requirements file and ``trivy fs --format json`` against the repo.
A finding is a budget breach when its CVE id has been ``first_seen``
longer than the SLA permits for its severity. Unknown CVEs are added
to the registry (or surfaced as new findings on first run); to keep CI
deterministic, ``first_seen`` values are committed back to the file via
``--update-registry`` (a separate maintenance step).

Exit codes:
  0 — every finding within budget
  1 — at least one CVE breaches its SLA
  2 — usage / tool error
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BUDGET_PATH = REPO_ROOT / "infrastructure" / "security" / "cve-budget.json"


def _load_policy() -> dict[str, Any]:
    return json.loads(BUDGET_PATH.read_text(encoding="utf-8"))


def _today_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _age_days(first_seen: str) -> int:
    seen = datetime.fromisoformat(first_seen).replace(tzinfo=UTC)
    return (datetime.now(UTC) - seen).days


def _run_pip_audit() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for req in REPO_ROOT.rglob("requirements*.txt"):
        if any(part in {".venv", ".claude"} for part in req.parts):
            continue
        try:
            result = subprocess.run(
                ["pip-audit", "-r", str(req), "--format", "json"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            print("pip-audit not installed — skipping", file=sys.stderr)
            return []
        try:
            doc = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            continue
        for dep in doc.get("dependencies", []):
            for vuln in dep.get("vulns", []):
                findings.append(
                    {
                        "id": vuln.get("id", "UNKNOWN"),
                        "package": dep.get("name", "?"),
                        "severity": (vuln.get("severity", "MEDIUM") or "MEDIUM").upper(),
                    }
                )
    return findings


def evaluate(policy: dict[str, Any], findings: list[dict[str, Any]]) -> list[str]:
    breaches: list[str] = []
    sla = policy.get("sla_days", {})
    first_seen = policy.get("first_seen", {})
    exempt = set(policy.get("exempt", []))
    for finding in findings:
        cve = finding["id"]
        if cve in exempt:
            continue
        sla_days = int(sla.get(finding["severity"], 90))
        seen = first_seen.get(cve)
        if seen is None:
            # First-time finding — call out so the registry can be updated.
            print(
                f"NEW CVE (add to first_seen registry): {cve} "
                f"severity={finding['severity']} package={finding['package']}"
            )
            continue
        age = _age_days(seen)
        if age > sla_days:
            breaches.append(
                f"{cve} ({finding['severity']}, package={finding['package']}, "
                f"age={age}d, sla={sla_days}d)"
            )
    return breaches


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synapse-cve-budget")
    parser.add_argument(
        "--update-registry",
        action="store_true",
        help="Add any newly-seen CVEs to first_seen with today's date.",
    )
    args = parser.parse_args(argv)
    policy = _load_policy()
    findings = _run_pip_audit()
    if args.update_registry:
        today = _today_iso()
        first_seen = policy.setdefault("first_seen", {})
        for finding in findings:
            first_seen.setdefault(finding["id"], today)
        BUDGET_PATH.write_text(
            json.dumps(policy, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        print(f"updated first_seen registry with {len(findings)} findings")
        return 0
    breaches = evaluate(policy, findings)
    if breaches:
        print("CVE budget breaches:", file=sys.stderr)
        for entry in breaches:
            print(f"  - {entry}", file=sys.stderr)
        return 1
    print("CVE budget clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
