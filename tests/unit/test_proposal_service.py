"""Unit tests for ProposalService (Agent 2 - The Proposer)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src_v2.core.domain.models import Frontmatter, Note
from src_v2.infrastructure.testing.adapters import MockVaultAdapter
from src_v2.use_cases.proposal_service import ProposalService, _is_safe_path


class TestIsSafePath:
    """Tests for path safety validation."""

    def test_rejects_path_traversal(self) -> None:
        assert _is_safe_path("../../../etc/passwd") is False
        assert _is_safe_path("foo/../bar") is False

    def test_rejects_leading_slash(self) -> None:
        assert _is_safe_path("/etc/passwd") is False

    def test_accepts_valid_paths(self) -> None:
        assert _is_safe_path("20. Projects/Foo/bar.md") is True
        assert _is_safe_path("30. Areas/Alpha.md") is True

    def test_rejects_empty(self) -> None:
        assert _is_safe_path("") is False
        assert _is_safe_path("   ") is False


class TestProposalService:
    """Tests for ProposalService.generate_draft()."""

    @pytest.fixture
    def mock_repo(self) -> MockVaultAdapter:
        """Repo with notes in 20. Projects for area context."""
        repo = MockVaultAdapter()
        # Add note at area root for list_note_paths_in(Path("20. Projects"))
        root_note = Note(
            path=Path("20. Projects/Overview.md"),
            frontmatter=Frontmatter(title="Overview"),
            body="Project overview content.",
        )
        repo.add_note(Path("20. Projects/Overview.md"), root_note)
        repo.set_raw_content(
            Path("20. Projects/Overview.md"),
            "# Overview\n\nProject overview content.",
        )
        # Add nested note for list_note_paths_in(Path("20. Projects/Pepsi"))
        pepsi_note = Note(
            path=Path("20. Projects/Pepsi/Overview.md"),
            frontmatter=Frontmatter(title="Pepsi Overview"),
            body="Pepsi project.",
        )
        repo.add_note(Path("20. Projects/Pepsi/Overview.md"), pepsi_note)
        repo.set_raw_content(
            Path("20. Projects/Pepsi/Overview.md"),
            "# Pepsi Overview\n\nPepsi project.",
        )
        return repo

    @pytest.fixture
    def service(self, mock_repo: MockVaultAdapter, tmp_path: Path) -> ProposalService:
        """ProposalService with mocked API key."""
        return ProposalService(
            mock_repo,
            vault_root=tmp_path,
            review_dir="00. Inbox/1. Review Queue",
            api_key="test-key",
        )

    def test_valid_proposal_written_to_review_queue(
        self, service: ProposalService, mock_repo: MockVaultAdapter, tmp_path: Path
    ) -> None:
        """generate_draft writes proposal with librarian: file to Review Queue."""
        llm_output = """%%FILE: 20. Projects/Pepsi/NewDoc.md%%
---
title: New Doc
tags: [project]
---
New content here."""

        mock_response = MagicMock()
        mock_response.text = llm_output
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch(
            "src_v2.use_cases.proposal_service.genai.GenerativeModel",
            return_value=mock_model,
        ):
            result = service.generate_draft(
                [
                    {"role": "user", "content": "Add a new doc for Pepsi."},
                    {"role": "assistant", "content": "I'll draft that."},
                ],
                "20. Projects",
            )

        assert "Draft saved to" in result
        assert "00. Inbox/1. Review Queue" in result

        # Verify save_note was called for the proposal
        review_paths = [
            p for p in mock_repo.files.keys()
            if str(p).startswith("00. Inbox/1. Review Queue/")
        ]
        assert len(review_paths) == 1
        assert review_paths[0].suffix == ".md"

        note = mock_repo.files[review_paths[0]]
        assert note.frontmatter.model_dump().get("librarian") == "file"
        assert "%%FILE: 20. Projects/Pepsi/NewDoc.md%%" in note.body
        assert "New content here" in note.body

    def test_path_traversal_rejected(
        self, service: ProposalService, mock_repo: MockVaultAdapter
    ) -> None:
        """Paths with .. are rejected; no malicious file is written."""
        llm_output = """%%FILE: ../../../etc/passwd%%
malicious content"""

        mock_response = MagicMock()
        mock_response.text = llm_output
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch(
            "src_v2.use_cases.proposal_service.genai.GenerativeModel",
            return_value=mock_model,
        ):
            result = service.generate_draft(
                [{"role": "user", "content": "Do something."}],
                "20. Projects",
            )

        assert "path traversal" in result.lower() or "No valid" in result
        # No proposal should be written to Review Queue
        review_paths = [
            p for p in mock_repo.files.keys()
            if str(p).startswith("00. Inbox/1. Review Queue/")
        ]
        assert len(review_paths) == 0

    def test_librarian_file_injected(
        self, service: ProposalService, mock_repo: MockVaultAdapter
    ) -> None:
        """Saved note always has librarian: file in frontmatter."""
        llm_output = """%%FILE: 20. Projects/Foo/bar.md%%
---
title: Bar
---
Body"""

        mock_response = MagicMock()
        mock_response.text = llm_output
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch(
            "src_v2.use_cases.proposal_service.genai.GenerativeModel",
            return_value=mock_model,
        ):
            service.generate_draft(
                [{"role": "user", "content": "Create bar.md"}],
                "20. Projects",
            )

        review_paths = [
            p for p in mock_repo.files.keys()
            if str(p).startswith("00. Inbox/1. Review Queue/")
        ]
        assert len(review_paths) == 1
        saved_note = mock_repo.files[review_paths[0]]
        assert saved_note.frontmatter.model_dump().get("librarian") == "file"

    def test_empty_chat_history_returns_error(
        self, service: ProposalService
    ) -> None:
        """Empty chat history returns helpful error."""
        result = service.generate_draft([], "20. Projects")
        assert "No chat history" in result or "conversation" in result.lower()
