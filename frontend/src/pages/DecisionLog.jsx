import React, { useState } from "react";

const COLUMNS = ["timestamp", "tier", "phase", "confidence", "escalated", "outcome"];

export default function DecisionLog() {
  const [search, setSearch] = useState("");
  const [decisions] = useState([]);

  const filtered = decisions.filter((d) =>
    JSON.stringify(d).toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 16 }}>Decision Log</h1>
      <input
        type="text"
        placeholder="Search decisions..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid #334155", background: "#0f172a", color: "#e2e8f0", marginBottom: 16 }}
      />
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            {COLUMNS.map((c) => (
              <th key={c} style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #334155", color: "#94a3b8", textTransform: "capitalize" }}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filtered.length === 0 && (
            <tr>
              <td colSpan={COLUMNS.length} style={{ padding: 16, color: "#64748b", textAlign: "center" }}>
                No decisions yet. Submit an order to generate decisions.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
