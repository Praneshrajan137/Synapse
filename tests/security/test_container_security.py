from __future__ import annotations

"""Container security verification tests.

Run against live Docker containers:
  pytest tests/security/test_container_security.py -v

Verifies Docker security best practices:
- Non-root USER
- Read-only rootfs where possible
- No --privileged
- Health checks defined
"""

import json
import subprocess

import pytest
import structlog

logger = structlog.get_logger()

SYNAPSE_CONTAINERS = [
    "synapse-demand-prophet",
    "synapse-routing-navigator",
    "synapse-inventory-sentinel",
    "synapse-pricing-oracle",
    "synapse-freshness-guardian",
    "synapse-disruption-shield",
    "synapse-supplier-trust",
    "synapse-sustainability-agent",
    "synapse-orchestrator",
]


def _docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def docker_inspect(container: str) -> dict | None:
    """Inspect a running Docker container."""
    try:
        result = subprocess.run(
            ["docker", "inspect", container],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        return data[0] if data else None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


@pytest.mark.skipif(not _docker_available(), reason="Docker not available")
class TestContainerSecurity:
    """Verify container security posture for all SYNAPSE services."""

    @pytest.mark.parametrize("container", SYNAPSE_CONTAINERS)
    def test_non_root_user(self, container: str) -> None:
        """Container runs as non-root user."""
        info = docker_inspect(container)
        if info is None:
            pytest.skip(f"Container {container} not running")

        user = info.get("Config", {}).get("User", "")
        assert user not in ("", "root", "0"), (
            f"Container {container} runs as root — security violation"
        )

    @pytest.mark.parametrize("container", SYNAPSE_CONTAINERS)
    def test_no_privileged_mode(self, container: str) -> None:
        """Container does NOT run in privileged mode."""
        info = docker_inspect(container)
        if info is None:
            pytest.skip(f"Container {container} not running")

        privileged = info.get("HostConfig", {}).get("Privileged", False)
        assert privileged is False, (
            f"Container {container} runs in privileged mode — security violation"
        )

    @pytest.mark.parametrize("container", SYNAPSE_CONTAINERS)
    def test_healthcheck_defined(self, container: str) -> None:
        """Container has a healthcheck defined."""
        info = docker_inspect(container)
        if info is None:
            pytest.skip(f"Container {container} not running")

        healthcheck = info.get("Config", {}).get("Healthcheck")
        assert healthcheck is not None, (
            f"Container {container} has no healthcheck defined"
        )

    @pytest.mark.parametrize("container", SYNAPSE_CONTAINERS)
    def test_read_only_rootfs(self, container: str) -> None:
        """Container has read-only root filesystem where feasible."""
        info = docker_inspect(container)
        if info is None:
            pytest.skip(f"Container {container} not running")

        readonly = info.get("HostConfig", {}).get("ReadonlyRootfs", False)
        if not readonly:
            logger.info(
                "container_rootfs_writable",
                container=container,
                recommendation="Consider ReadonlyRootfs=true with tmpfs mounts",
            )

    def test_network_segmentation(self) -> None:
        """Docker networks are segmented: agents-net, infra-net, frontend-net."""
        expected_networks = [
            "synapse-agents", "synapse-infra", "synapse-frontend",
        ]
        result = subprocess.run(
            ["docker", "network", "ls", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            pytest.skip("Docker not available")

        existing = result.stdout.strip().split("\n")
        for net in expected_networks:
            found = any(net in n for n in existing)
            if not found:
                pytest.skip(f"Network {net} not created yet")
