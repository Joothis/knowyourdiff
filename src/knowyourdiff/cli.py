"""The ``kyd`` command line."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.syntax import Syntax
from rich.table import Table

from knowyourdiff import __version__, git
from knowyourdiff.analyze import Analysis, AnalyzedHunk, analyze_staged

app = typer.Typer(
    name="kyd",
    help="KnowYourDiff: prove you understood the AI's code before you commit it.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()
err_console = Console(stderr=True)

_SYNTAX_LEXERS = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "tsx": "tsx",
}


def _version(value: bool) -> None:
    if value:
        console.print(f"knowyourdiff {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", "-V", callback=_version, is_eager=True, help="Show the version."),
    ] = False,
) -> None:
    """KnowYourDiff command line."""


def _location(item: AnalyzedHunk) -> str:
    h = item.hunk
    end = h.target_start + max(h.target_length - 1, 0)
    return f"{h.path}:{h.target_start}-{end}"


def _render_table(analysis: Analysis, top: int) -> None:
    table = Table(
        title=f"Riskiest staged hunks ({min(top, len(analysis.hunks))} of {len(analysis.hunks)})",
        title_justify="left",
    )
    table.add_column("#", justify="right", style="bold")
    table.add_column("Risk", justify="right")
    table.add_column("Where", overflow="fold", ratio=3)
    table.add_column("In", overflow="fold", ratio=2)
    table.add_column("Why", overflow="fold", ratio=3)
    for rank_no, item in enumerate(analysis.top(top), start=1):
        table.add_row(
            str(rank_no),
            f"{item.risk.total:.1f}",
            escape(_location(item)),
            escape(_where_in(item)),
            escape(_why(item)),
        )
    console.print(table)


def _where_in(item: AnalyzedHunk) -> str:
    ctx = item.context
    if ctx.enclosing is not None:
        return ctx.enclosing.label
    if not ctx.supported:
        return "-"
    top_level = [u for u in ctx.touched if u.kind != "method"]
    if not top_level:
        return "module level"
    names = ", ".join(u.name or "<anonymous>" for u in top_level[:3])
    more = f" +{len(top_level) - 3}" if len(top_level) > 3 else ""
    return f"{len(top_level)} definitions: {names}{more}"


def _why(item: AnalyzedHunk, limit: int = 3) -> str:
    reasons = list(item.risk.reasons)
    if not reasons:
        return "small change"
    shown = ", ".join(reasons[:limit])
    return f"{shown} (+{len(reasons) - limit} more)" if len(reasons) > limit else shown


def _render_code(item: AnalyzedHunk, rank_no: int) -> None:
    ctx = item.context
    if not ctx.snippet:
        return
    changed = {line.number for line in item.hunk.added}
    code = "\n".join(line.text for line in ctx.snippet)
    lexer = _SYNTAX_LEXERS.get(item.hunk.language or "", "text")
    console.rule(f"#{rank_no} {escape(_location(item))}")
    if ctx.symbols:
        console.print(f"[dim]symbols:[/] {escape(', '.join(ctx.symbols))}")
    console.print(
        Syntax(
            code,
            lexer,
            line_numbers=True,
            start_line=ctx.snippet[0].number,
            highlight_lines=changed,
            word_wrap=True,
        )
    )


@app.command()
def check(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Analyze and rank only; never call a model.")
    ] = False,
    top: Annotated[int, typer.Option("--top", "-n", min=1, help="How many hunks to show.")] = 5,
    as_json: Annotated[bool, typer.Option("--json", help="Print machine-readable JSON.")] = False,
    show_code: Annotated[
        bool, typer.Option("--show-code", help="Print the code around each top hunk.")
    ] = False,
    repo: Annotated[
        Path | None, typer.Option("--repo", help="Repository path (default: current directory).")
    ] = None,
    context_lines: Annotated[
        int,
        typer.Option(
            "--context-lines",
            min=0,
            max=20,
            help="Diff context lines. 0 (default) splits edits so each maps to one function.",
        ),
    ] = 0,
) -> None:
    """Rank the staged hunks by risk and show the code each one lives in."""
    try:
        analysis = analyze_staged(repo, context_lines=context_lines)
    except git.GitError as exc:
        err_console.print(f"[red]error:[/] {escape(str(exc))}")
        raise typer.Exit(2) from exc

    if as_json:
        typer.echo(json.dumps(analysis.to_dict(top=top), indent=2))
        return

    if not analysis.hunks:
        console.print("Nothing staged. Stage some changes with [bold]git add[/] first.")
        return

    if not dry_run:
        console.print(
            "[yellow]Questions and grading arrive in the next release; "
            "showing the analysis only (same as --dry-run).[/]"
        )
    _render_table(analysis, top)
    if show_code:
        for rank_no, item in enumerate(analysis.top(top), start=1):
            _render_code(item, rank_no)
