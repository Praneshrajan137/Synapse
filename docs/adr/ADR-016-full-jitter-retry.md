# ADR-016: Full Jitter Retry Strategy

## Status
Accepted

## Context
Fixed-delay retries cause thundering herd problems. Exponential backoff without jitter still creates synchronized retry waves.

## Decision
ALL retries in SYNAPSE use Full Jitter: sleep = random(0, min(cap, base * 2^attempt)). Implementation in synapse_common.retry. Fixed-delay time.sleep in non-test code is a PR rejection.

## Consequences
- Eliminates thundering herd on service recovery
- Jittered delays spread load evenly
- Pre-commit hook enforces jitter usage

## Alternatives Rejected
- Fixed delay: causes thundering herd
- Exponential backoff without jitter: synchronized retry waves
- Decorrelated Jitter: Full Jitter has better worst-case behavior per AWS analysis
