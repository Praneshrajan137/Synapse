# Quality Gate — Sprint 5: Hardening

## Scope
Productionize SYNAPSE through chaos engineering, load testing, security
hardening (JWT, audit immutability, nginx rate limiting), mutation testing,
Schemathesis API fuzzing, and DragonflyDB evaluation.

## Milestones
| # | Milestone | Verification |
|---|-----------|--------------|
| 1 | 9 chaos failure modes pass | `pytest tests/chaos -v` (E-S5-01..05, 11, 12) |
| 2 | 6 Locust load scenarios green (per `tests/load/README.md`) | `bash tests/load/run_load_tests.sh --all` |
| 3 | JWT (RS256) on all agent endpoints | `pytest tests/security/test_jwt_auth.py -v` (E-S5-08) |
| 4 | Audit immutability enforced (Postgres role permissions) | `pytest tests/security/test_audit_immutability.py -v` |
| 5 | nginx rate limiting + security headers | `pytest tests/security/test_nginx.py -v` (E-S5-06) |
| 6 | Mutation testing — rewards < 15% survival, guardrails/audit < 10% | `bash tests/mutation/run_mutation.sh` (E-S5-04, E-S5-10) |
| 7 | Schemathesis API fuzz — all agents `/openapi.json` reachable | `bash tests/api_fuzz/run_fuzz.sh` (E-S5-03) |
| 8 | DragonflyDB evaluation documented | ADR-019 |
| 9 | sprint5-exit-gate passes | `make sprint5-exit-gate` |

## Acceptance criteria
- All 9 milestones green
- p99 latency < 2 s on `sustained` load scenario (I-10)
- Zero P0/P1 security findings from Trivy + bandit
- All 8 agents have hermetic chaos fixtures (`chaos_*` namespace, E-S5-11)
- All RNG-dependent tests use `np.random.default_rng(seed)` (E-S5-12)

## Verification command
```bash
make sprint5-verify
```
