# SYNAPSE Load Testing — 6 Scenarios

This suite validates SYNAPSE under six distinct production-realistic load
profiles. Each scenario exercises a different invariant or capacity boundary;
together they form the v4.0 load-side acceptance gate.

## Prerequisites

```bash
pip install locust
make up          # API gateway, agents, orchestrator, infra
sleep 30         # let healthchecks settle
curl -sf http://localhost:8000/health
```

Set the API host once:

```bash
export SYNAPSE_API_HOST=http://localhost:8000
```

## Scenario matrix

| # | Scenario              | Users | Spawn rate | Duration | Success criteria                                        | Invariant validated |
|---|-----------------------|------:|-----------:|---------:|---------------------------------------------------------|---------------------|
| 1 | `sustained`           |   100 |         10 |    10 min | p99 < 2000 ms, 0 5xx, 500 orders/min                    | I-10 (latency SLA)  |
| 2 | `ipl_burst`           |   250 |         50 |     5 min | p99 < 5000 ms, 0 5xx, all spike requests acknowledged   | I-10 burst headroom |
| 3 | `multi_disruption`    |    50 |          5 |    10 min | All 3 agent endpoints respond, no consensus deadlock    | I-5 (HITL gate)     |
| 4 | `hitl_flood`          |   200 |         20 |     5 min | Escalation queue depth < 100, websocket render < 200 ms | I-5 (HITL queue)    |
| 5 | `kafka_backpressure`  |    80 |          8 |    10 min | `synapse_kafka_consumer_lag` stays < 10 000              | I-13 (KV-cache stable serialization) + Kafka SLO |
| 6 | `neo4j_concurrent`    |    60 |          6 |    10 min | Neo4j pool wait p95 < 100 ms, no `Neo.TransientError`   | I-3 (deterministic graph queries) |

## Invocation matrix

```bash
SYNAPSE_LOAD_SCENARIO=sustained \
    locust -f tests/load/locustfile.py --host=$SYNAPSE_API_HOST \
        --users 100 --spawn-rate 10 --run-time 10m --headless

SYNAPSE_LOAD_SCENARIO=ipl_burst \
    locust -f tests/load/locustfile.py --host=$SYNAPSE_API_HOST \
        --users 250 --spawn-rate 50 --run-time 5m --headless

SYNAPSE_LOAD_SCENARIO=multi_disruption \
    locust -f tests/load/locustfile.py --host=$SYNAPSE_API_HOST \
        --users 50 --spawn-rate 5 --run-time 10m --headless

SYNAPSE_LOAD_SCENARIO=hitl_flood \
    locust -f tests/load/locustfile.py --host=$SYNAPSE_API_HOST \
        --users 200 --spawn-rate 20 --run-time 5m --headless

SYNAPSE_LOAD_SCENARIO=kafka_backpressure \
    locust -f tests/load/locustfile.py --host=$SYNAPSE_API_HOST \
        --users 80 --spawn-rate 8 --run-time 10m --headless

SYNAPSE_LOAD_SCENARIO=neo4j_concurrent \
    locust -f tests/load/locustfile.py --host=$SYNAPSE_API_HOST \
        --users 60 --spawn-rate 6 --run-time 10m --headless
```

## Run all six sequentially

```bash
bash tests/load/run_load_tests.sh --all
```

CSV + HTML reports land in `tests/load/results/<scenario>_<timestamp>.{csv,html,log}`.

## How scenario selection works

`SYNAPSE_LOAD_SCENARIO` is read at `events.test_start`. The dispatcher narrows
`environment.user_classes` to the single user class matching that scenario, so
even though `locustfile.py` defines six user classes, only one runs per
invocation. Defaults to `sustained` if the variable is unset; raises on
unknown scenario names.

## Make targets

```bash
# default (sustained):
make load-test
# specific scenario:
LOCUST_SCENARIO=ipl_burst make load-test
# all six:
make load-test-all
```

## Validation against invariants

After each run, the script in `run_load_tests.sh` parses the aggregated CSV row
and asserts the per-scenario success criteria. Failure exits non-zero so it can
gate CI. The `synapse_kafka_consumer_lag` SLO for the `kafka_backpressure`
scenario is enforced inline by the `lag_check` task hitting `/metrics` between
bulk-order batches; lag breaches mark the request as failed in Locust's stats.

## Observability hooks

- Prometheus scrapes `/metrics` from the API gateway during the run.
- Jaeger captures distributed traces for the orchestrator's 5-phase consensus
  (sampled at 100 % during load tests via `OTEL_TRACES_SAMPLER=parentbased_always_on`).
- LangSmith captures all Tier-3/Tier-4 LLM calls invoked during the run
  (Tier-2 sampled at 10 % per Phase 8 config).
- Grafana dashboard `SYNAPSE / Load` summarises p50/p95/p99 per agent endpoint.
