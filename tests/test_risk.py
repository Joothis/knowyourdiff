from __future__ import annotations

import pytest

from knowyourdiff.diff.models import Hunk, Line
from knowyourdiff.diff.risk import MAX_LINES_PER_SIGNAL, SIGNALS, rank, score_hunk


def make(
    added: list[str] | None = None,
    removed: list[str] | None = None,
    path: str = "app/core.py",
    **kw: bool,
) -> Hunk:
    added_lines = tuple(Line(i + 1, t) for i, t in enumerate(added or []))
    removed_lines = tuple(Line(i + 1, t) for i, t in enumerate(removed or []))
    return Hunk(
        path=path,
        old_path=None,
        language="python",
        source_start=1,
        source_length=len(removed_lines),
        target_start=1,
        target_length=len(added_lines),
        section_header="",
        added=added_lines,
        removed=removed_lines,
        anchor_line=1,
        **kw,
    )


@pytest.mark.parametrize(
    ("line", "signal"),
    [
        ("subprocess.run(cmd, shell=True)", "security"),
        ("token = request.headers['Authorization']", "security"),
        ("except ValueError:", "error_handling"),
        ("promise.catch(handle)", "error_handling"),
        ("async def worker():", "concurrency"),
        ("await Promise.all(jobs)", "concurrency"),
        ("retry_count += 1", "resilience"),
        ("cursor.execute(sql)", "data_access"),
        ("with open(path) as fh:", "io_network"),
        ("if i <= len(items):", "boundaries"),
        ("self.total += amount", "state"),
        ("for item in items:", "control_flow"),
    ],
)
def test_signal_detection(line: str, signal: str) -> None:
    assert signal in score_hunk(make([line])).signals


def test_plain_assignment_has_only_size() -> None:
    assert set(score_hunk(make(["x = compute()"])).signals) == {"size"}


def test_signal_is_capped_per_hunk() -> None:
    lines = [f"except E{i}:" for i in range(10)]
    weight = next(s.weight for s in SIGNALS if s.name == "error_handling")
    assert score_hunk(make(lines)).signals["error_handling"] == weight * MAX_LINES_PER_SIGNAL


def test_removing_a_check_counts_fully() -> None:
    removed = score_hunk(make(removed=["    raise PermissionError('no')"]))
    added = score_hunk(make(["    raise PermissionError('no')"]))
    assert removed.signals["error_handling"] == added.signals["error_handling"]
    assert "removes error handling" in removed.reasons


def test_removing_a_loop_counts_half() -> None:
    removed = score_hunk(make(removed=["for x in y:"]))
    added = score_hunk(make(["for x in y:"]))
    assert removed.signals["control_flow"] == added.signals["control_flow"] / 2


def test_trivial_lines_are_ignored() -> None:
    score = score_hunk(make(["# comment", "", "import os", "from a import b", "    )"]))
    assert score.signals == {}
    assert score.total == 0
    assert "only comments, imports or blank lines" in score.reasons


@pytest.mark.parametrize(
    ("path", "multiplier"),
    [
        ("src/app.py", 1.0),
        ("tests/test_app.py", 0.6),
        ("web/button.test.tsx", 0.6),
        ("pkg/thing_test.go", 0.6),
        ("docs/guide.md", 0.2),
        ("config/settings.yaml", 0.5),
        ("package-lock.json", 0.05),
        ("dist/app.min.js", 0.05),
    ],
)
def test_path_multipliers(path: str, multiplier: float) -> None:
    assert score_hunk(make(["if a: b()"], path=path)).multiplier == multiplier


def test_deleted_file_is_downweighted() -> None:
    normal = score_hunk(make(removed=["try:", "    x()"]))
    deleted = score_hunk(make(removed=["try:", "    x()"], is_deleted_file=True))
    assert deleted.total == pytest.approx(normal.total * 0.3, abs=0.01)


def test_reasons_strongest_first() -> None:
    score = score_hunk(make(["for x in y:", "subprocess.run(x)"]))
    assert score.reasons[0] == "adds security-sensitive code"


def test_rank_is_stable_and_descending() -> None:
    a = make(["x = 1"], path="a.py")
    b = make(["eval(user_input)"], path="b.py")
    c = make(["y = 2"], path="c.py")
    assert [h.path for h, _ in rank([a, b, c])] == ["b.py", "a.py", "c.py"]
