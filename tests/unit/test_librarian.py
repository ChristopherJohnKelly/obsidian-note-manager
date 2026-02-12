"""Unit tests for LibrarianService."""

from pathlib import Path

import pytest

from src_v2.core.domain.models import CodeRegistryEntry
from src_v2.infrastructure.testing.adapters import MockVaultAdapter
from src_v2.use_cases.librarian_service import LibrarianService


class TestLibrarianService:
    """Tests for LibrarianService.generate_registry()."""

    def test_generate_registry_contains_table_headers(self, populated_vault: MockVaultAdapter) -> None:
        service = LibrarianService(populated_vault)
        result = service.generate_registry()
        assert "| Code | Name | Type | Folder |" in result
        assert "| :--- | :--- | :--- | :--- |" in result

    def test_generate_registry_includes_project_code(self, populated_vault: MockVaultAdapter) -> None:
        service = LibrarianService(populated_vault)
        result = service.generate_registry()
        assert "| PEPS |" in result
        assert "| Pepsi Project |" in result

    def test_generate_registry_sorts_by_folder(self) -> None:
        repo = MockVaultAdapter(
            initial_code_entries=[
                CodeRegistryEntry(code="Z", name="Zebra", type="area", folder="30. Areas/Zebra"),
                CodeRegistryEntry(code="A", name="Alpha", type="project", folder="20. Projects/Alpha"),
            ]
        )
        service = LibrarianService(repo)
        result = service.generate_registry()
        lines = result.strip().split("\n")
        # Header rows then data; data should be sorted by folder (20 before 30)
        data_lines = [l for l in lines if l.startswith("|") and "Code" not in l and ":---" not in l]
        assert len(data_lines) == 2
        assert "20. Projects/Alpha" in data_lines[0]
        assert "30. Areas/Zebra" in data_lines[1]

    def test_generate_registry_empty_vault(self) -> None:
        repo = MockVaultAdapter()
        service = LibrarianService(repo)
        result = service.generate_registry()
        assert "| Code | Name | Type | Folder |" in result
        assert "| :--- | :--- | :--- | :--- |" in result
        # No data rows beyond headers
        lines = result.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("|") and "Code" not in l and ":---" not in l]
        assert len(data_lines) == 0
