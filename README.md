# KnowYourDiff

> **Don't just ship the AI's diff. Know it.**
> 60-second comprehension checks for AI-written code, graded by an LLM judge whose accuracy we publish.

<!-- mcp-name: io.github.joothis/knowyourdiff -->

**Status: pre-alpha (Phase 1 of [the plan](docs/PLAN.md)).** Right now `kyd` can read your staged
diff, find the enclosing function of each change with tree-sitter, and rank the hunks by risk.
The questions, the LLM judge, the hint ladder, the MCP server and the Claude Code plugin come in
the next phases.

## What it will do

Before you commit AI-written code, KnowYourDiff:

1. reads the staged diff and picks the riskiest hunks (new branches, error handling, concurrency,
   security-sensitive calls),
2. asks 2–3 short questions about them ("What happens to `retry_count` if the request times out
   twice?"),
3. grades your answer against a rubric (correctness, causal reasoning, edge cases),
4. replies with a hint, not the solution, and
5. writes an "understanding receipt" you can keep or attach to a PR.

Nudge mode (the default) never blocks a commit. Learning mode, for courses and bootcamps, does.

The judge's agreement with human graders is measured by **KYD-Bench** and published in this
README on every release.

## Try what exists today

```bash
git add -p              # stage something
uvx knowyourdiff check --dry-run
```

Or from a clone:

```bash
uv sync
uv run kyd check --dry-run          # ranked hunks with enclosing functions
uv run kyd check --dry-run --json   # machine-readable
```

## Development

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

Supported languages for code context today: Python, JavaScript, TypeScript, TSX. Other files are
still ranked, just without the enclosing-function context.

## License

MIT. See [LICENSE](LICENSE).
