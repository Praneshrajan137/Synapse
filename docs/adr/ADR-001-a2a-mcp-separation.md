# ADR-001: A2A/MCP Protocol Separation

## Status
Accepted

## Context
SYNAPSE uses two communication protocols: Agent-to-Agent (A2A) and Model Context Protocol (MCP). Conflating them leads to confused routing, broken tool calls, and protocol violations.

## Decision
A2A (Google/Linux Foundation JSON-RPC 2.0) is used exclusively for inter-agent communication: proposal(), debate_respond(), execute(). MCP (Anthropic) is used exclusively for agent-to-tool communication. The two are never mixed in the same handler or endpoint (I-9).

## Consequences
- Clear separation of concerns between agent coordination and tool execution
- Each protocol can evolve independently
- Requires separate handler modules in each agent (a2a/ directory)

## Alternatives Rejected
- Single unified protocol: rejected because A2A and MCP serve fundamentally different purposes
- gRPC for inter-agent: rejected because A2A is the emerging standard for multi-agent systems
