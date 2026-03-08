"""Unit tests for Chainlit Copilot helpers."""

from pathlib import Path

import pytest

from src_v2.entrypoints.chainlit_helpers import scan_top_level_dirs


class TestScanTopLevelDirs:
    """Tests for scan_top_level_dirs()."""

    def test_returns_top_level_dirs(self, tmp_path: Path) -> None:
        """Create vault dirs and assert all appear in result."""
        (tmp_path / "20. Projects").mkdir()
        (tmp_path / "30. Areas").mkdir()
        (tmp_path / "40. Resources").mkdir()
        result = scan_top_level_dirs(tmp_path)
        assert result == ["20. Projects", "30. Areas", "40. Resources"]

    def test_excludes_hidden(self, tmp_path: Path) -> None:
        """Add .git, .obsidian; assert they are not in result."""
        (tmp_path / "20. Projects").mkdir()
        (tmp_path / ".git").mkdir()
        (tmp_path / ".obsidian").mkdir()
        result = scan_top_level_dirs(tmp_path)
        assert ".git" not in result
        assert ".obsidian" not in result
        assert "20. Projects" in result

    def test_excludes_excluded_dirs(self, tmp_path: Path) -> None:
        """Add 00. Inbox, 99. System; assert they are not in result."""
        (tmp_path / "20. Projects").mkdir()
        (tmp_path / "00. Inbox").mkdir()
        (tmp_path / "99. System").mkdir()
        result = scan_top_level_dirs(tmp_path)
        assert "00. Inbox" not in result
        assert "99. System" not in result
        assert "20. Projects" in result

    def test_returns_sorted(self, tmp_path: Path) -> None:
        """Create Z, A, M; assert result is sorted."""
        (tmp_path / "Z").mkdir()
        (tmp_path / "A").mkdir()
        (tmp_path / "M").mkdir()
        result = scan_top_level_dirs(tmp_path)
        assert result == ["A", "M", "Z"]

    def test_returns_empty_for_missing_path(self) -> None:
        """Pass non-existent path; assert []."""
        result = scan_top_level_dirs(Path("/nonexistent/path/12345"))
        assert result == []

    def test_ignores_files(self, tmp_path: Path) -> None:
        """Add readme.md; assert it is not in result."""
        (tmp_path / "20. Projects").mkdir()
        (tmp_path / "readme.md").write_text("# Readme")
        result = scan_top_level_dirs(tmp_path)
        assert "readme.md" not in result
        assert "20. Projects" in result
