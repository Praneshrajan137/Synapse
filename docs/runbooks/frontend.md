# Atlas Console — Frontend Runbook

**Audience:** SRE on call · supply-chain platform team.
**Sister docs:** [threat model](../security/frontend-threat-model.md),
[ADR-025 frontend elevation](../adr/ADR-025-frontend-elevation.md).

This is the operator-facing playbook for diagnosing and recovering
the Atlas Console SPA + its trust boundary against the gateway. The
"smoke checklist" at the top is the only thing you should need at 03:00.

---

## 12-minute smoke checklist (page-in)

1. **Edge healthy?** `curl -fsSL http://localhost/healthz` → expects
   `ok` from the in-container nginx (`infrastructure/nginx/frontend.conf`).
2. **Gateway healthy?** `curl -fsSL http://localhost/health`.
3. **Auth round-trip?** Log in via `/login`, then
   `curl -b cookie.jar http://localhost/auth/session` → `authenticated:true`.
4. **SSE bridge live?** Open `/bengaluru/` in a fresh tab, watch the
   `streams live` chip in the header → expect `9 / 9`.
5. **Mission Control responding?** Send a fixture escalation via the
   gateway's MSW pass-through; the queue card appears, `?` opens help.
6. **Decision Trace chain proof?** Open any decision drawer → green
   "Audit chain verified" banner.
7. **Audit Vault export deterministic?** Pull the PDF twice; compare
   `X-Atlas-Audit-SHA256` headers — they must match.

If steps 1–7 pass, the user-visible surface is intact. Below: failure
modes you'll most likely see during a page-in, with triage paths.

---

## Symptom → triage map

### Symptom: Mission Control queue is empty even though the orchestrator is escalating

1. Confirm `/ws/escalation` connectivity: in DevTools Network tab,
   look for a sustained WebSocket connection (`type: websocket`).
2. If absent → check nginx `/ws/` block (`location /ws/` in
   `infrastructure/nginx/nginx.conf`). A failed `Upgrade` header is
   the most common cause; corporate proxies strip them.
3. If present but no frames → tail orchestrator logs:
   `docker compose logs synapse-orchestrator | grep escalation`.
4. **Mitigation while triaging:** the offline queue
   (`use-offline-queue.ts`) preserves any in-flight responses. A
   reconnect replays them automatically.

### Symptom: Living City KPI band is `—` for every tile

1. SSE bridge is the source. Inspect Network → EventStream for
   `synapse.metrics.agent`. Expect a `:hb` heartbeat every 15 s.
2. If the EventSource shows `readyState: CONNECTING` repeatedly,
   `proxy_buffering` may have been re-enabled for the stream block.
   Check `infrastructure/nginx/nginx.conf` `/api/v1/stream/` block.
3. If the bridge is healthy but no metrics frames arrive, the agent
   is silent — fall through to backend on-call.

### Symptom: Decision Trace drawer flashes "Audit chain broken"

1. **Do not export.** The UI already blocks the export — confirm.
2. Verify which entry broke: drawer renders `expected` and `actual`
   hashes. Diff the `body` against
   `python tests/contract/refresh_openapi_snapshot.py`-friendly canonical
   form to see which field drifted.
3. If the chain is genuinely broken, escalate to security on-call —
   I-4 immutability says this should be impossible; the audit
   itself is suspect.
4. If it's a client-side parser drift (canonical-JSON mismatch), the
   property tests in `audit-hash.test.ts` should have caught it; bisect
   the most recent SDK / dependency bump.

### Symptom: PDF export downloads as JSON instead of PDF

This is the documented S5 fallback path: gateway returned 404 for
`GET /api/v1/audit/{id}/pdf`. Mitigation:

1. Verify the audit router is mounted: `curl -I
   http://localhost/api/v1/audit/<sample-uuid>/pdf` → expect 200/404,
   not 502/503.
2. If 503: gateway upstream (Postgres) is flaky.
3. If 404: the decision genuinely doesn't exist; the JSON path is
   the safe default and is itself byte-deterministic.

### Symptom: PII reveal succeeds but data stays redacted

1. The cookie's `elevated_until` is the source of truth, not URL state.
   In DevTools → Application → Cookies, `synapse_session` is opaque,
   so check `/auth/session` directly:
   `curl -b cookie.jar http://localhost/auth/session | jq .elevated_until`.
2. If null after a successful reauth, the gateway dropped the
   elevation. Restart `synapse-orchestrator` if Redis is wedged.
3. If non-null but in the past, the 5-minute window expired — reauth.

### Symptom: First paint is blank / "Atlas Console: missing #root"

1. The HTML at `/` redirects to `/bengaluru/`. If the SPA shell
   refuses to mount, the build is broken — re-pull the canary image.
2. `make rollback-frontend` flips the upstream to the previous good
   image (see [Rollback](#rollback)).

### Symptom: CSP violation reports flooding `/api/v1/rum`

1. Inspect `synapse_csp_violations_total` in Prometheus
   (`{blocked_uri,violated_directive}` labels are bounded —
   `api/routers/rum.py` truncates).
2. Most common: a third-party font / analytics injected by an
   over-zealous browser extension. Confirm `connect-src` allow-list
   is unchanged in nginx.

---

## Rollback

Image tags are `<git-sha>-<content-hash>`; the previous good image is
kept hot as `synapse-frontend-canary`. To roll back:

```bash
make rollback-frontend
```

This swaps the nginx upstream to the canary container, hot-reloads
nginx, and prints the new active SHA. Total downtime ≤ 2 s.

If `make rollback-frontend` is unavailable, the manual path is:

```bash
docker compose -f docker/docker-compose.yml \
  up -d --no-deps synapse-frontend-canary
docker compose exec synapse-nginx \
  nginx -s reload
```

---

## Demo-mode determinism

The demo-mode flag (`?demo=1`) pins the SPA into a recorded fixture
loop (see `frontend/src/shared/demo/provider.tsx`). Use this in
front of regulators to guarantee a flake-free walkthrough:

```bash
scripts/demo/run_demo.sh bengaluru 1.0 &
open "http://localhost/?demo=1"
```

The `DEMO` watermark is rendered bottom-right; clocks are seed-pinned;
RUM beacons are silenced.

---

## On-call escalations

- **Frontend bug, no impact**: file a sprint ticket; tag `frontend`.
- **Auth / PII reveal failures**: page security on-call (BFF + audit
  trail are jointly owned).
- **Audit chain anomaly**: page security on-call; do **not** roll
  forward until the anomaly is resolved (I-4 invariant).
- **CSP / supply-chain alerts**: page platform on-call; follow
  `docs/security/frontend-threat-model.md` flowcharts.
