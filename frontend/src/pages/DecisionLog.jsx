import React, { useState } from "react";

const COLUMNS = ["Timestamp", "Tier", "Phase", "Confidence", "Escalated", "Outcome"];

function PageHeader({ title, subtitle }) {
  return (
    <header className="mb-5">
      <h1 className="text-xl font-bold tracking-tight text-text-primary">{title}</h1>
      {subtitle && <p className="mt-0.5 text-sm text-text-tertiary">{subtitle}</p>}
    </header>
  );
}

export default function DecisionLog() {
  const [search, setSearch] = useState("");
  const [decisions] = useState([]);

  const filtered = decisions.filter((d) =>
    JSON.stringify(d).toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="mx-auto max-w-[1200px] animate-fade-in">
      <PageHeader title="Decision Log" subtitle="Append-only audit trail of consensus decisions (I-4)" />

      <input
        type="text"
        placeholder="Search decisions…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-4 w-full rounded-md border border-border-subtle bg-surface-raised px-3.5 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus-visible:border-brand-base focus-visible:outline-none"
      />

      <div className="panel overflow-hidden">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border-subtle bg-surface-raised">
              {COLUMNS.map((c) => (
                <th
                  key={c}
                  className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-text-tertiary"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={COLUMNS.length} className="px-4 py-10 text-center text-text-tertiary">
                  No decisions yet — submit an order to generate consensus decisions.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
