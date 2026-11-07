from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from knowyourdiff import git
from tests.conftest import Repo


def test_every_call_uses_safe_config_and_no_shell(
    make_repo: Callable[[str], Repo], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make_repo("r")
    calls: list[tuple[list[str], dict[str, Any]]] = []
    real_run = subprocess.run

    def spy(argv: list[str], **kwargs: Any) -> Any:
        calls.append((argv, kwargs))
        return real_run(argv, **kwargs)

    monkeypatch.setattr(git.subprocess, "run", spy)
    git.staged_diff(repo.path)
    argv, kwargs = calls[-1]
    assert kwargs.get("shell") is not True
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert list(git.SAFE_CONFIG) == argv[1 : 1 + len(git.SAFE_CONFIG)]
    for flag in ("--no-ext-diff", "--no-textconv", "--cached"):
        assert flag in argv


def test_external_diff_env_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_EXTERNAL_DIFF", "evil")
    assert "GIT_EXTERNAL_DIFF" not in git._env()


def _arm_textconv_trap(repo: Repo, marker: Path) -> None:
    repo.write(".gitattributes", "*.py diff=trap\n")
    repo.write("a.py", "x = 1\n")
    repo.commit()
    marker_path = marker.as_posix()
    repo.git("config", "diff.trap.textconv", f"touch '{marker_path}'; cat")
    repo.git("config", "diff.trap.command", f"touch '{marker_path}'; true")
    repo.write("a.py", "x = 2\n")
    repo.stage()


def test_repo_configured_diff_drivers_never_run(
    make_repo: Callable[[str], Repo], tmp_path: Path
) -> None:
    repo = make_repo("trap")
    marker = tmp_path / "pwned"
    _arm_textconv_trap(repo, marker)

    # Sanity check: a plain `git diff` does run the driver, so the trap is real on this machine.
    subprocess.run(["git", "diff", "--cached"], cwd=repo.path, capture_output=True, check=False)
    if not marker.exists():
        pytest.skip("this git cannot run the trap command (no POSIX shell available)")
    marker.unlink()

    diff = git.staged_diff(repo.path)
    assert "+x = 2" in diff
    assert not marker.exists()


def test_staged_blob_reads_index_not_worktree(make_repo: Callable[[str], Repo]) -> None:
    repo = make_repo("r")
    repo.write("f.txt", "staged\n")
    repo.stage()
    repo.write("f.txt", "unstaged edit\n")
    assert git.staged_blob("f.txt", repo.path) == b"staged\n"
    assert git.staged_blob("missing.txt", repo.path) is None


@pytest.mark.parametrize("bad", ["", "-c", "/etc/passwd", "a\x00b"])
def test_staged_blob_rejects_suspicious_paths(bad: str) -> None:
    with pytest.raises(ValueError):
        git.staged_blob(bad, ".")


def test_fresh_repo_without_commits(make_repo: Callable[[str], Repo]) -> None:
    repo = make_repo("fresh")
    assert not git.head_exists(repo.path)
    repo.write("new.py", "print('hi')\n")
    repo.stage()
    assert "+print('hi')" in git.staged_diff(repo.path)


def test_index_tree_sha_tracks_staged_content(make_repo: Callable[[str], Repo]) -> None:
    repo = make_repo("r")
    repo.write("f.py", "a = 1\n")
    repo.stage()
    first = git.index_tree_sha(repo.path)
    assert first == git.index_tree_sha(repo.path)
    repo.write("f.py", "a = 2\n")
    assert git.index_tree_sha(repo.path) == first  # unstaged edits don't change it
    repo.stage()
    assert git.index_tree_sha(repo.path) != first


def test_outside_a_repository_raises(tmp_path: Path) -> None:
    lonely = tmp_path / "not-a-repo"
    lonely.mkdir()
    with pytest.raises(git.GitError):
        git.repo_root(lonely)


def test_negative_context_rejected() -> None:
    with pytest.raises(ValueError):
        git.staged_diff(".", context_lines=-1)
