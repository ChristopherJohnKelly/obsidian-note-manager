"""Unit tests for AssistantService."""

import pytest

from src_v2.config.context_config import ContextConfig
from src_v2.infrastructure.testing.adapters import FakeLLM, MockVaultAdapter
from src_v2.use_cases.assistant_service import AssistantService


class TestAssistantService:
    """Tests for AssistantService.get_full_context() and generate_blueprint()."""

    def test_get_full_context_contains_sections(self, populated_vault: MockVaultAdapter, fake_llm: FakeLLM) -> None:
        config = ContextConfig(
            system_instructions_path="nonexistent.md",
            tag_glossary_path="nonexistent.md",
        )
        service = AssistantService(populated_vault, fake_llm, config)
        result = service.get_full_context()
        assert "=== SYSTEM INSTRUCTIONS ===" in result
        assert "=== TAG GLOSSARY ===" in result
        assert "=== CODE REGISTRY ===" in result
        assert "=== VAULT MAP (Use these for Deep Links) ===" in result

    def test_get_full_context_includes_registry_table(
        self, populated_vault: MockVaultAdapter, fake_llm: FakeLLM
    ) -> None:
        config = ContextConfig(
            system_instructions_path="nonexistent.md",
            tag_glossary_path="nonexistent.md",
        )
        service = AssistantService(populated_vault, fake_llm, config)
        result = service.get_full_context()
        assert "| PEPS |" in result
        assert "| Pepsi Project |" in result

    def test_get_full_context_includes_skeleton(
        self, populated_vault: MockVaultAdapter, fake_llm: FakeLLM
    ) -> None:
        config = ContextConfig(
            system_instructions_path="nonexistent.md",
            tag_glossary_path="nonexistent.md",
        )
        service = AssistantService(populated_vault, fake_llm, config)
        result = service.get_full_context()
        assert "[[Pepsi Project]]" in result
        assert "20. Projects/Pepsi/Pepsi Project.md" in result

    def test_generate_blueprint_returns_proposal(
        self, populated_vault: MockVaultAdapter, fake_llm: FakeLLM
    ) -> None:
        config = ContextConfig(
            system_instructions_path="nonexistent.md",
            tag_glossary_path="nonexistent.md",
        )
        service = AssistantService(populated_vault, fake_llm, config)
        result = service.generate_blueprint("Organize this")
        assert result
        assert "%%FILE" in result

    def test_generate_blueprint_uses_provided_context(
        self, populated_vault: MockVaultAdapter, fake_llm: FakeLLM
    ) -> None:
        config = ContextConfig(
            system_instructions_path="nonexistent.md",
            tag_glossary_path="nonexistent.md",
        )
        service = AssistantService(populated_vault, fake_llm, config)
        custom_context = "CUSTOM_CONTEXT_MARKER_123"
        result = service.generate_blueprint("Organize this", context=custom_context)
        assert custom_context in result

    def test_get_full_context_missing_files_return_empty(
        self, populated_vault: MockVaultAdapter, fake_llm: FakeLLM
    ) -> None:
        config = ContextConfig(
            system_instructions_path="nonexistent.md",
            tag_glossary_path="also_nonexistent.md",
        )
        service = AssistantService(populated_vault, fake_llm, config)
        result = service.get_full_context()
        assert "=== SYSTEM INSTRUCTIONS ===" in result
        assert "=== TAG GLOSSARY ===" in result
        # Missing files return empty string from _read_file_content
        assert result  # Should not crash
