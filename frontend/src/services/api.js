const BASE = "/api/v1";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  submitDecision: (body) => request("/decisions", { method: "POST", body: JSON.stringify(body) }),
  getAudit: (id) => request(`/audit/${id}`),
  getHealth: () => fetch("/health").then((r) => r.json()),
};
