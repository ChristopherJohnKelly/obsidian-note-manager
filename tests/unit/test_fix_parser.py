"""Unit tests for parse_fix — every case is a shipped reviewer finding.

parse_fix runs inside @workflow.run: an escaped exception is an infinite
workflow-task retry loop; a wrong guess overwrites a vault note and gets
pushed. The function must be total and resolve ambiguity to None.
"""

import pytest

from apps.vault_worker.core.fix_parser import parse_fix


def _block(content: str) -> str:
    return f"%%FILE%%\npath: notes/x.md\n{content}\n%%END%%"


def test_valid_fence_is_stripped():
    raw = _block("---\ntitle: X\ntags: [a]\n---\nClean body text.")
    assert parse_fix(raw) == "Clean body text."


def test_malformed_yaml_fence_returns_none_never_raises():
    # Round-4 finding: yaml.ParserError escaped @workflow.run.
    raw = _block("---\nkey: [unclosed\n---\nbody text")
    assert parse_fix(raw) is None


def test_unterminated_fence_returns_none_never_leaks():
    # Round-2 finding: raw YAML leaked into the note body.
    raw = _block("---\ntitle: X\nbody just continues with no closing fence")
    assert parse_fix(raw) is None


def test_thematic_break_pair_around_prose_is_kept_verbatim():
    # Round-1 finding: '---' rules deleted real body content.
    content = "---\nJust a divider between sections\n---\nMore text."
    raw = _block(content)
    assert parse_fix(raw) == content


def test_later_thematic_break_is_preserved():
    raw = _block("Intro paragraph.\n\n---\n\nSecond section.")
    assert parse_fix(raw) == "Intro paragraph.\n\n---\n\nSecond section."


def test_empty_block_returns_none_not_empty_string():
    # Round-1 finding: '' bypassed the `is None` skip guard.
    assert parse_fix("%%FILE%%\npath: notes/x.md\n\n%%END%%") is None


def test_markerless_output_returns_none():
    assert parse_fix("I could not produce a fix, sorry!") is None


@pytest.mark.parametrize("garbage", [
    "",
    "%%FILE%%%%END%%",
    "%%FILE%%\npath: x.md\n---\n\x00\x01\n---\n体\n%%END%%",
    "%%FILE%%\npath: x.md\n---\n" + "-" * 5000 + "\n%%END%%",
])
def test_never_raises_on_garbage(garbage):
    result = parse_fix(garbage)
    assert result is None or isinstance(result, str)
