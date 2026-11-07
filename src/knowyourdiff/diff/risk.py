"""Deterministic risk scoring: which hunks deserve a comprehension question?

The score is a weighted count of signals on changed lines. It is intentionally simple and fully
explainable: every point comes with a human-readable reason. No LLM is involved, so ranking is
free, instant and reproducible (it is pinned by golden-file tests).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from knowyourdiff.diff.models import Hunk, Line

__all__ = ["SIGNALS", "RiskScore", "Signal", "rank", "score_hunk"]

#: A signal counts at most this many matching lines, so one huge hunk cannot drown out the rest.
MAX_LINES_PER_SIGNAL = 3
#: Removing code that matches these signals is as risky as adding it (e.g. deleting a check).
REMOVAL_SENSITIVE = frozenset({"error_handling", "security", "resilience", "boundaries"})
REMOVAL_FACTOR = 0.5


@dataclass(frozen=True)
class Signal:
    name: str
    weight: float
    pattern: re.Pattern[str]
    label: str


SIGNALS: tuple[Signal, ...] = (
    Signal(
        "security",
        4.0,
        re.compile(
            r"\b(subprocess|os\.system|eval|exec|pickle|marshal|yaml\.load|shell\s*=\s*True"
            r"|password|passwd|secret|api[_-]?key|token|jwt|crypto|hashlib|bcrypt|hmac"
            r"|innerHTML|dangerouslySetInnerHTML|child_process|deserializ\w*|sanitiz\w*"
            r"|csrf|auth\w*|permission\w*|verify\s*=\s*False)\b",
            re.IGNORECASE,
        ),
        "security-sensitive code",
    ),
    Signal(
        "error_handling",
        3.0,
        re.compile(
            r"\b(try|except|catch|finally|raise|throw|rescue|panic|recover)\b|\.catch\(|reject\("
        ),
        "error handling",
    ),
    Signal(
        "concurrency",
        3.0,
        re.compile(
            r"\b(async|await|threading|Thread|R?Lock|Mutex|mutex|Semaphore|asyncio"
            r"|multiprocessing|concurrent|synchronized|atomic|setTimeout|setInterval)\b"
            r"|Promise\.(all|race|any|allSettled)\b"
        ),
        "concurrency",
    ),
    Signal(
        "resilience",
        2.0,
        re.compile(
            r"(retr(y|ies)|timeout|backoff|deadline|circuit|rate_?limit|cache|ttl|expir)",
            re.IGNORECASE,
        ),
        "retries, timeouts or caching",
    ),
    Signal(
        "data_access",
        2.0,
        re.compile(
            r"\b(execute(many)?|cursor|SELECT|INSERT|UPDATE|DELETE|rollback|transaction)\b"
            r"|\.query\("
        ),
        "database access",
    ),
    Signal(
        "io_network",
        2.0,
        re.compile(
            r"\b(open|fetch|requests|httpx|urllib|axios|socket|readFile|writeFile|unlink"
            r"|rmtree|shutil|os\.remove)\b|https?://"
        ),
        "file or network I/O",
    ),
    Signal(
        "boundaries",
        1.5,
        re.compile(
            r"<=|>=|\[\s*-1\s*\]|\blen\(|\.length\b|\brange\(|\bslice\(|\[\s*\w*\s*:\s*\w*\s*\]"
        ),
        "boundaries and indexing",
    ),
    Signal(
        "state",
        1.5,
        re.compile(r"\b(global|nonlocal)\b|\b(self|this)\.\w+\s*(\+|-|\*|/)?=(?!=)"),
        "shared or object state",
    ),
    Signal(
        "control_flow",
        1.0,
        re.compile(r"\b(if|elif|else|switch|case|match|while|for|break|continue|yield)\b|\?\?"),
        "branching and loops",
    ),
)

_TRIVIAL = re.compile(
    r"""^\s*(
        $                                   # blank
      | (\#|//|/\*|\*|\*/|<!--)             # comment
      | (import\s|from\s+\S+\s+import\s)    # python / js imports
      | (export\s+\*\s+from\s)
      | (const|let|var)\s+\w+\s*=\s*require\(
      | [)\]}]+[;,]?\s*$                    # closing brackets only
    )""",
    re.VERBOSE,
)

_LOCKFILES = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "uv.lock",
        "poetry.lock",
        "Cargo.lock",
        "Gemfile.lock",
        "composer.lock",
        "go.sum",
    }
)
_DOC_SUFFIXES = frozenset({".md", ".rst", ".txt", ".adoc"})
_CONFIG_SUFFIXES = frozenset({".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".lock", ".xml"})


@dataclass(frozen=True)
class RiskScore:
    total: float
    signals: dict[str, float] = field(default_factory=dict)
    """Points per signal name (after caps, before the path multiplier)."""
    reasons: tuple[str, ...] = ()
    multiplier: float = 1.0


def _is_trivial(line: Line) -> bool:
    return bool(_TRIVIAL.match(line.text))


def _path_multiplier(path: str) -> tuple[float, str | None]:
    p = PurePosixPath(path)
    name = p.name
    if name in _LOCKFILES or name.endswith((".min.js", ".snap", ".map")):
        return 0.05, "generated or lock file"
    if p.suffix.lower() in _DOC_SUFFIXES:
        return 0.2, "documentation"
    if p.suffix.lower() in _CONFIG_SUFFIXES:
        return 0.5, "configuration"
    parts = {part.lower() for part in p.parts[:-1]}
    if (
        parts & {"test", "tests", "__tests__", "spec"}
        or name.startswith("test_")
        or re.search(r"(_test\.\w+|\.(test|spec)\.\w+)$", name)
    ):
        return 0.6, "test code"
    return 1.0, None


def score_hunk(hunk: Hunk) -> RiskScore:
    code_added = [ln for ln in hunk.added if not _is_trivial(ln)]
    code_removed = [ln for ln in hunk.removed if not _is_trivial(ln)]

    points: dict[str, float] = {}
    signal_reasons: list[tuple[float, str]] = []
    for signal in SIGNALS:
        added_hits = sum(1 for ln in code_added if signal.pattern.search(ln.text))
        removed_hits = sum(1 for ln in code_removed if signal.pattern.search(ln.text))
        removal_weight = 1.0 if signal.name in REMOVAL_SENSITIVE else REMOVAL_FACTOR
        effective = min(added_hits + removed_hits * removal_weight, MAX_LINES_PER_SIGNAL)
        if effective <= 0:
            continue
        points[signal.name] = round(signal.weight * effective, 2)
        verb = "changes" if added_hits and removed_hits else "adds" if added_hits else "removes"
        signal_reasons.append((points[signal.name], f"{verb} {signal.label}"))

    # Strongest signal first; sorted() is stable, so equal points keep SIGNALS order.
    reasons = [text for _, text in sorted(signal_reasons, key=lambda pair: -pair[0])]
    changed_code = len(code_added) + len(code_removed)
    if changed_code:
        points["size"] = round(min(math.log2(1 + changed_code), 4.0), 2)

    multiplier, path_reason = _path_multiplier(hunk.path)
    if hunk.changed_line_count and not changed_code:
        multiplier *= 0.1
        reasons.append("only comments, imports or blank lines")
    if hunk.is_deleted_file:
        multiplier *= 0.3
        reasons.append("file deleted")
    if path_reason:
        reasons.append(path_reason)

    total = round(sum(points.values()) * multiplier, 2)
    return RiskScore(total=total, signals=points, reasons=tuple(reasons), multiplier=multiplier)


def rank(hunks: list[Hunk]) -> list[tuple[Hunk, RiskScore]]:
    """Hunks with scores, riskiest first. Ties keep diff order, so ranking is deterministic."""
    scored = [(hunk, score_hunk(hunk)) for hunk in hunks]
    return sorted(scored, key=lambda pair: -pair[1].total)
