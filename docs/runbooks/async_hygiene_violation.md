# Runbook: Async Hygiene Violation

**Test failure:** `tests/contracts/test_async_hygiene.py`
(WS-1 §1, ADR-025).

## What it means
A new commit introduced a synchronous I/O call inside an `async def`
function. The most common offenders are:

| Pattern | Why it's wrong |
|---|---|
| `requests.post(...)` inside `async def` | Blocks the event loop. Use `synapse_common.clients.get_client(name)`. |
| `psycopg2.connect(...)` inside `async def` | Same. Use `async_sessionmaker` + asyncpg. |
| `time.sleep(...)` inside `async def` | Same. Use `await asyncio.sleep(...)`. |
| `httpx.Client()` (synchronous) | Same. Use `httpx.AsyncClient` from bulkhead profile. |

## How to fix
1. Look at the test output — it points to the file + line number.
2. Replace the sync call with its async equivalent:
   - `requests` → `await get_client(...).post(...)`
   - `psycopg2` → `async with session_factory() as session: ...`
   - `time.sleep(s)` → `await asyncio.sleep(s)`
3. Re-run `pytest tests/contracts/test_async_hygiene.py`.

## Postmortem Anchor
The first reported incident
([Sprint 7 audit](docs/adr/ADR-025-resilience-mesh.md)) traced
event-loop stalls to two `requests.post` and one `psycopg2.connect`
inside `async def` in `api/routers/decisions.py`.
