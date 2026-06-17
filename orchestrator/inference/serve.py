"""
SYNAPSE Orchestrator — FastAPI inference server.

Endpoints:
  POST /api/v1/decisions  — submit a decision request
  GET  /health            — readiness probe
  GET  /metrics           — Prometheus scrape
  WS   /ws/escalation     — HITL escalation WebSocket
  POST /a2a               — A2A JSON-RPC handler
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from synapse_common.health import readiness_response
from synapse_common.kafka_client import KafkaConfig, SynapseProducer
from synapse_common.metrics import STARTUP_DEGRADED

from orchestrator.a2a.handler import OrchestratorA2AHandler
from orchestrator.audit.logger import AuditLogger
from orchestrator.audit.models import AuditOutboxRow
from orchestrator.audit.models import Base as AuditBase
from orchestrator.config import OrchestratorConfig
from orchestrator.consensus.protocol import ConsensusProtocol
from orchestrator.consensus.tier_router import TierRouter
from orchestrator.guardrails.rules import GuardrailEngine
from orchestrator.hitl.escalation import HITLEscalation, WebSocketManager
from orchestrator.llm.context_builder import ContextBuilder
from orchestrator.llm.ollama_client import OllamaClient
from orchestrator.llm.semantic_cache import SemanticDecisionCache
from orchestrator.meta_rl.meta_agent import MetaRLAgent
from orchestrator.outbox.dispatcher import OutboxDispatcher
from orchestrator.sensor import A2AWorldClient, SensorLoop

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger(__name__)

_config: OrchestratorConfig | None = None
_protocol: ConsensusProtocol | None = None
_ws_manager: WebSocketManager | None = None
_a2a_handler: OrchestratorA2AHandler | None = None
_hitl: HITLEscalation | None = None
_outbox_dispatcher: OutboxDispatcher | None = None
_sensor_loop: SensorLoop | None = None
_engine: AsyncEngine | None = None
_kafka_ok: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _config, _protocol, _ws_manager, _a2a_handler, _hitl, _outbox_dispatcher
    global _sensor_loop, _engine, _kafka_ok

    _config = OrchestratorConfig()

    engine = create_async_engine(_config.postgresql_url, echo=False)
    _engine = engine
    async with engine.begin() as conn:
        await conn.run_sync(AuditBase.metadata.create_all)
        # P1.2 fail-fast: refuse to start if the live audit_outbox columns drift from
        # the ORM. Otherwise the dispatcher swallows the schema error on every drain
        # (silently, forever) and no decision reaches Kafka. C55 guards this in CI;
        # this is its runtime counterpart against the actual deployed database.
        await _assert_outbox_schema(conn)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    kafka_cfg = KafkaConfig(bootstrap_servers=_config.kafka_bootstrap_servers)
    try:
        kafka_producer = SynapseProducer(kafka_cfg)
        _kafka_ok = True
        STARTUP_DEGRADED.labels(dependency="kafka").set(0.0)
    except Exception as exc:
        kafka_producer = None
        _kafka_ok = False
        STARTUP_DEGRADED.labels(dependency="kafka").set(1.0)
        # ERROR, not WARNING: the outbox dispatcher is disabled in this state, so
        # PENDING rows accumulate and no decision reaches Kafka until a restart with
        # Kafka up. Surfaced via synapse_startup_degraded + /health "degraded".
        logger.error(
            "kafka_unavailable_at_startup",
            error=str(exc),
            impact="outbox dispatcher disabled; PENDING rows accumulate until restart",
        )

    tier_router = TierRouter()
    guardrails = GuardrailEngine(confidence_threshold=_config.confidence_threshold)
    audit_logger = AuditLogger(session_factory)

    # ADR-044: register per-city brownout controllers at startup so the
    # posture endpoint (and @tier_budget's on_exceed="brownout" path,
    # E-S9-04) have live controllers instead of silently no-opping.
    # The "ollama"/"postgres" breaker names match the documented registry
    # convention (synapse_common.breakers.get_breaker).
    from synapse_common.breakers import get_breaker

    from orchestrator.consensus import brownout as brownout_registry

    for _city in ("bengaluru", "mumbai"):
        brownout_registry.register(
            brownout_registry.BrownoutController(
                _city,
                ollama_breaker=get_breaker("ollama"),
                postgres_breaker=get_breaker("postgres"),
            )
        )
    _ws_manager = WebSocketManager()
    _hitl = HITLEscalation(
        kafka_producer=kafka_producer,
        ws_manager=_ws_manager,
        timeout_seconds=_config.hitl_timeout_seconds,
        timeout_action=_config.hitl_timeout_action,
    )
    ctx_builder = ContextBuilder()
    ollama_client = OllamaClient(_config)
    meta_rl = MetaRLAgent(
        lr=_config.meta_rl_learning_rate,
        history_size=_config.meta_rl_history_size,
    )
    semantic_cache = SemanticDecisionCache(
        api_key=_config.pinecone_api_key,
        index_name=_config.pinecone_decision_cache_index,
    )

    _protocol = ConsensusProtocol(
        config=_config,
        tier_router=tier_router,
        guardrails=guardrails,
        audit_logger=audit_logger,
        hitl_escalation=_hitl,
        context_builder=ctx_builder,
        ollama_client=ollama_client,
        meta_rl=meta_rl,
        semantic_cache=semantic_cache,
        kafka_producer=kafka_producer,
        # ADR-052: learn from the realized world. Short timeout so the learning-phase
        # perceive never delays a decision; degrades to predicted utility if absent (I-7).
        world_observer=A2AWorldClient(timeout=2.0).world_state,
    )
    _a2a_handler = OrchestratorA2AHandler(consensus_protocol=_protocol)

    # WS-2: start the outbox dispatcher so audit_outbox rows actually
    # reach Kafka. The class existed since Sprint 7 but was never
    # started — see docs/state/CURRENT.md row C2 for the audit trail.
    if kafka_producer is not None:
        _outbox_dispatcher = OutboxDispatcher(session_factory, kafka_producer)
        await _outbox_dispatcher.start()
    else:
        logger.warning(
            "outbox_dispatcher_skipped_kafka_unavailable",
            reason=(
                "kafka_producer is None at startup; PENDING rows will "
                "accumulate until a restart with Kafka up"
            ),
        )

    # ADR-052 (the keystone): start the autonomous SensorLoop so the system perceives the
    # standing world and convenes consensus ON ITS OWN — no human POST, no synthetic ticker.
    # Guarded: a sensor failure must never block startup (tier-1/2 POST path still serves).
    if os.environ.get("SYNAPSE_SENSOR_ENABLED", "1") not in ("0", "false", "False"):
        try:
            cities = [
                c.strip()
                for c in os.environ.get("SYNAPSE_SENSOR_CITIES", "bengaluru,mumbai").split(",")
                if c.strip()
            ]
            _sensor_loop = SensorLoop(
                _protocol,
                A2AWorldClient(),
                cities=cities,
                poll_interval_s=float(os.environ.get("SYNAPSE_SENSOR_POLL_SECONDS", "10")),
            )
            await _sensor_loop.start()
        except Exception as exc:  # noqa: BLE001 — autonomy is additive; never block startup (I-7)
            logger.error("sensor_loop_start_failed", error=str(exc))
            _sensor_loop = None

    logger.info("orchestrator_started", port=_config.port, sensor=_sensor_loop is not None)
    yield

    if _sensor_loop is not None:
        await _sensor_loop.stop()
    if _outbox_dispatcher is not None:
        await _outbox_dispatcher.stop()
    await ollama_client.close()


async def _assert_outbox_schema(conn: Any) -> None:
    """Assert the live ``audit_outbox`` table has every ORM column (P1.2).

    A drift here is exactly what gate C55 catches statically: the dispatcher's
    claim/INSERT would error every cycle and the error would be swallowed. Fail
    fast and loud instead of degrading silently — the operator must run
    ``scripts/db/migrate.sh``.
    """
    expected = {c.name for c in AuditOutboxRow.__table__.columns}
    result = await conn.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = 'audit_outbox'")
    )
    actual = {row[0] for row in result}
    missing = expected - actual
    if missing:
        raise RuntimeError(
            f"audit_outbox schema drift: ORM columns missing in DB: {sorted(missing)}. "
            "Run scripts/db/migrate.sh (C55 guards this statically; this is the "
            "runtime guard against the deployed database)."
        )


async def _ping_db() -> bool:
    """Return True iff a trivial query against the audit DB succeeds (for /health)."""
    if _engine is None:
        return False
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 — health probes must never raise
        logger.warning("health_db_ping_failed", error=str(exc))
        return False


app = FastAPI(
    title="SYNAPSE Orchestrator",
    version="0.4.0",
    description="Multi-agent consensus engine for supply-chain orchestration",
    lifespan=lifespan,
)


class DecisionRequest(BaseModel):
    order_id: str | None = None
    store_id: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    agents_involved: list[str] = Field(default_factory=list)
    disruption_active: bool = False
    requires_twin_simulation: bool = False


class DecisionResponse(BaseModel):
    decision_id: str
    tier: str
    confidence: float
    phase_reached: int
    audit_id: str | None = None
    escalated: bool = False


@app.post("/api/v1/decisions", response_model=DecisionResponse)
async def create_decision(request: DecisionRequest) -> DecisionResponse:
    if _protocol is None:
        raise HTTPException(status_code=503, detail="Protocol not initialised")

    decision = await _protocol.run_consensus(request.model_dump())
    return DecisionResponse(
        decision_id=str(decision.decision_id),
        tier=str(decision.tier.value),
        confidence=decision.confidence,
        phase_reached=decision.phase_reached,
        audit_id=str(decision.audit_id) if decision.audit_id else None,
        escalated=decision.escalated_to_human,
    )


@app.get("/health")
async def health() -> JSONResponse:
    """Honest readiness (P1.1): HTTP 503 unless the protocol is initialised AND the
    audit DB answers. Kafka down is 'degraded' (tier-1/2 still serve), not unready.
    The Dockerfile HEALTHCHECK / compose probe and the C47/C50 deploy gates now
    reflect real readiness instead of merely 'the HTTP port answers'.
    """
    db_ok = await _ping_db()
    ready = _protocol is not None and db_ok
    dispatcher_running = _outbox_dispatcher is not None and _outbox_dispatcher.running
    return readiness_response(
        "orchestrator",
        ready=ready,
        degraded=not _kafka_ok or not dispatcher_running,
        version="0.4.0",
        database=db_ok,
        protocol=_protocol is not None,
        kafka="up" if _kafka_ok else "down",
        outbox_dispatcher="running" if dispatcher_running else "stopped",
        sensor_loop="running" if (_sensor_loop is not None and _sensor_loop.running) else "stopped",
    )


@app.get("/api/v1/status/posture")
async def status_posture() -> dict[str, Any]:
    """ADR-044: live degradation posture — brownout level per city + every
    circuit breaker's state. Until this endpoint, brownout/breaker state was
    Prometheus-only: the system could shed Tier-4 work or trip a dependency
    breaker with NOTHING in the operator UI saying so. The API gateway
    proxies this at ``GET /api/v1/system/posture`` (JWT) and the frontend
    polls it for the DegradedBanner.
    """
    from orchestrator.inference.posture import compute_posture

    return compute_posture()


@app.get("/metrics")
async def metrics() -> Response:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/a2a")
async def a2a_endpoint(request: dict[str, Any]) -> dict[str, Any]:
    if _a2a_handler is None:
        raise HTTPException(status_code=503, detail="Handler not initialised")
    return _a2a_handler.handle_request(request)


class HitlResolveRequest(BaseModel):
    audit_escalation_id: int
    operator_token_ref: str
    action: str = Field(..., pattern="^(approved|rejected|modified)$")
    reason: str
    modified_action: dict[str, Any] | None = None


@app.post("/api/v1/hitl/{decision_id}/resolve")
async def hitl_resolve(decision_id: UUID, payload: HitlResolveRequest) -> dict[str, Any]:
    """Resolve a pending HITL escalation and broadcast override_confirm.

    Called by the gateway's ``POST /api/v1/decisions/{id}/override`` after
    the audit row is persisted (FE-INV-021). Trust boundary is the gateway;
    this endpoint is reachable only over the internal Docker network.
    """
    if _hitl is None or _ws_manager is None:
        raise HTTPException(status_code=503, detail="HITL not initialised")
    await _hitl.receive_human_response(
        decision_id,
        {
            "action": payload.action,
            "reason": payload.reason,
            "modified_action": payload.modified_action,
            "operator_token_ref": payload.operator_token_ref,
            "audit_escalation_id": payload.audit_escalation_id,
        },
    )
    confirm_envelope = {
        "type": "override_confirm",
        "decision_id": str(decision_id),
        "audit_escalation_id": payload.audit_escalation_id,
        "operator_token_ref": payload.operator_token_ref,
        "action": payload.action,
        "status": "applied",
    }
    await _ws_manager.broadcast(confirm_envelope)
    return {"status": "resolved", "decision_id": str(decision_id)}


@app.websocket("/ws/escalation")
async def ws_escalation(websocket: WebSocket) -> None:
    await websocket.accept()
    if _ws_manager:
        _ws_manager.register(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            decision_id_str = data.get("decision_id")
            if decision_id_str and _hitl:
                await _hitl.receive_human_response(
                    UUID(decision_id_str),
                    data.get("response", {}),
                )
    except WebSocketDisconnect:
        pass
    finally:
        if _ws_manager:
            _ws_manager.unregister(websocket)


def main() -> None:
    import uvicorn

    config = OrchestratorConfig()
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
