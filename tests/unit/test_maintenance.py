"""Unit tests for MaintenanceService."""

from pathlib import Path

import pytest

from src_v2.core.domain.models import ValidationResult
from src_v2.infrastructure.testing.adapters import FakeLLM, MockVaultAdapter
from src_v2.use_cases.maintenance_service import MaintenanceService


class TestMaintenanceService:
    """Tests for MaintenanceService.audit_vault() and generate_fix()."""

    def test_audit_vault_returns_only_dirty_files(self, populated_vault: MockVaultAdapter, fake_llm: FakeLLM) -> None:
        service = MaintenanceService(populated_vault, fake_llm)
        results = service.audit_vault()
        assert len(results) == 1
        assert results[0].path == Path("20. Projects/Pepsi/dirty.md")
        assert results[0].score == 10

    def test_audit_vault_sorts_by_score_descending(self, fake_llm: FakeLLM) -> None:
        repo = MockVaultAdapter(
            initial_scan_results=[
                ValidationResult(path=Path("low.md"), score=5, reasons=["Minor"]),
                ValidationResult(path=Path("high.md"), score=50, reasons=["Major"]),
            ]
        )
        service = MaintenanceService(repo, fake_llm)
        results = service.audit_vault()
        assert len(results) == 2
        assert results[0].score == 50
        assert results[1].score == 5

    def test_audit_vault_excludes_clean_files(self, fake_llm: FakeLLM) -> None:
        repo = MockVaultAdapter(
            initial_scan_results=[
                ValidationResult(path=Path("clean.md"), score=0, reasons=[]),
            ]
        )
        service = MaintenanceService(repo, fake_llm)
        results = service.audit_vault()
        assert len(results) == 0

    def test_generate_fix_returns_llm_proposal(
        self, populated_vault: MockVaultAdapter, fake_llm: FakeLLM
    ) -> None:
        service = MaintenanceService(populated_vault, fake_llm)
        result = service.generate_fix(
            Path("20. Projects/Pepsi/dirty.md"),
            reasons=["Missing aliases/tags"],
            context="Test context",
        )
        assert result
        assert "%%FILE" in result

    def test_generate_fix_includes_note_content(
        self, populated_vault: MockVaultAdapter, fake_llm: FakeLLM
    ) -> None:
        service = MaintenanceService(populated_vault, fake_llm)
        result = service.generate_fix(
            Path("20. Projects/Pepsi/dirty.md"),
            reasons=["Missing aliases/tags"],
            context="Test context",
        )
        assert "Content without proper metadata" in result

    def test_generate_fix_raises_when_note_not_found(self, fake_llm: FakeLLM) -> None:
        repo = MockVaultAdapter(initial_scan_results=[])  # No notes in files
        service = MaintenanceService(repo, fake_llm)
        with pytest.raises(FileNotFoundError, match="Note .* not found"):
            service.generate_fix(
                Path("nonexistent.md"),
                reasons=["Missing tags"],
                context="",
            )
