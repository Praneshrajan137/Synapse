"""SYNAPSE -- live deployment truth oracle (Deploy Truth, Sprint 14).

One script is the single source of truth for "the deploy works", invoked
from three places: per-deploy (cd-gcp.yml), on a schedule (live-truth.yml
watchdog), and manually (``make verify-live``). Every check is an
ASSERTION that exits non-zero -- never a printed suggestion.

Modes
-----
--external --base-url URL [--expect-sha SHA]
    Probe the public endpoints (what a user sees):
      * GET /version            -> 200, git_sha matches --expect-sha and
                                   is a real CD-built SHA (not dev/unknown)
      * GET /healthz            -> 200 "ok"
      * GET /api/v1/topology    -> 200
      * GET /api/v1/agents      -> exactly 200 (a 307 fails: redirects
                                   are never followed)
      * GET /api/v1/decisions/recent -> 200 or 401 (auth gate alive)
      * GET /ws/firehose        -> 101 WebSocket handshake through nginx

--on-vm [--probe-decision] [--max-restarts N]
    Run on the VM at the repo root. Asserts container truth:
      * every compose service is running (no Created/Restarting/Exited)
      * every service with a healthcheck is healthy
      * RestartCount <= --max-restarts (default 0: fresh deploy)
      * --probe-decision: POST one decision to the orchestrator and
        assert the audit_outbox PUBLISHED count advances (proves
        orchestrator -> audit -> outbox -> dispatcher -> Kafka).

stdlib only (urllib/http.client/subprocess) so it runs on the VM host
and on CI runners without any pip install. ASCII-only output (E-S13-07).
"""

from __future__ import annotations

import argparse
import base64
import http.client
import json
import os
import secrets
import ssl
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

# Statuses a container may legitimately hold right after "Wait for health".
_BAD_STATES = ("created", "restarting", "exited", "paused", "dead")


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one assertion."""

    name: str
    ok: bool
    detail: str


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested in packages/tests/test_verify_live.py)
# ---------------------------------------------------------------------------


def sha_matches(got: str, want: str) -> bool:
    """True when two git SHAs agree on their common prefix (>= 7 chars)."""
    got = got.strip().lower()
    want = want.strip().lower()
    if len(got) < 7 or len(want) < 7:
        return False
    n = min(len(got), len(want))
    return got[:n] == want[:n]


def parse_compose_ps(output: str) -> list[dict[str, Any]]:
    """Parse ``docker compose ps --format json`` output.

    Compose v2 emits NDJSON (one object per line) on recent versions and a
    single JSON array on older ones; accept both.
    """
    text = output.strip()
    if not text:
        return []
    if text.startswith("["):
        loaded = json.loads(text)
        return list(loaded) if isinstance(loaded, list) else [loaded]
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def evaluate_containers(rows: list[dict[str, Any]]) -> list[CheckResult]:
    """Assert every compose service is running and (if checked) healthy."""
    results: list[CheckResult] = []
    if not rows:
        return [CheckResult("containers_present", False, "compose ps returned no services")]
    for row in rows:
        service = str(row.get("Service") or row.get("Name") or "?")
        state = str(row.get("State", "")).lower()
        health = str(row.get("Health", "")).lower()
        if state != "running":
            results.append(CheckResult(f"running:{service}", False, f"state={state or 'missing'}"))
            continue
        if health and health != "healthy":
            results.append(CheckResult(f"healthy:{service}", False, f"health={health}"))
            continue
        results.append(CheckResult(f"up:{service}", True, health or "running"))
    return results


def evaluate_restart_counts(counts: list[tuple[str, int]], max_restarts: int) -> list[CheckResult]:
    """Assert no container exceeded the allowed restart count (crash-loop)."""
    results: list[CheckResult] = []
    for name, count in counts:
        ok = count <= max_restarts
        results.append(
            CheckResult(
                f"restarts:{name}",
                ok,
                f"restart_count={count} (max {max_restarts})",
            )
        )
    return results


def evaluate_status(
    name: str, status: int, allowed: tuple[int, ...], detail: str = ""
) -> CheckResult:
    """Assert an HTTP status is one of the allowed values."""
    ok = status in allowed
    want = "/".join(str(s) for s in allowed)
    return CheckResult(name, ok, detail or f"status={status} (want {want})")


# ---------------------------------------------------------------------------
# External probes
# ---------------------------------------------------------------------------


def _connect(base_url: str, timeout: float) -> http.client.HTTPConnection:
    """Open a connection that never follows redirects.

    TLS verification is disabled on purpose: the demo VM serves a
    self-signed nip.io certificate. This probe asserts deploy truth, not
    transport trust -- image integrity is covered by Cosign verification.
    """
    parts = urlsplit(base_url)
    host = parts.hostname or base_url
    if parts.scheme == "https":
        ctx = ssl._create_unverified_context()  # noqa: S323 - see docstring
        return http.client.HTTPSConnection(host, parts.port or 443, timeout=timeout, context=ctx)
    return http.client.HTTPConnection(host, parts.port or 80, timeout=timeout)


def _http_get(base_url: str, path: str, timeout: float = 20.0) -> tuple[int, str]:
    conn = _connect(base_url, timeout)
    try:
        conn.request("GET", path, headers={"User-Agent": "synapse-verify-live"})
        resp = conn.getresponse()
        return resp.status, resp.read().decode("utf-8", errors="replace")
    finally:
        conn.close()


def check_version(base_url: str, expect_sha: str | None) -> CheckResult:
    try:
        status, body = _http_get(base_url, "/version")
    except OSError as exc:
        return CheckResult("version_sha", False, f"unreachable: {exc}")
    if status != 200:
        return CheckResult("version_sha", False, f"status={status}")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return CheckResult("version_sha", False, f"non-JSON body: {body[:80]}")
    got = str(payload.get("git_sha", ""))
    if got in ("", "dev", "unknown"):
        # E-S12-06: dev/unknown means the image was not produced by CD.
        return CheckResult("version_sha", False, f"git_sha={got!r} (not a CD build)")
    if expect_sha is not None and not sha_matches(got, expect_sha):
        return CheckResult(
            "version_sha", False, f"deployed {got[:12]} != expected {expect_sha[:12]}"
        )
    return CheckResult("version_sha", True, f"git_sha={got[:12]}")


def check_healthz(base_url: str) -> CheckResult:
    try:
        status, body = _http_get(base_url, "/healthz")
    except OSError as exc:
        return CheckResult("healthz", False, f"unreachable: {exc}")
    ok = status == 200 and "ok" in body.lower()
    return CheckResult("healthz", ok, f"status={status} body={body.strip()[:40]!r}")


def check_endpoint(base_url: str, path: str, name: str, allowed: tuple[int, ...]) -> CheckResult:
    try:
        status, _ = _http_get(base_url, path)
    except OSError as exc:
        return CheckResult(name, False, f"unreachable: {exc}")
    return evaluate_status(name, status, allowed)


def check_firehose_ws(base_url: str, path: str = "/ws/firehose") -> CheckResult:
    """Assert the WebSocket upgrade handshake completes (HTTP 101)."""
    key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
    headers = {
        "Upgrade": "websocket",
        "Connection": "Upgrade",
        "Sec-WebSocket-Key": key,
        "Sec-WebSocket-Version": "13",
        "User-Agent": "synapse-verify-live",
    }
    conn = _connect(base_url, timeout=20.0)
    try:
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        return evaluate_status("firehose_ws", resp.status, (101,))
    except OSError as exc:
        return CheckResult("firehose_ws", False, f"unreachable: {exc}")
    finally:
        conn.close()


def run_external(base_url: str, expect_sha: str | None) -> list[CheckResult]:
    return [
        check_version(base_url, expect_sha),
        check_healthz(base_url),
        check_endpoint(base_url, "/api/v1/topology", "topology", (200,)),
        # Exactly 200: http.client never follows redirects, so a 307
        # regression (the trailing-slash bug killed in PR #43) fails here.
        check_endpoint(base_url, "/api/v1/agents", "agents_no_redirect", (200,)),
        # 401 without a token proves the auth gate is alive (C35); a 5xx
        # here was the historical "decisions 503" outage signature.
        check_endpoint(base_url, "/api/v1/decisions/recent", "decisions_auth_gate", (200, 401)),
        check_firehose_ws(base_url),
    ]


# ---------------------------------------------------------------------------
# On-VM probes
# ---------------------------------------------------------------------------


def _compose_cmd(compose_file: str, env_files: list[str]) -> list[str]:
    cmd = ["docker", "compose", "-f", compose_file]
    for env_file in env_files:
        if os.path.exists(env_file):
            cmd.extend(["--env-file", env_file])
    return cmd


def _run(cmd: list[str], timeout: float = 120.0) -> str:
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        cmd, capture_output=True, text=True, timeout=timeout, check=True
    )
    return proc.stdout


def collect_restart_counts(compose_file: str, env_files: list[str]) -> list[tuple[str, int]]:
    ids = _run(_compose_cmd(compose_file, env_files) + ["ps", "-q"]).split()
    counts: list[tuple[str, int]] = []
    for cid in ids:
        out = _run(["docker", "inspect", "--format", "{{.Name}} {{.RestartCount}}", cid]).strip()
        name, _, count = out.rpartition(" ")
        counts.append((name.lstrip("/"), int(count)))
    return counts


def _outbox_published_count(compose_file: str, env_files: list[str]) -> int:
    out = _run(
        _compose_cmd(compose_file, env_files)
        + [
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "synapse",
            "-d",
            "synapse_audit",
            "-tAc",
            "SELECT count(*) FROM audit_outbox WHERE status='PUBLISHED'",
        ]
    )
    return int(out.strip() or "0")


_DECISION_SNIPPET = """
import json, urllib.request
payload = {
    "order_id": "verify-live-%d",
    "store_id": "STORE_BLR_001",
    "items": [{"sku_id": "SKU_DAIRY_001", "quantity": 2}],
}
req = urllib.request.Request(
    "http://localhost:8085/api/v1/decisions",
    data=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(),
    headers={"Content-Type": "application/json"},
)
print(urllib.request.urlopen(req, timeout=90).read().decode())
"""


def probe_decision(compose_file: str, env_files: list[str], wait_seconds: int = 90) -> CheckResult:
    """Trigger one decision and assert it reaches Kafka via the outbox."""
    try:
        before = _outbox_published_count(compose_file, env_files)
    except (subprocess.SubprocessError, ValueError) as exc:
        return CheckResult("decision_flow", False, f"outbox read failed: {exc}")
    snippet = _DECISION_SNIPPET % int(time.time())
    try:
        out = _run(
            _compose_cmd(compose_file, env_files)
            + ["exec", "-T", "orchestrator", "python", "-c", snippet],
            timeout=120.0,
        )
    except subprocess.SubprocessError as exc:
        return CheckResult("decision_flow", False, f"decision POST failed: {exc}")
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        try:
            after = _outbox_published_count(compose_file, env_files)
        except (subprocess.SubprocessError, ValueError):
            after = before
        if after > before:
            return CheckResult(
                "decision_flow",
                True,
                f"outbox PUBLISHED {before}->{after}; response={out.strip()[:120]}",
            )
        time.sleep(5)
    return CheckResult(
        "decision_flow",
        False,
        f"outbox PUBLISHED stuck at {before} after {wait_seconds}s "
        f"(decision response: {out.strip()[:120]})",
    )


def run_on_vm(
    compose_file: str,
    env_files: list[str],
    max_restarts: int,
    with_decision_probe: bool,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    try:
        ps_out = _run(_compose_cmd(compose_file, env_files) + ["ps", "--format", "json"])
        results.extend(evaluate_containers(parse_compose_ps(ps_out)))
    except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
        results.append(CheckResult("compose_ps", False, f"failed: {exc}"))
    try:
        counts = collect_restart_counts(compose_file, env_files)
        results.extend(evaluate_restart_counts(counts, max_restarts))
    except (subprocess.SubprocessError, ValueError) as exc:
        results.append(CheckResult("restart_counts", False, f"failed: {exc}"))
    if with_decision_probe:
        results.append(probe_decision(compose_file, env_files))
    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def report(results: list[CheckResult]) -> int:
    failures = 0
    for result in results:
        marker = "OK" if result.ok else "XX"
        print(f"[{marker}] {result.name}: {result.detail}")
        if not result.ok:
            failures += 1
    total = len(results)
    print(f"-- verify_live: {total - failures}/{total} checks passed --")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--external", action="store_true", help="probe public endpoints")
    mode.add_argument("--on-vm", action="store_true", help="assert container truth")
    parser.add_argument("--base-url", default="", help="public base URL (external)")
    parser.add_argument("--expect-sha", default=None, help="required deployed git SHA")
    parser.add_argument(
        "--compose-file", default="docker/docker-compose.gcp.yml", help="compose file"
    )
    parser.add_argument(
        "--env-file",
        action="append",
        default=None,
        help="env file(s) for compose (repeatable); missing files are skipped",
    )
    parser.add_argument(
        "--max-restarts",
        type=int,
        default=0,
        help="allowed container RestartCount (0 right after a deploy)",
    )
    parser.add_argument(
        "--probe-decision",
        action="store_true",
        help="trigger one decision and assert it reaches the outbox/Kafka",
    )
    args = parser.parse_args(argv)

    if args.external:
        if not args.base_url:
            parser.error("--external requires --base-url")
        results = run_external(args.base_url.rstrip("/"), args.expect_sha)
    else:
        env_files = args.env_file or [".env.gcp", ".env.gcp.local", ".env.gcp.version"]
        results = run_on_vm(args.compose_file, env_files, args.max_restarts, args.probe_decision)
    return report(results)


if __name__ == "__main__":
    sys.exit(main())
