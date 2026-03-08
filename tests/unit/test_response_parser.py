"""Unit tests for response parser."""

import pytest

from src_v2.core.response_parser import parse_proposal


class TestParseProposal:
    """Tests for parse_proposal()."""

    def test_empty_input_returns_empty_result(self) -> None:
        result = parse_proposal("")
        assert result["explanation"] == ""
        assert result["files"] == []

    def test_whitespace_only_returns_empty_result(self) -> None:
        result = parse_proposal("   \n  ")
        assert result["explanation"] == ""
        assert result["files"] == []

    def test_single_file_block(self) -> None:
        text = """%%FILE: 20. Projects/Foo/bar.md%%
---
title: Bar
---
Content here."""
        result = parse_proposal(text)
        assert len(result["files"]) == 1
        assert result["files"][0]["path"] == "20. Projects/Foo/bar.md"
        assert "title: Bar" in result["files"][0]["content"]
        assert "Content here." in result["files"][0]["content"]

    def test_multiple_file_blocks(self) -> None:
        text = """%%FILE: path/a.md%%
content a
%%FILE: path/b.md%%
content b"""
        result = parse_proposal(text)
        assert len(result["files"]) == 2
        assert result["files"][0]["path"] == "path/a.md"
        assert result["files"][0]["content"] == "content a"
        assert result["files"][1]["path"] == "path/b.md"
        assert result["files"][1]["content"] == "content b"

    def test_explanation_before_first_file(self) -> None:
        text = """Some reasoning here.
%%FILE: x.md%%
body"""
        result = parse_proposal(text)
        assert "Some reasoning" in result["explanation"]
        assert len(result["files"]) == 1
        assert result["files"][0]["path"] == "x.md"

    def test_explanation_marker_removed(self) -> None:
        text = """%%EXPLANATION%%
Reasoning
%%FILE: a.md%%
body"""
        result = parse_proposal(text)
        assert "Reasoning" in result["explanation"]
        assert "%%EXPLANATION%%" not in result["explanation"]

    def test_malformed_file_block_skipped(self) -> None:
        text = """%%FILE: valid.md%%
good
%%FILE:
%%FILE: also_valid.md%%
also good"""
        result = parse_proposal(text)
        assert len(result["files"]) == 2
        assert result["files"][0]["path"] == "valid.md"
        assert result["files"][1]["path"] == "also_valid.md"
