# Runbook — Quarterly Chaos Day

> **WS-10 deliverable.** A scheduled operator drill where on-call deliberately injects nine failure modes and verifies SYNAPSE degrades the way Sprint 5's chaos tests promised.
>
> **Cadence:** once per quarter (last Friday of Mar/Jun/Sep/Dec).
> **Duration:** 2 hours.
> **Pre-req:** non-prod GCP project synced to the latest `main`. **Never run against production.**

## Why this exists

Sprint 5 shipped 9 chaos tests (`tests/chaos/`). They run in CI but pass-by-default because they exercise simulated components (E-S5-01). The quarterly chaos day is the *human* counterpart — a real engineer in front of a real (non-prod) cluster, walking through the same nine injections and confirming the operator can:

1. **Detect** the failure within the SLO burn window.
2. **Diagnose** using the structured logs + Grafana dashboards.
3. **Mitigate** via the documented runbook.

If any of those three steps takes too long, that gap becomes the highest-priority follow-up for the next sprint.

## The nine injections

| # | Failure mode | How to inject | Expected detection | Mitigation runbook |
| - | --- | --- | --- | --- |
| 1 | Kafka broker down | `kubectl scale sts/kafka --replicas=0` | alert `KafkaBrokerUnavailable` ≤ 90s | `docs/runbooks/kafka_outage.md` |
| 2 | Postgres slow query (>5s) | `psql -c "SELECT pg_sleep(20)"` on the audit DB | alert `OrchestratorTier1LatencyBurn` ≤ 2m | `docs/runbooks/audit_latency.md` |
| 3 | One agent crashed | `kubectl delete pod -l app=demand-prophet` | breaker `kafka_outbox_publish` opens; orchestrator reroutes | `docs/runbooks/agent_crash.md` |
| 4 | All agents crashed | `kubectl scale deploy --all --replicas=0 -l synapse.agent` | HITL queue empty; ingress 503 | `docs/runbooks/total_agent_outage.md` |
| 5 | Ollama gone | `kubectl delete deploy ollama` | tier-2 path degrades; breaker opens; fallback to RL-only | `docs/runbooks/ollama_outage.md` |
| 6 | Outbox dispatcher stuck | `kubectl exec orchestrator-0 -- kill -STOP 1` (then `-CONT`) | `outbox_lag_seconds` > 60; alert fires | `docs/runbooks/outbox_stuck.md` |
| 7 | Network partition (orchestrator ↔ agents) | Apply restrictive NetworkPolicy temporarily | A2A timeouts → debate rounds drop; tier escalation | `docs/runbooks/network_partition.md` |
| 8 | Disk full (audit volume) | `dd if=/dev/zero of=/var/lib/postgresql/data/fill bs=1M count=10000` | INSERTs fail; gateway returns 503 | `docs/runbooks/disk_full.md` |
| 9 | KV-cache cold start (semantic cache flush) | `redis-cli FLUSHDB` against the Pinecone-mirror cache | KV-cache hit rate dives below 0.70 floor; alert fires | `docs/runbooks/kv_cache_collapse.md` |

## Procedure

For each injection in order:

1. **Announce in #synapse-oncall:** "Chaos Day injection N starting at HH:MM."
2. **Inject** per the table.
3. **Start a stopwatch.**
4. **Wait for the first alert.** Record `time_to_detect`.
5. **Open the runbook** linked above. Follow it as written — no improvising. Record `time_to_mitigate`.
6. **Restore** the injected resource.
7. **Verify** the SLO burn rate recovers within 10 minutes.

After all nine:

8. **Tally** `time_to_detect` and `time_to_mitigate` per row. Anything > 2× the SLO budget is a finding.
9. **File one issue per finding** with the `chaos-day-finding` label and a one-paragraph reproduction.
10. **Update this runbook** if any procedure was wrong (link the PR from the finding issue).

## Success criteria

A green chaos day means:

- All 9 alerts fired within their advertised windows.
- All 9 runbooks were followable end-to-end without IRC asks.
- Total time-to-mitigate across all 9 < 90 minutes.

A non-green chaos day is not a problem — it's the reason chaos day exists. The findings go straight into the next sprint's backlog.

## Why "non-prod only"

Two of these (1, 4, 8) cause real customer-visible outages. Even the others can leak into PII flows. Run against a fresh project; tear it down after.
