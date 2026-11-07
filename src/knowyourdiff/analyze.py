"""Staged diff → ranked hunks with code context. The input to question generation (Phase 2)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from knowyourdiff import git
from knowyourdiff.diff.context import CodeUnit, HunkContext, extract_context
from knowyourdiff.diff.models import Hunk
from knowyourdiff.diff.parse import parse_diff
from knowyourdiff.diff.risk import RiskScore, rank

__all__ = ["Analysis", "AnalyzedHunk", "analyze_diff", "analyze_staged"]

JSON_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class AnalyzedHunk:
    hunk: Hunk
    risk: RiskScore
    context: HunkContext


@dataclass(frozen=True)
class Analysis:
    repo_root: Path | None
    tree_sha: str | None
    hunks: tuple[AnalyzedHunk, ...]
    """Riskiest first."""

    def top(self, n: int) -> tuple[AnalyzedHunk, ...]:
        return self.hunks[: max(n, 0)]

    def to_dict(self, *, top: int | None = None) -> dict[str, Any]:
        selected = self.hunks if top is None else self.top(top)
        return {
            "schema_version": JSON_SCHEMA_VERSION,
            "repo_root": str(self.repo_root) if self.repo_root else None,
            "tree_sha": self.tree_sha,
            "total_hunks": len(self.hunks),
            "hunks": [_hunk_dict(i, item) for i, item in enumerate(selected, start=1)],
        }


def _unit_dict(unit: CodeUnit | None) -> dict[str, Any] | None:
    if unit is None:
        return None
    return {"kind": unit.kind, "name": unit.name, "start": unit.start_line, "end": unit.end_line}


def _hunk_dict(rank_no: int, item: AnalyzedHunk) -> dict[str, Any]:
    h, ctx = item.hunk, item.context
    return {
        "rank": rank_no,
        "id": h.id,
        "path": h.path,
        "old_path": h.old_path,
        "language": h.language,
        "target_start": h.target_start,
        "target_length": h.target_length,
        "added": len(h.added),
        "removed": len(h.removed),
        "new_file": h.is_new_file,
        "deleted_file": h.is_deleted_file,
        "score": item.risk.total,
        "signals": item.risk.signals,
        "reasons": list(item.risk.reasons),
        "context_supported": ctx.supported,
        "enclosing": _unit_dict(ctx.enclosing),
        "touched": [_unit_dict(u) for u in ctx.touched],
        "symbols": list(ctx.symbols),
    }


def analyze_diff(
    diff_text: str,
    blob_reader: Callable[[str], bytes | None] | None = None,
    *,
    repo_root: Path | None = None,
    tree_sha: str | None = None,
) -> Analysis:
    """Analyze diff text. ``blob_reader(path) -> bytes | None`` supplies new-file contents.

    Best results come from a zero-context diff (``-U0``): every edit is its own hunk, and edits
    that land in the same function are then merged back together, so each analyzed hunk maps to
    one function or class rather than to whatever git's context lines happened to join.
    """

    def source_for(hunk: Hunk) -> bytes | None:
        if blob_reader is None or hunk.is_deleted_file:
            return None
        return blob_reader(hunk.path)

    pairs = [(h, extract_context(h, source_for(h))) for h in parse_diff(diff_text)]
    merged: list[tuple[Hunk, HunkContext]] = []
    for hunk, context in pairs:
        if merged and _same_unit(merged[-1], (hunk, context)):
            combined = merge_hunks(merged[-1][0], hunk)
            merged[-1] = (combined, extract_context(combined, source_for(combined)))
        else:
            merged.append((hunk, context))

    contexts = {id(h): ctx for h, ctx in merged}
    items = [
        AnalyzedHunk(hunk=h, risk=risk, context=contexts[id(h)])
        for h, risk in rank([h for h, _ in merged])
    ]
    return Analysis(repo_root=repo_root, tree_sha=tree_sha, hunks=tuple(items))


def _same_unit(a: tuple[Hunk, HunkContext], b: tuple[Hunk, HunkContext]) -> bool:
    """Consecutive hunks of one file whose changes sit in the same function or class."""
    (ha, ca), (hb, cb) = a, b
    return (
        ha.path == hb.path
        and ca.enclosing is not None
        and cb.enclosing is not None
        and (ca.enclosing.start_line, ca.enclosing.end_line)
        == (cb.enclosing.start_line, cb.enclosing.end_line)
    )


def merge_hunks(a: Hunk, b: Hunk) -> Hunk:
    """One hunk covering both ``a`` and ``b`` (same file, ``a`` first)."""
    target_end = max(a.target_start + a.target_length, b.target_start + b.target_length)
    source_end = max(a.source_start + a.source_length, b.source_start + b.source_length)
    return replace(
        a,
        source_length=source_end - a.source_start,
        target_length=target_end - a.target_start,
        added=a.added + b.added,
        removed=a.removed + b.removed,
    )


def analyze_staged(cwd: Path | str | None = None, *, context_lines: int = 0) -> Analysis:
    """Analyze what is currently staged in the repository containing ``cwd``."""
    root = git.repo_root(cwd)
    diff_text = git.staged_diff(root, context_lines=context_lines)
    try:
        tree_sha: str | None = git.index_tree_sha(root)
    except git.GitError:  # e.g. unresolved merge conflicts
        tree_sha = None

    cache: dict[str, bytes | None] = {}

    def read(path: str) -> bytes | None:
        if path not in cache:
            cache[path] = git.staged_blob(path, root)
        return cache[path]

    return analyze_diff(diff_text, read, repo_root=root, tree_sha=tree_sha)
