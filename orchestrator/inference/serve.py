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

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from synapse_common.kafka_client import KafkaConfig, SynapseProducer

from orchestrator.a2a.handler import OrchestratorA2AHandler
from orchestrator.audit.logger import AuditLogger
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

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger(__name__)

_config: OrchestratorConfig | None = None
_protocol: ConsensusProtocol | None = None
_ws_manager: WebSocketManager | None = None
_a2a_handler: OrchestratorA2AHandler | None = None
_hitl: HITLEscalation | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _config, _protocol, _ws_manager, _a2a_handler, _hitl

    _config = OrchestratorConfig()

    engine = create_async_engine(_config.postgresql_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(AuditBase.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    kafka_cfg = KafkaConfig(bootstrap_servers=_config.kafka_bootstrap_servers)
    try:
        kafka_producer = SynapseProducer(kafka_cfg)
    except Exception:
        kafka_producer = None
        logger.warning("kafka_unavailable_at_startup")

    tier_router = TierRouter()
    guardrails = GuardrailEngine(confidence_threshold=_config.confidence_threshold)
    audit_logger = AuditLogger(session_factory)
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
    )
    _a2a_handler = OrchestratorA2AHandler(consensus_protocol=_protocol)

    logger.info("orchestrator_started", port=_config.port)
    yield

    await ollama_client.close()


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
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "agent": "orchestrator",
        "version": "0.4.0",
    }


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
