"""Unit tests for Bubble 2 infrastructure adapters."""

from pathlib import Path

import pytest

from src_v2.core.domain.models import Frontmatter, Note, ValidationResult
from src_v2.infrastructure.file_system.adapters import ObsidianFileSystemAdapter
from src_v2.infrastructure.llm.adapters import GeminiAdapter
from src_v2.infrastructure.testing.adapters import MockVaultAdapter


class TestObsidianFileSystemAdapter:
    """Tests for ObsidianFileSystemAdapter."""

    def test_get_note_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        adapter = ObsidianFileSystemAdapter(tmp_path)
        result = adapter.get_note(Path("nonexistent.md"))
        assert result is None

    def test_save_and_get_note_roundtrip(self, tmp_path: Path) -> None:
        adapter = ObsidianFileSystemAdapter(tmp_path)
        note = Note(
            path=Path("subdir/note.md"),
            frontmatter=Frontmatter(title="Test", tags=["tag1"]),
            body="Hello world",
        )
        adapter.save_note(Path("subdir/note.md"), note)
        loaded = adapter.get_note(Path("subdir/note.md"))
        assert loaded is not None
        assert loaded.frontmatter.title == "Test"
        assert loaded.frontmatter.tags == ["tag1"]
        assert loaded.body == "Hello world"

    def test_scan_vault_empty(self, tmp_path: Path) -> None:
        adapter = ObsidianFileSystemAdapter(tmp_path)
        projects = tmp_path / "20. Projects"
        areas = tmp_path / "30. Areas"
        projects.mkdir(parents=True)
        areas.mkdir(parents=True)
        results = adapter.scan_vault()
        assert results == []

    def test_scan_vault_identifies_missing_aliases_tags(self, tmp_path: Path) -> None:
        projects = tmp_path / "20. Projects" / "Foo"
        projects.mkdir(parents=True)
        (projects / "bare.md").write_text("---\n---\nNo aliases or tags\n", encoding="utf-8")
        adapter = ObsidianFileSystemAdapter(tmp_path)
        results = adapter.scan_vault()
        assert len(results) == 1
        assert results[0].score == 10
        assert "Missing aliases/tags" in results[0].reasons

    def test_scan_vault_identifies_generic_filename(self, tmp_path: Path) -> None:
        projects = tmp_path / "20. Projects" / "Foo"
        projects.mkdir(parents=True)
        (projects / "meeting.md").write_text(
            "---\ntags: [meeting]\naliases: [foo]\n---\nContent\n",
            encoding="utf-8",
        )
        adapter = ObsidianFileSystemAdapter(tmp_path)
        results = adapter.scan_vault()
        assert len(results) == 1
        assert results[0].score == 20
        assert "Generic Filename" in results[0].reasons

    def test_validate_note_distinct_from_file_walking(self, tmp_path: Path) -> None:
        """_validate_note is a separate helper; verify it evaluates rules correctly."""
        projects = tmp_path / "20. Projects" / "Foo"
        projects.mkdir(parents=True)
        (projects / "code.md").write_text("---\ncode: FOOBAR\n---\n", encoding="utf-8")
        adapter = ObsidianFileSystemAdapter(tmp_path)
        adapter._registry = adapter._build_registry()
        note_with_code = Note(
            path=Path("20. Projects/Foo/FOOBAR-ok.md"),
            frontmatter=Frontmatter(code="FOOBAR", tags=["t"]),
            body="",
        )
        result_ok = adapter._validate_note(note_with_code)
        assert result_ok is None
        note_without_code = Note(
            path=Path("20. Projects/Foo/bad.md"),
            frontmatter=Frontmatter(tags=["t"]),
            body="",
        )
        result_bad = adapter._validate_note(note_without_code)
        assert result_bad is not None
        assert any("Missing Project Code" in r for r in result_bad.reasons)


class TestMockVaultAdapter:
    """Tests for MockVaultAdapter."""

    def test_get_note_returns_none_when_empty(self) -> None:
        adapter = MockVaultAdapter()
        assert adapter.get_note(Path("x.md")) is None

    def test_save_and_get_note(self) -> None:
        adapter = MockVaultAdapter()
        note = Note(
            path=Path("a.md"),
            frontmatter=Frontmatter(title="A"),
            body="Body",
        )
        adapter.save_note(Path("a.md"), note)
        loaded = adapter.get_note(Path("a.md"))
        assert loaded is not None
        assert loaded.frontmatter.title == "A"

    def test_scan_vault_returns_configured_results(self) -> None:
        results = [
            ValidationResult(path=Path("x.md"), score=10, reasons=["Missing tags"]),
        ]
        adapter = MockVaultAdapter(initial_scan_results=results)
        assert adapter.scan_vault() == results

    def test_set_scan_results_helper(self) -> None:
        adapter = MockVaultAdapter()
        adapter.set_scan_results([ValidationResult(path=Path("y.md"), score=5, reasons=[])])
        assert len(adapter.scan_vault()) == 1
        assert adapter.scan_vault()[0].path == Path("y.md")

    def test_validate_note_returns_result_when_in_scan_results(self) -> None:
        results = [
            ValidationResult(path=Path("x.md"), score=10, reasons=["Missing tags"]),
        ]
        adapter = MockVaultAdapter(initial_scan_results=results)
        validation = adapter.validate_note(Path("x.md"))
        assert validation is not None
        assert validation.score == 10
        assert "Missing tags" in validation.reasons

    def test_validate_note_returns_none_when_not_in_scan_results(self) -> None:
        adapter = MockVaultAdapter(initial_scan_results=[])
        assert adapter.validate_note(Path("clean.md")) is None


class TestGeminiAdapter:
    """Tests for GeminiAdapter."""

    def test_raises_when_api_key_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiAdapter()
