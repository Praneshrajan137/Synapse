import React from "react";
import { useWebSocket } from "../hooks/useWebSocket";
import ConfidenceGauge from "../components/ConfidenceGauge";

export default function OverrideConsole() {
  const { messages, connected, send } = useWebSocket(
    `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws/escalation`,
  );

  const pending = messages.filter((m) => m.type === "escalation");

  function handleAction(decisionId, action) {
    send({ decision_id: decisionId, response: { action } });
  }

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Override Console</h1>
      <div style={{ marginBottom: 16, color: connected ? "#22c55e" : "#ef4444" }}>
        {connected ? "Connected" : "Disconnected"}
      </div>

      {pending.length === 0 && <p style={{ color: "#64748b" }}>No pending escalations.</p>}

      {pending.map((esc, i) => (
        <div key={i} style={{ background: "#1e293b", borderRadius: 12, padding: 20, marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <ConfidenceGauge value={esc.confidence} size={80} />
            <div>
              <div style={{ fontWeight: 600, fontSize: 16 }}>Decision {esc.decision_id?.slice(0, 8)}</div>
              <div style={{ color: "#94a3b8" }}>Tier {esc.tier} | {esc.violations?.length || 0} violations</div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <button onClick={() => handleAction(esc.decision_id, "approved")} style={{ padding: "8px 20px", borderRadius: 6, border: "none", background: "#22c55e", color: "#fff", cursor: "pointer" }}>Approve</button>
            <button onClick={() => handleAction(esc.decision_id, "rejected")} style={{ padding: "8px 20px", borderRadius: 6, border: "none", background: "#ef4444", color: "#fff", cursor: "pointer" }}>Reject</button>
            <button onClick={() => handleAction(esc.decision_id, "modified")} style={{ padding: "8px 20px", borderRadius: 6, border: "none", background: "#eab308", color: "#000", cursor: "pointer" }}>Modify</button>
          </div>
        </div>
      ))}
    </div>
  );
}
