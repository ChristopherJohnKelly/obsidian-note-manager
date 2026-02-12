"""Pytest fixtures for B4 test suite."""

from pathlib import Path

import pytest

from src_v2.core.domain.models import CodeRegistryEntry, Frontmatter, Note, ValidationResult
from src_v2.infrastructure.testing.adapters import FakeLLM, MockVaultAdapter


@pytest.fixture
def fake_llm() -> FakeLLM:
    """LLM mock that echoes back prompts (no API calls)."""
    return FakeLLM()


@pytest.fixture
def sample_note() -> Note:
    """Valid note with frontmatter and body for reuse."""
    return Note(
        path=Path("20. Projects/Pepsi/Pepsi Project.md"),
        frontmatter=Frontmatter(
            title="Pepsi Project",
            code="PEPS",
            type="project",
            tags=["project"],
            aliases=["Pepsi Scaling"],
        ),
        body="Project overview and goals.",
    )


@pytest.fixture
def populated_vault() -> MockVaultAdapter:
    """
    MockVaultAdapter pre-loaded with 1 valid project and 1 invalid (dirty) note.

    - Code registry: 1 entry (PEPS, Pepsi Project)
    - Scan results: 1 dirty file (dirty.md, missing aliases/tags)
    - Both notes are in files so get_note works for generate_fix
    """
    dirty_path = Path("20. Projects/Pepsi/dirty.md")
    dirty_note = Note(
        path=dirty_path,
        frontmatter=Frontmatter(title="Dirty Note"),
        body="Content without proper metadata.",
    )

    repo = MockVaultAdapter(
        initial_scan_results=[
            ValidationResult(
                path=dirty_path,
                score=10,
                reasons=["Missing aliases/tags"],
            )
        ],
        initial_code_entries=[
            CodeRegistryEntry(
                code="PEPS",
                name="Pepsi Project",
                type="project",
                folder="20. Projects/Pepsi",
            )
        ],
        initial_skeleton="- [[Pepsi Project]] (20. Projects/Pepsi/Pepsi Project.md)",
    )
    repo.add_note(dirty_path, dirty_note)
    return repo
