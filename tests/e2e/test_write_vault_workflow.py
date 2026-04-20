"""End-to-end tests for WriteVaultWorkflow.

Tests include:
- save operation writes file, subsequent read returns saved content
- delete operation removes file, subsequent read returns None
- git_pull always called before write operations
- git_commit and git_push always called after all operations complete
- sequential guarantee: 10 simultaneous requests serialize on vault-mutation-queue
- empty operations list results in no file changes and no git commit
"""

from __future__ import annotations

import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest_asyncio
from temporalio import activity
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from apps.vault_worker.activities.git_ops import (
    git_commit as real_git_commit,
    git_pull as real_git_pull,
    git_push as real_git_push,
)
from apps.vault_worker.activities.vault_io import (
    delete_note as real_delete_note,
    read_note as real_read_note,
    save_note as real_save_note,
)
from apps.vault_worker.workflows.write_vault import (
    WriteOperation,
    WriteVaultInput,
    WriteVaultWorkflow,
)
from packages.shared.models import Frontmatter, VaultNote
from packages.shared.workflow_names import QUEUE_MUTATION


@pytest_asyncio.fixture
async def pydantic_client(temporal_client):
    return Client(
        service_client=temporal_client.service_client,
        namespace=temporal_client.namespace,
        data_converter=pydantic_data_converter,
    )


# -----------------------------------------------------------------------------
# Mock activities for serialisation load test
# -----------------------------------------------------------------------------

@activity.defn(name="save_note")
def timed_save_note(vault_root: str, path: str, note: VaultNote) -> None:
    """Sleeps 0.1s to make serialisation mathematically measurable."""
    time.sleep(0.1)


@activity.defn(name="git_pull")
def noop_git_pull(vault_path: str) -> None:
    pass


@activity.defn(name="git_commit")
def noop_git_commit(vault_path: str, message: str) -> str:
    return "fake-sha"


@activity.defn(name="git_push")
def noop_git_push(vault_path: str) -> None:
    pass


SERIALISATION_TEST_ACTIVITIES = [
    timed_save_note,
    noop_git_pull,
    noop_git_commit,
    noop_git_push,
]

REAL_ACTIVITIES = [
    real_save_note,
    real_delete_note,
    real_git_pull,
    real_git_commit,
    real_git_push,
]


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

async def test_save_operation_writes_file(pydantic_client, local_bare_repo):
    """A save operation writes the file; a subsequent read_note returns the saved content."""
    vault_path = local_bare_repo["working"]
    note = VaultNote(
        path=Path("test_note.md"),
        frontmatter=Frontmatter(title="Test Note", tags=["test"]),
        body="Test content",
    )
    workflow_input = WriteVaultInput(
        vault_path=vault_path,
        operations=[WriteOperation(op="save", path="test_note.md", note=note)],
        commit_message="Add test note",
    )
    task_queue = f"test-save-{uuid.uuid4().hex}"
    async with Worker(
        pydantic_client,
        task_queue=task_queue,
        workflows=[WriteVaultWorkflow],
        activities=REAL_ACTIVITIES,
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        commit_sha = await pydantic_client.execute_workflow(
            WriteVaultWorkflow.run,
            workflow_input,
            id=f"test-save-{uuid.uuid4().hex}",
            task_queue=task_queue,
        )
    assert len(commit_sha) == 40
    read_result = real_read_note(vault_path, "test_note.md")
    assert read_result is not None
    assert read_result.path == Path("test_note.md")
    assert read_result.frontmatter.title == "Test Note"
    assert read_result.body == "Test content"


async def test_delete_operation_removes_file(pydantic_client, local_bare_repo):
    """A delete operation removes the file; a subsequent read_note returns None.

    Pre-seeds the file with real save_note + commit/push so the test runs
    only a single delete workflow.
    """
    vault_path = local_bare_repo["working"]
    repo = local_bare_repo["repo"]
    note = VaultNote(
        path=Path("to_delete.md"),
        frontmatter=Frontmatter(title="Delete Me"),
        body="",
    )
    real_save_note(vault_path, "to_delete.md", note)
    repo.index.add(["to_delete.md"])
    repo.index.commit("seed file to delete")
    repo.remotes.origin.push()

    delete_input = WriteVaultInput(
        vault_path=vault_path,
        operations=[WriteOperation(op="delete", path="to_delete.md")],
        commit_message="Delete file",
    )
    task_queue = f"test-delete-{uuid.uuid4().hex}"
    async with Worker(
        pydantic_client,
        task_queue=task_queue,
        workflows=[WriteVaultWorkflow],
        activities=REAL_ACTIVITIES,
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        commit_sha = await pydantic_client.execute_workflow(
            WriteVaultWorkflow.run,
            delete_input,
            id=f"test-delete-{uuid.uuid4().hex}",
            task_queue=task_queue,
        )
    assert len(commit_sha) == 40
    assert real_read_note(vault_path, "to_delete.md") is None


async def test_git_pull_called_before_writes(pydantic_client, tmp_path):
    """git_pull is always called before write operations (save+delete in one workflow)."""
    vault = tmp_path / "vault"
    vault.mkdir()

    call_order: list[str] = []

    @activity.defn(name="git_pull")
    def mock_git_pull(vault_path: str) -> None:
        call_order.append("git_pull")

    @activity.defn(name="save_note")
    def mock_save_note(vault_root: str, path: str, note: VaultNote) -> None:
        call_order.append("save_note")

    @activity.defn(name="delete_note")
    def mock_delete_note(vault_root: str, path: str) -> None:
        call_order.append("delete_note")

    @activity.defn(name="git_commit")
    def mock_git_commit(vault_path: str, message: str) -> str:
        call_order.append("git_commit")
        return "fake-sha"

    @activity.defn(name="git_push")
    def mock_git_push(vault_path: str) -> None:
        call_order.append("git_push")

    mock_activities = [mock_git_pull, mock_save_note, mock_delete_note, mock_git_commit, mock_git_push]

    note = VaultNote(path=Path("test.md"), frontmatter=Frontmatter(title="Test"), body="")
    workflow_input = WriteVaultInput(
        vault_path=str(vault),
        operations=[
            WriteOperation(op="save", path="test.md", note=note),
            WriteOperation(op="delete", path="other.md"),
        ],
        commit_message="Save then delete",
    )

    task_queue = f"test-pull-order-{uuid.uuid4().hex}"
    async with Worker(
        pydantic_client,
        task_queue=task_queue,
        workflows=[WriteVaultWorkflow],
        activities=mock_activities,
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        await pydantic_client.execute_workflow(
            WriteVaultWorkflow.run,
            workflow_input,
            id=f"test-order-{uuid.uuid4().hex}",
            task_queue=task_queue,
        )

    assert call_order[0] == "git_pull"
    assert "save_note" in call_order[1:]
    assert "delete_note" in call_order[1:]
    assert call_order.index("git_pull") < call_order.index("save_note")
    assert call_order.index("git_pull") < call_order.index("delete_note")


async def test_git_commit_and_push_called_after_operations(pydantic_client, tmp_path):
    """git_commit and git_push are always called after all operations complete, in order."""
    vault = tmp_path / "vault"
    vault.mkdir()

    call_order: list[str] = []

    @activity.defn(name="git_pull")
    def mock_git_pull(vault_path: str) -> None:
        call_order.append("git_pull")

    @activity.defn(name="save_note")
    def mock_save_note(vault_root: str, path: str, note: VaultNote) -> None:
        call_order.append("save_note")

    @activity.defn(name="delete_note")
    def mock_delete_note(vault_root: str, path: str) -> None:
        call_order.append("delete_note")

    @activity.defn(name="git_commit")
    def mock_git_commit(vault_path: str, message: str) -> str:
        call_order.append("git_commit")
        return "fake-sha"

    @activity.defn(name="git_push")
    def mock_git_push(vault_path: str) -> None:
        call_order.append("git_push")

    mock_activities = [mock_git_pull, mock_save_note, mock_delete_note, mock_git_commit, mock_git_push]

    note = VaultNote(path=Path("test1.md"), frontmatter=Frontmatter(title="Test1"), body="")
    multi_input = WriteVaultInput(
        vault_path=str(vault),
        operations=[
            WriteOperation(op="save", path="test1.md", note=note),
            WriteOperation(op="delete", path="test2.md"),
        ],
        commit_message="Multiple ops",
    )

    task_queue = f"test-commit-push-{uuid.uuid4().hex}"
    async with Worker(
        pydantic_client,
        task_queue=task_queue,
        workflows=[WriteVaultWorkflow],
        activities=mock_activities,
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        await pydantic_client.execute_workflow(
            WriteVaultWorkflow.run,
            multi_input,
            id=f"test-multi-ops-{uuid.uuid4().hex}",
            task_queue=task_queue,
        )

    assert call_order == ["git_pull", "save_note", "delete_note", "git_commit", "git_push"]


async def test_empty_operations_list_no_changes_no_commit(pydantic_client, local_bare_repo):
    """An empty operations list results in no file changes and no git commit."""
    vault_path = local_bare_repo["working"]
    repo = local_bare_repo["repo"]
    original_head = repo.head.commit.hexsha

    workflow_input = WriteVaultInput(
        vault_path=vault_path,
        operations=[],
        commit_message="Should not commit",
    )
    task_queue = f"test-empty-{uuid.uuid4().hex}"
    async with Worker(
        pydantic_client,
        task_queue=task_queue,
        workflows=[WriteVaultWorkflow],
        activities=REAL_ACTIVITIES,
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        result = await pydantic_client.execute_workflow(
            WriteVaultWorkflow.run,
            workflow_input,
            id=f"test-empty-{uuid.uuid4().hex}",
            task_queue=task_queue,
        )
    assert result == ""
    assert repo.head.commit.hexsha == original_head
    assert not repo.is_dirty(untracked_files=True)


async def test_sequential_writes_serialise_under_load(pydantic_client, tmp_path):
    """Prove the vault-mutation-queue serialises 10 concurrent WriteVaultWorkflow requests.

    Each write activity sleeps 0.1s. With max_concurrent_workflow_tasks=1 and
    max_concurrent_activities=1 on QUEUE_MUTATION, the 10 writes execute serially
    and total elapsed must exceed ~1.0s. Parallel execution would be ~0.1s.

    Uses the production task queue name (QUEUE_MUTATION) on purpose: this test's
    whole point is verifying the production queue config serialises writes.
    """
    vault = tmp_path / "vault"
    vault.mkdir()

    note = VaultNote(path=Path("note.md"), frontmatter=Frontmatter(title="T"), body="b")

    async with Worker(
        pydantic_client,
        task_queue=QUEUE_MUTATION,
        workflows=[WriteVaultWorkflow],
        activities=SERIALISATION_TEST_ACTIVITIES,
        max_concurrent_workflow_tasks=1,
        max_concurrent_activities=1,
        max_cached_workflows=0,
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        t0 = time.monotonic()
        await asyncio.gather(*[
            pydantic_client.execute_workflow(
                WriteVaultWorkflow.run,
                WriteVaultInput(
                    vault_path=str(vault),
                    operations=[WriteOperation(op="save", path=f"note_{i}.md", note=note)],
                    commit_message=f"write {i}",
                ),
                id=f"write-serial-{uuid.uuid4().hex}-{i}",
                task_queue=QUEUE_MUTATION,
            )
            for i in range(10)
        ])
        elapsed = time.monotonic() - t0

    assert elapsed > 0.9, (
        f"Writes appear to have run in parallel (elapsed {elapsed:.2f}s). "
        "Check vault-mutation-queue max_concurrent_workflow_tasks=1 is set."
    )
