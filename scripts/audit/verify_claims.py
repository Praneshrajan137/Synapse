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


def register(
    cid: str, title: str
) -> Callable[[Callable[[], CheckResult]], Callable[[], CheckResult]]:
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
        return CheckResult(
            "C2", "OutboxDispatcher running", "PASS", "instantiated and .start() called in serve.py"
        )
    return CheckResult(
        "C2",
        "OutboxDispatcher running",
        "FAIL",
        "OutboxDispatcher not referenced in orchestrator/inference/serve.py",
    )


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
        return CheckResult(
            "C3", "Traceparent at API boundary", "PASS", "tracing helper referenced in decisions.py"
        )
    return CheckResult(
        "C3",
        "Traceparent at API boundary",
        "FAIL",
        "no traceparent/inject_a2a_headers call in api/routers/decisions.py",
    )


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
        return CheckResult(
            "C4",
            "Orders shared producer",
            "FAIL",
            "orders.py instantiates confluent_kafka.Producer directly",
        )
    # PASS if it pulls from app.state.kafka_producer or uses outbox.enqueue
    if "app.state.kafka_producer" in text or "outbox.enqueue" in text or "enqueue_outbox" in text:
        return CheckResult(
            "C4", "Orders shared producer", "PASS", "uses shared producer / outbox enqueue"
        )
    return CheckResult(
        "C4", "Orders shared producer", "FAIL", "no evidence of shared producer or outbox usage"
    )


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
        return CheckResult(
            "C5", "Override idempotent", "PASS", "idempotency_key referenced in decisions.py"
        )
    return CheckResult(
        "C5", "Override idempotent", "FAIL", "no idempotency_key in override request model"
    )


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
        return CheckResult(
            "C6", "Order schema validation", "PASS", "schema registry validation called"
        )
    return CheckResult(
        "C6",
        "Order schema validation",
        "FAIL",
        "orders route does not validate against proto/domain/order_request.schema.json",
    )


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
        return CheckResult(
            "C8", "No raw fetch in FE", "FAIL", f"raw fetch() in: {', '.join(bad[:5])}"
        )
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
        return CheckResult("C9", "Firehose Zod-validated", "PASS", "schema imported and applied")
    return CheckResult(
        "C9", "Firehose Zod-validated", "FAIL", "ws-multiplex emits raw JSON without schema check"
    )


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
        return CheckResult(
            "C11", "Steering audited", "PASS", "steering store calls backend endpoint"
        )
    return CheckResult(
        "C11", "Steering audited", "FAIL", f"{store.relative_to(ROOT)} has no backend POST"
    )


# ---------------------------------------------------------------------------
# C14: GCP terraform source present on main
# ---------------------------------------------------------------------------
@register("C14", "GCP terraform source on main")
def check_gcp_terraform_on_main() -> CheckResult:
    tf_dir = ROOT / "infrastructure" / "gcp" / "terraform"
    if not tf_dir.is_dir():
        return CheckResult(
            "C14", "GCP terraform on main", "FAIL", "no infrastructure/gcp/terraform/"
        )
    tf_files = [p for p in tf_dir.glob("*.tf") if p.is_file()]
    if not tf_files:
        return CheckResult(
            "C14", "GCP terraform on main", "FAIL", "no .tf files in infrastructure/gcp/terraform/"
        )
    if any(p.name == "main.tf" for p in tf_files):
        return CheckResult(
            "C14", "GCP terraform on main", "PASS", f"{len(tf_files)} .tf files present"
        )
    return CheckResult(
        "C14",
        "GCP terraform on main",
        "PARTIAL",
        f"{len(tf_files)} .tf files but no main.tf root module",
    )


# ---------------------------------------------------------------------------
# C15: Coverage gate >= verified ratchet (ratcheting toward CLAUDE.md target)
# ---------------------------------------------------------------------------
# The verified current floor is 64% (PR #10 CI baseline @0befe0b: 63.87%).
# CLAUDE.md target stays 80%; the gate ratchets up as branch tests land.
# PASS = gate >= ratchet AND >= hard floor.
COVERAGE_FLOOR_MIN = 60
COVERAGE_FLOOR_NOW = 63  # verified CI floor: 63.87% (PR #10 @0befe0b)
COVERAGE_TARGET = 80


@register("C15", "Backend coverage gate >= verified floor")
def check_coverage_floor() -> CheckResult:
    ci = ROOT / ".github" / "workflows" / "ci.yml"
    if not ci.exists():
        return CheckResult("C15", "Coverage gate", "SKIP", "ci.yml missing")
    text = ci.read_text(encoding="utf-8")
    m = re.search(r"--cov-fail-under[= ](\d+)", text)
    if not m:
        return CheckResult("C15", "Coverage gate", "FAIL", "no --cov-fail-under in ci.yml")
    pct = int(m.group(1))
    if pct < COVERAGE_FLOOR_MIN:
        return CheckResult(
            "C15",
            "Coverage gate",
            "FAIL",
            f"--cov-fail-under={pct} below hard floor {COVERAGE_FLOOR_MIN}",
        )
    if pct >= COVERAGE_FLOOR_NOW:
        return CheckResult(
            "C15",
            "Coverage gate",
            "PASS",
            f"--cov-fail-under={pct} (ratchet={COVERAGE_FLOOR_NOW}, target={COVERAGE_TARGET})",
        )
    return CheckResult(
        "C15",
        "Coverage gate",
        "FAIL",
        f"--cov-fail-under={pct} regressed below ratchet={COVERAGE_FLOOR_NOW}",
    )


# ---------------------------------------------------------------------------
# C16: Stryker break threshold enforced
# ---------------------------------------------------------------------------
# Stryker ratchet: same pattern as coverage. Verified current floor 26.
STRYKER_BREAK_MIN = 20   # never let it drop below this
STRYKER_BREAK_NOW = 26   # verified mutation score floor (PR #10 CI: 26.12%)
STRYKER_TARGET = 85      # CLAUDE.md target (<15% survival)


@register("C16", "Stryker break threshold >= verified floor")
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
    if brk < STRYKER_BREAK_MIN:
        return CheckResult(
            "C16",
            "Stryker break",
            "FAIL",
            f'"thresholds.break"={brk} below hard floor {STRYKER_BREAK_MIN}',
        )
    if brk >= STRYKER_BREAK_NOW:
        return CheckResult(
            "C16",
            "Stryker break",
            "PASS",
            f'"thresholds.break"={brk} (ratchet={STRYKER_BREAK_NOW}, target={STRYKER_TARGET})',
        )
    return CheckResult(
        "C16",
        "Stryker break",
        "FAIL",
        f'"thresholds.break"={brk} regressed below ratchet={STRYKER_BREAK_NOW}',
    )


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
        "api-gateway",
        "orchestrator",
        "demand-prophet",
        "routing-navigator",
        "inventory-sentinel",
        "freshness-guardian",
        "pricing-oracle",
        "disruption-shield",
        "supplier-trust",
        "sustainability-agent",
        "digital-twin",
    ]
    missing = [r for r in required if f"name: {r}" not in text]
    if missing:
        return CheckResult("C12", "Helm full chart", "FAIL", f"missing dependencies: {missing}")
    # Also check the subchart directories exist.
    subchart_dir = ROOT / "infrastructure" / "helm" / "synapse" / "charts"
    missing_dirs = [r for r in required if not (subchart_dir / r).is_dir()]
    if missing_dirs:
        return CheckResult(
            "C12", "Helm full chart", "FAIL", f"missing subchart dirs: {missing_dirs}"
        )
    return CheckResult(
        "C12",
        "Helm full chart",
        "PASS",
        f"{len(required)} dependencies declared with subchart dirs present",
    )


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
    return CheckResult(
        "C13",
        "Mesh in Helm",
        "PASS",
        "Linkerd/KEDA/Flagger templates live under orchestrator subchart",
    )


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
        return CheckResult(
            "C22",
            "SLO metric truth",
            "FAIL",
            f"{len(missing)}/{len(metrics)} alerted metrics not emitted: "
            f"{missing[:3]}{'...' if len(missing) > 3 else ''}",
        )
    return CheckResult(
        "C22", "SLO metric truth", "PASS", f"{len(metrics)} alerted metrics all present in source"
    )


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
    return CheckResult("C19", "Image signing", "FAIL", "no cosign step in .github/workflows/cd.yml")


# ---------------------------------------------------------------------------
# C20: SBOM diff gate
# ---------------------------------------------------------------------------
@register("C20", "SBOM diff gate in CI")
def check_sbom_diff_gate() -> CheckResult:
    script = ROOT / "scripts" / "sbom_diff.py"
    if not script.exists():
        return CheckResult("C20", "SBOM diff", "FAIL", "scripts/sbom_diff.py missing")
    workflows = ROOT / ".github" / "workflows"
    if any(
        "sbom_diff" in p.read_text(encoding="utf-8", errors="ignore")
        for p in workflows.glob("*.yml")
        if p.is_file()
    ):
        return CheckResult("C20", "SBOM diff", "PASS", "sbom_diff invoked from CI")
    return CheckResult(
        "C20", "SBOM diff", "FAIL", "scripts/sbom_diff.py exists but no CI workflow references it"
    )


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
            return CheckResult("C21", "CVE budget", "PASS", f"invoked from {p.name}")
    return CheckResult("C21", "CVE budget", "FAIL", "no workflow references check_cve_budget.py")


@register("C24", "Worktree policy enforced by hook")
def check_worktree_hook() -> CheckResult:
    pc = ROOT / ".pre-commit-config.yaml"
    if not pc.exists():
        return CheckResult("C24", "Worktree hook", "FAIL", ".pre-commit-config.yaml missing")
    text = pc.read_text(encoding="utf-8")
    if "worktree" in text.lower() and "block" in text.lower():
        return CheckResult("C24", "Worktree hook", "PASS", "worktree-block hook present")
    return CheckResult(
        "C24", "Worktree hook", "FAIL", "no worktree-blocking hook in pre-commit-config"
    )


# ---------------------------------------------------------------------------
# C26: docker-compose.gcp.yml pulls signed images from Artifact Registry
# ---------------------------------------------------------------------------
# ADR-039. Every SYNAPSE-owned service in cd-gcp.yml's build matrix MUST be
# referenced by `image:` (not `build:`) in the GCP compose, with the AR URL
# pattern. Regression here is the exact trap that left an old purple UI live
# while 4 PRs landed on main — the compose silently bypassed the CD pipeline.
_SYNAPSE_SERVICE_IMAGE_NAMES = (
    "api-gateway",
    "orchestrator",
    "digital-twin",
    "demand-prophet",
    "routing-navigator",
    "inventory-sentinel",
    "freshness-guardian",
    "pricing-oracle",
    "disruption-shield",
    "supplier-trust",
    "sustainability-agent",
    "frontend",
)


def _load_gcp_compose() -> dict | None:
    compose = ROOT / "docker" / "docker-compose.gcp.yml"
    if not compose.exists():
        return None
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        return yaml.safe_load(compose.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None


@register("C26", "GCP compose pulls signed images from Artifact Registry")
def check_gcp_compose_pulls_images() -> CheckResult:
    data = _load_gcp_compose()
    if data is None:
        return CheckResult(
            "C26", "GCP compose pulls AR images", "SKIP", "compose unparseable or PyYAML missing"
        )
    services = data.get("services") or {}

    # Collect every image: reference and flag any build: directive on a
    # SYNAPSE-owned service. The matching key is the AR image name (with
    # one alias: compose service `api` → image `api-gateway`).
    service_to_image = {
        "api": "api-gateway",
        "frontend": "frontend",
        "orchestrator": "orchestrator",
        "digital-twin": "digital-twin",
        "demand-prophet": "demand-prophet",
        "routing-navigator": "routing-navigator",
        "inventory-sentinel": "inventory-sentinel",
        "freshness-guardian": "freshness-guardian",
        "pricing-oracle": "pricing-oracle",
        "disruption-shield": "disruption-shield",
        "supplier-trust": "supplier-trust",
        "sustainability-agent": "sustainability-agent",
    }
    expected_image = re.compile(
        r"^\$\{SYNAPSE_AR_REPO_URL[^}]*\}/(?P<name>[A-Za-z0-9-]+):\$\{SYNAPSE_VERSION"
    )

    problems: list[str] = []
    for svc_name, ar_image in service_to_image.items():
        svc = services.get(svc_name)
        if not isinstance(svc, dict):
            problems.append(f"{svc_name}: missing from compose")
            continue
        if "build" in svc:
            problems.append(f"{svc_name}: has `build:` (must be `image:` only)")
        image = svc.get("image", "")
        m = expected_image.match(str(image))
        if not m:
            problems.append(f"{svc_name}: image '{image}' does not match AR pattern")
            continue
        if m.group("name") != ar_image:
            problems.append(
                f"{svc_name}: image name '{m.group('name')}' != expected '{ar_image}'"
            )

    if problems:
        return CheckResult(
            "C26",
            "GCP compose pulls AR images",
            "FAIL",
            f"{len(problems)} issue(s): {problems[0]}"
            + (f" (+{len(problems) - 1} more)" if len(problems) > 1 else ""),
        )
    return CheckResult(
        "C26",
        "GCP compose pulls AR images",
        "PASS",
        f"{len(service_to_image)} services pull from Artifact Registry",
    )


# ---------------------------------------------------------------------------
# C27: verify_images.sh covers every image in the cd-gcp.yml build matrix
# ---------------------------------------------------------------------------
# ADR-039. The Cosign-verify gate on the VM must check every image the CD
# workflow signed; otherwise a tampered image can be served while the gate
# reports "all verified." Pre-fix, `frontend` was missing from this list.
@register("C27", "verify_images.sh covers the full CD matrix")
def check_verify_images_covers_matrix() -> CheckResult:
    cd = ROOT / ".github" / "workflows" / "cd-gcp.yml"
    vs = ROOT / "infrastructure" / "gcp" / "verify_images.sh"
    if not cd.exists() or not vs.exists():
        return CheckResult("C27", "verify_images coverage", "SKIP", "files missing")

    cd_text = cd.read_text(encoding="utf-8")
    matrix_images = set(re.findall(r"image:\s*([A-Za-z0-9-]+)\s*,", cd_text))
    if not matrix_images:
        return CheckResult(
            "C27", "verify_images coverage", "FAIL", "no matrix entries parsed from cd-gcp.yml"
        )

    vs_text = vs.read_text(encoding="utf-8")
    m = re.search(r"IMAGES=\(([^)]+)\)", vs_text, re.DOTALL)
    if not m:
        return CheckResult(
            "C27", "verify_images coverage", "FAIL", "IMAGES=(...) array not found"
        )
    listed = {
        line.strip().strip("\"'")
        for line in m.group(1).splitlines()
        if line.strip() and not line.strip().startswith("#")
    }

    missing = sorted(matrix_images - listed)
    if missing:
        return CheckResult(
            "C27",
            "verify_images coverage",
            "FAIL",
            f"images signed by CD but not verified: {missing}",
        )
    return CheckResult(
        "C27",
        "verify_images coverage",
        "PASS",
        f"all {len(matrix_images)} signed images are verified at boot",
    )


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
            "summary": {
                "pass": pass_n,
                "fail": fail_n,
                "partial": partial_n,
                "skip": skip_n,
                "total": len(results),
            },
            "checks": [r.__dict__ for r in results],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for r in results:
            sym = {"PASS": "[OK]", "FAIL": "[XX]", "PARTIAL": "[~~]", "SKIP": "[--]"}[r.status]
            print(f"{sym} {r.cid:>4} {r.title:<48} {r.detail}")
        print()
        print(
            f"Summary: PASS={pass_n} FAIL={fail_n} PARTIAL={partial_n} "
            f"SKIP={skip_n} TOTAL={len(results)}"
        )

    return 1 if fail_n else 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv))
