from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from typer.testing import CliRunner

from knowyourdiff import __version__
from knowyourdiff.cli import app
from tests.conftest import Repo

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_nothing_staged(make_repo: Callable[[str], Repo]) -> None:
    repo = make_repo("r")
    result = runner.invoke(app, ["check", "--dry-run", "--repo", str(repo.path)])
    assert result.exit_code == 0
    assert "Nothing staged" in result.stdout


def test_json_output(staged_case: Callable[[str], Repo]) -> None:
    repo = staged_case("py_multi_hunk")
    result = runner.invoke(app, ["check", "--json", "-n", "1", "--repo", str(repo.path)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["schema_version"] == 1
    assert data["total_hunks"] == 2
    assert len(data["hunks"]) == 1
    assert data["hunks"][0]["enclosing"]["name"] == "discount"
    assert len(data["tree_sha"]) in (40, 64)


def test_table_and_code(staged_case: Callable[[str], Repo]) -> None:
    repo = staged_case("py_retry_timeout")
    result = runner.invoke(
        app, ["check", "--dry-run", "--show-code", "--repo", str(repo.path)], env={"COLUMNS": "160"}
    )
    assert result.exit_code == 0, result.output
    assert "function fetch_user" in result.stdout
    assert "retry_count" in result.stdout
    assert "next release" not in result.stdout


def test_without_dry_run_explains_phase(staged_case: Callable[[str], Repo]) -> None:
    repo = staged_case("py_lock")
    result = runner.invoke(app, ["check", "--repo", str(repo.path)], env={"COLUMNS": "160"})
    assert result.exit_code == 0
    assert "next release" in result.stdout


def test_outside_repo_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(app, ["check", "--repo", str(tmp_path)])
    assert result.exit_code == 2
