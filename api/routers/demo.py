"""Demo runner endpoint (P4.B22).

Wraps ``scripts/demo/run_demo.sh`` as an admin-only HTTP + SSE pipeline so
the Frontend Demo Theater can drive the 5-segment narrative. One job per
invocation; SSE streams stdout lines as segment-progress events.

I-1 holds: the demo runs entirely on local OSS infrastructure.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Annotated, Any, AsyncIterator

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.middleware.jwt import RequireRole
from synapse_common.auth import OperatorContext, Role

logger = structlog.get_logger(__name__)
router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_SCRIPT = REPO_ROOT / "scripts" / "demo" / "run_demo.sh"
DATA_ROOT = REPO_ROOT / "data"

# Active jobs are kept in-memory; demo is a short-lived operator activity.
_jobs: dict[str, "DemoJob"] = {}


class DemoJob:
    def __init__(self, city: str, speed: float, kind: str) -> None:
        self.id = str(uuid.uuid4())
        self.city = city
        self.speed = speed
        self.kind = kind
        self.process: asyncio.subprocess.Process | None = None
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.finished = False
        self.exit_code: int | None = None
        self.started_at = time.time()


class DemoRunResponse(BaseModel):
    job_id: str
    city: str
    speed: float
    kind: str


@router.post(
    "/run",
    response_model=DemoRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_demo(
    city: Annotated[str, Query(...)],
    speed: Annotated[float, Query(ge=0.1, le=10.0)] = 1.0,
    kind: Annotated[str, Query(...)] = "warehouse_offline",
    _op: Annotated[OperatorContext, Depends(RequireRole(Role.ADMIN))] = None,  # type: ignore[assignment]
) -> DemoRunResponse:
    if city not in {"bengaluru", "mumbai"}:
        raise HTTPException(status_code=422, detail="city must be 'bengaluru' or 'mumbai'")
    if not DEMO_SCRIPT.exists():
        raise HTTPException(status_code=500, detail="run_demo.sh not packaged with image")
    job = DemoJob(city=city, speed=speed, kind=kind)
    _jobs[job.id] = job
    asyncio.create_task(_run_subprocess(job))
    return DemoRunResponse(job_id=job.id, city=city, speed=speed, kind=kind)


async def _run_subprocess(job: DemoJob) -> None:
    """Spawn run_demo.sh and stream stdout/stderr into the job's queue."""
    bash = shutil.which("bash") or "/bin/bash"
    try:
        proc = await asyncio.create_subprocess_exec(
            bash,
            str(DEMO_SCRIPT),
            job.city,
            str(job.speed),
            job.kind,
            cwd=str(REPO_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except OSError as exc:
        await job.events.put({"type": "error", "message": str(exc)})
        job.finished = True
        return
    job.process = proc
    assert proc.stdout is not None
    while True:
        raw = await proc.stdout.readline()
        if not raw:
            break
        line = raw.decode("utf-8", errors="replace").rstrip()
        await job.events.put({"type": "log", "line": line, "ts": time.time()})
        # Segment markers — the bash script logs "[demo:..." between segments.
        for marker in ("01_living_map", "02_ipl_signal", "03_disruption", "04_debate", "05_evidence"):
            if marker in line:
                await job.events.put({"type": "segment", "segment": marker})
                break
    job.exit_code = await proc.wait()
    job.finished = True
    await job.events.put({"type": "done", "exit_code": job.exit_code})


@router.get("/{job_id}/stream")
async def stream_demo(
    job_id: str,
    _op: Annotated[OperatorContext, Depends(RequireRole(Role.VIEWER))] = None,  # type: ignore[assignment]
) -> StreamingResponse:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")

    async def event_stream() -> AsyncIterator[bytes]:
        while True:
            if job.finished and job.events.empty():
                break
            try:
                event = await asyncio.wait_for(job.events.get(), timeout=15.0)
            except TimeoutError:
                yield b": ping\n\n"
                continue
            payload = json.dumps(event, sort_keys=True, separators=(",", ":"))
            yield f"event: {event['type']}\ndata: {payload}\n\n".encode("utf-8")
        yield b"event: close\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{job_id}/artifact/{segment}")
async def get_artifact(
    job_id: str,
    segment: str,
    _op: Annotated[OperatorContext, Depends(RequireRole(Role.VIEWER))] = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    path = DATA_ROOT / job.city / "demo" / f"{segment}.json"
    if not path.exists():
        # Demo segment 01 writes living_map_snapshot.json — try the legacy name.
        legacy = DATA_ROOT / job.city / "demo" / "living_map_snapshot.json"
        if segment.startswith("01_living_map") and legacy.exists():
            path = legacy
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"artifact {segment}.json missing")
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"segment": segment, "city": job.city, "body": body}


@router.post("/{job_id}/cancel")
async def cancel_demo(
    job_id: str,
    _op: Annotated[OperatorContext, Depends(RequireRole(Role.ADMIN))] = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    if job.process and job.process.returncode is None:
        job.process.terminate()
    return {"status": "cancelling", "job_id": job_id}
