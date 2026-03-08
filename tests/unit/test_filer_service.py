"""Unit tests for FilerService."""

from pathlib import Path

import pytest

from src_v2.core.domain.models import Frontmatter, Note
from src_v2.infrastructure.testing.adapters import MockVaultAdapter
from src_v2.use_cases.filer_service import FilerService


class TestFilerService:
    """Tests for FilerService.file_approved_notes()."""

    def test_empty_review_queue_returns_zero(self) -> None:
        repo = MockVaultAdapter()
        service = FilerService(
            repo,
            review_dir="00. Inbox/1. Review Queue",
            vault_root=Path("/vault"),
        )
        assert service.file_approved_notes() == 0

    def test_skip_non_file_proposals(self) -> None:
        review_dir = Path("00. Inbox/1. Review Queue")
        prop_path = review_dir / "proposal.md"
        prop_note = Note(
            path=prop_path,
            frontmatter=Frontmatter.model_validate({"librarian": "review"}),
            body="%%FILE: 20. Projects/Foo/bar.md%%\n---\ncontent",
        )
        repo = MockVaultAdapter()
        repo.add_note(prop_path, prop_note)

        service = FilerService(
            repo,
            review_dir=str(review_dir),
            vault_root=Path("/vault"),
        )
        assert service.file_approved_notes() == 0
        assert prop_path in repo.files

    def test_happy_path_files_proposal_and_deletes(self) -> None:
        review_dir = Path("00. Inbox/1. Review Queue")
        target_path = Path("20. Projects/Foo/bar.md")
        prop_path = review_dir / "proposal.md"
        prop_body = """%%FILE: 20. Projects/Foo/bar.md%%
---
title: Bar Note
tags: [project]
---
Body content here."""
        prop_note = Note(
            path=prop_path,
            frontmatter=Frontmatter.model_validate({"librarian": "file"}),
            body=prop_body,
        )
        repo = MockVaultAdapter()
        repo.add_note(prop_path, prop_note)

        service = FilerService(
            repo,
            review_dir=str(review_dir),
            vault_root=Path("/vault"),
        )
        result = service.file_approved_notes()

        assert result == 1
        assert prop_path not in repo.files
        filed_note = repo.get_note(target_path)
        assert filed_note is not None
        assert filed_note.frontmatter.model_dump().get("title") == "Bar Note"
        assert "Body content here" in filed_note.body

    def test_path_traversal_skipped(self) -> None:
        review_dir = Path("00. Inbox/1. Review Queue")
        prop_path = review_dir / "malicious.md"
        prop_body = """%%FILE: ../../../etc/passwd%%
content"""
        prop_note = Note(
            path=prop_path,
            frontmatter=Frontmatter.model_validate({"librarian": "file"}),
            body=prop_body,
        )
        repo = MockVaultAdapter()
        repo.add_note(prop_path, prop_note)

        service = FilerService(
            repo,
            review_dir=str(review_dir),
            vault_root=Path("/vault"),
        )
        result = service.file_approved_notes()

        assert result == 0
        assert prop_path in repo.files

    def test_maintenance_fix_in_place_updates_file(self) -> None:
        target_path = Path("20. Projects/Foo/existing.md")
        review_dir = Path("00. Inbox/1. Review Queue")
        prop_path = review_dir / "fix_proposal.md"
        existing_note = Note(
            path=target_path,
            frontmatter=Frontmatter(title="Old Title"),
            body="Old content",
        )
        prop_body = f"""%%FILE: {target_path}%%
---
title: Updated Title
tags: [project]
---
Updated content."""
        prop_note = Note(
            path=prop_path,
            frontmatter=Frontmatter.model_validate({
                "librarian": "file",
                "target-file": str(target_path),
            }),
            body=prop_body,
        )
        repo = MockVaultAdapter()
        repo.add_note(target_path, existing_note)
        repo.add_note(prop_path, prop_note)

        service = FilerService(
            repo,
            review_dir=str(review_dir),
            vault_root=Path("/vault"),
        )
        result = service.file_approved_notes()

        assert result == 1
        assert prop_path not in repo.files
        filed_note = repo.get_note(target_path)
        assert filed_note is not None
        assert filed_note.frontmatter.model_dump().get("title") == "Updated Title"
        assert "Updated content" in filed_note.body

    def test_proposal_with_no_files_kept(self) -> None:
        review_dir = Path("00. Inbox/1. Review Queue")
        prop_path = review_dir / "empty_proposal.md"
        prop_note = Note(
            path=prop_path,
            frontmatter=Frontmatter.model_validate({"librarian": "file"}),
            body="No %%FILE%% blocks here.",
        )
        repo = MockVaultAdapter()
        repo.add_note(prop_path, prop_note)

        service = FilerService(
            repo,
            review_dir=str(review_dir),
            vault_root=Path("/vault"),
        )
        result = service.file_approved_notes()

        assert result == 0
        assert prop_path in repo.files
