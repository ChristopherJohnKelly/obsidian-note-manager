"""Unit tests for git operations Activities (OBSE-P5-S05).

All tests use a local bare repository — no real network calls are made.
Activities are synchronous def functions; call them directly, no await needed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo

from apps.vault_worker.activities.git_ops import (
    git_clone,
    git_commit,
    git_pull,
    git_push,
)


# ---------------------------------------------------------------------------
# git_clone
# ---------------------------------------------------------------------------


def test_git_clone_creates_dot_git_folder(tmp_path, local_bare_repo):
    """AC: git_clone creates a local clone with a .git folder."""
    target = str(tmp_path / "cloned")
    git_clone(local_bare_repo["bare"], target, pat="dummy-pat")
    assert (Path(target) / ".git").is_dir()


def test_git_clone_contains_expected_files(tmp_path, local_bare_repo):
    """AC: cloned directory contains files committed to the remote."""
    target = str(tmp_path / "cloned2")
    git_clone(local_bare_repo["bare"], target, pat="dummy-pat")
    assert (Path(target) / "README.md").exists()


def test_git_clone_with_https_url_injects_pat(tmp_path, local_bare_repo, monkeypatch):
    """PAT is injected into https:// URLs; local paths are passed through unchanged."""
    captured = {}
    original_clone_from = Repo.clone_from

    def fake_clone_from(url, path, **kwargs):
        captured["url"] = url
        # Clone from the local bare repo so no real network call is made
        return original_clone_from(local_bare_repo["bare"], path, **kwargs)

    monkeypatch.setattr("apps.vault_worker.activities.git_ops.Repo.clone_from", fake_clone_from)
    target = str(tmp_path / "cloned_https")
    git_clone("https://github.com/owner/repo.git", target, pat="mytoken")
    assert "mytoken@" in captured["url"]


def test_git_clone_local_url_not_modified(tmp_path, local_bare_repo):
    """Non-https URLs (local paths) are not modified — no PAT injection."""
    target = str(tmp_path / "cloned_local")
    # Using the local bare path directly (no https://) — should work unchanged
    git_clone(local_bare_repo["bare"], target, pat="irrelevant")
    assert (Path(target) / ".git").is_dir()


# ---------------------------------------------------------------------------
# git_pull
# ---------------------------------------------------------------------------


def test_git_pull_fetches_new_remote_commit(tmp_path, local_bare_repo):
    """AC: git_pull pulls a new commit that was pushed to the remote after clone."""
    bare = local_bare_repo["bare"]

    # Push a new commit from a separate clone (simulates remote change)
    push_working = tmp_path / "push_working"
    push_repo = Repo.clone_from(bare, str(push_working))
    (push_working / "new_file.md").write_text("added by remote")
    push_repo.index.add(["new_file.md"])
    push_repo.index.commit("add new_file.md")
    push_repo.remotes.origin.push()

    # Pull into the original working repo
    git_pull(local_bare_repo["working"])

    assert (Path(local_bare_repo["working"]) / "new_file.md").exists()


def test_git_pull_idempotent_on_up_to_date_repo(local_bare_repo):
    """AC: git_pull on an already up-to-date repo completes without error."""
    git_pull(local_bare_repo["working"])  # first pull — nothing to fetch
    git_pull(local_bare_repo["working"])  # second pull — still safe


# ---------------------------------------------------------------------------
# git_commit
# ---------------------------------------------------------------------------


def test_git_commit_creates_commit_and_returns_sha(local_bare_repo):
    """AC: git_commit stages all changes, commits, and returns the commit SHA."""
    working = local_bare_repo["working"]
    (Path(working) / "committed.md").write_text("new content")

    sha = git_commit(working, "add committed.md")

    assert isinstance(sha, str)
    assert len(sha) == 40  # full SHA hex string
    repo = Repo(working)
    assert repo.head.commit.hexsha == sha


def test_git_commit_message_is_stored(local_bare_repo):
    """The commit message passed to git_commit is preserved in the commit object."""
    working = local_bare_repo["working"]
    (Path(working) / "msg_test.md").write_text("content")

    git_commit(working, "my specific message")

    repo = Repo(working)
    assert repo.head.commit.message.strip() == "my specific message"


def test_git_commit_no_changes_raises_value_error(local_bare_repo):
    """AC: git_commit raises ValueError when there is nothing to commit."""
    with pytest.raises(ValueError, match="[Nn]othing to commit"):
        git_commit(local_bare_repo["working"], "empty commit attempt")


def test_git_commit_stages_modified_tracked_file(local_bare_repo):
    """git_commit picks up modifications to already-tracked files."""
    working = local_bare_repo["working"]
    readme = Path(working) / "README.md"
    readme.write_text("modified content")

    sha = git_commit(working, "modify README")

    assert isinstance(sha, str) and len(sha) == 40


# ---------------------------------------------------------------------------
# git_push
# ---------------------------------------------------------------------------


def test_git_push_advances_remote_head(tmp_path, local_bare_repo):
    """AC: git_push pushes commits to the remote; a fresh clone sees them."""
    working = local_bare_repo["working"]
    bare = local_bare_repo["bare"]

    # Commit a new file locally
    (Path(working) / "pushed.md").write_text("pushed content")
    git_commit(working, "push test commit")

    # Push to bare remote
    git_push(working)

    # Verify by cloning from bare and checking the file exists
    verify_clone = tmp_path / "verify"
    Repo.clone_from(bare, str(verify_clone))
    assert (verify_clone / "pushed.md").exists()


def test_git_push_after_multiple_commits(tmp_path, local_bare_repo):
    """git_push pushes all local commits not yet on the remote."""
    working = local_bare_repo["working"]
    bare = local_bare_repo["bare"]

    (Path(working) / "file_a.md").write_text("a")
    git_commit(working, "commit A")
    (Path(working) / "file_b.md").write_text("b")
    git_commit(working, "commit B")

    git_push(working)

    verify = tmp_path / "verify2"
    Repo.clone_from(bare, str(verify))
    assert (verify / "file_a.md").exists()
    assert (verify / "file_b.md").exists()
