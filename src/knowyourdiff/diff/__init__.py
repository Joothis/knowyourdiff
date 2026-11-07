"""Understanding a staged diff: parsing, code context and risk ranking. No LLM calls here."""

from knowyourdiff.diff.context import CodeUnit, HunkContext, extract_context
from knowyourdiff.diff.models import Hunk, Line
from knowyourdiff.diff.parse import parse_diff
from knowyourdiff.diff.risk import RiskScore, score_hunk

__all__ = [
    "CodeUnit",
    "Hunk",
    "HunkContext",
    "Line",
    "RiskScore",
    "extract_context",
    "parse_diff",
    "score_hunk",
]
