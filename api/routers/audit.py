"""Audit Vault export endpoints.

S5 ships:
- ``GET /api/v1/audit/{decision_id}/pdf`` — deterministic PDF evidence
  pack (regulator-grade, byte-equal across runs).

Determinism is the load-bearing property for FSSAI / DPDPA auditors:
two exports of the same decision MUST be byte-identical so a tampered
pack is detectable by hash. We achieve that by:

1. **Canonical body**: re-serialise the audit_consensus row through
   ``json.dumps(sort_keys=True, separators=(',',':'))`` (I-13).
2. **Pinned PDF metadata**: zero-out the CreationDate / ModDate so two
   runs differ only in the audit content (which is itself canonical).
3. **No randomness**: no UUIDs, no font subset shuffling. We embed a
   single PDF page rendered from a deterministic textual layout — the
   simplest compliant PDF that will render in any reader.

S6 hardening will swap the hand-rolled PDF for ``reportlab`` with
``invariantTime=True`` and embed a chain-proof QR code.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Path, Response

logger = structlog.get_logger(__name__)
router = APIRouter()

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
)


def _audit_dsn() -> str:
    return os.environ.get(
        "POSTGRES_DSN",
        "postgresql://synapse:synapse_audit_2026@postgres:5432/synapse_audit",
    )


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _build_deterministic_pdf(decision_id: str, body: str) -> bytes:
    """Hand-rolled minimal PDF.

    Format (PDF 1.4):
      1 0 obj — Catalog
      2 0 obj — Pages
      3 0 obj — single Page
      4 0 obj — page Contents stream (Helvetica text drawing)
      5 0 obj — Helvetica font
    Cross-reference table + trailer with deterministic /ID derived from
    sha256(body). No Info dictionary (so CreationDate isn't present).
    """
    doc_id = hashlib.sha256(body.encode("utf-8")).hexdigest()[:32].upper()
    title = f"SYNAPSE Atlas Console — Audit Evidence — {decision_id}"

    # PDF strings are bytes encoded with PDFDocEncoding (a superset of
    # WinAnsi for ASCII). We escape parentheses + backslashes to keep the
    # syntax legal, then split into lines that fit comfortably on A4.
    def escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    # Wrap to ~100 chars per line, truncate to 80 lines (A4 single page).
    raw_lines = body.replace("\r", "").split("\n")
    wrapped: list[str] = []
    for raw in raw_lines:
        for i in range(0, max(1, len(raw)), 100):
            wrapped.append(raw[i : i + 100])
            if len(wrapped) >= 80:
                break
        if len(wrapped) >= 80:
            break

    text_ops = ["BT", "/F1 9 Tf", "12 TL", "40 800 Td", f"({escape(title)}) Tj", "T*"]
    for line in wrapped:
        text_ops.append(f"({escape(line)}) Tj")
        text_ops.append("T*")
    text_ops.append("ET")
    contents = "\n".join(text_ops).encode("latin-1", errors="replace")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(contents)).encode("ascii") + b" >>\nstream\n"
        + contents
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"

    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n"
    out += (
        f"<< /Size {len(objects) + 1} /Root 1 0 R "
        f"/ID [<{doc_id}><{doc_id}>] >>\n"
    ).encode("ascii")
    out += b"startxref\n"
    out += f"{xref_offset}\n".encode("ascii")
    out += b"%%EOF\n"
    return bytes(out)


@router.get("/{decision_id}/pdf")
async def export_decision_pdf(
    decision_id: str = Path(..., description="audit_consensus.decision_id"),
) -> Response:
    """Return a deterministic PDF evidence pack for one decision."""
    if not _UUID_RE.match(decision_id):
        raise HTTPException(status_code=400, detail="decision_id must be a UUID")

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(_audit_dsn())
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id::text, decision_id::text, timestamp, tier, phase_reached,
                           proposals, selected_action, pareto_weights, confidence,
                           debate_rounds, escalated, human_override,
                           execution_confirmations, context_messages, audit_trace,
                           pareto_front, outcome, created_at
                      FROM audit_consensus
                     WHERE decision_id = %s
                    """,
                    (decision_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit_pdf_fetch_failed", decision_id=decision_id, error=str(exc))
        raise HTTPException(status_code=503, detail=f"audit unavailable: {exc}") from exc

    if row is None:
        raise HTTPException(status_code=404, detail=f"no decision with id {decision_id}")

    # Stringify timestamps so json.dumps doesn't reject them; we keep the
    # canonical encoder simple (sort_keys + tight separators).
    payload: dict[str, Any] = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            payload[k] = v.isoformat().replace("+00:00", "Z")
        else:
            payload[k] = v
    body = _canonical(payload)

    pdf = _build_deterministic_pdf(decision_id, body)
    digest = hashlib.sha256(pdf).hexdigest()
    logger.info("audit_pdf_export", decision_id=decision_id, sha256=digest, size=len(pdf))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="atlas-audit-{decision_id}.pdf"',
            "X-Atlas-Audit-SHA256": digest,
            "Cache-Control": "no-store",
        },
    )
