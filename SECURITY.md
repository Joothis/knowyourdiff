# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub's
[private vulnerability reporting](https://github.com/Joothis/knowyourdiff/security/advisories/new).
Do not open a public issue. You should get a reply within 7 days.

## Threat model in brief

KnowYourDiff reads code you did not necessarily write. We treat all of it as untrusted:

- **Git is called with a fixed argument list and no shell.** External diff drivers, textconv
  filters and fsmonitor hooks configured in a repository are disabled for every call, so a
  hostile repo cannot run code through `kyd`.
- **Diff text and your answers are data, never instructions.** When LLM calls arrive (Phase 2+),
  both are wrapped in delimited blocks, stripped of invisible/bidi characters, size-capped, and
  every model output is schema-validated.
- **The repository is never written to.** Local history lives in your user data directory.
- **The MCP server (Phase 5) is stdio-only, with static tool descriptions.**

## Supported versions

Only the latest release receives fixes until 1.0.
