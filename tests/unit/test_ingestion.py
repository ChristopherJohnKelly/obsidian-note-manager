"""Unit tests for IngestionService."""

from pathlib import Path

import pytest

from src_v2.core.domain.models import Frontmatter, Note
from src_v2.infrastructure.testing.adapters import FakeLLM, MockVaultAdapter
from src_v2.use_cases.ingestion_service import IngestionResult, IngestionService


class TestIngestionService:
    """Tests for IngestionService.run()."""

    def test_empty_capture_returns_success_zero_processed(
        self, fake_llm: FakeLLM
    ) -> None:
        repo = MockVaultAdapter()
        service = IngestionService(
            repo,
            fake_llm,
            capture_dir="00. Inbox/0. Capture",
            review_dir="00. Inbox/1. Review Queue",
            vault_root=Path("/vault"),
        )
        result = service.run()
        assert result == IngestionResult(processed_count=0, success=True)

    def test_happy_path_processes_file_and_deletes_capture(
        self, fake_llm: FakeLLM
    ) -> None:
        capture_dir = Path("00. Inbox/0. Capture")
        review_dir = Path("00. Inbox/1. Review Queue")
        capture_path = capture_dir / "scratch.md"
        raw_content = "Raw note content for testing."

        repo = MockVaultAdapter()
        repo.set_raw_content(capture_path, raw_content)

        service = IngestionService(
            repo,
            fake_llm,
            capture_dir=str(capture_dir),
            review_dir=str(review_dir),
            vault_root=Path("/vault"),
        )
        result = service.run()

        assert result.processed_count == 1
        assert result.success is True
        assert repo.read_raw(capture_path) is None
        assert capture_path not in repo.files and capture_path not in repo._raw_content

        review_paths = repo.list_note_paths_in(review_dir)
        assert len(review_paths) == 1
        note = repo.get_note(review_paths[0])
        assert note is not None
        assert "librarian" in note.frontmatter.model_dump()
        assert note.frontmatter.model_dump().get("librarian") == "review"
        assert "Raw note content" in note.body

    def test_llm_failure_does_not_delete_capture(self, fake_llm: FakeLLM) -> None:
        capture_dir = Path("00. Inbox/0. Capture")
        capture_path = capture_dir / "scratch.md"
        repo = MockVaultAdapter()
        repo.set_raw_content(capture_path, "content")

        class FailingLLM(FakeLLM):
            def generate_proposal(self, instructions, body, context, skeleton):
                raise RuntimeError("API error")

        service = IngestionService(
            repo,
            FailingLLM(),
            capture_dir=str(capture_dir),
            review_dir="00. Inbox/1. Review Queue",
            vault_root=Path("/vault"),
        )
        result = service.run()

        assert result.success is False
        assert result.processed_count == 0
        assert repo.read_raw(capture_path) is not None

    def test_extracts_llm_instructions_block(self, fake_llm: FakeLLM) -> None:
        capture_dir = Path("00. Inbox/0. Capture")
        capture_path = capture_dir / "with_instructions.md"
        raw_content = """```LLM-Instructions
Use custom instructions.
```
Body content here."""

        repo = MockVaultAdapter()
        repo.set_raw_content(capture_path, raw_content)

        service = IngestionService(
            repo,
            fake_llm,
            capture_dir=str(capture_dir),
            review_dir="00. Inbox/1. Review Queue",
            vault_root=Path("/vault"),
        )
        result = service.run()

        assert result.processed_count == 1
        assert result.success is True
        review_paths = repo.list_note_paths_in(Path("00. Inbox/1. Review Queue"))
        note = repo.get_note(review_paths[0])
        assert "Use custom instructions" in note.body
        assert "Body content here" in note.body
