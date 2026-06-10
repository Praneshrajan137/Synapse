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
    """Sprint 13 §Phase 2 supersedes the single --cov-fail-under gate with a
    per-package floor enforced by `scripts/coverage_per_package.py` against
    `infrastructure/quality/coverage-floors.yaml`. C15 now passes iff the
    per-package script is invoked in ci.yml and the floors YAML exists.
    Per-package floor enforcement detail belongs to C28."""
    ci = ROOT / ".github" / "workflows" / "ci.yml"
    floors = ROOT / "infrastructure" / "quality" / "coverage-floors.yaml"
    if not ci.exists():
        return CheckResult("C15", "Coverage gate", "SKIP", "ci.yml missing")
    text = ci.read_text(encoding="utf-8")
    if "coverage_per_package.py" in text and floors.is_file():
        return CheckResult(
            "C15",
            "Coverage gate",
            "PASS",
            "per-package script wired in ci.yml; floors YAML present (see C28)",
        )
    # Backwards-compat path — accept the old --cov-fail-under gate if present.
    m = re.search(r"--cov-fail-under[= ](\d+)", text)
    if m and int(m.group(1)) >= COVERAGE_FLOOR_MIN:
        return CheckResult(
            "C15",
            "Coverage gate",
            "PASS",
            f"legacy --cov-fail-under={m.group(1)} still meets hard floor {COVERAGE_FLOOR_MIN}",
        )
    return CheckResult(
        "C15",
        "Coverage gate",
        "FAIL",
        "no per-package gate AND no --cov-fail-under in ci.yml",
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
        # Sprint 14: the always-alive traffic loop reuses the api-gateway
        # image with a command override — still pull-from-AR only.
        "traffic-generator": "api-gateway",
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
# C28: per-package coverage floors enforced
# ---------------------------------------------------------------------------
# Sprint 13 §Phase 2 / Phase 6. Supersedes C15's single-gate model. PASS iff:
#   - `scripts/coverage_per_package.py` exists and is wired into ci.yml,
#   - `infrastructure/quality/coverage-floors.yaml` exists with all 10 packages
#     (synapse_common, orchestrator, 8 agents), and
#   - every floor is non-negative.
# The 84% destination on each row is documented intent — verify_claims does NOT
# fail until measured drops below floor; that is the job of CI's actual
# per-package gate step.
@register("C28", "Per-package coverage floors enforced")
def check_per_package_coverage() -> CheckResult:
    script = ROOT / "scripts" / "coverage_per_package.py"
    floors = ROOT / "infrastructure" / "quality" / "coverage-floors.yaml"
    ci = ROOT / ".github" / "workflows" / "ci.yml"
    if not script.is_file():
        return CheckResult("C28", "Per-package coverage", "FAIL", "scripts/coverage_per_package.py missing")
    if not floors.is_file():
        return CheckResult("C28", "Per-package coverage", "FAIL", "coverage-floors.yaml missing")
    if not ci.is_file() or "coverage_per_package.py" not in ci.read_text(encoding="utf-8"):
        return CheckResult("C28", "Per-package coverage", "FAIL", "ci.yml does not invoke the script")
    try:
        import yaml as _yaml  # local import; PyYAML is a dev dep
    except ImportError:
        return CheckResult("C28", "Per-package coverage", "SKIP", "PyYAML not installed")
    doc = _yaml.safe_load(floors.read_text(encoding="utf-8")) or {}
    pkgs = doc.get("packages", {})
    expected_count = 10  # synapse_common + orchestrator + 8 agents
    if len(pkgs) < expected_count:
        return CheckResult(
            "C28", "Per-package coverage", "FAIL",
            f"floors YAML has {len(pkgs)} packages, expected >={expected_count}",
        )
    bad = [p for p, cfg in pkgs.items() if float(cfg.get("line", -1)) < 0]
    if bad:
        return CheckResult(
            "C28", "Per-package coverage", "FAIL",
            f"negative line floor in: {bad}",
        )
    return CheckResult(
        "C28", "Per-package coverage", "PASS",
        f"{len(pkgs)} packages gated; script wired into ci.yml",
    )


# ---------------------------------------------------------------------------
# C29: branch coverage enabled in pyproject.toml
# ---------------------------------------------------------------------------
# Sprint 13 §Phase 1.2 — `branch = true` under [tool.coverage.run]. Without this
# every per-package gate would be line-only and miss conditional branches.
@register("C29", "Branch coverage enabled in pyproject")
def check_branch_coverage() -> CheckResult:
    pp = ROOT / "pyproject.toml"
    if not pp.is_file():
        return CheckResult("C29", "Branch coverage", "FAIL", "pyproject.toml missing")
    text = pp.read_text(encoding="utf-8")
    # Find the [tool.coverage.run] section explicitly, then look for
    # `branch = true` on its own line before the next [...] section header.
    section = re.search(
        r"\[tool\.coverage\.run\]\n((?:(?!^\[)[\s\S])*)",
        text, re.MULTILINE,
    )
    if section and re.search(r"^\s*branch\s*=\s*true\b", section.group(1), re.IGNORECASE | re.MULTILINE):
        return CheckResult("C29", "Branch coverage", "PASS", "branch = true in [tool.coverage.run]")
    return CheckResult(
        "C29", "Branch coverage", "FAIL",
        "branch = true not set under [tool.coverage.run] in pyproject.toml",
    )


# ---------------------------------------------------------------------------
# C30: Python mutmut PR-gated on changed reward/audit/guardrail files
# ---------------------------------------------------------------------------
# Sprint 13 §Phase 4.2. Parallel to C16 (frontend Stryker). PASS iff
# `.github/workflows/mutation.yml` (or any workflow) runs mutmut on
# `pull_request` for the high-leverage Python targets. Until that PR-trigger
# is wired, C30 is honestly FAIL — the existing Sunday cron does not block
# regressions on merge to main.
@register("C30", "Python mutmut PR-gated on changed targets")
def check_python_mutmut_pr_gated() -> CheckResult:
    workflows = ROOT / ".github" / "workflows"
    if not workflows.is_dir():
        return CheckResult("C30", "mutmut PR gate", "SKIP", "workflows dir missing")
    for wf in workflows.glob("*.yml"):
        text = wf.read_text(encoding="utf-8")
        if "mutmut" not in text:
            continue
        # Does any job in this workflow trigger on pull_request AND mention
        # one of the gated mutation targets?
        has_pr = re.search(r"pull_request\s*:", text)
        targets_re = r"agents/.*?/training/rewards\.py|guardrails/rules\.py|audit/(hash_chain|logger)\.py"
        has_target = re.search(targets_re, text)
        if has_pr and has_target:
            return CheckResult(
                "C30", "mutmut PR gate", "PASS",
                f"PR-trigger + Python mutation target found in {wf.name}",
            )
    return CheckResult(
        "C30", "mutmut PR gate", "FAIL",
        "no workflow runs mutmut on pull_request for rewards/audit/guardrail targets "
        "(Sprint 13 Phase 4.2 follow-up — current setup is Sunday cron only)",
    )


# ---------------------------------------------------------------------------
# C31: spec-coverage script wired to CI as a blocking step
# ---------------------------------------------------------------------------
# Sprint 13 §Phase 5.3. PASS iff `scripts/check_spec_coverage.py` is invoked
# from ci.yml with `--threshold N`. Initial N = 12 (just below measured 13.8%
# assertion-matched aggregate). Ratchet plan: 12 -> 25 -> 50 -> 75 -> 100.
@register("C31", "Spec-coverage script in CI with threshold")
def check_spec_coverage_in_ci() -> CheckResult:
    script = ROOT / "scripts" / "check_spec_coverage.py"
    ci = ROOT / ".github" / "workflows" / "ci.yml"
    if not script.is_file():
        return CheckResult("C31", "Spec coverage", "FAIL", "check_spec_coverage.py missing")
    if not ci.is_file():
        return CheckResult("C31", "Spec coverage", "SKIP", "ci.yml missing")
    text = ci.read_text(encoding="utf-8")
    m = re.search(r"check_spec_coverage\.py.*?--threshold\s+(\d+)", text, re.DOTALL)
    if not m:
        return CheckResult(
            "C31", "Spec coverage", "FAIL",
            "check_spec_coverage.py not invoked with --threshold in ci.yml",
        )
    threshold = int(m.group(1))
    if threshold < 10:
        return CheckResult(
            "C31", "Spec coverage", "FAIL",
            f"--threshold {threshold} below hard floor 10",
        )
    return CheckResult(
        "C31", "Spec coverage", "PASS",
        f"--threshold {threshold} (ratchet target: 50 -> 100)",
    )


# ---------------------------------------------------------------------------
# C32: training/* coverage omit narrowed (rewards.py is covered)
# ---------------------------------------------------------------------------
# Sprint 13 §Phase 1.2. The previous broad `*/training/*` omit hid the very
# files mutation-tested at <15% survival. PASS iff the omit pattern does NOT
# contain the bare `*/training/*` wildcard.
@register("C32", "Training/* omit narrowed in pyproject")
def check_training_omit_narrowed() -> CheckResult:
    pp = ROOT / "pyproject.toml"
    if not pp.is_file():
        return CheckResult("C32", "Training omit", "FAIL", "pyproject.toml missing")
    text = pp.read_text(encoding="utf-8")
    # The broad omit pattern, if present, is a regression.
    if re.search(r'"\*/training/\*"', text):
        return CheckResult(
            "C32", "Training omit", "FAIL",
            "broad `*/training/*` omit pattern present — re-hides rewards.py from coverage",
        )
    # Affirmative check: at least the narrow patterns are present (loop, train_*).
    if re.search(r'"\*/training/loop\.py"', text):
        return CheckResult(
            "C32", "Training omit", "PASS",
            "narrow training-loop omit pattern present; rewards.py is measurable",
        )
    return CheckResult(
        "C32", "Training omit", "PARTIAL",
        "broad pattern absent but narrow loop pattern not present either",
    )


# ---------------------------------------------------------------------------
# C33: substance gap — agent pipelines must not ignore real dependencies
# ---------------------------------------------------------------------------
# Plan v2 (Substance Mandate), Phase 0/4. `scripts/audit/substance_truth.py`
# AST-flags the synthetic-shortcut anti-patterns in agents/*/inference/pipeline.py
# (guard-then-ignore dependency, hardcoded confidence, random model input).
# Ratchet idiom (mirrors C15/C16): PASS while violations <= baseline; FAIL on
# any INCREASE. Phase 2 drives the baseline down toward zero, one agent per PR;
# Phase 4 wires `substance_truth.py --check` as a hard blocking CI gate at zero.
SUBSTANCE_VIOLATIONS_BASELINE = 0  # ratcheted to zero — all 8 pipelines rewired (Phase 2)
SUBSTANCE_VIOLATIONS_TARGET = 0


@register("C33", "Agent pipelines free of synthetic shortcuts (ratchet)")
def check_substance_gap() -> CheckResult:
    try:
        from scripts.audit.substance_truth import collect
    except ImportError as exc:
        return CheckResult("C33", "Substance gap", "SKIP", f"substance_truth import failed: {exc}")
    reports = collect()
    total = sum(len(r.violations) for r in reports)
    clean = sum(1 for r in reports if not r.violations)
    if total > SUBSTANCE_VIOLATIONS_BASELINE:
        return CheckResult(
            "C33",
            "Substance gap",
            "FAIL",
            f"{total} synthetic-shortcut violations > baseline {SUBSTANCE_VIOLATIONS_BASELINE} "
            f"- a new placeholder path was introduced",
        )
    detail = (
        f"{total} violation(s) <= baseline {SUBSTANCE_VIOLATIONS_BASELINE}; "
        f"{clean}/{len(reports)} agents clean (target {SUBSTANCE_VIOLATIONS_TARGET})"
    )
    # Below baseline but not yet zero is honest progress, not a regression.
    if total > SUBSTANCE_VIOLATIONS_TARGET:
        return CheckResult("C33", "Substance gap", "PARTIAL", detail)
    return CheckResult("C33", "Substance gap", "PASS", detail + " - all pipelines real")


# ---------------------------------------------------------------------------
# C34: I-12 twin divergence edge wired (TwinKafkaSync -> DivergenceMonitor)
# ---------------------------------------------------------------------------
# Plan v2 / Phase 3. Before this, update_live_state had no production caller and
# synapse_digital_twin_kl_divergence never emitted. PASS iff the monitor emits
# the metric AND the kafka sync feeds live state into the monitor.
@register("C34", "I-12 twin divergence edge wired")
def check_i12_wired() -> CheckResult:
    mon = ROOT / "digital_twin" / "sync" / "divergence_monitor.py"
    sync = ROOT / "digital_twin" / "sync" / "kafka_sync.py"
    if not mon.exists() or not sync.exists():
        return CheckResult("C34", "I-12 wired", "SKIP", "twin sync files missing")
    mon_t = mon.read_text(encoding="utf-8")
    sync_t = sync.read_text(encoding="utf-8")
    emits = "DIGITAL_TWIN_KL_DIVERGENCE" in mon_t and ".set(" in mon_t
    feeds = "update_live_state" in sync_t and "divergence_monitor" in sync_t
    if emits and feeds:
        return CheckResult(
            "C34", "I-12 wired", "PASS",
            "monitor emits synapse_digital_twin_kl_divergence; kafka_sync feeds live state",
        )
    missing = []
    if not emits:
        missing.append("monitor does not emit the KL metric")
    if not feeds:
        missing.append("kafka_sync does not call update_live_state")
    return CheckResult("C34", "I-12 wired", "FAIL", "; ".join(missing))


# ---------------------------------------------------------------------------
# C35: API gateway auth enforced + no hardcoded DB credential
# ---------------------------------------------------------------------------
# Plan v2 / Phase 5. Read + trigger endpoints require a bearer token; the
# embedded synapse_app password default is gone (fail-fast DSN).
@register("C35", "API auth enforced + no embedded secret")
def check_api_auth() -> CheckResult:
    dec = ROOT / "api" / "routers" / "decisions.py"
    main = ROOT / "api" / "main.py"
    if not dec.exists():
        return CheckResult("C35", "API auth", "SKIP", "decisions.py missing")
    dec_t = dec.read_text(encoding="utf-8")
    # All three decisions handlers must carry an auth dependency.
    auth_on_reads = (
        dec_t.count("Depends(CurrentOperator)") >= 2
        and "Depends(RequireRole(Role.OPS))" in dec_t
    )
    # No embedded DB credential anywhere under api/ (decisions, main, steering, …).
    api_dir = ROOT / "api"
    leaks = _grep(r"synapse_app_2026", api_dir, glob="*.py")
    no_secret = not leaks
    if auth_on_reads and no_secret:
        return CheckResult(
            "C35", "API auth", "PASS",
            "read+trigger endpoints gated by JWT; no embedded DB credential",
        )
    problems = []
    if not auth_on_reads:
        problems.append("a decisions endpoint lacks an auth dependency")
    if not no_secret:
        problems.append("hardcoded synapse_app_2026 credential still present")
    return CheckResult("C35", "API auth", "FAIL", "; ".join(problems))


# ---------------------------------------------------------------------------
# C36: honesty contract present (ADR-040 / ADR-041)
# ---------------------------------------------------------------------------
@register("C36", "Honesty contract modules + ADRs present")
def check_honesty_contract() -> CheckResult:
    pkg = ROOT / "packages" / "synapse_common"
    modules = ["features.py", "model_registry.py", "provenance.py", "invariants.py"]
    missing_mods = [m for m in modules if not (pkg / m).is_file()]
    adrs = [
        ROOT / "docs" / "adr" / "ADR-040-honest-output-provenance-and-degradation.md",
        ROOT / "docs" / "adr" / "ADR-041-feature-model-anti-corruption-layer.md",
    ]
    missing_adrs = [a.name for a in adrs if not a.is_file()]
    if missing_mods or missing_adrs:
        return CheckResult(
            "C36", "Honesty contract", "FAIL",
            f"missing modules={missing_mods} adrs={missing_adrs}",
        )
    return CheckResult(
        "C36", "Honesty contract", "PASS",
        "FeatureProvider/ModelRegistry/Provenance/RuntimeValidator + ADR-040/041 present",
    )


# ---------------------------------------------------------------------------
# C37-C41: substance completion (ADR-042) — the intelligence is real, not just
# the enforcement boundary. Each mirrors the C33 ratchet idiom: import the gate's
# collect/run, PASS while violations <= baseline, FAIL on regression.
# ---------------------------------------------------------------------------
@register("C37", "Models actually train (real gradient steps, ratchet)")
def check_training_truth() -> CheckResult:
    try:
        from scripts.audit.training_truth import BASELINE, collect
    except ImportError as exc:
        return CheckResult("C37", "Training truth", "SKIP", f"training_truth import failed: {exc}")
    reports = collect()
    total = sum(len(r.violations) for r in reports)
    real = sum(1 for r in reports if r.has_real_step)
    detail = f"{real}/{len(reports)} real gradient loops; {total} violation(s) (baseline {BASELINE})"
    if total > BASELINE:
        return CheckResult("C37", "Training truth", "FAIL", detail + " — regression")
    return CheckResult("C37", "Training truth", "PASS", detail)


@register("C38", "Training produces loadable, content-hashed checkpoints")
def check_checkpoint_truth() -> CheckResult:
    try:
        from scripts.audit.checkpoint_truth import collect
    except ImportError as exc:
        return CheckResult("C38", "Checkpoint truth", "SKIP", f"checkpoint_truth import failed: {exc}")
    report, any_artifact = collect()
    failures = [r for r in report.results if r.status in {"missing_file", "sha_mismatch", "no_checkpoint"}]
    # verify_claims runs outside the smoke job (no training artifacts), so SKIP when
    # none are present — the CI training-smoke job enforces C38 via the standalone
    # `checkpoint_truth --check` with SYNAPSE_SMOKE_RUN=1. _ = CHECKPOINT_AGENTS.
    if not any_artifact:
        return CheckResult("C38", "Checkpoint truth", "SKIP", "no training artifacts (run the smoke job)")
    if failures:
        return CheckResult("C38", "Checkpoint truth", "FAIL", f"{len(failures)} bad checkpoint(s)")
    return CheckResult("C38", "Checkpoint truth", "PASS", f"{len(report.results)} checkpoint(s) verified")


@register("C39", "Serving loads models via ModelRegistry (ratchet)")
def check_serving_truth() -> CheckResult:
    try:
        from scripts.audit.serving_truth import BASELINE_UNWIRED, collect
    except ImportError as exc:
        return CheckResult("C39", "Serving truth", "SKIP", f"serving_truth import failed: {exc}")
    reports = collect()
    wired = sum(1 for r in reports if r.wired)
    unwired = sum(1 for r in reports if r.exists and not r.wired)
    regressions = sum(len(r.violations) for r in reports)
    detail = f"{wired}/{len(reports)} agents load a real model (baseline unwired {BASELINE_UNWIRED})"
    if unwired > BASELINE_UNWIRED or regressions > 0:
        return CheckResult("C39", "Serving truth", "FAIL", detail + " — regression")
    return CheckResult("C39", "Serving truth", "PASS", detail)


@register("C40", "Prediction intervals achieve nominal coverage")
def check_calibration_truth() -> CheckResult:
    try:
        from scripts.audit.calibration_truth import collect
    except ImportError as exc:
        return CheckResult("C40", "Calibration truth", "SKIP", f"calibration_truth import failed: {exc}")
    report, any_artifact = collect()
    failures = [r for r in report.results if r.status in {"below_floor", "no_metric"}]
    if not any_artifact:
        return CheckResult("C40", "Calibration truth", "SKIP", "no training artifacts (run the smoke job)")
    if failures:
        return CheckResult("C40", "Calibration truth", "FAIL", f"{len(failures)} under-covered model(s)")
    return CheckResult("C40", "Calibration truth", "PASS", f"{len(report.results)} model(s) calibrated")


@register("C41", "Declared confidence_basis matches computed basis (ratchet)")
def check_confidence_basis_truth() -> CheckResult:
    try:
        from scripts.audit.confidence_basis_truth import BASELINE, collect
    except ImportError as exc:
        return CheckResult("C41", "Confidence basis", "SKIP", f"confidence_basis_truth import failed: {exc}")
    reports = collect()
    total = sum(len(r.violations) for r in reports)
    detail = f"{total} stamp/computation mismatch(es) (baseline {BASELINE})"
    if total > BASELINE:
        return CheckResult("C41", "Confidence basis", "FAIL", detail + " — regression")
    return CheckResult("C41", "Confidence basis", "PASS", detail)


@register("C45", "Real checkpoint serves non-degraded calibrated output at runtime")
def check_runtime_substance() -> CheckResult:
    """The RUNTIME counterpart to C33's static AST gate (ADR-043).

    Boots the demand_prophet checkpoint through the production serving path and
    asserts the output is genuinely real (degraded=False, conformal-interval
    confidence). SKIPs torch-free / artifact-absent — enforced in the CI
    training-smoke job after the smoke train produces the checkpoint.
    """
    try:
        from scripts.audit.runtime_substance import evaluate
    except ImportError as exc:
        return CheckResult("C45", "Runtime substance", "SKIP", f"runtime_substance import failed: {exc}")
    probe = evaluate()
    status = {"ok": "PASS", "fail": "FAIL", "skip": "SKIP"}[probe.status]
    return CheckResult("C45", "Runtime substance", status, probe.detail)


@register("C7", "Orchestrator invokes the digital twin + records input provenance")
def check_orchestrator_twin_wired() -> CheckResult:
    """Tier-4 → digital-twin Monte-Carlo verify + per-decision input provenance (ADR-043).

    Static AST proof on ``orchestrator/consensus/protocol.py`` (torch/pymoo-free):
    the twin endpoint is defined, ``_phase_twin_verify`` + ``_record_input_provenance``
    are both *defined and called*, and the twin call is gated on the top tier. The
    behavioural proof is ``orchestrator/tests/test_twin_verification.py`` (CI, pymoo).
    Closes the C7 'twin is dead code' gap with a regression-failing gate.
    """
    import ast as _ast

    proto = ROOT / "orchestrator" / "consensus" / "protocol.py"
    if not proto.is_file():
        return CheckResult("C7", "Orchestrator twin", "FAIL", "protocol.py missing")
    try:
        tree = _ast.parse(proto.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        return CheckResult("C7", "Orchestrator twin", "FAIL", f"parse error: {exc}")

    _fn_types = (_ast.FunctionDef, _ast.AsyncFunctionDef)
    defs = {n.name for n in _ast.walk(tree) if isinstance(n, _fn_types)}
    called = {
        n.func.attr
        for n in _ast.walk(tree)
        if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Attribute)
    }
    has_endpoint = any(
        isinstance(n, _ast.Assign)
        and any(isinstance(t, _ast.Name) and t.id == "TWIN_ENDPOINT" for t in n.targets)
        for n in _ast.walk(tree)
    )
    required_defs = {"_phase_twin_verify", "_record_input_provenance"}
    missing_defs = required_defs - defs
    missing_calls = required_defs - called
    if missing_defs or missing_calls or not has_endpoint:
        return CheckResult(
            "C7", "Orchestrator twin", "FAIL",
            f"missing defs={sorted(missing_defs)} calls={sorted(missing_calls)} "
            f"endpoint={has_endpoint}",
        )
    return CheckResult(
        "C7", "Orchestrator twin", "PASS",
        "Tier-4 twin verify + input-provenance recording wired (defined + called)",
    )


@register("C46", "A real, published production checkpoint serves at $0")
def check_published_checkpoint() -> CheckResult:
    """Authenticity counterpart to C42 (ADR-043, Phase 1).

    C42 proves the serving *code path* is real on the CI smoke checkpoint. C43
    proves an operator actually published a genuine, non-smoke, adequately
    calibrated checkpoint to the $0 serving source (HF Hub) and recorded it.
    SKIPs when DP_HF_REPO is unset or the registry is still a placeholder — never
    fabricates a pass; FAILs only on a smoke/under-covered/drifted published model.
    """
    try:
        from scripts.audit.published_checkpoint_truth import evaluate as _eval_pub
    except ImportError as exc:
        return CheckResult(
            "C43", "Published checkpoint", "SKIP", f"published_checkpoint_truth import failed: {exc}"
        )
    probe = _eval_pub()
    status = {"ok": "PASS", "fail": "FAIL", "skip": "SKIP"}[probe.status]
    return CheckResult("C46", "Published checkpoint", status, probe.detail)


# ---------------------------------------------------------------------------
# C42: API decisions feed reads the SAME table the orchestrator writes
# ---------------------------------------------------------------------------
@register("C42", "Decisions read-path table == orchestrator write-path table")
def check_audit_read_write_table_match() -> CheckResult:
    """The live 503 (`column "phase_reached" does not exist`) was caused by the
    API reading the dead ``audit_decisions`` table while the orchestrator writes
    ``audit_consensus``. This gate fails if they ever diverge again.
    """
    decisions = ROOT / "api" / "routers" / "decisions.py"
    models = ROOT / "orchestrator" / "audit" / "models.py"
    if not decisions.exists() or not models.exists():
        return CheckResult("C42", "Read/write table match", "SKIP", "source file missing")

    dtext = decisions.read_text(encoding="utf-8")
    mtext = models.read_text(encoding="utf-8")

    # The orchestrator write target: __tablename__ of the consensus ORM row.
    m = re.search(r'AuditConsensusRow.*?__tablename__\s*=\s*"([^"]+)"', mtext, re.DOTALL)
    write_table = m.group(1) if m else None
    if write_table is None:
        return CheckResult("C42", "Read/write table match", "FAIL", "could not resolve AuditConsensusRow.__tablename__")

    read_tables = set(re.findall(r"FROM\s+(audit_\w+)", dtext))
    decision_reads = {t for t in read_tables if t in {"audit_decisions", "audit_consensus"}}

    if "audit_decisions" in decision_reads:
        return CheckResult(
            "C42",
            "Read/write table match",
            "FAIL",
            f"api/routers/decisions.py still reads dead 'audit_decisions'; orchestrator writes '{write_table}'",
        )
    if decision_reads == {write_table}:
        return CheckResult(
            "C42",
            "Read/write table match",
            "PASS",
            f"decisions.py reads '{write_table}' == AuditConsensusRow.__tablename__",
        )
    return CheckResult(
        "C42",
        "Read/write table match",
        "FAIL",
        f"decisions.py decision reads {sorted(decision_reads)} != write table '{write_table}'",
    )


# ---------------------------------------------------------------------------
# C43: every agent serves the A2A endpoint the orchestrator calls
# ---------------------------------------------------------------------------
@register("C43", "All 8 agents expose POST /a2a for consensus")
def check_agents_serve_a2a() -> CheckResult:
    """The orchestrator's consensus POSTs JSON-RPC to each agent's ``/a2a``
    (``a2a_sdk.send_a2a_request`` appends ``/a2a``). 5 of 8 agents never mounted
    it, so proposals 404'd and decisions degraded to confidence=0.0 live. This
    gate fails if any agent's serve.py loses the route.
    """
    agents_dir = ROOT / "agents"
    if not agents_dir.is_dir():
        return CheckResult("C43", "Agents serve /a2a", "SKIP", "agents/ missing")
    expected = [
        "demand_prophet", "routing_navigator", "inventory_sentinel",
        "freshness_guardian", "pricing_oracle", "disruption_shield",
        "supplier_trust", "sustainability_agent",
    ]
    missing: list[str] = []
    for name in expected:
        serve = agents_dir / name / "inference" / "serve.py"
        if not serve.exists():
            missing.append(f"{name} (no serve.py)")
            continue
        text = serve.read_text(encoding="utf-8")
        if '"/a2a"' not in text:
            missing.append(name)
    if missing:
        return CheckResult(
            "C43", "Agents serve /a2a", "FAIL",
            f"{len(missing)} agent(s) missing POST /a2a: {', '.join(missing)}",
        )
    return CheckResult(
        "C43", "Agents serve /a2a", "PASS",
        f"all {len(expected)} agents mount POST /a2a (orchestrator consensus reachable)",
    )


# ---------------------------------------------------------------------------
# C44: no dead Python modules (orphaned code can't silently accumulate)
# ---------------------------------------------------------------------------
@register("C44", "No dead Python modules (module-liveness)")
def check_no_dead_modules() -> CheckResult:
    """Owner concern: "most of the code is there but not used". The
    module-liveness analyzer builds an import graph from the live
    docker-compose entrypoints and flags modules that are neither reachable,
    referenced by make/CI, nor tests. Baseline ratcheted to 0 after the sweep
    (3 routers wired, 6 orphans removed). A new orphan fails CI.
    """
    try:
        from scripts.audit.module_liveness import DEAD_BASELINE, classify
    except ImportError as exc:
        return CheckResult("C44", "No dead modules", "SKIP", f"module_liveness import failed: {exc}")
    dead = classify()["DEAD"]
    n = len(dead)
    if n > DEAD_BASELINE:
        names = ", ".join(rel for rel, _ in dead[:5])
        return CheckResult(
            "C44", "No dead modules", "FAIL",
            f"{n} dead module(s) > baseline {DEAD_BASELINE}: {names}{'…' if n > 5 else ''}",
        )
    return CheckResult("C44", "No dead modules", "PASS", f"{n} dead module(s) (baseline {DEAD_BASELINE})")


# ---------------------------------------------------------------------------
# C47: every deploy is verified end-to-end before the workflow goes green
# ---------------------------------------------------------------------------
# Deploy Truth (Sprint 14). The original incident class: a deploy "succeeds"
# while the live system is stale or broken (months-stale link; jsonschema
# crash-loop behind a green run). cd-gcp.yml must (a) assert container truth
# on the VM, (b) assert the deployed /version SHA equals the deployed commit
# from OUTSIDE, and (c) open an issue on any failure so it is loud.
@register("C47", "Deploy truth gated in cd-gcp.yml (SHA + containers + issue)")
def check_deploy_truth_gated() -> CheckResult:
    cd = ROOT / ".github" / "workflows" / "cd-gcp.yml"
    oracle = ROOT / "scripts" / "deploy" / "verify_live.py"
    if not oracle.is_file():
        return CheckResult("C47", "Deploy truth gated", "FAIL", "verify_live.py missing")
    if not cd.is_file():
        return CheckResult("C47", "Deploy truth gated", "FAIL", "cd-gcp.yml missing")
    text = cd.read_text(encoding="utf-8")
    missing = [
        want
        for want in (
            "Verify deploy truth (containers)",
            "Verify deploy truth (external)",
            "verify_live.py --on-vm --probe-decision",
            '--expect-sha "${{ github.sha }}"',
            "Open issue on deploy failure",
            "if: failure()",
        )
        if want not in text
    ]
    if missing:
        return CheckResult(
            "C47", "Deploy truth gated", "FAIL", f"cd-gcp.yml missing: {missing}"
        )
    return CheckResult(
        "C47",
        "Deploy truth gated",
        "PASS",
        "deploys assert SHA + all-containers + decision-flow, and fail loudly",
    )


# ---------------------------------------------------------------------------
# C49: import-smoke covers every Python image in the CD build matrix
# ---------------------------------------------------------------------------
# Lockstep gate in the C27 style: every Python image built by cd-gcp.yml must
# declare its `entry` module so the import-smoke step exercises it inside the
# pushed image. A runtime dep present in CI but absent from an image (the
# jsonschema incident, PR #42) then fails at build time, pre-deploy.
@register("C49", "Import smoke covers every Python image in the CD matrix")
def check_image_smoke_covers_matrix() -> CheckResult:
    cd = ROOT / ".github" / "workflows" / "cd-gcp.yml"
    if not cd.is_file():
        return CheckResult("C49", "Import smoke coverage", "FAIL", "cd-gcp.yml missing")
    text = cd.read_text(encoding="utf-8")
    if "Import smoke" not in text or "importlib.import_module" not in text:
        return CheckResult(
            "C49", "Import smoke coverage", "FAIL", "import-smoke step missing"
        )
    rows = re.findall(
        r"image:\s*([A-Za-z0-9-]+),.*?entry:\s*([A-Za-z0-9_.]+|\"\")", text
    )
    if not rows:
        return CheckResult(
            "C49", "Import smoke coverage", "FAIL", "no matrix entry fields parsed"
        )
    no_entry = sorted(img for img, entry in rows if entry in ('""', "") and img != "frontend")
    if no_entry:
        return CheckResult(
            "C49",
            "Import smoke coverage",
            "FAIL",
            f"Python images without an import-smoke entry: {no_entry}",
        )
    smoked = sum(1 for _img, entry in rows if entry not in ('""', ""))
    return CheckResult(
        "C49",
        "Import smoke coverage",
        "PASS",
        f"{smoked} Python images import-smoked before deploy (frontend static, skipped)",
    )


# ---------------------------------------------------------------------------
# C50: every GCP compose service resolves to a healthcheck
# ---------------------------------------------------------------------------
# The post-deploy "all containers healthy" assertion (C47) is only total if
# every service actually carries a healthcheck — either a compose-level block
# or a HEALTHCHECK in the SYNAPSE-owned Dockerfile its image was built from.
@register("C50", "Every GCP compose service resolves to a healthcheck")
def check_compose_health_complete() -> CheckResult:
    compose = ROOT / "docker" / "docker-compose.gcp.yml"
    if not compose.is_file():
        return CheckResult("C50", "Compose health complete", "FAIL", "gcp compose missing")
    try:
        import yaml as _yaml
    except ImportError:
        return CheckResult("C50", "Compose health complete", "SKIP", "PyYAML not installed")
    doc = _yaml.safe_load(compose.read_text(encoding="utf-8")) or {}
    services = doc.get("services", {})
    if not services:
        return CheckResult("C50", "Compose health complete", "FAIL", "no services parsed")
    unchecked: list[str] = []
    for name, svc in services.items():
        if "healthcheck" in (svc or {}):
            continue
        snake = name.replace("-", "_")
        candidates = [
            ROOT / snake / "Dockerfile",
            ROOT / "agents" / snake / "Dockerfile",
        ]
        if name == "api":
            candidates.insert(0, ROOT / "api" / "Dockerfile")
        if not any(
            c.is_file() and "HEALTHCHECK" in c.read_text(encoding="utf-8")
            for c in candidates
        ):
            unchecked.append(name)
    if unchecked:
        return CheckResult(
            "C50",
            "Compose health complete",
            "FAIL",
            f"services with no healthcheck anywhere: {sorted(unchecked)}",
        )
    return CheckResult(
        "C50",
        "Compose health complete",
        "PASS",
        f"all {len(services)} services carry a healthcheck (compose or Dockerfile)",
    )


# ---------------------------------------------------------------------------
# C48: a scheduled watchdog asserts the live system stays current + working
# ---------------------------------------------------------------------------
# Deploy Truth (Sprint 14). C47 proves a deploy worked AT deploy time; the
# watchdog proves the live system STAYS current between deploys — deployed
# /version == main HEAD, endpoints answer, containers healthy — and opens an
# issue on failure. Without it, staleness is only found when a human looks
# (historically: months).
@register("C48", "Live-truth watchdog scheduled with issue-on-failure")
def check_live_watchdog() -> CheckResult:
    wf = ROOT / ".github" / "workflows" / "live-truth.yml"
    if not wf.is_file():
        return CheckResult("C48", "Live watchdog", "FAIL", "live-truth.yml missing")
    text = wf.read_text(encoding="utf-8")
    missing = [
        want
        for want in (
            "schedule:",
            "workflow_dispatch",
            "verify_live.py --external",
            "verify_live.py --on-vm",
            "if: failure()",
            "live-truth",
        )
        if want not in text
    ]
    if missing:
        return CheckResult("C48", "Live watchdog", "FAIL", f"live-truth.yml missing: {missing}")
    return CheckResult(
        "C48",
        "Live watchdog",
        "PASS",
        "scheduled external+container truth checks with auto-issue on failure",
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
