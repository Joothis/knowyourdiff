"""Turn ``git diff`` text into :class:`Hunk` objects."""

from __future__ import annotations

from unidiff.errors import UnidiffParseError
from unidiff.patch import Hunk as UnidiffHunk
from unidiff.patch import PatchedFile, PatchSet

from knowyourdiff.diff.models import Hunk, Line, detect_language

__all__ = ["DiffParseError", "parse_diff"]


class DiffParseError(ValueError):
    """The text is not a unified diff we can read."""


def _clean(value: str) -> str:
    return value.rstrip("\r\n")


def _anchor_line(hunk: UnidiffHunk) -> int:
    """New-file line next to the first change (used when a hunk only removes lines)."""
    previous_target = 0
    seen_change = False
    for line in hunk:
        if line.is_added:
            return line.target_line_no or 0
        if line.is_removed:
            seen_change = True
            continue
        if line.target_line_no is not None:
            if seen_change:
                return line.target_line_no or 0
            previous_target = int(line.target_line_no)
    return previous_target or int(hunk.target_start)


def _convert(patched_file: PatchedFile, hunk: UnidiffHunk) -> Hunk:
    path = str(patched_file.path)
    source = str(patched_file.source_file or "")
    target = str(patched_file.target_file or "")
    old_path: str | None = None
    if source.startswith("a/") and target.startswith("b/") and source[2:] != target[2:]:
        old_path = source[2:]

    added = tuple(Line(ln.target_line_no or 0, _clean(ln.value)) for ln in hunk if ln.is_added)
    removed = tuple(Line(ln.source_line_no or 0, _clean(ln.value)) for ln in hunk if ln.is_removed)
    return Hunk(
        path=path,
        old_path=old_path,
        language=detect_language(path),
        source_start=int(hunk.source_start),
        source_length=int(hunk.source_length),
        target_start=int(hunk.target_start),
        target_length=int(hunk.target_length),
        section_header=_clean(str(hunk.section_header or "")).strip(),
        added=added,
        removed=removed,
        is_new_file=bool(patched_file.is_added_file),
        is_deleted_file=bool(patched_file.is_removed_file),
        anchor_line=_anchor_line(hunk),
    )


def parse_diff(text: str) -> list[Hunk]:
    """Parse a unified diff. Binary files are skipped; hunk order follows the diff."""
    if not text.strip():
        return []
    try:
        patch = PatchSet(text)
    except UnidiffParseError as exc:
        raise DiffParseError(str(exc)) from exc

    hunks: list[Hunk] = []
    for patched_file in patch:
        if patched_file.is_binary_file:
            continue
        hunks.extend(_convert(patched_file, hunk) for hunk in patched_file)
    return hunks
