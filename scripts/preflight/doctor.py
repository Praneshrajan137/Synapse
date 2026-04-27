"""``make doctor`` -- pre-flight checks for a fresh-machine SYNAPSE run.

Verifies the host has every dependency the demo needs *before* you spend ten
minutes watching ``docker compose up`` only to discover Ollama is unreachable
or the Bengaluru seed data was never generated.

Each check returns one of three states:

    PASS  -- ready
    WARN  -- the demo will run but something is suboptimal (e.g. no jq)
    FAIL  -- the demo will not work without fixing this

Exit code:
    0 if no FAIL,
    1 if any FAIL.

Run as::

    python scripts/preflight/doctor.py
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class CheckResult:
    name: str
    status: str  # "PASS" | "WARN" | "FAIL"
    detail: str
    fix: str | None = None


# --------------------------------------------------------------------------- checks


def check_python_version() -> CheckResult:
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 11)
    return CheckResult(
        name="python>=3.11",
        status="PASS" if ok else "FAIL",
        detail=f"running {major}.{minor}",
        fix=None if ok else "Install Python 3.11+ (https://www.python.org/downloads/).",
    )


def check_command(name: str, *, hint: str, severity: str = "FAIL") -> CheckResult:
    path = shutil.which(name)
    if path:
        return CheckResult(name=f"{name} on PATH", status="PASS", detail=path)
    return CheckResult(name=f"{name} on PATH", status=severity, detail="missing", fix=hint)


def check_docker() -> CheckResult:
    if shutil.which("docker") is None:
        return CheckResult(
            name="docker",
            status="FAIL",
            detail="missing",
            fix="Install Docker Desktop or Docker Engine (https://docs.docker.com/get-docker/).",
        )
    try:
        out = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return CheckResult(
            name="docker daemon",
            status="FAIL",
            detail=f"docker info failed: {exc}",
            fix="Start the Docker daemon.",
        )
    if out.returncode != 0:
        return CheckResult(
            name="docker daemon",
            status="FAIL",
            detail=out.stderr.strip().splitlines()[-1] if out.stderr else "non-zero exit",
            fix="Start the Docker daemon.",
        )
    return CheckResult(name="docker daemon", status="PASS", detail=out.stdout.strip())


def check_ollama() -> CheckResult:
    """Ollama must be reachable + at least one chat model must be pulled."""
    base = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    if base.startswith("host.docker.internal"):
        # The compose network alias is not reachable from the host; map it.
        base = base.replace("host.docker.internal", "localhost")
    if not base.startswith("http"):
        base = f"http://{base}"
    url = base.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return CheckResult(
            name="ollama reachable",
            status="FAIL",
            detail=f"{url}: {exc}",
            fix=(
                "Install + start Ollama (https://ollama.com), then pull a model: "
                "`ollama pull llama3.1:8b`."
            ),
        )
    models = [m.get("name", "") for m in data.get("models", [])]
    if not models:
        return CheckResult(
            name="ollama models",
            status="FAIL",
            detail="ollama is up but has no models pulled",
            fix="Run `ollama pull llama3.1:8b` (or your preferred chat model).",
        )
    return CheckResult(
        name="ollama models", status="PASS", detail=f"{len(models)} pulled: {models[:3]}"
    )


def check_port_free(port: int, label: str) -> CheckResult:
    """A port is free if nothing is listening locally."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.5)
        result = sock.connect_ex(("127.0.0.1", port))
    finally:
        sock.close()
    if result != 0:
        return CheckResult(name=f"port {port} ({label}) free", status="PASS", detail="ok")
    return CheckResult(
        name=f"port {port} ({label}) free",
        status="WARN",
        detail="something is already listening",
        fix=(
            f"Stop whatever owns 127.0.0.1:{port} or `make down` to clear an old "
            "synapse stack."
        ),
    )


def check_seed_data(city: str) -> CheckResult:
    path = REPO_ROOT / "data" / city
    stores = path / "stores.json"
    skus = path / "skus.json"
    if stores.exists() and skus.exists():
        try:
            n_stores = len(json.loads(stores.read_text()))
        except (OSError, json.JSONDecodeError):
            n_stores = -1
        return CheckResult(
            name=f"seed data ({city})",
            status="PASS",
            detail=f"{n_stores} stores",
        )
    return CheckResult(
        name=f"seed data ({city})",
        status="WARN" if city == "mumbai" else "FAIL",
        detail=f"missing {path}",
        fix=f"Run `make generate-{city}` before `make demo`.",
    )


def check_env_template() -> CheckResult:
    template = REPO_ROOT / "docker" / ".env.template"
    env = REPO_ROOT / "docker" / ".env"
    if not template.exists():
        return CheckResult(
            name="docker/.env.template",
            status="FAIL",
            detail="missing",
            fix="The .env.template ships with the repo; restore it from git.",
        )
    if not env.exists():
        return CheckResult(
            name="docker/.env",
            status="WARN",
            detail="missing -- will be auto-copied from .env.template by `make up`",
        )
    return CheckResult(name="docker/.env", status="PASS", detail="present")


def check_kafka_topics_script() -> CheckResult:
    script = REPO_ROOT / "scripts" / "create_kafka_topics.sh"
    if not script.exists():
        return CheckResult(
            name="kafka topic script",
            status="FAIL",
            detail="scripts/create_kafka_topics.sh missing",
            fix=None,
        )
    if shutil.which("jq") is None:
        return CheckResult(
            name="jq for topic script",
            status="WARN",
            detail="jq not installed",
            fix=(
                "create_kafka_topics.sh uses jq to parse topics.json. "
                "Install jq (apt/brew/choco install jq) or topics will be created "
                "with defaults."
            ),
        )
    return CheckResult(name="jq for topic script", status="PASS", detail="ok")


# --------------------------------------------------------------------------- runner


def run_all() -> list[CheckResult]:
    results: list[CheckResult] = []
    results.append(check_python_version())
    results.append(check_docker())
    results.append(
        check_command("docker compose", hint="ships with Docker Desktop / docker-ce.")
    )
    results.append(check_command("git", hint="Install git."))
    results.append(check_command("curl", hint="Install curl.", severity="WARN"))
    results.append(check_ollama())
    results.append(check_kafka_topics_script())
    results.append(check_env_template())
    results.append(check_seed_data("bengaluru"))
    results.append(check_seed_data("mumbai"))
    for port, label in [
        (3000, "Grafana"),
        (5000, "MLflow / OSRM-blr"),
        (5001, "OSRM-mum"),
        (5432, "Postgres"),
        (6379, "Redis"),
        (7474, "Neo4j HTTP"),
        (7687, "Neo4j Bolt"),
        (8001, "demand_prophet"),
        (9090, "Prometheus"),
        (9092, "Kafka"),
        (11434, "Ollama"),
    ]:
        results.append(check_port_free(port, label))
    return results


def render(results: list[CheckResult]) -> int:
    longest = max(len(r.name) for r in results)
    fail = 0
    warn = 0
    for r in results:
        glyph = {"PASS": "ok ", "WARN": "WARN", "FAIL": "FAIL"}[r.status]
        print(f"  [{glyph}] {r.name.ljust(longest)}  {r.detail}")
        if r.status == "FAIL":
            fail += 1
            if r.fix:
                print(f"          fix: {r.fix}")
        elif r.status == "WARN":
            warn += 1
            if r.fix:
                print(f"          hint: {r.fix}")
    print()
    print(f"  Summary: {len(results) - fail - warn} pass, {warn} warn, {fail} fail.")
    if fail:
        print("  -> Run `make doctor` again after fixing the FAIL items.")
    return 1 if fail else 0


def main() -> int:
    print("SYNAPSE doctor -- pre-flight checks")
    print("-" * 52)
    return render(run_all())


if __name__ == "__main__":
    raise SystemExit(main())
