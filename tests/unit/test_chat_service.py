"""Unit tests for ChatService (Agent 1 - The Analyst)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src_v2.core.domain.models import Frontmatter, Note
from src_v2.infrastructure.testing.adapters import MockVaultAdapter
from src_v2.use_cases.chat_service import (
    ChatService,
    _resolve_path_within_area,
)


class TestResolvePathWithinArea:
    """Tests for path resolution and traversal prevention."""

    def test_rejects_path_traversal_parent(self, tmp_path: Path) -> None:
        """../secrets.md must be rejected."""
        result = _resolve_path_within_area(
            "20. Projects",
            "../secrets.md",
            tmp_path,
        )
        assert result is None

    def test_rejects_path_traversal_deep(self, tmp_path: Path) -> None:
        """Pepsi/../../../secrets.md must be rejected."""
        result = _resolve_path_within_area(
            "20. Projects",
            "Pepsi/../../../secrets.md",
            tmp_path,
        )
        assert result is None

    def test_rejects_absolute_path(self, tmp_path: Path) -> None:
        """Leading slash must be rejected."""
        result = _resolve_path_within_area(
            "20. Projects",
            "/etc/passwd",
            tmp_path,
        )
        assert result is None

    def test_accepts_valid_relative_path(self, tmp_path: Path) -> None:
        """Valid subpath within area must be accepted."""
        (tmp_path / "20. Projects" / "Pepsi").mkdir(parents=True)
        result = _resolve_path_within_area(
            "20. Projects",
            "Pepsi/Overview.md",
            tmp_path,
        )
        assert result is not None
        assert str(result) == "20. Projects/Pepsi/Overview.md"

    def test_empty_path_returns_area_root(self, tmp_path: Path) -> None:
        """Empty or '.' returns the active area."""
        result = _resolve_path_within_area("20. Projects", "", tmp_path)
        assert result == Path("20. Projects")
        result2 = _resolve_path_within_area("20. Projects", ".", tmp_path)
        assert result2 == Path("20. Projects")


class TestChatServiceTools:
    """Tests for ChatService tool execution and path traversal blocking."""

    @pytest.fixture
    def mock_repo(self) -> MockVaultAdapter:
        """Repo with a note in 20. Projects/Pepsi."""
        repo = MockVaultAdapter()
        note = Note(
            path=Path("20. Projects/Pepsi/Overview.md"),
            frontmatter=Frontmatter(title="Overview"),
            body="Project overview.",
        )
        repo.add_note(Path("20. Projects/Pepsi/Overview.md"), note)
        repo.set_raw_content(Path("20. Projects/Pepsi/Overview.md"), "Content here")
        return repo

    @pytest.fixture
    def service(self, mock_repo: MockVaultAdapter, tmp_path: Path) -> ChatService:
        """ChatService with mocked API key."""
        return ChatService(
            mock_repo,
            vault_root=tmp_path,
            api_key="test-key",
        )

    def test_list_files_in_area_path_traversal_blocked(
        self, service: ChatService, tmp_path: Path
    ) -> None:
        """list_files_in_area must block ../secrets.md."""
        result = service._list_files_in_area("20. Projects", "../secrets.md")
        data = json.loads(result)
        assert "error" in data
        assert "path traversal" in data["error"].lower()

    def test_read_file_content_path_traversal_blocked(
        self, service: ChatService, tmp_path: Path
    ) -> None:
        """read_file_content must block ../secrets.md."""
        result = service._read_file_content("20. Projects", "../secrets.md")
        data = json.loads(result)
        assert "error" in data
        assert "path traversal" in data["error"].lower()

    def test_list_files_in_area_valid_path(
        self, service: ChatService, tmp_path: Path
    ) -> None:
        """list_files_in_area returns files for valid path."""
        (tmp_path / "20. Projects" / "Pepsi").mkdir(parents=True)
        result = service._list_files_in_area("20. Projects", "Pepsi")
        paths = json.loads(result)
        assert isinstance(paths, list)
        assert "20. Projects/Pepsi/Overview.md" in paths

    def test_read_file_content_valid_path(
        self, service: ChatService, tmp_path: Path
    ) -> None:
        """read_file_content returns content for valid path."""
        result = service._read_file_content("20. Projects", "Pepsi/Overview.md")
        assert result == "Content here"

    def test_chat_returns_text_without_tool_calls(
        self, service: ChatService, tmp_path: Path
    ) -> None:
        """chat() returns LLM text when model responds without tool use."""
        mock_response = MagicMock()
        mock_response.candidates = [
            MagicMock(
                content=MagicMock(
                    parts=[MagicMock(text="Here are the files.", function_call=None)]
                )
            )
        ]
        mock_chat = MagicMock()
        mock_chat.send_message.return_value = mock_response

        mock_model = MagicMock()
        mock_model.return_value = mock_model  # GenerativeModel(...) returns model
        mock_model.start_chat.return_value = mock_chat

        with patch("src_v2.use_cases.chat_service.genai.GenerativeModel", mock_model):
            result = service.chat("What files are here?", "20. Projects")

        assert result == "Here are the files."
        mock_chat.send_message.assert_called_once()
