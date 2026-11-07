"""End-to-end analysis of real git repositories built from tests/fixtures/cases.

Each case is committed as ``before/`` and staged as ``after/``. The full JSON output is pinned in
tests/golden/; the semantic tests below state what each case is meant to demonstrate.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from knowyourdiff.analyze import analyze_staged
from tests.conftest import CASES, GOLDEN, Repo

CASE_NAMES = sorted(p.name for p in CASES.iterdir() if p.is_dir())


def _analysis_json(repo: Repo) -> dict[str, Any]:
    data = analyze_staged(repo.path).to_dict()
    data.pop("repo_root")  # a temp directory
    # The tree SHA is content-only, but file modes differ across platforms; check presence only.
    assert data.pop("tree_sha")
    return data


@pytest.mark.parametrize("name", CASE_NAMES)
def test_golden(name: str, staged_case: Callable[[str], Repo], update_golden: bool) -> None:
    actual = _analysis_json(staged_case(name))
    golden_path = GOLDEN / f"{name}.json"
    if update_golden or not golden_path.exists():
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8", newline="\n")
        if not update_golden:
            pytest.fail(f"golden file created: {golden_path.name}; review it and re-run")
    expected = json.loads(golden_path.read_text(encoding="utf-8"))
    assert actual == expected


def _hunks(staged_case: Callable[[str], Repo], name: str) -> list[dict[str, Any]]:
    hunks: list[dict[str, Any]] = _analysis_json(staged_case(name))["hunks"]
    return hunks


def test_retry_loop_is_found_inside_function(staged_case: Callable[[str], Repo]) -> None:
    hunks = _hunks(staged_case, "py_retry_timeout")
    top = hunks[0]
    assert top["enclosing"]["name"] == "fetch_user"
    assert {"error_handling", "resilience", "control_flow"} <= set(top["signals"])
    assert "retry_count" in top["symbols"]


def test_lock_is_a_method_change_with_concurrency(staged_case: Callable[[str], Repo]) -> None:
    hunks = _hunks(staged_case, "py_lock")
    assert any("concurrency" in h["signals"] for h in hunks)
    increment = next(h for h in hunks if h["enclosing"] and h["enclosing"]["name"] == "increment")
    assert increment["enclosing"]["kind"] == "method"


def test_shell_true_is_security(staged_case: Callable[[str], Repo]) -> None:
    top = _hunks(staged_case, "py_subprocess_shell")[0]
    assert top["signals"]["security"] > 0


def test_comment_only_change_scores_near_zero(staged_case: Callable[[str], Repo]) -> None:
    hunks = _hunks(staged_case, "py_comment_only")
    assert all(h["score"] < 1 for h in hunks)
    assert "only comments, imports or blank lines" in hunks[0]["reasons"]


def test_removed_permission_check_is_flagged(staged_case: Callable[[str], Repo]) -> None:
    top = _hunks(staged_case, "py_removed_validation")[0]
    assert top["added"] == 0
    assert "removes security-sensitive code" in top["reasons"]
    assert "removes error handling" in top["reasons"]
    assert top["enclosing"]["name"] == "delete_account"


def test_decorated_method_resolves_through_decorator(staged_case: Callable[[str], Repo]) -> None:
    top = _hunks(staged_case, "py_decorated_method")[0]
    assert top["enclosing"] == {"kind": "method", "name": "convert", "start": 8, "end": 12}


def test_new_file_lists_its_definitions(staged_case: Callable[[str], Repo]) -> None:
    (only,) = _hunks(staged_case, "py_new_file")
    assert only["new_file"]
    assert [u["name"] for u in only["touched"]] == ["paginate", "page_count"]


def test_deleted_file_is_downweighted_without_context(staged_case: Callable[[str], Repo]) -> None:
    (only,) = _hunks(staged_case, "py_deleted_file")
    assert only["deleted_file"]
    assert not only["context_supported"]
    assert "file deleted" in only["reasons"]


def test_arrow_function_takes_variable_name(staged_case: Callable[[str], Repo]) -> None:
    top = _hunks(staged_case, "js_arrow_fetch")[0]
    assert top["enclosing"]["name"] == "loadUser"
    assert top["signals"]["error_handling"] > 0


def test_typescript_method_in_generic_class(staged_case: Callable[[str], Repo]) -> None:
    hunks = _hunks(staged_case, "ts_class_method")
    get = next(h for h in hunks if h["enclosing"] and h["enclosing"]["name"] == "get")
    assert get["enclosing"]["kind"] == "method"
    assert "expiresAt" in get["symbols"]


def test_tsx_component_function(staged_case: Callable[[str], Repo]) -> None:
    hunks = _hunks(staged_case, "tsx_component")
    assert any(h["enclosing"] and h["enclosing"]["name"] == "Badge" for h in hunks)


def test_code_outranks_tests_docs_and_lockfiles(staged_case: Callable[[str], Repo]) -> None:
    order = [h["path"] for h in _hunks(staged_case, "mixed_paths")]
    assert order[0] == "app.py"
    assert order.index("tests/test_app.py") < order.index("README.md")
    assert order[-1] == "package-lock.json"


def test_rename_keeps_old_path(staged_case: Callable[[str], Repo]) -> None:
    (only,) = _hunks(staged_case, "py_rename")
    assert only["path"] == "new_name.py"
    assert only["old_path"] == "old_name.py"
    assert only["enclosing"]["name"] == "farewell"


def test_separate_edits_in_one_function_are_merged(staged_case: Callable[[str], Repo]) -> None:
    (only,) = _hunks(staged_case, "py_same_function_edits")
    assert only["enclosing"]["name"] == "invoice"
    assert (only["added"], only["removed"]) == (3, 1)
    assert only["target_start"] == 2
    assert only["target_length"] == 9


def test_multi_hunk_file_ranks_conditional_first(staged_case: Callable[[str], Repo]) -> None:
    hunks = _hunks(staged_case, "py_multi_hunk")
    assert len(hunks) == 2
    assert hunks[0]["enclosing"]["name"] == "discount"
    assert hunks[1]["enclosing"]["name"] == "total"
