import React from "react";
import ConfidenceGauge from "./ConfidenceGauge";

export default function AgentDebate({ proposals = [], debateRounds = [] }) {
  return (
    <div>
      <h3 style={{ marginBottom: 12 }}>Agent Proposals</h3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
        {proposals.map((p, i) => (
          <div key={i} style={{ background: "#1e293b", borderRadius: 8, padding: 16 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>{p.agent_name}</div>
            <ConfidenceGauge value={p.confidence} size={72} />
            <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 8 }}>
              Utility: {p.utility_score?.toFixed(3)}
            </div>
            <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>
              {p.justification_trace?.[0] ?? ""}
            </div>
          </div>
        ))}
      </div>

      {debateRounds.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <h3>Debate Rounds</h3>
          {debateRounds.map((round, i) => (
            <div key={i} style={{ background: "#1e293b", borderRadius: 8, padding: 12, marginTop: 8 }}>
              <strong>Round {round.round_number}</strong>
              <p style={{ color: "#94a3b8", fontSize: 13 }}>{round.llm_analysis ?? "No analysis"}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
