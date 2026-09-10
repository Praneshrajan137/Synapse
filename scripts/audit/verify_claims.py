"""Verify SYNAPSE claims against code reality.

Each check is one function decorated with ``@register``. Workstreams in
``plans/i-have-finished-most-nifty-sifakis.md`` add new checks here as they
land. The script exits with code 1 if any check FAILS, 0 otherwise.

Run with ``make verify-claims`` or ``python -m scripts.audit.verify_claims``.
``--check`` delegates to ``scripts.audit.registry_gate`` for the gate verdict
(exit ``0`` pass / ``1`` fail / ``2`` unavailable), so a CI step and this script
never disagree about what the registry decided.

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


# R8.7: the four emitted status categories. Every registered check lands in
# exactly one of them, so the four counts sum to TOTAL == len(_CHECKS) and no
# check can be silently omitted from the headline the README is pinned to.
STATUSES: tuple[str, ...] = ("PASS", "FAIL", "PARTIAL", "SKIP")


# The gate vocabulary the E1/E4/E5 gate modules report, mapped onto the four emitted
# registry statuses (purpose-achievement-audit task 12.1).
#
# Two vocabularies are folded in on purpose. The older probes (`runtime_substance`,
# `published_checkpoint_truth`, `doc_truth`, `topic_service_truth`) report
# ``ok``/``fail``/``skip``; the gates added by this feature report
# ``pass``/``fail``/``unavailable`` and, in ``ratchet_truth`` and
# ``published_checkpoint_truth.assess``, a FOURTH state (``skip`` alongside
# ``unavailable``). The three-key mapping those rows used could not express the fourth
# state and would ``KeyError`` on it -- coerced to FAIL by :func:`_run_check`, so never
# silent, but a mapping defect reported as a gate defect.
#
# **Both non-passing states map to SKIP, and neither may ever map to PASS.** A gate that
# could not read its inputs (``unavailable``) and a gate whose subject is absent
# (``skip``) have each established nothing; SKIP is excluded from the published PASS
# count (R2.9) and a SKIP is not a PASS (I-7). A verdict outside this vocabulary raises
# ``KeyError``, which ``_run_check`` coerces to FAIL naming the check -- an unknown
# verdict is a defect, not a pass.
#
# ``declared-unmeasurable`` is the FIFTH member, added with `replay_metrics`' fourth
# outcome (decision-quality-proof session 6, obstruction 2.5 disposition (b)), **and the
# paragraph above is exactly the trap it fell into**: the new state reached C71 before it
# reached this table, `_run_check` coerced the ``KeyError`` to FAIL, and the registry
# counts moved SKIP 11 -> 10 / FAIL 2 -> 3, which drifted the README headline and
# reddened C56 one gate ahead of the step the change was meant to unblock. It maps to
# **SKIP**, for the same reason ``unavailable`` does: a floor whose measurement is
# declared unobtainable in CI has established nothing about that floor. The gate's own
# exit code is 0 there so a step can gate on the floors it CAN measure; this registry row
# is the stricter surface and says the floor went unmeasured. Two vocabularies, one fact,
# and the strict reading is the one the published counts carry.
GATE_STATUS: dict[str, str] = {
    "pass": "PASS",
    "ok": "PASS",
    "fail": "FAIL",
    "skip": "SKIP",
    "unavailable": "SKIP",
    "declared-unmeasurable": "SKIP",
}


class StatusPartitionError(RuntimeError):
    """The emitted counts do not partition the registered checks (R8.7)."""


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
STRYKER_BREAK_MIN = 20  # never let it drop below this
# Mirrors `frontend/stryker.conf.json`'s shipped `thresholds.break`. Sprint 13 Phase 4.1
# bumped the config 26 -> 50 (json-canonical.ts reached a 96.30% kill rate) and this
# mirror was never moved with it, which C70 reports as "a gate comparing against the
# constant cannot catch a regression to it": frozen at 26, the check accepted any config
# value >= 26, so a silent regression from the shipped 50 down to 26 would have passed.
# Raising the mirror to the value the config already ships STRENGTHENS the gate - it is
# not a ratchet raise, because the enforced floor is `stryker.conf.json` and that is
# unchanged. Next destinations stay 70 -> 85 (CLAUDE.md: <15% survival = >=85% killed);
# move this line in the same commit as the config, never ahead of it.
STRYKER_BREAK_NOW = 50
STRYKER_TARGET = 85  # CLAUDE.md target (<15% survival)


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
            problems.append(f"{svc_name}: image name '{m.group('name')}' != expected '{ar_image}'")

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
        return CheckResult("C27", "verify_images coverage", "FAIL", "IMAGES=(...) array not found")
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
        return CheckResult(
            "C28", "Per-package coverage", "FAIL", "scripts/coverage_per_package.py missing"
        )
    if not floors.is_file():
        return CheckResult("C28", "Per-package coverage", "FAIL", "coverage-floors.yaml missing")
    if not ci.is_file() or "coverage_per_package.py" not in ci.read_text(encoding="utf-8"):
        return CheckResult(
            "C28", "Per-package coverage", "FAIL", "ci.yml does not invoke the script"
        )
    try:
        import yaml as _yaml  # local import; PyYAML is a dev dep
    except ImportError:
        return CheckResult("C28", "Per-package coverage", "SKIP", "PyYAML not installed")
    doc = _yaml.safe_load(floors.read_text(encoding="utf-8")) or {}
    pkgs = doc.get("packages", {})
    expected_count = 10  # synapse_common + orchestrator + 8 agents
    if len(pkgs) < expected_count:
        return CheckResult(
            "C28",
            "Per-package coverage",
            "FAIL",
            f"floors YAML has {len(pkgs)} packages, expected >={expected_count}",
        )
    bad = [p for p, cfg in pkgs.items() if float(cfg.get("line", -1)) < 0]
    if bad:
        return CheckResult(
            "C28",
            "Per-package coverage",
            "FAIL",
            f"negative line floor in: {bad}",
        )
    return CheckResult(
        "C28",
        "Per-package coverage",
        "PASS",
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
        text,
        re.MULTILINE,
    )
    if section and re.search(
        r"^\s*branch\s*=\s*true\b", section.group(1), re.IGNORECASE | re.MULTILINE
    ):
        return CheckResult("C29", "Branch coverage", "PASS", "branch = true in [tool.coverage.run]")
    return CheckResult(
        "C29",
        "Branch coverage",
        "FAIL",
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
        targets_re = (
            r"agents/.*?/training/rewards\.py|guardrails/rules\.py|audit/(hash_chain|logger)\.py"
        )
        has_target = re.search(targets_re, text)
        if has_pr and has_target:
            return CheckResult(
                "C30",
                "mutmut PR gate",
                "PASS",
                f"PR-trigger + Python mutation target found in {wf.name}",
            )
    return CheckResult(
        "C30",
        "mutmut PR gate",
        "FAIL",
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
            "C31",
            "Spec coverage",
            "FAIL",
            "check_spec_coverage.py not invoked with --threshold in ci.yml",
        )
    threshold = int(m.group(1))
    if threshold < 10:
        return CheckResult(
            "C31",
            "Spec coverage",
            "FAIL",
            f"--threshold {threshold} below hard floor 10",
        )
    return CheckResult(
        "C31",
        "Spec coverage",
        "PASS",
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
            "C32",
            "Training omit",
            "FAIL",
            "broad `*/training/*` omit pattern present — re-hides rewards.py from coverage",
        )
    # Affirmative check: at least the narrow patterns are present (loop, train_*).
    if re.search(r'"\*/training/loop\.py"', text):
        return CheckResult(
            "C32",
            "Training omit",
            "PASS",
            "narrow training-loop omit pattern present; rewards.py is measurable",
        )
    return CheckResult(
        "C32",
        "Training omit",
        "PARTIAL",
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
            "C34",
            "I-12 wired",
            "PASS",
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
        dec_t.count("Depends(CurrentOperator)") >= 2 and "Depends(RequireRole(Role.OPS))" in dec_t
    )
    # No embedded DB credential anywhere under api/ (decisions, main, steering, …).
    api_dir = ROOT / "api"
    leaks = _grep(r"synapse_app_2026", api_dir, glob="*.py")
    no_secret = not leaks
    if auth_on_reads and no_secret:
        return CheckResult(
            "C35",
            "API auth",
            "PASS",
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
            "C36",
            "Honesty contract",
            "FAIL",
            f"missing modules={missing_mods} adrs={missing_adrs}",
        )
    return CheckResult(
        "C36",
        "Honesty contract",
        "PASS",
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
    detail = (
        f"{real}/{len(reports)} real gradient loops; {total} violation(s) (baseline {BASELINE})"
    )
    if total > BASELINE:
        return CheckResult("C37", "Training truth", "FAIL", detail + " — regression")
    return CheckResult("C37", "Training truth", "PASS", detail)


@register("C38", "Training produces loadable, content-hashed checkpoints")
def check_checkpoint_truth() -> CheckResult:
    try:
        from scripts.audit.checkpoint_truth import collect
    except ImportError as exc:
        return CheckResult(
            "C38", "Checkpoint truth", "SKIP", f"checkpoint_truth import failed: {exc}"
        )
    report, any_artifact = collect()
    failures = [
        r for r in report.results if r.status in {"missing_file", "sha_mismatch", "no_checkpoint"}
    ]
    # verify_claims runs outside the smoke job (no training artifacts), so SKIP when
    # none are present — the CI training-smoke job enforces C38 via the standalone
    # `checkpoint_truth --check` with SYNAPSE_SMOKE_RUN=1. _ = CHECKPOINT_AGENTS.
    if not any_artifact:
        return CheckResult(
            "C38", "Checkpoint truth", "SKIP", "no training artifacts (run the smoke job)"
        )
    if failures:
        return CheckResult("C38", "Checkpoint truth", "FAIL", f"{len(failures)} bad checkpoint(s)")
    return CheckResult(
        "C38", "Checkpoint truth", "PASS", f"{len(report.results)} checkpoint(s) verified"
    )


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
    detail = (
        f"{wired}/{len(reports)} agents load a real model (baseline unwired {BASELINE_UNWIRED})"
    )
    if unwired > BASELINE_UNWIRED or regressions > 0:
        return CheckResult("C39", "Serving truth", "FAIL", detail + " — regression")
    return CheckResult("C39", "Serving truth", "PASS", detail)


@register("C40", "Prediction intervals achieve nominal coverage")
def check_calibration_truth() -> CheckResult:
    try:
        from scripts.audit.calibration_truth import collect
    except ImportError as exc:
        return CheckResult(
            "C40", "Calibration truth", "SKIP", f"calibration_truth import failed: {exc}"
        )
    report, any_artifact = collect()
    failures = [r for r in report.results if r.status in {"below_floor", "no_metric"}]
    if not any_artifact:
        return CheckResult(
            "C40", "Calibration truth", "SKIP", "no training artifacts (run the smoke job)"
        )
    if failures:
        return CheckResult(
            "C40", "Calibration truth", "FAIL", f"{len(failures)} under-covered model(s)"
        )
    return CheckResult(
        "C40", "Calibration truth", "PASS", f"{len(report.results)} model(s) calibrated"
    )


@register("C41", "Declared confidence_basis matches computed basis (ratchet)")
def check_confidence_basis_truth() -> CheckResult:
    try:
        from scripts.audit.confidence_basis_truth import BASELINE, collect
    except ImportError as exc:
        return CheckResult(
            "C41", "Confidence basis", "SKIP", f"confidence_basis_truth import failed: {exc}"
        )
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
        return CheckResult(
            "C45", "Runtime substance", "SKIP", f"runtime_substance import failed: {exc}"
        )
    probe = evaluate()
    status = GATE_STATUS[probe.status]
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
            "C7",
            "Orchestrator twin",
            "FAIL",
            f"missing defs={sorted(missing_defs)} calls={sorted(missing_calls)} "
            f"endpoint={has_endpoint}",
        )
    return CheckResult(
        "C7",
        "Orchestrator twin",
        "PASS",
        "Tier-4 twin verify + input-provenance recording wired (defined + called)",
    )


@register("C46", "A real, published production checkpoint serves at $0")
def check_published_checkpoint() -> CheckResult:
    """Authenticity counterpart to C42 (ADR-043, Phase 1).

    C42 proves the serving *code path* is real on the CI smoke checkpoint. C46
    proves an operator actually published a genuine, non-smoke, adequately
    calibrated checkpoint to the $0 serving source (HF Hub) and recorded it.
    SKIPs when DP_HF_REPO is unset or the registry is still a placeholder — never
    fabricates a pass; FAILs only on a smoke/under-covered/drifted published model.

    Every branch reports ``cid="C46"``: this SKIP branch previously returned
    ``"C43"``, so an unavailable published-checkpoint probe landed on another
    check's row and left C46 with no result (R10.5, design AD-14).
    """
    try:
        from scripts.audit.published_checkpoint_truth import evaluate as _eval_pub
    except ImportError as exc:
        return CheckResult(
            "C46",
            "Published checkpoint",
            "SKIP",
            f"published_checkpoint_truth import failed: {exc}",
        )
    probe = _eval_pub()
    status = GATE_STATUS[probe.status]
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
        return CheckResult(
            "C42",
            "Read/write table match",
            "FAIL",
            "could not resolve AuditConsensusRow.__tablename__",
        )

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
        "demand_prophet",
        "routing_navigator",
        "inventory_sentinel",
        "freshness_guardian",
        "pricing_oracle",
        "disruption_shield",
        "supplier_trust",
        "sustainability_agent",
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
            "C43",
            "Agents serve /a2a",
            "FAIL",
            f"{len(missing)} agent(s) missing POST /a2a: {', '.join(missing)}",
        )
    return CheckResult(
        "C43",
        "Agents serve /a2a",
        "PASS",
        f"all {len(expected)} agents mount POST /a2a (orchestrator consensus reachable)",
    )


# ---------------------------------------------------------------------------
# C44: module liveness — total classification, named baseline, dormant projections
# ---------------------------------------------------------------------------
@register("C44", "Module liveness: total classification + named baseline + projections")
def check_no_dead_modules() -> CheckResult:
    """Owner concern: "most of the code is there but not used" (R13).

    ``scripts/audit/module_liveness.py`` builds an import graph from the live
    docker-compose entrypoints and classifies every first-party Python module into
    exactly one of five classes — ALIVE / TOOLING / TEST / SEAM_EXEMPT / DEAD — with
    totality checked rather than assumed (R13.1). The only exemption from DEAD is an
    in-source ``# synapse: seam(reason=..., adr=ADR-0NN)`` marker (R13.2), so the
    justification travels with the code. The baseline is the *named* list in
    ``infrastructure/quality/dead-modules.yaml`` and ``DEAD_BASELINE`` is derived from
    it as ``len(dormant)`` (R13.9) — that file is not a suppression list: a name in it
    fixes the count a FAIL is measured against, it never turns a FAIL into a PASS.

    Two projections ride along. R13.7 — a symbol encoding an invariant pre/postcondition
    that only tests invoke — FAILs naming the symbol and the invariant. R13.3 — a
    property test whose target no non-test module imports — is *reported* as validating a
    model (the criterion's verb is "SHALL be reported"), so it never moves the status.

    Expect a FAIL here while ``synapse_common.contracts.validate_audit_insertion`` has no
    production caller. ``orchestrator.guardrails.rules.execute_consensus`` already passes
    — task 8.5's ``_ratify_and_dispatch`` calls it — and so do
    ``uplift.uplift_floor.is_proven_uplift`` / ``ratchet_to_measured``, which task 10.3
    wired into ``uplift_truth.verdict`` / ``uplift_truth.admit_floor_raise``. That
    remaining FAIL is the requirement working. Note it also makes C44's declared
    fault-injection operators read
    *indeterminate* until they clear: a gate that is already red proves nothing by
    staying red, and that is the honest label, not an exemption.
    """
    try:
        from scripts.audit.module_liveness import Outcome, evaluate
    except ImportError as exc:
        return CheckResult(
            "C44", "Module liveness", "SKIP", f"module_liveness import failed: {exc}"
        )

    report = evaluate()
    if report.outcome is Outcome.UNAVAILABLE:
        # I-7: a classification that is not total, or a baseline that cannot be read,
        # has no verdict to give. Absence of proof is not a pass.
        return CheckResult("C44", "Module liveness", "SKIP", report.detail)
    if report.outcome is Outcome.FAIL:
        return CheckResult("C44", "Module liveness", "FAIL", report.detail)
    return CheckResult(
        "C44",
        "Module liveness",
        "PASS",
        f"{report.total_modules} module(s) over 5 classes "
        f"(ALIVE {report.counts.get('ALIVE', 0)} / TOOLING {report.counts.get('TOOLING', 0)} / "
        f"TEST {report.counts.get('TEST', 0)} / SEAM_EXEMPT {report.counts.get('SEAM_EXEMPT', 0)} "
        f"/ DEAD {report.counts.get('DEAD', 0)}); dead <= named baseline "
        f"{report.dead_baseline}; {len(report.model_projections)} model-validating "
        f"projection(s) reported; every invariant symbol on a production path",
    )


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
        return CheckResult("C47", "Deploy truth gated", "FAIL", f"cd-gcp.yml missing: {missing}")
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
        return CheckResult("C49", "Import smoke coverage", "FAIL", "import-smoke step missing")
    rows = re.findall(r"image:\s*([A-Za-z0-9-]+),.*?entry:\s*([A-Za-z0-9_.]+|\"\")", text)
    if not rows:
        return CheckResult("C49", "Import smoke coverage", "FAIL", "no matrix entry fields parsed")
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
            c.is_file() and "HEALTHCHECK" in c.read_text(encoding="utf-8") for c in candidates
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
# C51: Decision outcomes are scored, append-only, never fabricated (ADR-047)
# ---------------------------------------------------------------------------
@register("C51", "Decision outcomes never fabricated")
def check_outcome_truth() -> CheckResult:
    try:
        from scripts.audit.outcome_truth import collect
    except ImportError as exc:
        return CheckResult("C51", "Outcome truth", "SKIP", f"outcome_truth import failed: {exc}")
    reports = collect()
    total = sum(len(v) for _rel, v in reports)
    if total > 0:
        first = next((v[0] for _rel, v in reports if v), None)
        where = f"{first.file}:{first.line} {first.kind}" if first else ""
        return CheckResult(
            "C51",
            "Outcome truth",
            "FAIL",
            f"{total} fabricated/dishonest outcome path(s) - {where}",
        )
    # The scorer + table + the honest pure contract must all be present.
    missing = [
        rel
        for rel in (
            "infrastructure/postgres/08_sprint19_outcomes.sql",
            "data_fabric/jobs/outcome_score.py",
            "packages/synapse_common/outcomes.py",
        )
        if not (ROOT / rel).is_file()
    ]
    if missing:
        return CheckResult("C51", "Outcome truth", "FAIL", f"missing outcome wiring: {missing}")
    return CheckResult(
        "C51",
        "Outcome truth",
        "PASS",
        "0 fabricated outcomes; append-only decision_outcomes + scorer + honest contract present",
    )


# ---------------------------------------------------------------------------
# C52: Operations aggregate endpoints exist + authenticated (ADR-047)
# ---------------------------------------------------------------------------
@register("C52", "Operations aggregate endpoints exist")
def check_operations_endpoints() -> CheckResult:
    system_py = ROOT / "api" / "routers" / "system.py"
    escal_py = ROOT / "api" / "routers" / "escalations.py"
    main_py = ROOT / "api" / "main.py"
    for path in (system_py, escal_py, main_py):
        if not path.is_file():
            return CheckResult("C52", "Operations endpoints", "SKIP", f"{path.name} missing")
    sys_src = system_py.read_text(encoding="utf-8")
    esc_src = escal_py.read_text(encoding="utf-8")
    main_src = main_py.read_text(encoding="utf-8")

    problems: list[str] = []
    if '@router.get("/slo")' not in sys_src:
        problems.append("missing /slo")
    if '@router.get("/calibration")' not in sys_src:
        problems.append("missing /calibration")
    if '@router.get("/analytics")' not in esc_src:
        problems.append("missing /analytics")
    if "escalations.router" not in main_src:
        problems.append("escalations router not mounted")
    # Each supervisory read must be JWT-gated (VIEWER) — a trust surface that
    # leaks to anonymous callers is a different bug.
    if "CurrentOperator" not in sys_src or "CurrentOperator" not in esc_src:
        problems.append("an endpoint is not CurrentOperator-gated")
    if problems:
        return CheckResult("C52", "Operations endpoints", "FAIL", "; ".join(problems))
    return CheckResult(
        "C52",
        "Operations endpoints",
        "PASS",
        "/slo + /calibration + /escalations/analytics mounted and VIEWER-gated",
    )


# ---------------------------------------------------------------------------
# C55: audit_outbox DDL matches the ORM (Sprint 20). Before this the ORM and the
# mounted DDL drifted (the ORM had audit_id/headers/next_attempt_at + an
# outbox_status ENUM; the DDL had message_key/attempts/trace_id + TEXT status),
# so on a fresh DB the enqueue INSERT failed and rolled back the whole
# decision-logging transaction — the orchestrator could log NO decisions.
# ---------------------------------------------------------------------------
@register("C55", "audit_outbox DDL matches the ORM (no schema drift)")
def check_outbox_schema_truth() -> CheckResult:
    try:
        from scripts.audit.outbox_schema_truth import collect
    except ImportError as exc:
        return CheckResult(
            "C55", "Outbox schema truth", "SKIP", f"outbox_schema_truth import failed: {exc}"
        )
    violations = collect()
    total = len(violations)
    if total > 0:
        first = violations[0]
        return CheckResult(
            "C55",
            "Outbox schema truth",
            "FAIL",
            f"{total} ORM<->DDL drift(s) - {first.file} {first.kind}: {first.detail}",
        )
    return CheckResult(
        "C55",
        "Outbox schema truth",
        "PASS",
        "ORM == canonical DDL == docker mirror; outbox enqueue cannot fail on a fresh DB",
    )


@register("C56", "Docs match mechanical reality (no narrative drift)")
def check_doc_truth() -> CheckResult:
    """Phase 0 narrative-truth gate — the one new gate worth adding.

    Pins the load-bearing numbers/cadence claims in CLAUDE.md + workflow headers
    to their mechanical source (the declarative `doc-number-pins.yaml` table, the
    deploy cadence, the README headline counts) and FAILs on drift — closing the
    root cause of the biggest risk in this repo: the narrative silently diverging
    from what the gates enforce.

    `unavailable` maps to SKIP, never PASS: since task 2.5 the aggregate reports
    `unavailable` whenever a *required* claim could not be evaluated, and an `ok`
    sibling no longer supplies a passing verdict for it (R1.6, I-7).
    """
    try:
        from scripts.audit.doc_truth import evaluate as _eval_doc
    except ImportError as exc:
        return CheckResult("C56", "Doc truth", "SKIP", f"doc_truth import failed: {exc}")
    probe = _eval_doc()
    status = GATE_STATUS[probe.status]
    return CheckResult("C56", "Doc truth", status, probe.detail)


@register("C57", "Agentic loop is real (perceive→decide→act→learn)")
def check_agency_loop() -> CheckResult:
    """ADR-052 agency gate — the system is autonomous, not request-response.

    Asserts the five structural loop invariants (SensorLoop triggers consensus on its
    own; it is wired into the orchestrator; the standing WorldRuntime perceives + is
    actuated; consensus learns from the realized world; ≥1 agent execute() actuates)
    and the stub-execute ratchet. A regression to the dormant pipeline fails CI.
    """
    try:
        from scripts.audit.agency_truth import evaluate as _eval_agency
    except ImportError as exc:
        return CheckResult("C57", "Agency loop", "SKIP", f"agency_truth import failed: {exc}")
    probe = _eval_agency()
    return CheckResult("C57", "Agency loop", "PASS" if probe.ok else "FAIL", probe.detail)


# ---------------------------------------------------------------------------
# C58: Decision initiator is typed + autonomous is NEVER mislabeled synthetic
# ---------------------------------------------------------------------------
@register("C58", "Decision initiator typed (autonomous != synthetic)")
def check_initiator_truth() -> CheckResult:
    """ADR-053. The three-way origin (autonomous/synthetic/operator) is:
    * single-owned in synapse_common.synthetic (both prefixes live there),
    * carried additively by the decisions API (/recent + /{id}) and the
      firehose decision envelope (audit logger),
    * and — the load-bearing honesty guarantee — an ``auto-`` decision is
      NEVER classified synthetic.
    """
    try:
        from synapse_common.synthetic import (
            AUTONOMOUS_ORDER_PREFIX,
            initiator_of_order_id,
            is_synthetic_order_id,
        )
    except ImportError as exc:
        return CheckResult("C58", "Initiator truth", "SKIP", f"synthetic import failed: {exc}")

    auto_id = AUTONOMOUS_ORDER_PREFIX + "bengaluru-reorder_point-1"
    if is_synthetic_order_id(auto_id) or initiator_of_order_id(auto_id) != "autonomous":
        return CheckResult(
            "C58", "Initiator truth", "FAIL", "autonomous order misclassified (synthetic/operator)"
        )
    if initiator_of_order_id("synthetic-1-1") != "synthetic":
        return CheckResult("C58", "Initiator truth", "FAIL", "synthetic prefix not classified")
    if initiator_of_order_id("ORD-1") != "operator":
        return CheckResult("C58", "Initiator truth", "FAIL", "operator default broken")

    decisions = (ROOT / "api" / "routers" / "decisions.py").read_text(encoding="utf-8")
    logger_py = (ROOT / "orchestrator" / "audit" / "logger.py").read_text(encoding="utf-8")
    wired = (
        '"initiator"' in decisions
        and "AUTONOMOUS_ORDER_PREFIX" in decisions
        and '"initiator"' in logger_py
        and "initiator_of_decision" in logger_py
    )
    if not wired:
        return CheckResult(
            "C58", "Initiator truth", "FAIL", "initiator not wired into decisions API + firehose"
        )
    return CheckResult(
        "C58",
        "Initiator truth",
        "PASS",
        "three-way origin single-owned; autonomous never synthetic",
    )


# ---------------------------------------------------------------------------
# C59: Autonomy endpoint exists (VIEWER) + the metric channel has a producer
# ---------------------------------------------------------------------------
@register("C59", "Autonomy endpoint + live metric producer exist")
def check_autonomy_visibility() -> CheckResult:
    """ADR-053. The autonomous loop is observable through the gateway:
    * GET /api/v1/system/autonomy joins twin world_state + SensorLoop status,
      VIEWER-gated (never direct-to-twin from the browser),
    * the orchestrator exposes /api/v1/status/autonomy (sensor counters),
    * synapse.metrics.agent finally has a REAL producer (emit_agent_metrics),
    * both new proto schemas exist (I-3).
    """
    system_py = (ROOT / "api" / "routers" / "system.py").read_text(encoding="utf-8")
    serve_py = (ROOT / "orchestrator" / "inference" / "serve.py").read_text(encoding="utf-8")
    signals = (ROOT / "orchestrator" / "consensus" / "firehose_signals.py").read_text(
        encoding="utf-8"
    )
    protocol = (ROOT / "orchestrator" / "consensus" / "protocol.py").read_text(encoding="utf-8")

    gateway_ok = (
        '"/autonomy"' in system_py
        and "CurrentOperator" in system_py
        and "/world/state" in system_py
        and "/api/v1/status/autonomy" in system_py
    )
    orch_ok = "/api/v1/status/autonomy" in serve_py
    producer_ok = (
        "def emit_agent_metrics" in signals
        and "synapse.metrics.agent" in signals
        and "emit_agent_metrics(" in protocol
    )
    schemas_ok = (ROOT / "proto" / "domain" / "world_state.schema.json").exists() and (
        ROOT / "proto" / "domain" / "agent_metric.schema.json"
    ).exists()

    missing = [
        name
        for name, ok in (
            ("gateway /autonomy proxy", gateway_ok),
            ("orchestrator status/autonomy", orch_ok),
            ("metric producer", producer_ok),
            ("proto schemas", schemas_ok),
        )
        if not ok
    ]
    if missing:
        return CheckResult("C59", "Autonomy visibility", "FAIL", "missing: " + ", ".join(missing))
    return CheckResult(
        "C59",
        "Autonomy visibility",
        "PASS",
        "world+sensor proxy, metric producer, proto schemas present",
    )


# ---------------------------------------------------------------------------
# C60: Consensus decisions beat the baseline uplift floor (ADR-042 ratchet)
# ---------------------------------------------------------------------------
@register("C60", "Consensus decisions beat the uplift floor")
def check_uplift_truth() -> CheckResult:
    """ADR-042. The other honesty gates prove SYNAPSE is honest/trained/
    calibrated/auditable; C60 proves it is *intelligent* — that the four-tier
    consensus actually beats a transparent baseline policy on business KPIs.

    **Trigger-aware (AD-9, CF-4).** R2.7 requires the harness to be regenerated in
    the job that evaluates the gate and R2.8 forbids evaluating an artifact read
    from version control, so C60 returns PASS/FAIL only in the job that produced
    its evidence in this run and SKIP everywhere else. Under R2.9 that SKIP is
    excluded from the published PASS count — absence of proof is not a pass (I-7).

    The status comes from ``uplift_truth.registry_status`` so the registry row and
    the ``--check`` exit code are one implementation. Previously this check read a
    single ``headline_uplift`` field and reported PASS on an artifact that
    self-declared ``incomplete: true`` with fidelity ``unknown``; the verdict now
    derives from ``uplift.uplift_floor.is_proven_uplift`` via
    ``uplift_truth.admit``/``verdict`` (purpose-achievement-audit R2).
    """
    try:
        from scripts.audit.uplift_truth import (
            EXIT_UNAVAILABLE,
            admit,
            registry_status,
            resolve_run_context,
            verdict,
        )
    except ImportError as exc:
        return CheckResult("C60", "Uplift truth", "SKIP", f"uplift_truth import failed: {exc}")

    # `verify_claims` is never the generating job: the powered run lives in the
    # scheduled `uplift.yml`, which calls the gate directly with --require-fresh-run.
    context = resolve_run_context(generating_job=False)
    admission = admit(run=context)
    code = verdict(admission.proof) if admission.admitted else EXIT_UNAVAILABLE
    status, detail = registry_status(admission, code)
    return CheckResult("C60", "Uplift truth", status, detail)


# ---------------------------------------------------------------------------
# C61: Oracle auditor — no reintroduced docstring-body mismatch (R8.6 ratchet)
# ---------------------------------------------------------------------------
@register("C61", "Oracle auditor: no reintroduced docstring-body mismatch")
def check_oracle_truth() -> CheckResult:
    """R8. ``tests/oracle/`` is SYNAPSE's "Layer 6": each test compares an
    agent claim to a Digital-Twin simulation. Several docstrings promise a
    measurable bound the body never asserts — the latent lie the oracle auditor
    (``scripts/audit/oracle_truth``) exposes by AST-walking each test.

    C61 is a BASELINE-ALLOWLIST RATCHET, not a green-at-zero gate. Four
    docstring-body mismatches predate this spec (task 13.3 repaired only the
    pricing oracle); wiring a strict zero-gate would fail CI on debt outside
    this spec's scope. So this row PASSES while the current mismatches are a
    SUBSET of ``KNOWN_BASELINE`` and FAILS the moment a NON-allowlisted (new or
    reintroduced) mismatch appears — satisfying R8.6 ("a reintroduced
    docstring-body mismatch fails CI"). The raw ``oracle_truth --check`` stays
    strict (R8.4); only this surfaced row tolerates the known baseline.

    R12 (purpose-achievement-audit task 5.5) adds the second half. The same row
    now also carries the **derived** oracle-layer membership verdict: a test
    registered in the Oracle layer that does not import and invoke the subject it
    names, or whose reference value is not independent of the implementation it
    judges, FAILs naming that test (R12.1, R12.2, R12.6); so does a test whose
    *title* claims the layer while the derivation refuses it. A tolerance bound at
    or above the committed ceiling is reported unconstraining (R12.7). The
    allowlist that carries the pre-existing exceptions is itself validated: an
    entry without both a dated rationale and a stated removal condition is a FAIL
    (R12.5), and it excuses nothing while it is malformed.
    """
    try:
        from scripts.audit.oracle_truth import (
            KNOWN_BASELINE,
            all_mismatches,
            collect,
            evaluate_membership,
            unresolved_mismatches,
        )
    except ImportError as exc:
        return CheckResult("C61", "Oracle truth", "SKIP", f"oracle_truth import failed: {exc}")

    mismatches = all_mismatches(collect())
    unresolved = unresolved_mismatches(mismatches, KNOWN_BASELINE)
    if unresolved:
        ids = ", ".join(sorted(m.node_id for m in unresolved))
        return CheckResult(
            "C61",
            "Oracle truth",
            "FAIL",
            f"{len(unresolved)} reintroduced/new docstring-body mismatch(es): {ids}",
        )

    membership = evaluate_membership()
    if membership.verdict == "unavailable":
        # I-7: a derivation that could not run has established nothing. SKIP is
        # not a PASS, and the registry gate treats an all-SKIP run as non-passing.
        return CheckResult(
            "C61",
            "Oracle truth",
            "SKIP",
            f"oracle-layer membership could not be derived: {membership.reason}",
        )
    if membership.unresolved:
        details = "; ".join(
            f"{finding.rule} ({finding.requirement}): {finding.detail}"
            for finding in membership.unresolved
        )
        return CheckResult(
            "C61",
            "Oracle truth",
            "FAIL",
            f"{len(membership.unresolved)} unresolved oracle-layer finding(s): {details}",
        )
    return CheckResult(
        "C61",
        "Oracle truth",
        "PASS",
        f"{len(mismatches)} mismatch(es), all within known baseline "
        f"({len(KNOWN_BASELINE)} pre-existing) — none reintroduced; "
        f"{len(membership.oracle_members)} test(s) earn Oracle-layer membership "
        f"({len(membership.findings)} allowlisted finding(s), each dated with a "
        "removal condition)",
    )


# ---------------------------------------------------------------------------
# C62: a topic recorded with real consumers has a deployed consuming service
# ---------------------------------------------------------------------------
@register("C62", "Recorded topic consumers resolve to a deployed service")
def check_topic_service_truth() -> CheckResult:
    """R4.7 (purpose-achievement-audit task 10.14). Two legs, one row.

    ``scripts/audit/topic_consumer_truth.py`` was reachable from ``Makefile:22``
    and from nothing else — no workflow, no registry row — so the
    ``consumers`` vs ``consumers_planned`` distinction it enforces could not fail
    anything. This row registers it, and ``topic_service_truth`` adds the leg R4.7
    actually asks for: a topic recorded with real consumers must resolve to a
    service in the deployed compose file, because a subscribe call site in a module
    nothing deploys is code, not a consumer.

    ``unavailable`` maps to SKIP, never PASS: an unreadable compose file or a
    sub-check that could not run establishes nothing about the deployed stack (I-7).
    The exempt declared absences are named in the detail, so the PASS cannot be read
    as proof about bindings this gate does not prove.
    """
    try:
        from scripts.audit.topic_service_truth import evaluate as _eval_topic_services
    except ImportError as exc:
        return CheckResult(
            "C62", "Topic service truth", "SKIP", f"topic_service_truth import failed: {exc}"
        )
    probe = _eval_topic_services()
    status = GATE_STATUS[probe.status]
    return CheckResult("C62", "Topic service truth", status, probe.detail)


# ---------------------------------------------------------------------------
# C63-C65: the enforcement spine's own gates, registered so they can bite
# ---------------------------------------------------------------------------
# purpose-achievement-audit task 2.17. RC-1's finding was that the verification
# apparatus had no consequence attached; these three rows attach it to the three
# spine gates that CAN be registered, and `.github/workflows/truth-gates.yml`
# attaches it to all six by running each as a blocking step.
#
# THREE OF THE SIX SPINE GATES ARE DELIBERATELY NOT REGISTERED HERE, and the reason
# is mechanical rather than a matter of taste:
#
#   * `registry_gate`  IS this registry's driver. `registry_gate.evaluate()` calls
#     `collect_results()`, so a row for it would re-enter the registry from inside
#     the registry -- unbounded recursion, not a check. Its enforcement path is the
#     workflow step, which is the whole point of task 2.17.
#   * `ledger_gen`     projects `docs/state/CURRENT.md` from one `RegistryVerdict`,
#     which it obtains by calling `registry_gate.evaluate()`. Same recursion. Its
#     enforcement path is `ledger_gen --check` in truth-gates. (`doc_truth` executes
#     the suite too, but as a SUBPROCESS behind the `SYNAPSE_DOC_TRUTH_NESTED` guard,
#     which bounds it at depth 1; nothing equivalent exists for an in-process call.)
#   * `doc_truth`      is already registered, as C56.
#
# `unavailable` maps to SKIP in all three rows, never to PASS: a gate that could not
# read its own inputs has established nothing (I-7), and a SKIP is excluded from the
# published PASS count (R2.9).


@register("C63", "Gate-surface record is generated from the workflow tree")
def check_gate_surface_truth() -> CheckResult:
    """R11.1, R11.2, R11.7, R11.9 (purpose-achievement-audit task 2.12, registered 2.17).

    R11's finding was that the aggregate blocking surface of CI is stated nowhere: a
    reader summing CLAUDE.md's gate inventory substantially overestimates what a merge
    to `main` actually runs. `docs/state/GATE_SURFACE.md` is the generated statement,
    and this row is what stops it from drifting: the record is re-projected from the
    parsed workflow files and compared byte-for-byte against the committed copy, so a
    trigger change that stops a gate executing on `push:main` FAILs unless the record
    is regenerated in the same change (R11.2).

    Deliberately duplicated with the `gate_surface --check` step in
    `truth-gates.yml`. The step is the enforcement path that exists even when the
    registry cannot run; the row is what puts the same fact inside the honesty meter
    the README headline is pinned to. They cannot disagree -- both call the same
    projection.
    """
    try:
        from scripts.audit.gate_surface import (
            SURFACE_DOC,
            collect_record,
            render_document,
        )
    except ImportError as exc:
        return CheckResult(
            "C63", "Gate surface truth", "SKIP", f"gate_surface import failed: {exc}"
        )
    record = collect_record()
    if record.workflow_count == 0 or record.step_count == 0:
        return CheckResult(
            "C63",
            "Gate surface truth",
            "SKIP",
            "no workflow step could be parsed, so no surface record could be projected",
        )
    if not SURFACE_DOC.is_file():
        return CheckResult(
            "C63",
            "Gate surface truth",
            "FAIL",
            f"no committed record at {SURFACE_DOC.relative_to(ROOT).as_posix()}; "
            "run `python -m scripts.audit.gate_surface --write`",
        )
    existing = SURFACE_DOC.read_text(encoding="utf-8")
    if existing != render_document(record, existing):
        return CheckResult(
            "C63",
            "Gate surface truth",
            "FAIL",
            f"{SURFACE_DOC.relative_to(ROOT).as_posix()} differs from the parsed "
            f"workflow tree ({record.workflow_count} workflow(s), {record.job_count} "
            f"job(s), {record.step_count} step(s)); regenerate it in the same change "
            "(R11.2, R11.7) -- `python -m scripts.audit.gate_surface --check` prints the diff",
        )
    return CheckResult(
        "C63",
        "Gate surface truth",
        "PASS",
        f"{len(record.rows)} surface row(s) match the parsed tree "
        f"({record.workflow_count} workflow(s), {record.step_count} step(s))",
    )


@register("C64", "Declared-blocking workflow steps propagate their exit status")
def check_workflow_shape_truth() -> CheckResult:
    """R1.8, R6.13, R8.9, R11.3 (purpose-achievement-audit task 2.10, registered 2.17).

    The audit found `|| true`, `|| echo`, and `continue-on-error: true` on steps that
    governance documents call blocking -- including the deploy-time audit verifier and
    the frontend step the workflow itself calls "the REAL effectiveness signal". This
    row makes the shape of the workflow tree mechanical: a step declared in
    `infrastructure/quality/blocking-steps.yaml` that carries a discarding construct
    FAILs naming the file and the step, and a non-propagating step that is NOT declared
    must say `ADVISORY`/`informational` in its own name.

    Expected FAIL on landing, and honestly so: `blocking-steps.yaml` declares the three
    R8.9 frontend entries that still carry `|| true`, precisely so the gate reports the
    unremediated state until task 11.x drops them. That is an honest red gate, not an
    exemption.
    """
    try:
        from scripts.audit.workflow_shape_truth import evaluate as _eval_shape
    except ImportError as exc:
        return CheckResult(
            "C64", "Workflow shape truth", "SKIP", f"workflow_shape_truth import failed: {exc}"
        )
    report = _eval_shape()
    status = GATE_STATUS[report.verdict]
    return CheckResult("C64", "Workflow shape truth", status, report.reason)


@register("C65", "Required-check declaration resolves to real jobs")
def check_required_checks_truth() -> CheckResult:
    """R14.1, R14.2 (purpose-achievement-audit task 2.14, registered 2.17).

    R14 is a boundary, not a divergence: whether a red run BLOCKS a merge lives in
    GitHub branch-protection settings that are not in this tree, so every "blocking"
    claim rests on a fact this repository could not check. `required-checks.yaml` is the
    in-repo half, and this row keeps it resolvable: every declared job must exist in
    the workflow it names, under the exact display string branch protection matches, so
    a rename or removal FAILs naming the job rather than leaving branch protection
    waiting on a check that never reports.

    Scope, stated so the PASS cannot be over-read: this is IN-REPO consistency only. It
    makes no claim about the live configuration -- only a run of
    `.github/workflows/required-checks-reconcile.yml` can, and until one happens the
    declaration's own `reconciliation.status` reads `unverified` (R14.5, R14.6).
    """
    try:
        from scripts.audit.required_checks_truth import evaluate as _eval_required
    except ImportError as exc:
        return CheckResult(
            "C65",
            "Required checks truth",
            "SKIP",
            f"required_checks_truth import failed: {exc}",
        )
    report = _eval_required()
    # `report.reason` is `rule=count` on a failure, which names no subject. AD-4's
    # contract is "exits non-zero NAMING the mutated subject", and this row is the only
    # output `gate_fault_injection` sees (it spawns `--run-check C65` and reads one
    # line), so the leading findings are carried through. Without them a declared
    # falsification could only expect the rule name, and a gate that fails without
    # saying which job failed cannot be acted on.
    named = "; ".join(
        f"{finding.rule} at {finding.workflow}::{finding.job} ({finding.section}): {finding.detail}"
        for finding in report.findings[:2]
    )
    more = "" if len(report.findings) <= 2 else f" (+{len(report.findings) - 2} more)"
    detail = f"{report.reason}; {named}{more}" if report.findings else report.reason
    return CheckResult("C65", "Required checks truth", GATE_STATUS[report.verdict], detail)


# ---------------------------------------------------------------------------
# C66-C72: the remaining audit gates, registered so they can bite
# ---------------------------------------------------------------------------
# purpose-achievement-audit task 12.1. Seven gates existed under `scripts/audit/` with
# a CLI and a property test each, and with NO row here -- so `make verify-claims` could
# not report them and `registry_gate` could not fail on them. That is RC-1's finding in
# its purest form: a gate reachable only by hand is not enforcement.
#
# The ids continue the registry's sparse numbering from C65. **The task's own NOTE said
# to start at C63; that NOTE predates tasks 10.14 and 2.17.** C62 is
# `check_topic_service_truth` and C63/C64/C65 are the three spine gates, so the first
# free id is C66. `required_checks_truth`, the eighth name on 12.1's list, was ALREADY
# registered as C65 by task 2.17 and is deliberately not registered a second time -- two
# rows executing one gate would double-count it in every published total.
#
# Every row maps its gate's verdict through :data:`GATE_STATUS`, so `unavailable` and
# `skip` both become SKIP and neither can become PASS (I-7, R2.9).
#
# `registry_gate`, `ledger_gen` and `doc_truth`'s in-process twin remain unregistered for
# the recursion reason recorded above C63. `gate_fault_injection` is different and IS
# registerable: it reads `verify_claims._CHECKS` for the id list only and never executes
# a check, so registering it introduces no re-entry.


@register("C66", "Named audit commands resolve to a real module, script, or entry point")
def check_command_path_truth() -> CheckResult:
    """R6.14 (purpose-achievement-audit task 2.16, registered 12.1).

    The finding was a governance document naming a verification command that resolves to
    nothing -- a step that cannot run reported as a gate that does. This row resolves
    every command named by an audit-verification step in `.github/workflows/**` and in
    the `Makefile` against the tree: a `python -m` module that does not exist, a console
    script with no entry point, and a script path that is not a file each FAIL naming the
    source, the step, and the unresolvable command. The second rule is the exit-status
    rule: such a step must not discard the status of the command it names.

    An input naming no audit-verification step at all reports `unavailable` -> SKIP, not
    PASS: a resolution gate with nothing to resolve has proved nothing (I-7).
    """
    try:
        from scripts.audit.command_path_truth import evaluate as _eval_commands
    except ImportError as exc:
        return CheckResult(
            "C66", "Command path truth", "SKIP", f"command_path_truth import failed: {exc}"
        )
    report = _eval_commands()
    unresolved = sum(1 for command in report.commands if not command.resolves)
    # Same reason as C65: the gate's own `reason` is `rule=count`, and R6.14's finding is
    # only actionable when the source, the step and the unresolvable command are named.
    named = "; ".join(
        f"{finding.rule} at {finding.source}::{finding.scope} step "
        f"'{finding.step_name}': {finding.subject} -- {finding.detail}"
        for finding in report.findings[:2]
    )
    more = "" if len(report.findings) <= 2 else f" (+{len(report.findings) - 2} more)"
    return CheckResult(
        "C66",
        "Command path truth",
        GATE_STATUS[report.verdict],
        f"{len(report.commands)} named command(s), {unresolved} unresolved; {report.reason}"
        + (f"; {named}{more}" if report.findings else ""),
    )


@register("C67", "Audit-chain anchors are fresh enough to verify the chain externally")
def check_anchor_truth() -> CheckResult:
    """R6.11, R6.12 (purpose-achievement-audit task 7.4, registered 12.1).

    An external anchor is what lets a third party check the hash chain without trusting
    this repository, and the freshness bound is what stops a years-old commitment being
    read as a current one. `chain_status` is carried into the detail on purpose: it has
    exactly two values, `anchored` and `unverifiable`, and NEITHER of them is
    `verified` -- walking the chain against the anchored head is a separate job. A PASS
    here means "a fresh commitment exists to walk against", never "the chain is intact".

    No anchor, and an anchor staler than the committed bound, are both `unavailable` ->
    SKIP. That is the honest reading: whatever else is green, an unanchored chain is not
    verifiable from outside, and calling that a pass would be the exact over-claim R6.11
    exists to prevent. Locally the anchor directory is normally empty, so this row reads
    SKIP off the dev box; the publisher is
    `.github/workflows/publish-audit-anchor.yml`.
    """
    try:
        from scripts.audit.anchor_truth import SettingsUnavailableError
        from scripts.audit.anchor_truth import evaluate as _eval_anchors
    except ImportError as exc:
        return CheckResult("C67", "Anchor truth", "SKIP", f"anchor_truth import failed: {exc}")
    try:
        report = _eval_anchors()
    except SettingsUnavailableError as exc:
        return CheckResult(
            "C67",
            "Anchor truth",
            "SKIP",
            f"the committed anchor settings could not be read, so no bound was applied: {exc}",
        )
    return CheckResult(
        "C67",
        "Anchor truth",
        GATE_STATUS[report.verdict],
        f"chain={report.chain_status}, {len(report.anchors)} anchor file(s); {report.reason}",
    )


@register("C68", "World-feed provenance: the declared source class matches the code")
def check_feed_provenance() -> CheckResult:
    """R4.8 (purpose-achievement-audit task 5.7 / ADR-050, registered 12.1).

    The finding was a `WorldSource` whose name and docstring promise an external feed
    while its body returns a seeded draw or an empty list. This row classifies every
    production implementation from its own body and FAILs when the derived class
    contradicts the declared one, when a declared class is outside the three the audit
    schema permits, or when a candidate file could not be parsed at all.

    Scope, stated so the PASS cannot be over-read. This gate settles the STATIC half:
    whether a feed-capable implementation exists and whether every implementation's
    declaration matches its body. It makes NO claim that the loop actually ran on
    external data -- that evidence is `decision_data_provenance` rows carrying
    `source_class = 'EXTERNAL'` (AD-10), which only a job with the database in front of
    it can count, so `external_decisions` is zero in this row by construction and
    `externally_driven` is therefore reported as `no`. "Nobody measured it" is the honest
    reading, not a failure and never a pass (I-7).

    Composed from `collect()` rather than a module-level `evaluate()`, because
    `feed_provenance` exposes no report object; the CLI's own `--check` rule (non-zero
    iff there is a violation) is reproduced here exactly.
    """
    try:
        from scripts.audit.feed_provenance import (
            DECLARABLE,
            UNCLASSIFIED,
            collect,
            external_implementation_present,
        )
    except ImportError as exc:
        return CheckResult(
            "C68", "Feed provenance", "SKIP", f"feed_provenance import failed: {exc}"
        )
    reports, scan_errors = collect()
    violations = [v for report in reports for v in report.violations] + scan_errors
    if not reports:
        return CheckResult(
            "C68",
            "Feed provenance",
            "SKIP",
            "no WorldSource implementation was classified, so no declaration was checked; "
            "absence of a scan is not a pass (I-7)",
        )
    if violations:
        named = "; ".join(f"{v.file}:{v.line} {v.kind}: {v.detail}" for v in violations[:4])
        more = "" if len(violations) <= 4 else f" (+{len(violations) - 4} more)"
        return CheckResult(
            "C68",
            "Feed provenance",
            "FAIL",
            f"{len(violations)} provenance violation(s) over "
            f"{len(reports)} implementation(s): {named}{more}",
        )
    counts = {
        cls: sum(1 for report in reports if report.derived == cls)
        for cls in (*DECLARABLE, UNCLASSIFIED)
    }
    summary = ", ".join(f"{cls}={counts[cls]}" for cls in (*DECLARABLE, UNCLASSIFIED))
    capable = external_implementation_present(reports)
    return CheckResult(
        "C68",
        "Feed provenance",
        "PASS",
        f"{len(reports)} implementation(s) classified ({summary}); external feed capability: "
        f"{'present' if capable else 'absent'}. This row asserts declaration-vs-body "
        "agreement only -- whether the loop RAN on external data is counted from "
        "decision_data_provenance by a job with the database, and is not claimed here",
    )


@register("C69", "Completed task records resolve to landed work, not a placeholder")
def check_task_claim_truth() -> CheckResult:
    """R3.6 (purpose-achievement-audit task 10.8, registered 12.1).

    R3.6's finding was a spec task marked `[x]` for publishing a checkpoint while the
    serving registry still held `__placeholder__` -- a completion claim with nothing
    behind it. This row makes that mechanical: a checked task whose committed subject is
    still absent FAILs naming the spec, the task id, and the subject it claims.

    **Expected FAIL on landing, and deliberately not softened (I-7).**
    `core-purpose-uplift` tasks 9 and 9.1 are `[x]` against an unchanged
    `__placeholder__`, so this row reddens the registry the moment it is registered. That
    is R3.6's finding becoming a gate, which is what this feature is for -- not a gate
    defect, and not something to allowlist. It clears when the claim is retracted or the
    checkpoint is genuinely published.

    An unreadable specs root or policy reports `unavailable` -> SKIP, never PASS: no scan
    is not a clean scan.
    """
    try:
        from scripts.audit.task_claim_truth import evaluate as _eval_claims
    except ImportError as exc:
        return CheckResult(
            "C69", "Task claim truth", "SKIP", f"task_claim_truth import failed: {exc}"
        )
    report = _eval_claims()
    return CheckResult(
        "C69",
        "Task claim truth",
        GATE_STATUS[report.outcome.value],
        f"{report.records_scanned} task record(s) over {len(report.specs_scanned)} spec(s), "
        f"registry={report.registry_state}; {report.detail}",
    )


@register("C70", "Ratcheted thresholds never regress and agree with what they guard")
def check_ratchet_truth() -> CheckResult:
    """R7.4, R7.8, R2.10 (purpose-achievement-audit task 4.3, registered 12.1).

    Two clauses over `infrastructure/quality/ratchets.json`. MONOTONICITY: a committed
    threshold on the wrong side of its recorded bound FAILs naming both values, so a
    quietly loosened floor stops a merge instead of stopping nothing. CONFIG AGREEMENT: a
    ratchet constant that sits below the configuration it claims to guard cannot catch a
    regression to itself, so the disagreement is itself a failure.

    **Expected FAIL on landing.** The live example is the one the audit found: the
    frontend ships `thresholds.break: 50` while `STRYKER_BREAK_NOW` here is frozen at 26,
    so a regression 50 -> 26 passes C16 today. `ratchets.json` records that as
    `agrees_with_shipped: false`, and recording it does not excuse it. Repairing the
    constant needs a coordinated change across `CLAUDE.md`, `doc-number-pins.yaml` and
    `tests/verify/test_ratchet_monotonicity_property.py` (whose docstring names 12.1 as
    the repair point and whose assertions pin the hole), so it is reported rather than
    half-done -- an honest red gate, not an exemption.

    A row with no measurement behind it reports `skip`, and the aggregate orders
    FAIL > UNAVAILABLE > SKIP > PASS so an absent measurement can never mask a
    regression. Both `skip` and `unavailable` map to SKIP here; neither is a pass.
    """
    try:
        from scripts.audit.ratchet_truth import evaluate as _eval_ratchets
    except ImportError as exc:
        return CheckResult("C70", "Ratchet truth", "SKIP", f"ratchet_truth import failed: {exc}")
    report = _eval_ratchets()
    failing = [row for row in report.ratchets if row.outcome.value == "fail"]
    unmeasured = sum(1 for row in report.ratchets if row.outcome.value == "skip")
    if failing:
        named = "; ".join(row.detail for row in failing[:3])
        more = "" if len(failing) <= 3 else f" (+{len(failing) - 3} more)"
        detail = f"{len(failing)} of {len(report.ratchets)} ratchet(s) breached: {named}{more}"
    else:
        detail = (
            f"{len(report.ratchets)} ratchet(s) hold their recorded bounds; "
            f"{unmeasured} carry no measurement, so they are declared values only "
            "(SKIP, never PASS)"
        )
    return CheckResult("C70", "Ratchet truth", GATE_STATUS[report.outcome.value], detail)


@register("C71", "Replayed KV-cache and tier-routing metrics meet their committed floors")
def check_replay_metrics() -> CheckResult:
    """R7.6, R7.7 (purpose-achievement-audit task 4.5, registered 12.1).

    Two numbers CLAUDE.md has stated since Sprint 9 with no gate anywhere: the KV-cache
    0.70 floor and the tier-routing 80% floor. This row measures both against
    `infrastructure/quality/replay-floors.yaml` by replaying the committed golden traces
    through the real `TierRouter` and reading the real cache gauge.

    A measured breach outranks an unavailability, so an absent measurement can never mask
    a real floor regression; and an unavailability outranks a pass, so absence of proof is
    never a pass (I-7). Off a live Ollama the cache gauge carries no samples, so this row
    reads SKIP rather than reporting a zero -- "no hit rate was measured" is not "the hit
    rate is 0.0", and either of those read as a PASS would be a fabricated measurement.
    Trace-count or seed drift against the generator is also `unavailable`, not a pass:
    a replay over the wrong traces measures the wrong thing.

    **A floor declared unmeasurable in CI reads SKIP here, and that is stricter than the
    gate's own exit code on purpose.** `replay-floors.yaml` may declare a floor
    unmeasurable with its prerequisite, its reason and its procedure, and
    `replay_metrics` then exits 0 so `ci.yml::quality-gates` can gate on the floors it CAN
    measure. This row is the other surface: it reports that the floor went unmeasured, so
    the published PASS count never absorbs a declared absence. A declaration a measurement
    contradicts is `void` and the gate reports FAIL, which arrives here as FAIL unchanged.
    """
    try:
        from scripts.audit.replay_metrics import evaluate as _eval_replay
    except ImportError as exc:
        return CheckResult("C71", "Replay metrics", "SKIP", f"replay_metrics import failed: {exc}")
    report = _eval_replay()
    parts = [
        f"{metric.metric}="
        + ("unmeasured" if metric.measured is None else f"{metric.measured:.4f}")
        + (" (no floor read)" if metric.floor is None else f" vs floor {metric.floor:.2f}")
        + f" [{metric.outcome.value}]: {metric.detail}"
        for metric in report.metrics
    ]
    found = 0 if report.traces_found is None else report.traces_found
    return CheckResult(
        "C71",
        "Replay metrics",
        GATE_STATUS[report.outcome.value],
        f"{found} golden trace(s) from {report.traces_dir or '(unresolved)'}; " + "; ".join(parts),
    )


@register("C72", "Every gate declares a mutation that falsifies it")
def check_gate_fault_injection() -> CheckResult:
    """R1.2, R9.5, R12.3, R12.7 (purpose-achievement-audit task 5.1, registered 12.1).

    AD-4's requirement is that a gate prove it can fail. `gate-mutations.yaml` declares,
    per check, a mutation that MUST make that check exit non-zero naming the mutated
    subject. This row validates the declaration against its schema and against this
    registry: a declared id that no `@register` call declares FAILs, and a
    `completeness.declared_gates` count that disagrees with the `gates:` block FAILs --
    so a hand edit to the declaration is itself detectable.

    Registered with `probe=False`, which is the only form allowed to run here. The sweep
    copies the whole tree and spawns one subprocess per gate plus one per operator; that
    is a CI workload (`ci.yml::uplift-verify`), never a laptop one (I-0). Unprobed, the
    gate's own verdict is `unavailable` -> SKIP, which is the honest label: the
    declaration is valid but nothing was falsified, and absence of proof is not a pass.
    This row therefore reports SKIP in a normal run and FAIL on a declaration defect. It
    can never report PASS outside a `--sweep`, and that asymmetry is deliberate.

    Undeclared registered checks are excluded from PASS-eligibility and named in the
    report; they do not FAIL here. Turning that shortfall into a hard failure would make
    the row permanently red over roughly fifty pre-existing rows -- a gate born red for
    someone else's debt asserts nothing new. The exclusion is the honest label AD-4 asks
    for, and it is recorded, not hidden.

    R1.12 (decision-quality-proof task 5.5). The row used to end in a fixed sentence --
    `no falsification was probed` -- and that sentence was true in every context this
    check runs in, because the sweep is a category-2/3 workload that cannot run inside
    the registry's own process. It is no longer true in the one context that matters:
    `truth-gates.yml::falsification-sweep` runs the sweep and writes its canonical
    report, and this row projects the counts of THAT run when it is pointed at it. Three
    counts, in the units the sweep reports them: probed operators, falsified checks,
    unproven operators.

    Three guards on that projection, because a row that projects the wrong run is worse
    than one that projects none:

    * The path comes from `$SYNAPSE_FAULT_INJECTION_REPORT` when set, and the resolved
      path is named in the detail. Provenance is a claim, so it is stated rather than
      assumed.
    * A payload carrying `probed: false` is not a probe, and one carrying
      `baseline_suppressed: true` proved nothing by construction (R1.16). Either is
      reported as read-but-not-probing, and the row stays with the unprobed detail.
    * When no report is readable at all, the row keeps the unprobed detail and reports
      SKIP -- the honest state of a job in which no sweep ran, and never a PASS (I-7).
    """
    try:
        from scripts.audit.gate_fault_injection import evaluate as _eval_injection
        from scripts.audit.gate_fault_injection import read_sweep_report as _read_sweep
    except ImportError as exc:
        return CheckResult(
            "C72",
            "Gate fault injection",
            "SKIP",
            f"gate_fault_injection import failed: {exc}",
        )

    swept, swept_reason = _read_sweep()
    if swept is not None and swept.probed and not swept.baseline_suppressed:
        return CheckResult(
            "C72",
            "Gate fault injection",
            GATE_STATUS[swept.verdict],
            f"{swept.probed_operators} of {swept.declared_operators} declared operator(s) "
            f"probed, {len(swept.falsified_ids)} check(s) falsified by every declared "
            f"mutation, {len(swept.unproven_operator_ids)} operator(s) unproven; "
            f"{swept_reason}; {swept.reason}",
        )

    report = _eval_injection(probe=False)
    suffix = (
        f"; {swept_reason}, and it reports "
        + ("a suppressed baseline" if swept.baseline_suppressed else "no probe")
        + ", so nothing is projected from it (I-7)"
        if swept is not None
        else f"; {swept_reason}"
    )
    return CheckResult(
        "C72",
        "Gate fault injection",
        GATE_STATUS[report.verdict],
        f"{len(report.declared_ids)} of {len(report.registered_ids)} registered check(s) "
        f"declare a falsification over {report.declared_operators} operator(s), "
        f"{len(report.undeclared_ids)} undeclared and excluded from PASS-eligibility; "
        f"{report.reason}{suffix}",
    )


@register("C73", "The falsification sweep's cost budget is an arithmetic claim that holds")
def check_sweep_budget() -> CheckResult:
    """R1.11 (decision-quality-proof task 5.3).

    `gate-mutations.yaml::sweep_budget` commits three numbers and one inequality over
    them. The inequality was worked once, in a comment, against counts that were true
    that day: 30 subprocesses at 90s plus a 420s install allowance against a 3600s job.
    A comment is not a gate, and a fifteenth declaring check -- or a second operator on
    an existing one -- would make the committed budget stop fitting with nothing to say
    so. This row is the gate: `sweep_budget_truth` re-derives BOTH counts from the
    declaration's own `gates:` block through the pointers the declaration itself commits,
    and asserts the inequality over them.

    It also pins the third number to its consumer. `job_timeout_minutes` is documented as
    "MUST equal `timeout-minutes` on the job that runs the sweep"; unchecked, that leaves
    the inequality verified against a job budget the job does not have. The gate resolves
    `truth-gates.yml::falsification-sweep` and compares.

    Nothing here measures a duration. The bounds are committed, and the declaration says
    so in its own words; a gate that cannot answer inside the per-subprocess bound reports
    `indeterminate` naming the timeout, which is non-passing and therefore surfaces. What
    this row establishes is narrower and checkable: that the committed numbers are
    consistent with each other, with the declared operator set, and with the job that
    hosts them.

    `unavailable` -> SKIP for an absent budget, an absent `derivation` block, an
    unresolvable sweep job, or a `declared_gates` count that disagrees with `gates:` (that
    last drift is C72's finding and is not re-reported here as a second FAIL). SKIP is
    non-passing and is never a PASS (I-7).
    """
    try:
        from scripts.audit.sweep_budget_truth import assess as _assess_budget
    except ImportError as exc:
        return CheckResult(
            "C73", "Sweep budget", "SKIP", f"sweep_budget_truth import failed: {exc}"
        )
    report = _assess_budget()
    return CheckResult(
        "C73", "Sweep budget", GATE_STATUS[report.verdict], report.reason
    )


@register("C74", "External-dataset licence terms are recorded, schema-valid and confirmed")
def check_dataset_licence() -> CheckResult:
    """R8.1, R8.2, R8.16 (decision-quality-proof task 7.2).

    There is no dataset-licence gate anywhere else in the tree, so this row is the whole
    of the mechanism. `dataset_licence_truth` reads
    `infrastructure/data/dataset-licences.yaml`, validates it against its committed
    draft-07 schema, and reports every field that is absent, malformed or explicitly
    unconfirmed -- by name, per dataset.

    R8.16's "before the first ingestion" is enforceable only on the change that performs
    the ingestion, which is why this lives in the Check_Registry:
    `truth-gates.yml::truth-gates` runs the registry on every push and pull request,
    including Markdown-only ones, so no ingesting change can avoid it. The runtime
    companion is `data_fabric/ingest/m5.py::record_ingestion`, which REFUSES to record an
    ingestion whose licence entry is unconfirmed, whose dataset is undeclared, or whose
    revision disagrees with the revision the terms were read against. This row reports;
    that refusal enforces. Neither alone is enough -- a gate can be merged around, and a
    refusal inside a job nobody reads is invisible.

    Two non-passing verdicts, split on WHY rather than on severity. An **absent or null**
    field, an unparseable artifact, an unreadable schema, a schema that is not itself a
    valid draft-07 schema, or a register declaring no dataset at all is `unavailable` ->
    SKIP: nobody knows the term, and a term nobody knows must never be able to read as a
    permissive one. A field that is **present and wrong** -- a `read_date` that is not a
    date, an empty `permitted_use` -- or a `confirmation.confirmed` flag that contradicts
    its own fields is a FAIL: somebody wrote that value in this tree. Both are non-passing,
    so R8.2's "non-passing result IF any declared field is absent or fails schema
    validation" holds under either branch; the split is what makes the report actionable,
    because "go and read the terms" and "fix the value you wrote" are different work for
    different people. `LicenceFinding.fatal` carries that distinction per finding.

    **Completeness has exactly one owner.** The six R8.1 fields are deliberately NOT in the
    schema's `required` list and default to `None` on the model, so an ABSENT key and a NULL
    key are the same fact and produce one verdict. Had the schema required them, a dropped
    key would surface as `schema-invalid` -> FAIL while a null key surfaced as
    `field-absent` -> SKIP: two verdicts for "nobody established this term", decided by
    whichever mechanism noticed first. What the schema owns is the complementary half -- a
    term that is PRESENT must be well-formed -- and it is constructed WITH a format checker,
    because `format` is annotation-only in draft-07 by default and `read_date: "banana"`
    would otherwise validate. `DatasetLicence` re-checks the date at the model layer too,
    since `load_licence_document` deliberately skips JSON-Schema validation on the runtime
    ingestion path.

    **`confirmed` is derived, never read.** `DatasetLicence.confirmed` is computed from
    whether every R8.1 field is non-null; the artifact's own `confirmation.confirmed` flag is
    only ever compared against it, via `flag_disagrees()`. A boolean that can disagree with
    its own subject is a claim, not evidence -- the same shape that let
    `published_checkpoint_truth.evaluate` fall through from `UNAVAILABLE` to `ok`. Note the
    asymmetry: over-claiming (`confirmed: true` beside a null term) is a FAIL, while
    under-claiming (every field populated, flag still false) is not a finding at all -- that
    is an operator mid-procedure, and failing it would punish the honest half of the work.

    The runtime companion is `data_fabric/ingest/m5.py::record_ingestion`, which REFUSES to
    record an ingestion whose licence entry is unconfirmed, whose dataset is undeclared, or
    whose revision disagrees with the revision the terms were read against. This row
    reports; that refusal enforces (I-6: a hard guardrail beats a learned policy). Neither
    alone is enough -- a gate can be merged around, and a refusal inside a job nobody reads
    is invisible.

    **Today this row reads SKIP, and that is the honest state, not a defect.** The M5
    licence terms are competition rules requiring acceptance by a logged-in person, so they
    cannot be confirmed by CI or by a code-authoring session. The artifact records
    `licence_id`, `read_date`, `permitted_use`, `dataset_revision` and the redistribution
    disposition as `null` -- a positive assertion of ignorance -- with a `confirmation` block
    naming the operator steps and why they cannot be automated. `dataset_id` and
    `licence_text_uri` ARE populated, because a dataset's identity and the location of its
    terms are establishable from public metadata without reading them; naming where a
    document lives is not a claim to have read it. Writing a plausible `licence_id` such as
    `CC-BY-4.0` instead would be indistinguishable from a fact for every reader downstream
    and is precisely the fabrication I-7 forbids. A SKIP is not a PASS.
    """
    try:
        from scripts.audit.dataset_licence_truth import assess as _assess_licence
    except ImportError as exc:
        return CheckResult(
            "C74", "Dataset licence", "SKIP", f"dataset_licence_truth import failed: {exc}"
        )
    report = _assess_licence()
    return CheckResult(
        "C74", "Dataset licence", GATE_STATUS[report.verdict], report.reason
    )


@register("C75", "Every declared document pin's extractor resolves when actually run")
def check_pin_extractors() -> CheckResult:
    """R5.2, R5.12 (decision-quality-proof task 8.3). AD-13's one-word addition.

    A pin is a triple -- document anchor, mechanical source, extractor. The predecessor
    spec's Property 5 asserts that the two extracted values AGREE and that extraction is
    IDEMPOTENT. It does not assert that the extractor RESOLVES, and that gap is silent: a
    `yaml_path:` naming a key that no longer exists yields nothing, a `json_path:` into a
    restructured file yields nothing, and *nothing compared against nothing agrees*. `None
    == None`. Such a pin reports green having established nothing about the number it was
    written to protect -- the same shape as `published_checkpoint_truth.evaluate` letting an
    `UNAVAILABLE` fall through to `ok`, and as a property passing over a stub returning `[]`.

    Why this cannot be left to C56/`doc_truth`. `doc_truth` only reaches a source extractor
    when the DOCUMENT anchor resolved first, so a long-dead `yaml_path:` sitting behind a
    reworded sentence is never exercised at all. `pin_extractor_truth` inverts that: it runs
    every declared extractor against its declared source UNCONDITIONALLY, independent of the
    document side, and fails naming the pin, the side, the file and the expression.

    This row FAILs on a dead extractor or a dead anchor -- a defect in this tree, fixable in
    the change that broke it. It reports `unavailable` -> SKIP when a declared file is absent
    or the pin table itself cannot be read, because "the file is gone" and "the file is there
    and the expression no longer matches it" are different repairs and only the second is
    evidence that a pin silently stopped measuring.

    `kind: generated` pins are skipped by design and COUNTED in the report: their document
    side is a projection of their source side, so comparing them compares a mechanism to
    itself (the defect AD-21 rejects), and their generator's own `--check` mode owns them.
    The exemption is visible rather than silent.

    Nothing here compares values -- whether the two sides agree is C56's subject. This row
    answers the strictly prior question nobody was asking: did either side produce a value at
    all?
    """
    try:
        from scripts.audit.pin_extractor_truth import assess as _assess_pins
    except ImportError as exc:
        return CheckResult(
            "C75", "Pin extractors", "SKIP", f"pin_extractor_truth import failed: {exc}"
        )
    report = _assess_pins()
    return CheckResult(
        "C75", "Pin extractors", GATE_STATUS[report.verdict], report.reason
    )


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------
def _run_check(cid: str, title: str, fn: Callable[[], CheckResult]) -> CheckResult:
    """Execute one registered check and coerce its outcome into a valid status.

    R8.7 totality: a check that raises, returns the wrong type, or reports a
    status outside ``STATUSES`` must still occupy exactly one emitted category.
    All three cases become an explicit FAIL naming the defect, so a broken
    check surfaces loudly instead of aborting the run or vanishing from the
    counts (which would let the pinned headline overstate reality).

    R10.5 / design AD-14: reported identity is coerced, not trusted. A result
    whose ``cid`` differs from the identifier it was registered under is coerced
    to FAIL naming *both* ids, and is emitted under the registered id. C46's SKIP
    branch returning ``cid="C43"`` is exactly this defect: a check reporting under
    another check's number silently moves a status onto a row it does not own, and
    leaves the registered row with no result at all. The guard runs after the
    status coercion and over its output, so a result carrying both defects is
    still reported under the id that was registered.
    """
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001 - a crashing check is a FAIL, not an omission
        return CheckResult(cid, title, "FAIL", f"check raised {type(exc).__name__}: {exc}")
    if not isinstance(result, CheckResult):
        return CheckResult(
            cid, title, "FAIL", f"check returned {type(result).__name__}, expected CheckResult"
        )
    if result.status not in STATUSES:
        result = CheckResult(
            result.cid or cid,
            result.title or title,
            "FAIL",
            f"check reported unknown status {result.status!r} "
            f"(expected one of {', '.join(STATUSES)}); detail was: {result.detail}",
        )
    if result.cid != cid:
        return CheckResult(
            cid,
            title,
            "FAIL",
            f"check registered as {cid} reported under {result.cid!r}: a check must "
            f"report the identifier it is registered under; the reported "
            f"{result.status} was: {result.detail}",
        )
    return result


def collect_results() -> list[CheckResult]:
    """Run every registered check exactly once, in registration order."""
    results = [_run_check(cid, title, fn) for cid, title, fn in _CHECKS]
    if len(results) != len(_CHECKS):
        raise StatusPartitionError(
            f"{len(results)} result(s) for {len(_CHECKS)} registered check(s)"
        )
    return results


def status_counts(results: list[CheckResult]) -> dict[str, int]:
    """Partition results into the four emitted categories (R8.7).

    Raises ``StatusPartitionError`` when the four counts do not sum to the
    number of results — the arithmetic guarantee behind the reported TOTAL.
    """
    counts = {status: 0 for status in STATUSES}
    for r in results:
        if r.status not in counts:
            raise StatusPartitionError(f"{r.cid}: status {r.status!r} outside {STATUSES}")
        counts[r.status] += 1
    if sum(counts.values()) != len(results):
        raise StatusPartitionError(
            f"counts {counts} sum to {sum(counts.values())}, expected {len(results)}"
        )
    return counts


def run(as_json: bool = False, check: bool = False) -> int:
    """Execute every registered check and report.

    Default mode is the historical report: exit ``1`` if any check FAILed, else
    ``0``. ``check=True`` delegates to ``scripts.audit.registry_gate.run`` so the
    gate verdict has exactly one implementation (design E1.2) - identity of the
    executed set, the all-SKIP case, and the ``2`` (unavailable) exit code all come
    from there rather than being reimplemented here.
    """
    if check:
        # Imported inside the function on purpose: ``registry_gate`` imports this
        # module at its top level, so a module-scope import here would be circular.
        from scripts.audit import registry_gate

        return registry_gate.run(as_json=as_json, check=True)

    results = collect_results()
    counts = status_counts(results)
    pass_n = counts["PASS"]
    fail_n = counts["FAIL"]
    partial_n = counts["PARTIAL"]
    skip_n = counts["SKIP"]

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
        if skip_n:
            # A SKIP is NOT a PASS — the claim was not verified in this
            # environment (missing dep/file, or an unpublished artifact).
            # Surface them loudly so a green-looking headline is never mistaken
            # for "everything proven". C46 (a real published model serves at
            # $0) is the load-bearing one to watch here.
            print()
            print(f"NOT VERIFIED -- {skip_n} SKIP (a SKIP is not a PASS):")
            for r in results:
                if r.status == "SKIP":
                    print(f"  [--] {r.cid:>4} {r.title:<40} {r.detail}")

    return 1 if fail_n else 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv, check="--check" in sys.argv))
