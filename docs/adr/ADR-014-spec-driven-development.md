# ADR-014: Spec-Driven Development (SDD)

## Status
Accepted

## Context
Traditional TDD writes tests after understanding the code. For a multi-agent system with 14 invariants, we need tests derived from formal specifications before any code is written.

## Decision
Every agent has a spec.yaml defining invariants, pre/postconditions, state machine, metamorphic relations, and consumer contracts. Tests are auto-generated from specs (RED), then code is implemented to make them GREEN. Coverage checker ensures 100% invariant coverage.

## Consequences
- Specs are the single source of truth for agent behavior
- Auto-generated tests ensure no invariant is accidentally untested
- Ralph loop automates the iterative RED→GREEN cycle

## Alternatives Rejected
- Manual test writing: risk of missing invariants
- Property-based testing only: doesn't capture state machine behavior
