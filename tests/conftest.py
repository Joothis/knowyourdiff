from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
CASES = FIXTURES / "cases"
GOLDEN = Path(__file__).parent / "golden"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Rewrite tests/golden/*.json from the current output.",
    )


@pytest.fixture
def update_golden(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-golden"))


class Repo:
    """A throwaway git repository for tests."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "commit.gpgsign", "false")

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-c", "init.defaultBranch=main", *args],
            cwd=self.path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def write(self, rel: str, content: str | bytes) -> Path:
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        data = content.encode() if isinstance(content, str) else content
        target.write_bytes(data)
        return target

    def stage(self) -> None:
        self.git("add", "-A")

    def commit(self, message: str = "commit") -> None:
        self.stage()
        self.git("commit", "-q", "--allow-empty", "-m", message)

    def load_tree(self, source: Path) -> None:
        """Make the working tree match ``source`` exactly (except .git)."""
        for child in self.path.iterdir():
            if child.name == ".git":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        if source.exists():
            shutil.copytree(source, self.path, dirs_exist_ok=True)


@pytest.fixture
def make_repo(tmp_path: Path) -> Callable[[str], Repo]:
    def factory(name: str = "repo") -> Repo:
        return Repo(tmp_path / name)

    return factory


@pytest.fixture
def staged_case(make_repo: Callable[[str], Repo]) -> Callable[[str], Repo]:
    """Commit ``cases/<name>/before`` then stage ``cases/<name>/after``."""

    def factory(name: str) -> Repo:
        case = CASES / name
        repo = make_repo(name)
        repo.load_tree(case / "before")
        repo.commit("before")
        repo.load_tree(case / "after")
        repo.stage()
        return repo

    return factory
