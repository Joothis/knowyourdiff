# ADR 0003: LLM access behind a protocol; LiteLLM pinned with hashes

- Status: accepted (implementation in Phase 2)
- Date: 2026-11-06

## Context

Users must be able to choose any model, including local Ollama models. LiteLLM covers this and
provides cost tables. But LiteLLM had malicious releases on PyPI (1.82.7 and 1.82.8, March 2026)
and a quarantined release (1.107.0, November 2026).

## Decision

- All model calls go through an `LLMClient` protocol in `llm/client.py`. `LiteLLMClient` is the
  default implementation; `FakeLLMClient` replays recorded fixtures for offline tests.
- LiteLLM is pinned to an exact version in `uv.lock` (which records hashes). Upgrades are manual,
  reviewed PRs, never automatic, and only after a release has been public for at least 7 days.
- Every model output is validated against a Pydantic schema at temperature 0.

## Consequences

- Swapping LiteLLM for instructor or pydantic-ai is a one-file change.
- We accept slower uptake of new LiteLLM features in exchange for supply-chain safety.
