# ADR 0002: Pure engine functions, orchestrated by LangGraph

- Status: accepted (implementation in Phase 3)
- Date: 2026-11-06

## Context

The quiz loop is short: select hunks → generate questions → collect answer → judge → hint →
retry or next → record. A plain Python loop would work for the CLI. But the same loop must also
be driven from MCP tool calls (stateless, one call per step) and resumed across separate git-hook
invocations.

## Decision

- Each step is a pure function in `engine/`, unit-testable without any framework.
- `graph.py` wires them into a LangGraph `StateGraph`, using `interrupt()` to wait for answers
  and `langgraph-checkpoint-sqlite` keyed by `thread_id = index tree SHA`.
- Every LLM call gets its own node, because LangGraph re-runs an interrupted node from the top
  on resume; an LLM call in the same node as `interrupt()` would be paid for twice.
- `LANGGRAPH_STRICT_MSGPACK=true` restricts checkpoint deserialization.

## Consequences

- One orchestration path for CLI, hook and MCP; resume after Ctrl-C comes for free.
- LangGraph releases often. Pin it, and keep it out of `engine/` so it can be replaced by a plain
  loop if it becomes a burden.
