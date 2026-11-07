from __future__ import annotations

from knowyourdiff.diff.context import MAX_SNIPPET_LINES, extract_context
from knowyourdiff.diff.models import Hunk, Line


def hunk_at(lines: dict[int, str], language: str = "python", **kw: bool) -> Hunk:
    added = tuple(Line(n, t) for n, t in sorted(lines.items()))
    start = min(lines) if lines else 1
    return Hunk(
        path="x",
        old_path=None,
        language=language,
        source_start=start,
        source_length=0,
        target_start=start,
        target_length=len(added),
        section_header="",
        added=added,
        removed=(),
        anchor_line=start,
        **kw,
    )


PY = b"""\
import os


class Store:
    def save(self, item):
        def inner():
            return item
        return inner()


def top_level(x):
    return x * 2
"""


def test_nested_function_is_innermost() -> None:
    ctx = extract_context(hunk_at({7: "            return item"}), PY)
    assert ctx.enclosing is not None
    assert (ctx.enclosing.kind, ctx.enclosing.name) == ("function", "inner")
    assert [u.name for u in ctx.touched] == ["Store", "save", "inner"]


def test_method_kind_and_module_level() -> None:
    method = extract_context(hunk_at({8: "        return inner()"}), PY)
    assert method.enclosing is not None
    assert method.enclosing.label == "method save"
    module = extract_context(hunk_at({1: "import os"}), PY)
    assert module.supported and module.enclosing is None


def test_symbols_skip_keywords_and_self() -> None:
    ctx = extract_context(hunk_at({5: "    def save(self, item):"}), PY)
    assert ctx.symbols == ("save", "item")


def test_snippet_is_enclosing_unit_when_short() -> None:
    ctx = extract_context(hunk_at({12: "    return x * 2"}), PY)
    assert [ln.number for ln in ctx.snippet] == [11, 12]


def test_long_unit_snippet_is_windowed() -> None:
    body = "\n".join(f"    v{i} = {i}" for i in range(200))
    source = f"def big():\n{body}\n".encode()
    ctx = extract_context(hunk_at({100: "    v98 = 98"}), source)
    assert ctx.enclosing is not None and ctx.enclosing.name == "big"
    assert len(ctx.snippet) <= MAX_SNIPPET_LINES
    assert 100 in [ln.number for ln in ctx.snippet]


JS = b"""\
const handlers = {
  onSave: function () {
    return save();
  },
};
export const load = async (id) => {
  return fetch(id);
};
export default class Widget {
  render() {
    return null;
  }
}
"""


def test_js_naming_from_pair_and_declarator() -> None:
    pair = extract_context(hunk_at({3: "    return save();"}, "javascript"), JS)
    assert pair.enclosing is not None and pair.enclosing.name == "onSave"
    arrow = extract_context(hunk_at({7: "  return fetch(id);"}, "javascript"), JS)
    assert arrow.enclosing is not None and arrow.enclosing.name == "load"


def test_exported_class_method() -> None:
    ctx = extract_context(hunk_at({11: "    return null;"}, "javascript"), JS)
    assert ctx.enclosing is not None and ctx.enclosing.label == "method render"
    assert [u.label for u in ctx.touched] == ["class Widget", "method render"]
    assert ctx.touched[0].start_line == 9  # span includes "export default"


def test_unsupported_inputs() -> None:
    assert not extract_context(hunk_at({1: "x"}, "go"), b"package main\n").supported
    assert not extract_context(hunk_at({1: "x"}), None).supported
    assert not extract_context(hunk_at({1: "x"}, is_deleted_file=True), PY).supported


def test_invalid_utf8_does_not_crash() -> None:
    ctx = extract_context(hunk_at({1: "x = '�'"}), b"x = '\xff\xfe'\n")
    assert ctx.supported
