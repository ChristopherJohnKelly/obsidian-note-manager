"""E2E tests for ObsidianFileSystemAdapter on real disk."""

from pathlib import Path

import pytest

from src_v2.infrastructure.file_system.adapters import ObsidianFileSystemAdapter


class TestFilesystemE2E:
    """Integration tests using tmp_path (real disk I/O)."""

    def test_read_note_from_disk_happy_path(self, tmp_path: Path) -> None:
        """Create a real .md file with valid YAML frontmatter and verify get_note reads it."""
        projects_dir = tmp_path / "20. Projects" / "Test"
        projects_dir.mkdir(parents=True)

        # Valid YAML frontmatter with triple-dash separators for python-frontmatter
        sample_content = """---
title: Sample Note
tags:
  - project
  - test
aliases:
  - Sample
---
# Sample Note Body

This is the body content for the E2E test.
"""
        sample_file = projects_dir / "sample.md"
        sample_file.write_text(sample_content, encoding="utf-8")

        adapter = ObsidianFileSystemAdapter(tmp_path)
        note = adapter.get_note(Path("20. Projects/Test/sample.md"))

        assert note is not None
        assert note.frontmatter.title == "Sample Note"
        assert "project" in note.frontmatter.tags
        assert "test" in note.frontmatter.tags
        assert "Sample" in note.frontmatter.aliases
        assert "Sample Note Body" in note.body
        assert "body content for the E2E test" in note.body

    def test_scan_vault_on_disk(self, tmp_path: Path) -> None:
        """Add a dirty file (no tags/aliases) and verify scan_vault identifies it."""
        projects_dir = tmp_path / "20. Projects" / "Foo"
        projects_dir.mkdir(parents=True)

        # Dirty file: valid YAML but missing aliases/tags
        dirty_content = """---
---
No aliases or tags
"""
        dirty_file = projects_dir / "bare.md"
        dirty_file.write_text(dirty_content, encoding="utf-8")

        adapter = ObsidianFileSystemAdapter(tmp_path)
        results = adapter.scan_vault()

        assert len(results) == 1
        assert results[0].score == 10
        assert "Missing aliases/tags" in results[0].reasons
