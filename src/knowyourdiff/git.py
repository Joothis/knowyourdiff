"""The only module allowed to run git.

KnowYourDiff reads repositories whose authors it does not trust. A repository can configure
commands that git runs on our behalf: external diff drivers (``diff.external``,
``diff.<x>.command``, ``GIT_EXTERNAL_DIFF``), textconv filters (``diff.<x>.textconv``) and
fsmonitor hooks (``core.fsmonitor``). Every call here therefore:

* runs ``git`` with a fixed argument list and ``shell=False``;
* disables fsmonitor and forces plain, prefix-stable diff output with ``-c`` overrides;
* passes ``--no-ext-diff --no-textconv`` to every diff;
* reads blobs with ``git cat-file blob``, which never applies filters.

The caller's environment is otherwise preserved on purpose: inside a git hook, ``GIT_DIR`` and
``GIT_INDEX_FILE`` point at the index being committed (``git commit -a`` uses a temporary index),
and we must read that one.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

__all__ = [
    "SAFE_CONFIG",
    "GitError",
    "head_exists",
    "index_tree_sha",
    "repo_root",
    "staged_blob",
    "staged_diff",
]

#: ``-c`` overrides applied to every git invocation.
SAFE_CONFIG: tuple[str, ...] = (
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.quotePath=false",
    "-c",
    "diff.noprefix=false",
    "-c",
    "diff.mnemonicPrefix=false",
    "-c",
    "diff.relative=false",
    "-c",
    "color.ui=false",
)

#: Flags added to every ``git diff`` call.
SAFE_DIFF_FLAGS: tuple[str, ...] = (
    "--no-ext-diff",
    "--no-textconv",
    "--no-color",
    "--no-relative",
    "--src-prefix=a/",
    "--dst-prefix=b/",
)

_TIMEOUT_SECONDS = 30


class GitError(RuntimeError):
    """A git command failed or git is not available."""


def _git_executable() -> str:
    exe = shutil.which("git")
    if exe is None:
        raise GitError("git was not found on PATH")
    return exe


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "PAGER": "cat",
        }
    )
    env.pop("GIT_EXTERNAL_DIFF", None)
    return env


def _run(args: list[str], cwd: Path | str | None) -> bytes:
    argv = [_git_executable(), *SAFE_CONFIG, *args]
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            env=_env(),
            capture_output=True,
            check=False,
            timeout=_TIMEOUT_SECONDS,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitError(f"could not run git {args[0]}: {exc}") from exc
    if proc.returncode != 0:
        message = proc.stderr.decode("utf-8", errors="replace").strip()
        raise GitError(f"git {args[0]} failed: {message or f'exit code {proc.returncode}'}")
    return proc.stdout


def _text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def repo_root(cwd: Path | str | None = None) -> Path:
    """Absolute path of the working tree containing ``cwd``."""
    return Path(_text(_run(["rev-parse", "--show-toplevel"], cwd)).strip())


def head_exists(cwd: Path | str | None = None) -> bool:
    """False in a fresh repository with no commits yet."""
    try:
        _run(["rev-parse", "--verify", "--quiet", "HEAD"], cwd)
    except GitError:
        return False
    return True


def staged_diff(cwd: Path | str | None = None, *, context_lines: int = 3) -> str:
    """Unified diff of the index against HEAD (against the empty tree before the first commit)."""
    if context_lines < 0:
        raise ValueError("context_lines must be >= 0")
    args = ["diff", "--cached", *SAFE_DIFF_FLAGS, f"-U{context_lines}", "--find-renames"]
    return _text(_run(args, cwd))


def staged_blob(path: str, cwd: Path | str | None = None) -> bytes | None:
    """Raw staged content of ``path`` (repo-relative, forward slashes), or None if not staged."""
    if not path or path.startswith(("-", "/")) or "\x00" in path:
        raise ValueError(f"refusing suspicious path: {path!r}")
    try:
        return _run(["cat-file", "blob", f":{path}"], cwd)
    except GitError:
        return None


def index_tree_sha(cwd: Path | str | None = None) -> str:
    """SHA of the tree object for the current index: a stable key for "exactly what is staged".

    ``git write-tree`` stores that tree in the object database (the same object ``git commit``
    would create). It does not touch refs, the index or the working tree.
    """
    return _text(_run(["write-tree"], cwd)).strip()
