"""E6 (elevation): Prometheus scrape targets must match docker-compose services.

CLAUDE.md notes Redis / Kafka / Neo4j do not expose ``/metrics`` natively. We
ran for several sprints with prometheus.yml referencing
``redis-exporter:9121`` and ``kafka-jmx-exporter:9404`` even though those
services were never declared in docker-compose, so Grafana dashboards were
silently empty.

This test parses the prometheus config and the compose file as plain YAML
and asserts that every scrape target whose host is not Prometheus itself
is satisfied by either an explicit container_name in compose or an agent
service we expect to surface ``/metrics`` directly.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]
PROM_CONFIG = REPO_ROOT / "infrastructure" / "prometheus" / "prometheus.yml"
COMPOSE_FILE = REPO_ROOT / "docker" / "docker-compose.yml"
COMPOSE_MUMBAI = REPO_ROOT / "docker" / "docker-compose.mumbai.yml"

# Host names we deliberately don't ship in compose (e.g. external services
# the dashboards link to but don't probe in CI). Add to this set if you
# add a target intentionally not in compose.
EXTERNAL_HOSTS: set[str] = {"localhost"}


def _load(path: Path) -> dict:
    if not path.exists():
        pytest.skip(f"{path} not present in this checkout")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _scrape_hosts() -> set[str]:
    cfg = _load(PROM_CONFIG)
    hosts: set[str] = set()
    for job in cfg.get("scrape_configs", []):
        for sc in job.get("static_configs", []):
            for target in sc.get("targets", []) or []:
                host = target.split(":", 1)[0]
                hosts.add(host)
    return hosts


def _compose_service_names() -> set[str]:
    names: set[str] = set()
    for path in (COMPOSE_FILE, COMPOSE_MUMBAI):
        cfg = _load(path)
        services = cfg.get("services", {}) or {}
        for service_name, service_cfg in services.items():
            names.add(service_name)
            container = (service_cfg or {}).get("container_name")
            if container:
                names.add(container)
                # The "synapse-" prefix is repo convention but Prometheus
                # references the unprefixed compose service name; record
                # both forms so the assertion is symmetric.
                names.add(container.removeprefix("synapse-"))
    return names


# Agent service names appear in compose as e.g. "demand-prophet-mumbai"
# but Prometheus uses the same. Anchor: any host with these stem names is
# accepted because compose declares them under the agent block.
AGENT_STEMS = {
    "demand-prophet",
    "routing-navigator",
    "inventory-sentinel",
    "freshness-guardian",
    "pricing-oracle",
    "disruption-shield",
    "supplier-trust",
    "sustainability-agent",
    "orchestrator",
    "mlflow",
    "api",
}


def test_every_prometheus_target_resolvable_in_compose() -> None:
    hosts = _scrape_hosts() - EXTERNAL_HOSTS
    services = _compose_service_names()

    missing: list[str] = []
    for host in sorted(hosts):
        if host in services:
            continue
        if any(host.startswith(stem) for stem in AGENT_STEMS):
            continue
        missing.append(host)
    assert not missing, (
        f"Prometheus scrapes {missing} but no compose service of that name exists. "
        "Add the exporter sidecar to docker/docker-compose.yml or remove the "
        "target from infrastructure/prometheus/prometheus.yml."
    )


def test_redis_exporter_present() -> None:
    services = _compose_service_names()
    assert "redis-exporter" in services or "synapse-redis-exporter" in services, (
        "E6: redis-exporter missing from docker-compose.yml; Grafana 'Redis' "
        "dashboard will be empty without it."
    )


def test_kafka_jmx_exporter_present() -> None:
    services = _compose_service_names()
    assert (
        "kafka-jmx-exporter" in services
        or "synapse-kafka-jmx-exporter" in services
    ), (
        "E6: kafka-jmx-exporter missing from docker-compose.yml; Grafana 'Kafka' "
        "dashboard will be empty without it."
    )
