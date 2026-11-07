# ADR 0005: MCP server is stdio-only, stateless, with static descriptions

- Status: accepted (implementation in Phase 5)
- Date: 2026-11-06

## Context

The MCP 2026-07-28 revision is stateless: no protocol sessions, and sampling, roots and logging are
deprecated. More than 30 MCP-related CVEs were filed in early 2026; tool poisoning through
descriptions and prompt injection through untrusted content are the main threats.

## Decision

- FastMCP 4.x (`>=4.1,<5`), stdio transport only. No HTTP listener.
- The server calls its own configured model; it never asks the client to sample.
- State between calls is an explicit random `quiz_id` (UUID4) that expires after 30 minutes and is
  bound to the repository root. Holding a handle is not authentication.
- Tool names, descriptions and schemas are hard-coded constants; `tools/list` order is fixed.
- `mask_error_details=True`; logs go to stderr only.

## Consequences

- Remote or hosted use is out of scope until there is a real need and an auth design.
