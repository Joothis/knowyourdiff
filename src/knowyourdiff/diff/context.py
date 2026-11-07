"""Code context for a hunk via tree-sitter: enclosing function/class, touched definitions, symbols.

Grammars come from individual wheels (``tree-sitter-python`` etc.) so nothing is downloaded at
commit time.
"""

from __future__ import annotations

import keyword
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import cache

from tree_sitter import Language, Node, Parser

from knowyourdiff.diff.models import Hunk, Line

__all__ = ["SUPPORTED_LANGUAGES", "CodeUnit", "HunkContext", "extract_context"]

MAX_SNIPPET_LINES = 60
SNIPPET_PADDING = 5
MAX_SYMBOLS = 15


@dataclass(frozen=True, slots=True)
class CodeUnit:
    kind: str
    """"function", "method" or "class"."""
    name: str | None
    start_line: int
    """1-based, inclusive."""
    end_line: int
    """1-based, inclusive."""

    @property
    def label(self) -> str:
        return f"{self.kind} {self.name or '<anonymous>'}"


@dataclass(frozen=True, slots=True)
class HunkContext:
    supported: bool
    """False when the language has no grammar or the staged blob is unavailable."""
    enclosing: CodeUnit | None = None
    """Innermost function or class that contains every changed line."""
    touched: tuple[CodeUnit, ...] = ()
    """Definitions overlapping a changed line, outermost first."""
    symbols: tuple[str, ...] = ()
    """Identifiers on changed lines, in order of first appearance."""
    snippet: tuple[Line, ...] = ()
    """New-file source lines around the change (the enclosing unit when it is short)."""


@dataclass(frozen=True)
class _LanguageSpec:
    load: Callable[[], object]
    units: dict[str, str]
    identifiers: frozenset[str]
    reserved: frozenset[str]
    wrappers: dict[str, str]
    """Node type → field holding the wrapped definition (decorators, ``export``)."""


def _load_python() -> object:
    import tree_sitter_python

    return tree_sitter_python.language()


def _load_javascript() -> object:
    import tree_sitter_javascript

    return tree_sitter_javascript.language()


def _load_typescript() -> object:
    import tree_sitter_typescript

    return tree_sitter_typescript.language_typescript()


def _load_tsx() -> object:
    import tree_sitter_typescript

    return tree_sitter_typescript.language_tsx()


_JS_UNITS = {
    "function_declaration": "function",
    "generator_function_declaration": "function",
    "function_expression": "function",
    "function": "function",
    "arrow_function": "function",
    "method_definition": "method",
    "class_declaration": "class",
    "class": "class",
}
_TS_UNITS = {**_JS_UNITS, "abstract_class_declaration": "class"}
_JS_IDENTIFIERS = frozenset(
    {
        "identifier",
        "property_identifier",
        "shorthand_property_identifier",
        "private_property_identifier",
    }
)
_JS_RESERVED = frozenset(
    """break case catch class const continue debugger default delete do else export extends
    false finally for function if import in instanceof let new null return super switch this
    throw true try typeof undefined var void while with yield async await of static get set
    interface type enum implements private protected public readonly declare as""".split()
)
_JS_WRAPPERS = {"export_statement": "declaration"}

_SPECS: dict[str, _LanguageSpec] = {
    "python": _LanguageSpec(
        load=_load_python,
        units={"function_definition": "function", "class_definition": "class"},
        identifiers=frozenset({"identifier"}),
        reserved=frozenset(keyword.kwlist) | frozenset(keyword.softkwlist) | {"self", "cls"},
        wrappers={"decorated_definition": "definition"},
    ),
    "javascript": _LanguageSpec(
        _load_javascript, _JS_UNITS, _JS_IDENTIFIERS, _JS_RESERVED, _JS_WRAPPERS
    ),
    "typescript": _LanguageSpec(
        _load_typescript,
        _TS_UNITS,
        _JS_IDENTIFIERS | {"type_identifier"},
        _JS_RESERVED,
        _JS_WRAPPERS,
    ),
    "tsx": _LanguageSpec(
        _load_tsx, _TS_UNITS, _JS_IDENTIFIERS | {"type_identifier"}, _JS_RESERVED, _JS_WRAPPERS
    ),
}

SUPPORTED_LANGUAGES: frozenset[str] = frozenset(_SPECS)

_WORD = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


@cache
def _parser(language: str) -> Parser:
    return Parser(Language(_SPECS[language].load()))


def _text(node: Node | None, source: bytes) -> str | None:
    # Slice the source ourselves rather than relying on ``Node.text``, which is only populated when
    # the tree keeps a reference to its source.
    if node is None:
        return None
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _unit_name(node: Node, source: bytes) -> str | None:
    name = _text(node.child_by_field_name("name"), source)
    if name:
        return name
    parent = node.parent
    if parent is None:
        return None
    # const f = () => {};  { key: function () {} };  x.y = () => {};  class { f = () => {} }
    field = _NAMING_PARENTS.get(parent.type)
    return _text(parent.child_by_field_name(field), source) if field else None


_NAMING_PARENTS = {
    "variable_declarator": "name",
    "pair": "key",
    "assignment_expression": "left",
    "public_field_definition": "name",
    "field_definition": "property",
}


def _unwrap(node: Node, spec: _LanguageSpec) -> Node | None:
    """For a wrapper (decorator, ``export``) around a definition, the definition itself."""
    field = spec.wrappers.get(node.type)
    if field is None:
        return None
    inner = node.child_by_field_name(field)
    return inner if inner is not None and _kind(inner, spec) else None


def _kind(node: Node, spec: _LanguageSpec) -> str | None:
    # Named nodes only: in the JS grammars the keyword tokens ``function`` and ``class`` share
    # their type names with the expression nodes.
    return spec.units.get(node.type) if node.is_named else None


def _is_wrapped(node: Node, spec: _LanguageSpec) -> bool:
    return node.parent is not None and _unwrap(node.parent, spec) is not None


def _to_unit(node: Node, spec: _LanguageSpec, source: bytes) -> CodeUnit | None:
    """A definition, reported with the span of its wrapper (decorators, ``export``) if any."""
    definition = _unwrap(node, spec) or node
    kind = _kind(definition, spec)
    if kind is None:
        return None
    wrapper = node.parent if node is definition and _is_wrapped(node, spec) else None
    outer = wrapper or node
    if kind == "function" and _inside_class(definition, spec):
        kind = "method"
    return CodeUnit(
        kind=kind,
        name=_unit_name(definition, source),
        start_line=outer.start_point.row + 1,
        end_line=outer.end_point.row + 1,
    )


def _inside_class(node: Node, spec: _LanguageSpec) -> bool:
    """True if the nearest enclosing unit is a class (so this function is a method)."""
    parent = node.parent
    while parent is not None:
        kind = _kind(parent, spec)
        if kind == "class":
            return True
        if kind in {"function", "method"}:
            return False
        parent = parent.parent
    return False


def _nodes_in_rows(root: Node, first: int, last: int) -> Iterator[Node]:
    """Pre-order walk over nodes whose span intersects rows [first, last] (0-based)."""
    stack = [root]
    while stack:
        node = stack.pop()
        if node.end_point.row < first or node.start_point.row > last:
            continue
        yield node
        stack.extend(reversed(node.children))


def _snippet(
    lines: list[str], rows: tuple[int, ...], enclosing: CodeUnit | None
) -> tuple[Line, ...]:
    first, last = min(rows), max(rows)
    if enclosing is not None and enclosing.end_line - enclosing.start_line < MAX_SNIPPET_LINES:
        start, end = enclosing.start_line, enclosing.end_line
    else:
        start = max(1, first - SNIPPET_PADDING)
        end = min(len(lines), last + SNIPPET_PADDING, start + MAX_SNIPPET_LINES - 1)
        if enclosing is not None:
            start = max(start, enclosing.start_line)
            end = min(end, enclosing.end_line)
    return tuple(Line(n, lines[n - 1]) for n in range(start, end + 1) if 0 < n <= len(lines))


def _removed_symbols(removed: tuple[Line, ...], reserved: frozenset[str]) -> list[str]:
    found: list[str] = []
    for line in removed:
        stripped = line.text.strip()
        if stripped.startswith(("#", "//")):
            continue
        found.extend(w for w in _WORD.findall(stripped) if w not in reserved and len(w) > 1)
    return found


def _dedupe(items: list[str], limit: int) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for item in items:
        seen.setdefault(item, None)
        if len(seen) >= limit:
            break
    return tuple(seen)


def extract_context(hunk: Hunk, source: bytes | None) -> HunkContext:
    """Locate ``hunk`` in the staged ``source`` of its file."""
    spec = _SPECS.get(hunk.language or "")
    rows = hunk.changed_rows
    if spec is None or source is None or hunk.is_deleted_file or not rows:
        return HunkContext(supported=False)

    tree = _parser(hunk.language or "").parse(source)
    root = tree.root_node
    lines = source.decode("utf-8", errors="replace").splitlines()
    first, last = min(rows) - 1, max(rows) - 1
    last_len = len(lines[last].encode("utf-8")) if last < len(lines) else 0

    enclosing: CodeUnit | None = None
    node: Node | None = root.descendant_for_point_range((first, 0), (last, last_len))
    while node is not None:
        unit = _to_unit(node, spec, source)
        if unit is not None:
            enclosing = unit
            break
        node = node.parent

    row_set = {r - 1 for r in rows}
    touched: list[CodeUnit] = []
    identifiers: list[str] = []
    for candidate in _nodes_in_rows(root, first, last):
        is_definition = _kind(candidate, spec) is not None and not _is_wrapped(candidate, spec)
        if is_definition or _unwrap(candidate, spec) is not None:
            unit = _to_unit(candidate, spec, source)
            if unit is not None and any(
                r in row_set for r in range(unit.start_line - 1, unit.end_line)
            ):
                touched.append(unit)
        elif candidate.type in spec.identifiers and candidate.start_point.row in row_set:
            word = _text(candidate, source)
            if word and word not in spec.reserved:
                identifiers.append(word)

    identifiers.extend(_removed_symbols(hunk.removed, spec.reserved))
    return HunkContext(
        supported=True,
        enclosing=enclosing,
        touched=tuple(touched),
        symbols=_dedupe(identifiers, MAX_SYMBOLS),
        snippet=_snippet(lines, rows, enclosing),
    )
