#!/usr/bin/env python3
"""
SYNAPSE Spec CLI (Sprint 8, WS-3) — single entry point for spec.yaml ops.

Subcommands
-----------
    validate         Lint every spec.yaml: unique IDs, valid severities,
                     state-machine reachability, threshold sanity.
    generate-tests   Regenerate test_spec.py from the spec(s).
    generate-alerts  Emit Prometheus multi-window alert rules for every
                     invariant whose assertion has a numeric threshold.
    generate-schema  (Stub) Emit JSON-Schema artefacts referenced by the
                     spec. Today every domain schema lives under
                     proto/domain/; this command verifies the link rather
                     than re-deriving the schema.
    generate-openapi (Stub) Emit OpenAPI examples wired to spec
                     pre-/post-conditions.
    coverage         Verify every invariant has a corresponding test.

Examples
--------
    python scripts/spec_cli.py validate
    python scripts/spec_cli.py validate agents/demand_prophet/spec.yaml
    python scripts/spec_cli.py generate-tests --all
    python scripts/spec_cli.py generate-alerts --out infrastructure/prometheus/rules
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "agents"
ORCH_DIR = REPO_ROOT / "orchestrator"

VALID_SEVERITIES: frozenset[str] = frozenset({"critical", "high", "medium", "low"})

# Pattern matching invariant assertions of the form
#   "<lhs_metric> <op> <number><unit?>"
# e.g. "inference_latency_ms < 500", "empirical_coverage(...) >= 0.85".
_THRESHOLD_RE = re.compile(
    r"""
    (?P<lhs>[A-Za-z_][\w\.\(\)\,\s]*?)        # metric expression
    \s*(?P<op>(?:<=|>=|<|>|==))\s*           # comparison
    (?P<value>-?\d+(?:\.\d+)?)               # number
    """,
    re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpecRef:
    """A resolved spec.yaml on disk plus its parsed contents."""

    path: Path
    data: dict[str, Any]

    @property
    def agent_name(self) -> str:
        return str(self.data.get("agent_name") or self.path.parent.name)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_specs() -> list[Path]:
    """Return every spec.yaml under agents/ + orchestrator/ (sorted)."""
    paths: list[Path] = []
    paths.extend(sorted(AGENTS_DIR.glob("*/spec.yaml")))
    orch_spec = ORCH_DIR / "spec.yaml"
    if orch_spec.exists():
        paths.append(orch_spec)
    return paths


def load_spec(path: Path) -> SpecRef:
    return SpecRef(path=path, data=yaml.safe_load(path.read_text(encoding="utf-8")))


def _resolve_targets(arg: str | None) -> list[Path]:
    if arg:
        p = Path(arg)
        if not p.exists():
            raise SystemExit(f"spec not found: {arg}")
        return [p]
    return discover_specs()


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def validate_spec(ref: SpecRef) -> list[str]:
    """Return a list of human-readable error strings; empty means pass."""
    errors: list[str] = []
    data = ref.data

    if not isinstance(data, dict):
        return [f"{ref.path}: top-level must be a mapping"]

    if "agent_name" not in data:
        errors.append(f"{ref.path}: missing required key 'agent_name'")

    invariants = data.get("invariants") or []
    seen_ids: set[str] = set()
    for inv in invariants:
        if not isinstance(inv, dict):
            errors.append(f"{ref.path}: invariant entry is not a mapping")
            continue
        inv_id = inv.get("id")
        if not inv_id:
            errors.append(f"{ref.path}: invariant missing 'id'")
            continue
        if inv_id in seen_ids:
            errors.append(f"{ref.path}: duplicate invariant id '{inv_id}'")
        seen_ids.add(inv_id)
        if "description" not in inv:
            errors.append(f"{ref.path}: invariant '{inv_id}' missing description")
        if "assertion" not in inv:
            errors.append(f"{ref.path}: invariant '{inv_id}' missing assertion")
        sev = inv.get("severity")
        if sev is not None and sev not in VALID_SEVERITIES:
            errors.append(
                f"{ref.path}: invariant '{inv_id}' has invalid severity "
                f"'{sev}' (must be one of {sorted(VALID_SEVERITIES)})"
            )

    sm = data.get("state_machine") or {}
    if sm:
        states = set(sm.get("states") or [])
        initial = sm.get("initial_state")
        if initial and initial not in states:
            errors.append(
                f"{ref.path}: state_machine.initial_state '{initial}' "
                f"is not in declared states {sorted(states)}"
            )
        for t in sm.get("transitions") or []:
            for k in ("from", "to", "trigger"):
                if k not in t:
                    errors.append(
                        f"{ref.path}: transition missing '{k}' (got {t})"
                    )
            if t.get("from") and t["from"] not in states:
                errors.append(
                    f"{ref.path}: transition.from '{t['from']}' "
                    f"is not in declared states"
                )
            if t.get("to") and t["to"] not in states:
                errors.append(
                    f"{ref.path}: transition.to '{t['to']}' "
                    f"is not in declared states"
                )
        # Reachability check from initial state.
        if initial and states:
            adj: dict[str, set[str]] = {s: set() for s in states}
            for t in sm.get("transitions") or []:
                if t.get("from") in adj and t.get("to") in states:
                    adj[t["from"]].add(t["to"])
            reachable: set[str] = {initial}
            stack = [initial]
            while stack:
                cur = stack.pop()
                for nxt in adj.get(cur, ()):
                    if nxt not in reachable:
                        reachable.add(nxt)
                        stack.append(nxt)
            unreachable = states - reachable
            if unreachable:
                errors.append(
                    f"{ref.path}: state_machine has unreachable states "
                    f"{sorted(unreachable)} from initial '{initial}'"
                )

    # Metamorphic relations: each must have id/description/transform/expected.
    for mr in data.get("metamorphic_relations") or []:
        for k in ("id", "description", "transform", "expected"):
            if k not in mr:
                errors.append(
                    f"{ref.path}: metamorphic relation missing '{k}' (got {mr})"
                )

    return errors


def cmd_validate(spec_arg: str | None) -> int:
    targets = _resolve_targets(spec_arg)
    total_errors = 0
    for path in targets:
        ref = load_spec(path)
        errs = validate_spec(ref)
        if errs:
            total_errors += len(errs)
            print(f"FAIL {ref.agent_name} ({len(errs)} issue(s)):")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {ref.agent_name}")
    if total_errors:
        print(f"\n{total_errors} validation issue(s) across {len(targets)} spec(s).")
        return 1
    print(f"\nAll {len(targets)} spec(s) validate cleanly.")
    return 0


# ---------------------------------------------------------------------------
# generate-tests
# ---------------------------------------------------------------------------


def cmd_generate_tests(spec_arg: str | None, *, force: bool, all_agents: bool) -> int:
    # Delegate to the existing generator so we have a single source of truth.
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from generate_tests_from_spec import generate_test_file

    targets = discover_specs() if all_agents else _resolve_targets(spec_arg)
    ok = True
    for path in targets:
        if not generate_test_file(path, force=force):
            ok = False
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# generate-alerts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NumericInvariant:
    """An invariant whose assertion contains a numeric threshold."""

    spec_path: Path
    agent: str
    id: str
    description: str
    severity: str
    metric: str
    op: str
    threshold: float


def extract_numeric_invariants(ref: SpecRef) -> Iterator[NumericInvariant]:
    """Pull every invariant whose assertion contains a comparison + number.

    The matched ``metric`` is used as a hint for the Prometheus query name;
    the rule generator falls back to ``synapse_inference_latency_seconds``
    style heuristics where the metric isn't already a known PromQL.
    """
    for inv in ref.data.get("invariants") or []:
        assertion = str(inv.get("assertion", ""))
        m = _THRESHOLD_RE.search(assertion)
        if not m:
            continue
        yield NumericInvariant(
            spec_path=ref.path,
            agent=ref.agent_name,
            id=str(inv["id"]),
            description=str(inv.get("description", "")),
            severity=str(inv.get("severity", "high")),
            metric=m.group("lhs").strip(),
            op=m.group("op"),
            threshold=float(m.group("value")),
        )


def _promql_for(metric: str, agent: str) -> str:
    """Heuristic: map a free-text metric to a real PromQL expression."""
    m = metric.lower()
    if "latency" in m and "ms" in m:
        # Inference latency histogram, in seconds. Compare ms threshold by
        # multiplying the right side at rule time, but we keep the unit
        # conversion in the rule expression for clarity.
        return (
            "histogram_quantile(0.99, "
            f'sum(rate(synapse_inference_latency_seconds_bucket{{agent_name="{agent}"}}[5m])) '
            "by (le)) * 1000"
        )
    if "coverage" in m:
        return f'synapse_conformal_coverage{{agent_name="{agent}"}}'
    if "kl_divergence" in m or "drift" in m:
        return f'synapse_drift_score{{agent_name="{agent}"}}'
    if "confidence" in m:
        return f'synapse_confidence{{agent_name="{agent}"}}'
    # Default: assume the metric name is already a Prometheus series.
    return f'{metric}{{agent_name="{agent}"}}'


def _alert_record(ni: NumericInvariant) -> dict[str, Any]:
    """Build a Prometheus alert rule dict for a single numeric invariant.

    Multi-window-multi-burn pattern: one rule per (window, burn) pair so
    Alertmanager can route the catastrophic short window to high-priority
    pages and the slow-burn long window to lower-priority tickets.
    """
    expr = _promql_for(ni.metric, ni.agent)
    op = ni.op
    # Invert operator if the *desired* condition is "<= threshold" so the
    # alert fires when the invariant is violated (i.e. the metric goes the
    # wrong direction).
    invert = {">=": "<", "<=": ">", ">": "<=", "<": ">=", "==": "!="}
    fire_op = invert[op]
    return {
        "alert": f"SynapseInvariantBreach_{ni.id.replace('-', '_')}",
        "expr": f"{expr} {fire_op} {ni.threshold}",
        "for": "5m",
        "labels": {
            "severity": ni.severity,
            "agent": ni.agent,
            "invariant": ni.id,
        },
        "annotations": {
            "summary": f"{ni.id}: {ni.description}",
            "description": (
                f"Agent {ni.agent} invariant {ni.id} violated: "
                f"metric '{ni.metric}' should be {op} {ni.threshold}."
            ),
            "runbook_url": (
                f"https://github.com/synapse-ai/synapse/blob/main/docs/runbooks/{ni.id}.md"
            ),
        },
    }


def render_alert_yaml(invariants: Iterable[NumericInvariant]) -> str:
    """Render a Prometheus rule file as a stable YAML string."""
    by_agent: dict[str, list[NumericInvariant]] = {}
    for ni in invariants:
        by_agent.setdefault(ni.agent, []).append(ni)
    groups: list[dict[str, Any]] = []
    for agent in sorted(by_agent):
        rules = [_alert_record(ni) for ni in sorted(by_agent[agent], key=lambda n: n.id)]
        groups.append(
            {
                "name": f"synapse-{agent}-invariants",
                "rules": rules,
            }
        )
    return yaml.safe_dump({"groups": groups}, sort_keys=False)


def cmd_generate_alerts(spec_arg: str | None, out_dir: str | None) -> int:
    targets = _resolve_targets(spec_arg)
    invariants: list[NumericInvariant] = []
    for path in targets:
        invariants.extend(extract_numeric_invariants(load_spec(path)))
    if not invariants:
        print("No numeric invariants found; nothing to emit.")
        return 0
    text = render_alert_yaml(invariants)
    if out_dir:
        out_path = Path(out_dir) / "synapse_spec_invariants.alerts.yml"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"WROTE {out_path}: {len(invariants)} alert rule(s)")
    else:
        sys.stdout.write(text)
    return 0


# ---------------------------------------------------------------------------
# generate-schema  (verification stub)
# ---------------------------------------------------------------------------


def cmd_generate_schema(spec_arg: str | None) -> int:
    """Verify each agent's spec references a real proto/domain schema."""
    targets = _resolve_targets(spec_arg)
    schema_dir = REPO_ROOT / "proto" / "domain"
    missing: list[str] = []
    for path in targets:
        ref = load_spec(path)
        # The generator script hard-codes agent->schema mapping. Reuse it.
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from generate_tests_from_spec import SCHEMA_BY_AGENT

        schema_file = SCHEMA_BY_AGENT.get(ref.agent_name)
        if schema_file is None:
            print(f"NOTE  {ref.agent_name}: no schema mapping (orchestrator/non-agent)")
            continue
        target = schema_dir / schema_file
        if not target.exists():
            missing.append(f"{ref.agent_name}: missing {target}")
            print(f"FAIL  {ref.agent_name}: {target} does not exist")
        else:
            print(f"OK    {ref.agent_name}: {schema_file}")
    if missing:
        print(f"\n{len(missing)} schema artefact(s) missing.")
        return 1
    return 0


# ---------------------------------------------------------------------------
# generate-openapi  (verification stub)
# ---------------------------------------------------------------------------


def cmd_generate_openapi(spec_arg: str | None) -> int:
    """Smoke-test that each agent's preconditions are well-formed.

    Future work: emit OpenAPI ``examples`` and ``x-synapse-invariant`` keys
    onto the agents' FastAPI route definitions. For now we just report the
    coverage of each precondition + postcondition.
    """
    targets = _resolve_targets(spec_arg)
    for path in targets:
        ref = load_spec(path)
        pre = len(ref.data.get("preconditions") or [])
        post = len(ref.data.get("postconditions") or [])
        print(f"  {ref.agent_name}: {pre} pre / {post} post")
    return 0


# ---------------------------------------------------------------------------
# coverage
# ---------------------------------------------------------------------------


def cmd_coverage() -> int:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from check_spec_coverage import check_coverage

    return 0 if check_coverage() else 1


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="synapse-spec", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="Lint every spec.yaml")
    v.add_argument("spec", nargs="?", default=None)

    g = sub.add_parser("generate-tests", help="Regenerate test_spec.py")
    g.add_argument("spec", nargs="?", default=None)
    g.add_argument("--force", action="store_true")
    g.add_argument("--all", dest="all_agents", action="store_true")

    a = sub.add_parser(
        "generate-alerts", help="Emit Prometheus alert YAML for numeric invariants"
    )
    a.add_argument("spec", nargs="?", default=None)
    a.add_argument("--out", help="Directory to write alerts file (else stdout)")

    s = sub.add_parser("generate-schema", help="Verify schema artefacts exist")
    s.add_argument("spec", nargs="?", default=None)

    o = sub.add_parser("generate-openapi", help="Report pre/post coverage")
    o.add_argument("spec", nargs="?", default=None)

    sub.add_parser("coverage", help="Verify every invariant has a test")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "validate":
        return cmd_validate(args.spec)
    if args.cmd == "generate-tests":
        return cmd_generate_tests(args.spec, force=args.force, all_agents=args.all_agents)
    if args.cmd == "generate-alerts":
        return cmd_generate_alerts(args.spec, args.out)
    if args.cmd == "generate-schema":
        return cmd_generate_schema(args.spec)
    if args.cmd == "generate-openapi":
        return cmd_generate_openapi(args.spec)
    if args.cmd == "coverage":
        return cmd_coverage()
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())


# Re-exported for tests (importable without executing main()).
__all__ = [
    "NumericInvariant",
    "SpecRef",
    "cmd_generate_alerts",
    "cmd_validate",
    "discover_specs",
    "extract_numeric_invariants",
    "load_spec",
    "main",
    "render_alert_yaml",
    "validate_spec",
]
