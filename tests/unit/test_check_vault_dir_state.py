"""Unit test for check_vault_dir_state Activity.

Tests the three return states: empty, valid_repo, invalid.
"""

import pytest
from pathlib import Path

from apps.vault_worker.activities.vault_io import check_vault_dir_state


def test_check_vault_dir_state_empty_nonexistent(tmp_path):
    """Returns 'empty' when vault_path does not exist."""
    non_existent = tmp_path / "missing"
    result = check_vault_dir_state(str(non_existent))
    assert result == "empty"


def test_check_vault_dir_state_empty_directory(tmp_path):
    """Returns 'empty' when directory exists but has no files."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    result = check_vault_dir_state(str(empty_dir))
    assert result == "empty"


def test_check_vault_dir_state_valid_repo(tmp_path):
    """Returns 'valid_repo' when .git directory exists."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    result = check_vault_dir_state(str(repo_dir))
    assert result == "valid_repo"


def test_check_vault_dir_state_invalid_non_empty_no_git(tmp_path):
    """Returns 'invalid' when directory non-empty but no .git."""
    dir_with_file = tmp_path / "nonrepo"
    dir_with_file.mkdir()
    (dir_with_file / "file.txt").write_text("content")
    result = check_vault_dir_state(str(dir_with_file))
    assert result == "invalid"


def test_check_vault_dir_state_invalid_mixed_content(tmp_path):
    """Returns 'invalid' when directory contains files/subdirs but no .git."""
    mixed_dir = tmp_path / "mixed"
    mixed_dir.mkdir()
    (mixed_dir / "subdir").mkdir()
    (mixed_dir / "note.md").write_text("# Note")
    result = check_vault_dir_state(str(mixed_dir))
    assert result == "invalid"