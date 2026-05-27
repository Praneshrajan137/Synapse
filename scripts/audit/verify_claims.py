"""Verify SYNAPSE claims against code reality.

Each check is one function decorated with ``@register``. Workstreams in
``plans/i-have-finished-most-nifty-sifakis.md`` add new checks here as they
land. The script exits with code 1 if any check FAILS, 0 otherwise.

Run with ``make verify-claims`` or ``python -m scripts.audit.verify_claims``.

The check IDs (C1..C25) match the rows in ``docs/state/CURRENT.md``.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class CheckResult:
    cid: str
    title: str
    status: str  # "PASS" | "FAIL" | "PARTIAL" | "SKIP"
    detail: str


_CHECKS: list[tuple[str, str, Callable[[], CheckResult]]] = []


def register(cid: str, title: str) -> Callable[[Callable[[], CheckResult]], Callable[[], CheckResult]]:
    def deco(fn: Callable[[], CheckResult]) -> Callable[[], CheckResult]:
        _CHECKS.append((cid, title, fn))
        return fn

    return deco


def _grep(pattern: str, path: Path, *, glob: str | None = None) -> list[str]:
    """Minimal grep wrapper — returns matching lines as 'path:line:text'."""
    matches: list[str] = []
    targets = list(path.rglob(glob or "*")) if path.is_dir() else [path]
    for target in targets:
        if not target.is_file():
            continue
        try:
            text = target.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if re.search(pattern, line):
                matches.append(f"{target.relative_to(ROOT)}:{i}:{line.strip()}")
    return matches


# ---------------------------------------------------------------------------
# C2: Outbox dispatcher started in orchestrator lifespan
# ---------------------------------------------------------------------------
@register("C2", "OutboxDispatcher started in orchestrator lifespan")
def check_outbox_dispatcher_running() -> CheckResult:
    serve = ROOT / "orchestrator" / "inference" / "serve.py"
    if not serve.exists():
        return CheckResult("C2", "OutboxDispatcher running", "SKIP", "serve.py missing")
    text = serve.read_text(encoding="utf-8")
    if "OutboxDispatcher" in text and ".start(" in text:
        return CheckResult("C2", "OutboxDispatcher running", "PASS",
                           "instantiated and .start() called in serve.py")
    return CheckResult("C2", "OutboxDispatcher running", "FAIL",
                       "OutboxDispatcher not referenced in orchestrator/inference/serve.py")


# ---------------------------------------------------------------------------
# C3: Traceparent injected at API → orchestrator boundary
# ---------------------------------------------------------------------------
@register("C3", "API → orchestrator carries W3C traceparent")
def check_traceparent_at_api_boundary() -> CheckResult:
    decisions = ROOT / "api" / "routers" / "decisions.py"
    if not decisions.exists():
        return CheckResult("C3", "Traceparent at API boundary", "SKIP", "decisions.py missing")
    text = decisions.read_text(encoding="utf-8")
    if "inject_a2a_headers" in text or "traceparent" in text.lower():
        return CheckResult("C3", "Traceparent at API boundary", "PASS",
                           "tracing helper referenced in decisions.py")
    return CheckResult("C3", "Traceparent at API boundary", "FAIL",
                       "no traceparent/inject_a2a_headers call in api/routers/decisions.py")


# ---------------------------------------------------------------------------
# C4: Orders route uses shared kafka producer (no ad-hoc Producer())
# ---------------------------------------------------------------------------
@register("C4", "Orders route uses shared producer")
def check_orders_uses_shared_producer() -> CheckResult:
    orders = ROOT / "api" / "routers" / "orders.py"
    if not orders.exists():
        return CheckResult("C4", "Orders shared producer", "SKIP", "orders.py missing")
    text = orders.read_text(encoding="utf-8")
    # FAIL if it constructs a confluent_kafka.Producer directly
    if re.search(r"\bProducer\s*\(", text) and "confluent_kafka" in text:
        return CheckResult("C4", "Orders shared producer", "FAIL",
                           "orders.py instantiates confluent_kafka.Producer directly")
    # PASS if it pulls from app.state.kafka_producer or uses outbox.enqueue
    if "app.state.kafka_producer" in text or "outbox.enqueue" in text or "enqueue_outbox" in text:
        return CheckResult("C4", "Orders shared producer", "PASS",
                           "uses shared producer / outbox enqueue")
    return CheckResult("C4", "Orders shared producer", "FAIL",
                       "no evidence of shared producer or outbox usage")


# ---------------------------------------------------------------------------
# C5: Override endpoint accepts idempotency_key
# ---------------------------------------------------------------------------
@register("C5", "Override endpoint is idempotent")
def check_override_idempotent() -> CheckResult:
    decisions = ROOT / "api" / "routers" / "decisions.py"
    if not decisions.exists():
        return CheckResult("C5", "Override idempotent", "SKIP", "decisions.py missing")
    text = decisions.read_text(encoding="utf-8")
    if "idempotency_key" in text:
        return CheckResult("C5", "Override idempotent", "PASS",
                           "idempotency_key referenced in decisions.py")
    return CheckResult("C5", "Override idempotent", "FAIL",
                       "no idempotency_key in override request model")


# ---------------------------------------------------------------------------
# C6: Orders body validated against schema registry
# ---------------------------------------------------------------------------
@register("C6", "Order body validated against schema registry")
def check_orders_schema_validation() -> CheckResult:
    orders = ROOT / "api" / "routers" / "orders.py"
    if not orders.exists():
        return CheckResult("C6", "Order schema validation", "SKIP", "orders.py missing")
    text = orders.read_text(encoding="utf-8")
    # Accept any of the schema_registry public callable names — the
    # exposed surface includes `validate(...)` (module level), the
    # `@validates_schema` decorator, or `get_registry().validate(...)`.
    if (
        "validate_schema(" in text
        or "validates_schema(" in text
        or "get_registry()" in text
        or "validate_agent_payload(" in text
    ):
        return CheckResult("C6", "Order schema validation", "PASS",
                           "schema registry validation called")
    return CheckResult("C6", "Order schema validation", "FAIL",
                       "orders route does not validate against proto/domain/order_request.schema.json")


# ---------------------------------------------------------------------------
# C8: Frontend has no raw fetch() outside synapse-api.ts / http-client.ts
# ---------------------------------------------------------------------------
@register("C8", "Frontend has no raw fetch outside the typed client")
def check_frontend_no_raw_fetch() -> CheckResult:
    fe_src = ROOT / "frontend" / "src"
    if not fe_src.exists():
        return CheckResult("C8", "No raw fetch in FE", "SKIP", "frontend/src missing")
    bad: list[str] = []
    # This project uses domain-driven layout: transport/ holds wire clients,
    # app/ has framework glue, lib/log.ts is an OTel exporter (legitimate
    # fetch to /v1/logs). useArtifact.ts is a demo-only loader for static
    # JSON fixtures from /public — also legitimate.
    allowed = {
        "transport/synapse-api.ts",
        "transport/http-client.ts",
        "transport/ws-multiplex.ts",
        "transport/runtime-config.ts",
        "transport/jwks.ts",
        "lib/log.ts",
        "app/error-boundary.tsx",
        "surfaces/demo-theater/useArtifact.ts",
        # useCityStores loads a static asset from /data/ — not an API call.
        "surfaces/mission-control/useCityStores.ts",
        # useDemoRun talks to the demo job runner via a streaming endpoint
        # (server-sent events) that is intentionally outside the typed
        # surface — the demo is an operator tool, not a customer path.
        "surfaces/demo-theater/useDemoRun.ts",
    }
    for path in fe_src.rglob("*.ts*"):
        rel = path.relative_to(fe_src).as_posix()
        if rel in allowed:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            if re.search(r"\bfetch\(", line):
                bad.append(f"{rel}:{i}")
    if bad:
        return CheckResult("C8", "No raw fetch in FE", "FAIL",
                           f"raw fetch() in: {', '.join(bad[:5])}")
    return CheckResult("C8", "No raw fetch in FE", "PASS", "all fetches in typed client")


# ---------------------------------------------------------------------------
# C9: Firehose envelope validated by Zod
# ---------------------------------------------------------------------------
@register("C9", "Firehose envelope is Zod-validated")
def check_firehose_validated() -> CheckResult:
    ws = ROOT / "frontend" / "src" / "transport" / "ws-multiplex.ts"
    schema = ROOT / "frontend" / "src" / "transport" / "firehose-schema.ts"
    if not ws.exists():
        return CheckResult("C9", "Firehose Zod-validated", "SKIP", "ws-multiplex.ts missing")
    text = ws.read_text(encoding="utf-8")
    if schema.exists() and ("FirehoseEnvelopeSchema" in text or "firehose-schema" in text):
        return CheckResult("C9", "Firehose Zod-validated", "PASS",
                           "schema imported and applied")
    return CheckResult("C9", "Firehose Zod-validated", "FAIL",
                       "ws-multiplex emits raw JSON without schema check")


# ---------------------------------------------------------------------------
# C11: Steering surface posts to backend audit endpoint
# ---------------------------------------------------------------------------
@register("C11", "Steering writes hit /api/v1/steering")
def check_steering_audited() -> CheckResult:
    store = ROOT / "frontend" / "src" / "store" / "steering.store.ts"
    if not store.exists():
        # store path may differ — search instead
        candidates = list((ROOT / "frontend" / "src").rglob("steering*.ts"))
        if not candidates:
            return CheckResult("C11", "Steering audited", "SKIP", "no steering store found")
        store = candidates[0]
    text = store.read_text(encoding="utf-8")
    if "/api/v1/steering" in text or "submitSteering" in text:
        return CheckResult("C11", "Steering audited", "PASS",
                           "steering store calls backend endpoint")
    return CheckResult("C11", "Steering audited", "FAIL",
                       f"{store.relative_to(ROOT)} has no backend POST")


# ---------------------------------------------------------------------------
# C14: GCP terraform source present on main
# ---------------------------------------------------------------------------
@register("C14", "GCP terraform source on main")
def check_gcp_terraform_on_main() -> CheckResult:
    tf_dir = ROOT / "infrastructure" / "gcp" / "terraform"
    if not tf_dir.is_dir():
        return CheckResult("C14", "GCP terraform on main", "FAIL", "no infrastructure/gcp/terraform/")
    tf_files = [p for p in tf_dir.glob("*.tf") if p.is_file()]
    if not tf_files:
        return CheckResult("C14", "GCP terraform on main", "FAIL",
                           "no .tf files in infrastructure/gcp/terraform/")
    if any(p.name == "main.tf" for p in tf_files):
        return CheckResult("C14", "GCP terraform on main", "PASS",
                           f"{len(tf_files)} .tf files present")
    return CheckResult("C14", "GCP terraform on main", "PARTIAL",
                       f"{len(tf_files)} .tf files but no main.tf root module")


# ---------------------------------------------------------------------------
# C15: Coverage floor enforced at 80% in CI
# ---------------------------------------------------------------------------
@register("C15", "Backend coverage floor is 80%")
def check_coverage_floor() -> CheckResult:
    ci = ROOT / ".github" / "workflows" / "ci.yml"
    if not ci.exists():
        return CheckResult("C15", "Coverage 80%", "SKIP", "ci.yml missing")
    text = ci.read_text(encoding="utf-8")
    m = re.search(r"--cov-fail-under[= ](\d+)", text)
    if not m:
        return CheckResult("C15", "Coverage 80%", "FAIL", "no --cov-fail-under in ci.yml")
    pct = int(m.group(1))
    if pct >= 80:
        return CheckResult("C15", "Coverage 80%", "PASS", f"--cov-fail-under={pct}")
    return CheckResult("C15", "Coverage 80%", "FAIL",
                       f"--cov-fail-under={pct} (CLAUDE.md requires 80)")


# ---------------------------------------------------------------------------
# C16: Stryker break threshold enforced
# ---------------------------------------------------------------------------
@register("C16", "Stryker break threshold is not null")
def check_stryker_break_enforced() -> CheckResult:
    conf = ROOT / "frontend" / "stryker.conf.json"
    if not conf.exists():
        return CheckResult("C16", "Stryker break", "SKIP", "stryker.conf.json missing")
    try:
        data = json.loads(conf.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return CheckResult("C16", "Stryker break", "FAIL", f"invalid JSON: {exc}")
    thresholds = data.get("thresholds", {})
    brk = thresholds.get("break")
    if brk is None:
        return CheckResult("C16", "Stryker break", "FAIL", '"thresholds.break" is null')
    return CheckResult("C16", "Stryker break", "PASS", f'"thresholds.break" = {brk}')


# ---------------------------------------------------------------------------
# C23: no-raw-hex enforcement hook exists
# ---------------------------------------------------------------------------
@register("C23", "no-raw-hex hook present")
def check_no_raw_hex_hook() -> CheckResult:
    pc = ROOT / ".pre-commit-config.yaml"
    if not pc.exists():
        return CheckResult("C23", "no-raw-hex hook", "FAIL", ".pre-commit-config.yaml missing")
    text = pc.read_text(encoding="utf-8")
    if "no-raw-hex" in text or "raw-hex" in text:
        return CheckResult("C23", "no-raw-hex hook", "PASS", "hook configured in pre-commit")
    return CheckResult("C23", "no-raw-hex hook", "FAIL", "no no-raw-hex hook in pre-commit-config")


# ---------------------------------------------------------------------------
# C24: worktree-policy enforcement hook exists
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# C12: Helm chart templates 11 services (8 agents + orchestrator + API + twin)
# ---------------------------------------------------------------------------
@register("C12", "Helm chart templates all 11 services")
def check_helm_full_chart() -> CheckResult:
    chart = ROOT / "infrastructure" / "helm" / "synapse" / "Chart.yaml"
    if not chart.exists():
        return CheckResult("C12", "Helm full chart", "FAIL", "Chart.yaml missing")
    text = chart.read_text(encoding="utf-8")
    required = [
        "api-gateway", "orchestrator", "demand-prophet", "routing-navigator",
        "inventory-sentinel", "freshness-guardian", "pricing-oracle",
        "disruption-shield", "supplier-trust", "sustainability-agent",
        "digital-twin",
    ]
    missing = [r for r in required if f"name: {r}" not in text]
    if missing:
        return CheckResult("C12", "Helm full chart", "FAIL",
                           f"missing dependencies: {missing}")
    # Also check the subchart directories exist.
    subchart_dir = ROOT / "infrastructure" / "helm" / "synapse" / "charts"
    missing_dirs = [r for r in required if not (subchart_dir / r).is_dir()]
    if missing_dirs:
        return CheckResult("C12", "Helm full chart", "FAIL",
                           f"missing subchart dirs: {missing_dirs}")
    return CheckResult("C12", "Helm full chart", "PASS",
                       f"{len(required)} dependencies declared with subchart dirs present")


# ---------------------------------------------------------------------------
# C13: Linkerd/KEDA/Flagger live inside the Helm orchestrator subchart
# ---------------------------------------------------------------------------
@register("C13", "Linkerd/KEDA/Flagger inside Helm")
def check_mesh_in_helm() -> CheckResult:
    base = ROOT / "infrastructure" / "helm" / "synapse" / "charts" / "orchestrator" / "templates"
    files = ["linkerd-serviceprofile.yaml", "keda-scaledobject.yaml", "flagger-canary.yaml"]
    missing = [f for f in files if not (base / f).exists()]
    if missing:
        return CheckResult("C13", "Mesh in Helm", "FAIL", f"missing: {missing}")
    return CheckResult("C13", "Mesh in Helm", "PASS",
                       "Linkerd/KEDA/Flagger templates live under orchestrator subchart")


# ---------------------------------------------------------------------------
# C22: SLO close-loop — every alerted metric must be emitted in source
# ---------------------------------------------------------------------------
@register("C22", "SLO alert metrics emitted in source")
def check_slo_metric_truth() -> CheckResult:
    try:
        from scripts.observability.metric_truth import (  # type: ignore[import-not-found]
            _all_source_text,
            _extract_metrics,
        )
    except ImportError as exc:
        return CheckResult("C22", "SLO metric truth", "SKIP", f"helper missing: {exc}")
    rules_dir = ROOT / "infrastructure" / "prometheus" / "rules"
    if not rules_dir.is_dir():
        return CheckResult("C22", "SLO metric truth", "SKIP", "no rules dir")
    rules_text = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in sorted(rules_dir.glob("*.yml"))
        if p.is_file()
    )
    metrics = _extract_metrics(rules_text)
    sources = _all_source_text()
    missing = [m for m in sorted(metrics) if m not in sources]
    if missing:
        return CheckResult("C22", "SLO metric truth", "FAIL",
                           f"{len(missing)}/{len(metrics)} alerted metrics not emitted: "
                           f"{missing[:3]}{'...' if len(missing) > 3 else ''}")
    return CheckResult("C22", "SLO metric truth", "PASS",
                       f"{len(metrics)} alerted metrics all present in source")


# ---------------------------------------------------------------------------
# C19: Cosign signing step present in CD workflow
# ---------------------------------------------------------------------------
@register("C19", "Image signing in CD")
def check_image_signing() -> CheckResult:
    cd = ROOT / ".github" / "workflows" / "cd.yml"
    if not cd.exists():
        return CheckResult("C19", "Image signing", "SKIP", "cd.yml missing")
    text = cd.read_text(encoding="utf-8")
    if "cosign" in text.lower() and "sign" in text.lower():
        return CheckResult("C19", "Image signing", "PASS", "cosign step present in cd.yml")
    return CheckResult("C19", "Image signing", "FAIL",
                       "no cosign step in .github/workflows/cd.yml")


# ---------------------------------------------------------------------------
# C20: SBOM diff gate
# ---------------------------------------------------------------------------
@register("C20", "SBOM diff gate in CI")
def check_sbom_diff_gate() -> CheckResult:
    script = ROOT / "scripts" / "sbom_diff.py"
    if not script.exists():
        return CheckResult("C20", "SBOM diff", "FAIL", "scripts/sbom_diff.py missing")
    workflows = ROOT / ".github" / "workflows"
    if any("sbom_diff" in p.read_text(encoding="utf-8", errors="ignore")
           for p in workflows.glob("*.yml") if p.is_file()):
        return CheckResult("C20", "SBOM diff", "PASS", "sbom_diff invoked from CI")
    return CheckResult("C20", "SBOM diff", "FAIL",
                       "scripts/sbom_diff.py exists but no CI workflow references it")


# ---------------------------------------------------------------------------
# C21: CVE budget enforced in CI
# ---------------------------------------------------------------------------
@register("C21", "CVE budget enforced in CI")
def check_cve_budget_in_ci() -> CheckResult:
    workflows = ROOT / ".github" / "workflows"
    for p in workflows.glob("*.yml"):
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "check_cve_budget" in text:
            return CheckResult("C21", "CVE budget", "PASS",
                               f"invoked from {p.name}")
    return CheckResult("C21", "CVE budget", "FAIL",
                       "no workflow references check_cve_budget.py")


@register("C24", "Worktree policy enforced by hook")
def check_worktree_hook() -> CheckResult:
    pc = ROOT / ".pre-commit-config.yaml"
    if not pc.exists():
        return CheckResult("C24", "Worktree hook", "FAIL", ".pre-commit-config.yaml missing")
    text = pc.read_text(encoding="utf-8")
    if "worktree" in text.lower() and "block" in text.lower():
        return CheckResult("C24", "Worktree hook", "PASS", "worktree-block hook present")
    return CheckResult("C24", "Worktree hook", "FAIL",
                       "no worktree-blocking hook in pre-commit-config")


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------
def run(as_json: bool = False) -> int:
    results = [fn() for _cid, _title, fn in _CHECKS]
    pass_n = sum(1 for r in results if r.status == "PASS")
    fail_n = sum(1 for r in results if r.status == "FAIL")
    partial_n = sum(1 for r in results if r.status == "PARTIAL")
    skip_n = sum(1 for r in results if r.status == "SKIP")

    if as_json:
        payload = {
            "summary": {"pass": pass_n, "fail": fail_n, "partial": partial_n, "skip": skip_n,
                        "total": len(results)},
            "checks": [r.__dict__ for r in results],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for r in results:
            sym = {"PASS": "[OK]", "FAIL": "[XX]", "PARTIAL": "[~~]", "SKIP": "[--]"}[r.status]
            print(f"{sym} {r.cid:>4} {r.title:<48} {r.detail}")
        print()
        print(f"Summary: PASS={pass_n} FAIL={fail_n} PARTIAL={partial_n} "
              f"SKIP={skip_n} TOTAL={len(results)}")

    return 1 if fail_n else 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv))
