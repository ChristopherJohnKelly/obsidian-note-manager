"""Unit tests for vault I/O Activities.

Each test exercises one acceptance criterion from OBSE-P5-S04.
Activities are synchronous def functions — call them directly, no await needed.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from apps.vault_worker.activities.vault_io import (
    delete_note,
    get_code_registry,
    get_skeleton,
    list_notes_in,
    read_note,
    read_raw,
    save_note,
    scan_vault,
    validate_note,
)
from packages.shared.models import Frontmatter, VaultNote


# ---------------------------------------------------------------------------
# read_note
# ---------------------------------------------------------------------------


def test_read_note_returns_vault_note(dummy_vault_path):
    """AC: read_note returns VaultNote with correct frontmatter for clean fixture."""
    result = read_note(str(dummy_vault_path), "20. Projects/TEST-P01/TEST-P01 - Project Root.md")
    assert result is not None
    assert result.frontmatter.code == "TEST-P01"
    assert result.frontmatter.type == "project"


def test_read_note_returns_none_for_missing(dummy_vault_path):
    """AC: read_note returns None for a non-existent path."""
    result = read_note(str(dummy_vault_path), "does/not/exist.md")
    assert result is None


# ---------------------------------------------------------------------------
# save_note / delete_note
# ---------------------------------------------------------------------------


def test_save_note_then_read_returns_same_content(dummy_vault_path, tmp_path):
    """AC: save_note writes a file; subsequent read_note returns the same content."""
    vault_root = str(tmp_path)
    path = "20. Projects/SAVE-TEST/SAVE-TEST - Note.md"
    note = VaultNote(
        path=Path(path),
        frontmatter=Frontmatter(
            type="project",
            code="SAVE-TEST",
            aliases=["Save Test"],
            tags=["type/project"],
        ),
        body="Save test body content.",
    )
    save_note(vault_root, path, note)
    result = read_note(vault_root, path)
    assert result is not None
    assert result.frontmatter.code == "SAVE-TEST"
    assert "Save test body content." in result.body


def test_delete_note_removes_file(dummy_vault_path, tmp_path):
    """AC: delete_note removes a file; subsequent read_note returns None."""
    vault_root = str(tmp_path)
    path = "20. Projects/DEL-TEST/DEL-TEST - Note.md"
    note = VaultNote(
        path=Path(path),
        frontmatter=Frontmatter(code="DEL-TEST", aliases=["Del"], tags=["type/project"]),
        body="To be deleted.",
    )
    save_note(vault_root, path, note)
    assert read_note(vault_root, path) is not None

    delete_note(vault_root, path)
    assert read_note(vault_root, path) is None


# ---------------------------------------------------------------------------
# list_notes_in
# ---------------------------------------------------------------------------


def test_list_notes_in_returns_relative_paths(dummy_vault_path):
    """AC: list_notes_in returns list of relative string paths for the directory."""
    result = list_notes_in(str(dummy_vault_path), "20. Projects/TEST-P01")
    assert isinstance(result, list)
    assert len(result) > 0
    # Paths are strings, not Path objects
    assert all(isinstance(p, str) for p in result)
    assert any("TEST-P01 - Project Root.md" in p for p in result)


def test_list_notes_in_missing_directory_returns_empty(dummy_vault_path):
    """AC: list_notes_in on missing directory returns empty list."""
    result = list_notes_in(str(dummy_vault_path), "99. NonExistent")
    assert result == []


# ---------------------------------------------------------------------------
# read_raw
# ---------------------------------------------------------------------------


def test_read_raw_returns_string_with_frontmatter(dummy_vault_path):
    """AC: read_raw returns raw file content including YAML frontmatter."""
    result = read_raw(str(dummy_vault_path), "20. Projects/TEST-P01/TEST-P01 - Project Root.md")
    assert result is not None
    assert isinstance(result, str)
    assert "TEST-P01" in result


def test_read_raw_returns_none_for_missing(dummy_vault_path):
    """AC: read_raw returns None for a non-existent path."""
    result = read_raw(str(dummy_vault_path), "does/not/exist.md")
    assert result is None


# ---------------------------------------------------------------------------
# scan_vault
# ---------------------------------------------------------------------------


def test_scan_vault_returns_expected_scores(dummy_vault_path):
    """AC: scan_vault on Dummy Vault returns correct scores for non-excluded files.

    Expected scores (from fixture annotations):
    - wrong-prefix-note.md: 60 (Rule 1 + Rule 2)
    - another-wrong-prefix.md: 50 (Rule 2 only)
    - AREA - Context Note.md: 10 (Rule 1 only)
    - AREA - Bad Note.md: 10 (Rule 1 only)
    - meeting.md: 30 (Rule 1 + Rule 3)
    - untitled.md: 30 (Rule 1 + Rule 3)
    - note.md: 30 (Rule 1 + Rule 3)
    Clean files (score 0) are not returned.
    """
    results = scan_vault(str(dummy_vault_path))
    score_map = {str(r.path): r.score for r in results}

    assert score_map.get("20. Projects/TEST-P01/wrong-prefix-note.md") == 60
    assert score_map.get("20. Projects/TEST-P01/another-wrong-prefix.md") == 50
    assert score_map.get("30. Areas/1. Test Area/AREA - Context Note.md") == 10
    assert score_map.get("30. Areas/1. Test Area/AREA - Bad Note.md") == 10
    assert score_map.get("30. Areas/1. Test Area/meeting.md") == 30
    assert score_map.get("30. Areas/1. Test Area/untitled.md") == 30
    assert score_map.get("30. Areas/1. Test Area/note.md") == 30


def test_scan_vault_excludes_inbox(dummy_vault_path):
    """AC: scan_vault excludes files under 00. Inbox/ and excluded directories."""
    results = scan_vault(str(dummy_vault_path))
    paths = [str(r.path) for r in results]
    assert not any("00. Inbox" in p for p in paths)


# ---------------------------------------------------------------------------
# validate_note
# ---------------------------------------------------------------------------


def test_validate_note_code_mismatch_returns_score_50(dummy_vault_path):
    """AC: validate_note on code-mismatch file returns ValidationResult with score=50."""
    result = validate_note(
        str(dummy_vault_path),
        "20. Projects/TEST-P01/another-wrong-prefix.md",
    )
    assert result is not None
    assert result.score == 50


def test_validate_note_clean_file_returns_none(dummy_vault_path):
    """AC: validate_note on a clean file returns None."""
    result = validate_note(
        str(dummy_vault_path),
        "20. Projects/TEST-P01/TEST-P01 - Project Root.md",
    )
    assert result is None


def test_validate_note_missing_path_returns_none(dummy_vault_path):
    """AC: validate_note on non-existent path returns None."""
    result = validate_note(str(dummy_vault_path), "does/not/exist.md")
    assert result is None


# ---------------------------------------------------------------------------
# get_skeleton
# ---------------------------------------------------------------------------


def test_get_skeleton_returns_nonempty_string_with_wiki_links(dummy_vault_path):
    """AC: get_skeleton returns a non-empty string containing [[ wiki-link targets."""
    result = get_skeleton(str(dummy_vault_path))
    assert isinstance(result, str)
    assert len(result) > 0
    assert "[[" in result


# ---------------------------------------------------------------------------
# get_code_registry
# ---------------------------------------------------------------------------


def test_get_code_registry_returns_entries_with_test_p01(dummy_vault_path):
    """AC: get_code_registry returns at least one CodeRegistryEntry for TEST-P01."""
    results = get_code_registry(str(dummy_vault_path))
    assert len(results) > 0
    codes = [e.code for e in results]
    assert "TEST-P01" in codes


def test_get_code_registry_entries_have_required_fields(dummy_vault_path):
    """AC: each CodeRegistryEntry has code, name, folder fields."""
    results = get_code_registry(str(dummy_vault_path))
    for entry in results:
        assert entry.code
        assert entry.name
        assert entry.folder


# ---------------------------------------------------------------------------
# Edge-case / coverage-gap tests
# ---------------------------------------------------------------------------


def test_scan_vault_on_empty_vault_returns_empty(tmp_path):
    """scan_vault on a vault with no Projects/Areas folders returns empty list."""
    result = scan_vault(str(tmp_path))
    assert result == []


def test_get_code_registry_on_empty_vault_returns_empty(tmp_path):
    """get_code_registry on a vault with no Areas/Projects returns empty list."""
    result = get_code_registry(str(tmp_path))
    assert result == []


def test_get_skeleton_on_empty_vault_returns_empty_string(tmp_path):
    """get_skeleton on a vault with no Areas/Projects/Resources returns empty string."""
    result = get_skeleton(str(tmp_path))
    assert result == ""


def test_validate_note_in_unregistered_folder(tmp_path):
    """validate_note on a file in a folder with no code registry entry.

    Covers _find_expected_code returning None (Rule 2 skipped, only Rule 1 fires).
    """
    path = "20. Projects/unregistered/my-note.md"
    note = VaultNote(
        path=Path(path),
        frontmatter=Frontmatter(),  # no aliases, no tags
        body="content without metadata",
    )
    save_note(str(tmp_path), path, note)
    result = validate_note(str(tmp_path), path)
    # Rule 1 fires (+10); Rule 2 skipped (no registry entry); Rule 3 not in BAD_TITLES
    assert result is not None
    assert result.score == 10
    assert "Missing aliases/tags" in result.reasons


def test_delete_note_nonexistent_is_noop(tmp_path):
    """delete_note on a path that does not exist is a no-op (no exception)."""
    delete_note(str(tmp_path), "does/not/exist.md")  # should not raise


def test_list_notes_in_file_path_returns_empty(tmp_path):
    """list_notes_in on a path that is a file (not directory) returns empty list."""
    file_path = tmp_path / "somefile.md"
    file_path.write_text("content")
    result = list_notes_in(str(tmp_path), "somefile.md")
    assert result == []


# ---------------------------------------------------------------------------
# Integration smoke test: Activity registration with Temporal worker
# ---------------------------------------------------------------------------


import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
import pytest_asyncio
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from apps.vault_worker.activities.vault_io import (
    delete_note,
    get_code_registry,
    get_skeleton,
    list_notes_in,
    read_note,
    read_raw,
    save_note,
    scan_vault,
    validate_note,
)

ALL_VAULT_IO_ACTIVITIES = [
    read_note,
    save_note,
    delete_note,
    list_notes_in,
    read_raw,
    scan_vault,
    validate_note,
    get_skeleton,
    get_code_registry,
]


from temporalio import workflow as _workflow


@_workflow.defn
class _ListNotesWorkflow:
    """Minimal workflow wrapping list_notes_in for registration smoke test.

    Uses list_notes_in (returns list[str]) instead of read_note (returns VaultNote
    with Path field) to avoid Pydantic serialization complexity in this smoke test.
    The purpose is to verify Activity registration, not data converter configuration.
    """

    @_workflow.run
    async def run(self, vault_root: str, directory: str) -> list[str]:
        return await _workflow.execute_activity(
            list_notes_in,
            args=[vault_root, directory],
            schedule_to_close_timeout=__import__("datetime").timedelta(seconds=30),
        )


@pytest.mark.asyncio
async def test_all_activities_registered_and_executable(temporal_client: Client, dummy_vault_path):
    """AC: all Activities register with the Temporal worker; list_notes_in executes via client.

    Smoke test: registers all vault I/O activities with a Worker and executes
    list_notes_in through the Temporal task queue to confirm registration is correct.
    """
    task_queue = "test-vault-io-smoke"
    async with Worker(
        temporal_client,
        task_queue=task_queue,
        workflows=[_ListNotesWorkflow],
        activities=ALL_VAULT_IO_ACTIVITIES,
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        result = await temporal_client.execute_workflow(
            _ListNotesWorkflow.run,
            args=[str(dummy_vault_path), "20. Projects/TEST-P01"],
            id="test-vault-io-smoke-list-notes",
            task_queue=task_queue,
        )
    assert isinstance(result, list)
    assert any("TEST-P01 - Project Root.md" in p for p in result)
