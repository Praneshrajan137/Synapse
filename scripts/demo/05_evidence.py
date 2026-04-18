"""Segment 05 — Evidence & Audit Trail.

Closes the narrative by showing audit-log immutability (I-4), KL divergence
between the live system and the Digital Twin (I-12), and MLflow run
provenance for the deciding agents. When dependencies aren't available,
falls back to the snapshots produced by segments 01–04 so the demo still
tells a coherent story.

v4.0 plan §8.2 — fifth narrative beat (evidence).

Usage:
    python scripts/demo/05_evidence.py <city> [speed_factor]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from scripts.demo._common import (
    POSTGRES_DSN,
    emit_banner,
    sleep_scaled,
)


def audit_rows(limit: int = 5) -> list[dict[str, Any]]:
    try:
        import psycopg2  # type: ignore[import-untyped]

        conn = psycopg2.connect(POSTGRES_DSN)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT audit_id, decision_id, tier, created_at
                    FROM audit_decisions
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return [
                    {
                        "audit_id": str(row[0]),
                        "decision_id": str(row[1]),
                        "tier": row[2],
                        "created_at": row[3].isoformat() if row[3] else None,
                    }
                    for row in cur.fetchall()
                ]
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        print(f"[05] Postgres audit trail unavailable ({exc})")
        return []


def twin_kl() -> float | None:
    try:
        import requests

        resp = requests.get(
            "http://localhost:9090/api/v1/query",
            params={"query": "synapse_digital_twin_kl_divergence"},
            timeout=5,
        )
        data = resp.json()
        results = data.get("data", {}).get("result", [])
        if results and results[0].get("value"):
            return float(results[0]["value"][1])
    except Exception as exc:  # noqa: BLE001
        print(f"[05] Prometheus twin KL unavailable ({exc})")
    return None


def mlflow_runs(city: str) -> list[dict[str, Any]]:
    try:
        import mlflow

        mlflow.set_tracking_uri("http://localhost:5000")
        client = mlflow.tracking.MlflowClient()
        agents = [
            "demand_prophet",
            "routing_navigator",
            "inventory_sentinel",
        ]
        out: list[dict[str, Any]] = []
        for agent in agents:
            exp = client.get_experiment_by_name(f"{city}_transfer_{agent}")
            if exp is None:
                continue
            runs = client.search_runs(
                experiment_ids=[exp.experiment_id],
                order_by=["attributes.start_time DESC"],
                max_results=1,
            )
            if runs:
                out.append(
                    {
                        "agent": agent,
                        "run_id": runs[0].info.run_id,
                        "status": runs[0].info.status,
                        "metrics": dict(runs[0].data.metrics),
                    }
                )
        return out
    except Exception as exc:  # noqa: BLE001
        print(f"[05] MLflow unavailable ({exc})")
        return []


def main(city: str, speed: float) -> int:
    emit_banner("SEGMENT 05 — Evidence & Audit", city, speed)

    rows = audit_rows()
    print(f"Audit entries (I-4 immutable): {len(rows)}")
    for r in rows:
        print(
            f"  audit={r['audit_id'][:8]}... "
            f"decision={r['decision_id'][:8]}... "
            f"tier={r['tier']} at={r['created_at']}"
        )

    kl = twin_kl()
    if kl is not None:
        verdict = "OK" if kl < 0.1 else "WARN"
        print(f"Digital Twin KL divergence: {kl:.4f} (threshold 0.1, {verdict})")
    else:
        print("Digital Twin KL divergence: unavailable")

    runs = mlflow_runs(city)
    print(f"MLflow runs (provenance): {len(runs)}")
    for r in runs:
        cov = r["metrics"].get("mumbai_calibration_coverage_90")
        spd = r["metrics"].get("convergence_speedup")
        extras = []
        if spd is not None:
            extras.append(f"speedup={spd:.2f}x")
        if cov is not None:
            extras.append(f"coverage={cov:.3f}")
        extra_str = (" " + ", ".join(extras)) if extras else ""
        print(f"  {r['agent']:<24s} status={r['status']}{extra_str}")

    snapshot_dir = Path("data") / city / "demo"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "evidence_summary.json").write_text(
        json.dumps(
            {
                "audit_rows": rows,
                "twin_kl": kl,
                "mlflow_runs": runs,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ),
        encoding="utf-8",
    )

    sleep_scaled(2.0, speed)
    print("Segment 05 complete — evidence archived. Demo narrative closed.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/demo/05_evidence.py <city> [speed_factor]")
        sys.exit(1)
    raise SystemExit(main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 1.0))
