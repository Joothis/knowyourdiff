from knowyourdiff.diff.parse import parse_diff

MODIFY = """\
diff --git a/pkg/mod.py b/pkg/mod.py
index 1111111..2222222 100644
--- a/pkg/mod.py
+++ b/pkg/mod.py
@@ -1,4 +1,4 @@ def handler():
 def handler():
-    return 1
+    return 2

 x = 3
"""

DELETION_ONLY = """\
diff --git a/a.py b/a.py
index 1111111..2222222 100644
--- a/a.py
+++ b/a.py
@@ -1,5 +1,3 @@
 def f(user):
-    if not user:
-        raise ValueError
     return user

"""

BINARY = """\
diff --git a/logo.png b/logo.png
index 1111111..2222222 100644
Binary files a/logo.png and b/logo.png differ
"""


def test_modify_hunk_fields() -> None:
    (hunk,) = parse_diff(MODIFY)
    assert hunk.path == "pkg/mod.py"
    assert hunk.old_path is None
    assert hunk.language == "python"
    assert hunk.id == "pkg/mod.py:1"
    assert hunk.section_header == "def handler():"
    assert [(ln.number, ln.text) for ln in hunk.added] == [(2, "    return 2")]
    assert [(ln.number, ln.text) for ln in hunk.removed] == [(2, "    return 1")]
    assert hunk.changed_rows == (2,)


def test_deletion_only_hunk_anchors_to_following_line() -> None:
    (hunk,) = parse_diff(DELETION_ONLY)
    assert not hunk.added
    assert len(hunk.removed) == 2
    assert hunk.anchor_line == 2  # "return user" now sits where the check was
    assert hunk.changed_rows == (2,)


def test_empty_and_binary_diffs() -> None:
    assert parse_diff("") == []
    assert parse_diff("   \n") == []
    assert parse_diff(BINARY) == []


def test_crlf_lines_are_cleaned() -> None:
    (hunk,) = parse_diff(MODIFY.replace("    return 2\n", "    return 2\r\n"))
    assert hunk.added[0].text == "    return 2"
