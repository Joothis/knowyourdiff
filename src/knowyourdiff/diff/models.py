from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

#: File extension → language name. Languages with a tree-sitter grammar get code context;
#: the rest are still ranked by the risk scorer.
LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".swift": "swift",
    ".sh": "shell",
    ".sql": "sql",
}


def detect_language(path: str) -> str | None:
    return LANGUAGE_BY_EXTENSION.get(PurePosixPath(path).suffix.lower())


@dataclass(frozen=True, slots=True)
class Line:
    """One added or removed line. ``number`` is 1-based in the new file (added) or old file
    (removed)."""

    number: int
    text: str


@dataclass(frozen=True, slots=True)
class Hunk:
    path: str
    """Repo-relative path, forward slashes. For a deleted file, the old path."""
    old_path: str | None
    """Set only when the file was renamed or copied."""
    language: str | None
    source_start: int
    source_length: int
    target_start: int
    target_length: int
    section_header: str
    added: tuple[Line, ...]
    removed: tuple[Line, ...]
    is_new_file: bool = False
    is_deleted_file: bool = False
    anchor_line: int = 0
    """Line in the new file nearest to the change. For pure deletions, the line that now sits
    where the removed lines were."""

    @property
    def id(self) -> str:
        return f"{self.path}:{self.target_start}"

    @property
    def changed_line_count(self) -> int:
        return len(self.added) + len(self.removed)

    @property
    def changed_rows(self) -> tuple[int, ...]:
        """1-based new-file line numbers to locate in the staged blob."""
        if self.added:
            return tuple(line.number for line in self.added)
        return (self.anchor_line,) if self.anchor_line > 0 else ()
