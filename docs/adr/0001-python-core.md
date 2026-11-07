# ADR 0001: Python core, thin adapters

- Status: accepted
- Date: 2026-11-06

## Context

KnowYourDiff has to reach four surfaces: a CLI, a git/pre-commit hook, an MCP server and a Claude
Code plugin, with a VS Code extension later. The eval suite (KYD-Bench) needs scipy-class
statistics and Inspect AI, both Python. The maintainer's strongest language is Python.

## Decision

One Python 3.11+ package, `knowyourdiff`, holds all logic. Every surface is a thin adapter:

- CLI and hook: Typer commands in `cli.py`.
- MCP: FastMCP server in `mcp_server.py`, launched with `uvx knowyourdiff mcp`.
- Claude Code plugin: static files at the repo root that call the CLI and the MCP server.

Packaging uses hatchling and uv. Two console scripts, `kyd` and `knowyourdiff`, point at the same
app so that both `uvx knowyourdiff` and the short `kyd` work.

## Consequences

- No second implementation to keep in sync; the eval suite tests the same code users run.
- Users need Python or uv. `uvx` makes this a single command; the VS Code extension will shell out
  to it.
