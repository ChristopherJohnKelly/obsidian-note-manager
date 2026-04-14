"""Pytest fixtures for test suite."""

from pathlib import Path

import pytest


# Lazy imports: only available when src_v2 dependencies are installed
def _FakeLLM():
    from src_v2.infrastructure.testing.adapters import FakeLLM
    return FakeLLM


def _MockVaultAdapter():
    from src_v2.infrastructure.testing.adapters import MockVaultAdapter
    return MockVaultAdapter


def _Note():
    from src_v2.core.domain.models import Note
    return Note


def _Frontmatter():
    from src_v2.core.domain.models import Frontmatter
    return Frontmatter


def _CodeRegistryEntry():
    from src_v2.core.domain.models import CodeRegistryEntry
    return CodeRegistryEntry


def _ValidationResult():
    from src_v2.core.domain.models import ValidationResult
    return ValidationResult


@pytest.fixture
def fake_llm():
    """LLM mock that echoes back prompts (no API calls)."""
    return _FakeLLM()()


@pytest.fixture
def sample_note():
    """Valid note with frontmatter and body for reuse."""
    Note = _Note()
    Frontmatter = _Frontmatter()
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
def populated_vault():
    """
    MockVaultAdapter pre-loaded with 1 valid project and 1 invalid (dirty) note.

    - Code registry: 1 entry (PEPS, Pepsi Project)
    - Scan results: 1 dirty file (dirty.md, missing aliases/tags)
    - Both notes are in files so get_note works for generate_fix
    """
    Note = _Note()
    Frontmatter = _Frontmatter()
    MockVaultAdapter = _MockVaultAdapter()
    ValidationResult = _ValidationResult()
    CodeRegistryEntry = _CodeRegistryEntry()

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
