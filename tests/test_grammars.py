"""Every bundled grammar loads and parses. Guards against ABI mismatches between tree-sitter and
the grammar wheels, which crash the interpreter rather than raising."""

import pytest

from knowyourdiff.diff.context import SUPPORTED_LANGUAGES, _parser

SAMPLES = {
    "python": b"def f(x):\n    return x + 1\n",
    "javascript": b"function f(x) { return x + 1; }\n",
    "typescript": b"function f(x: number): number { return x + 1; }\n",
    "tsx": b"const A = () => <div>hi</div>;\n",
}


@pytest.mark.parametrize("language", sorted(SUPPORTED_LANGUAGES))
def test_grammar_parses(language: str) -> None:
    tree = _parser(language).parse(SAMPLES[language])
    assert not tree.root_node.has_error
