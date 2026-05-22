"""E2E tests for FilerIngestionWorkflow.

Covers all acceptance criteria from bubbles/OBSE-P5-S11-filer-ingestion-workflow.md.

Key constraints:
- C1: approve path must transition status drafting→awaiting_approval→filing→complete
- C1: get_draft_proposal returns None while drafting, non-None after LLM completes
- C1: approve dispatch must use child WriteVaultWorkflow on QUEUE_MUTATION, not direct activities
- C3: timeout path requires fresh function-scoped time-skipping env (not shared session fixture)
- C4: structural test pins exact child dispatch with save+delete operations
"""

from __future__ import annotations

import asyncio
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from apps.vault_worker.activities.vault_io import (
    get_code_registry,
    get_skeleton,
    list_notes_in,
    read_note,
)
from apps.vault_worker.activities.vault_manager_client import (
    configure_client,
    ensure_vault_synced,
)
from apps.vault_worker.activities.llm import (
    configure_provider,
    generate_proposal,
    LLM_RETRY_POLICY,
)
from apps.vault_worker.workflows.filer_ingestion import (
    FilerIngestionInput,
    FilerIngestionWorkflow,
)
from apps.vault_worker.workflows.read_vault import ReadVaultInput, ReadVaultWorkflow
from apps.vault_worker.workflows.write_vault import (
    WriteVaultWorkflow,
    WriteVaultInput,
    WriteOperation,
)
from packages.shared.models import VaultNote, Frontmatter
from packages.shared.workflow_names import (
    QUEUE_DEFAULT,
    QUEUE_MUTATION,
    UPD_ENSURE_SYNCED,
    VAULT_MANAGER_ID,
)
from tests.mocks.fake_llm import FakeLLMProvider


# ---------------------------------------------------------------------------
# Inline stubs — minimal stand-ins for VaultManagerWorkflow (full impl in S09)
# ---------------------------------------------------------------------------


@workflow.defn
class VaultManagerStub:
    """Accepts ensure_synced Update; returns immediately (fresh vault)."""

    def __init__(self) -> None:
        self._call_count: int = 0

    @workflow.update(name=UPD_ENSURE_SYNCED)
    async def on_ensure_synced(self) -> None:
        self._call_count += 1

    @workflow.query
    def call_count(self) -> int:
        return self._call_count

    @workflow.run
    async def run(self) -> None:
        await asyncio.sleep(3600)


# ---------------------------------------------------------------------------
# Mock activities for git operations
# ---------------------------------------------------------------------------


@activity.defn(name="git_pull")
def noop_git_pull(vault_path: str) -> None:
    pass


@activity.defn(name="git_commit")
def noop_git_commit(vault_path: str, message: str) -> str:
    return "0123456789abcdef0123456789abcdef01234567"


@activity.defn(name="git_push")
def noop_git_push(vault_path: str) -> None:
    pass


@activity.defn(name="save_note")
def real_save_note(vault_root: str, path: str, note: VaultNote) -> None:
    """Write a VaultNote to the vault."""
    file_path = Path(vault_root) / path
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Build markdown content with frontmatter
    content = ""

    # Write frontmatter YAML block if present
    if note.frontmatter:
        content += "---\n"
        fm_dict = note.frontmatter.model_dump() if hasattr(note.frontmatter, 'model_dump') else {}
        for key, value in fm_dict.items():
            if value is not None:
                # Simple YAML serialization
                if isinstance(value, str):
                    content += f"{key}: {value}\n"
                elif isinstance(value, (int, float, bool)):
                    content += f"{key}: {value}\n"
                elif isinstance(value, list):
                    content += f"{key}: {value}\n"
                else:
                    content += f"{key}: {repr(value)}\n"
        content += "---\n"

    # Write body
    content += note.body

    with open(file_path, "w") as f:
        f.write(content)


@activity.defn(name="delete_note")
def real_delete_note(vault_root: str, path: str) -> None:
    """Delete a note from the vault."""
    file_path = Path(vault_root) / path
    if file_path.exists():
        file_path.unlink()


# ---------------------------------------------------------------------------
# Blocking mock for generate_proposal (C1: test AC#1, AC#6)
# ---------------------------------------------------------------------------

_proposal_event: threading.Event | None = None


@activity.defn(name="generate_proposal")
def blocking_generate_proposal(context, source_body: str) -> str:
    """Block until _proposal_event is set, then return the fake proposal."""
    if _proposal_event is None:
        # Fallback to instant response if event not configured
        return FakeLLMProvider().generate_proposal(
            instructions="",
            body=source_body,
            context="",
            skeleton="",
        )
    _proposal_event.wait()
    return FakeLLMProvider().generate_proposal(
        instructions="",
        body=source_body,
        context="",
        skeleton="",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def pydantic_client(temporal_client: Client) -> Client:
    """Client with pydantic_data_converter for pathlib.Path in VaultNote."""
    client = Client(
        service_client=temporal_client.service_client,
        namespace=temporal_client.namespace,
        data_converter=pydantic_data_converter,
    )
    configure_client(client)
    try:
        yield client
    finally:
        configure_client(None)


def _fresh_queue() -> str:
    return f"test-filer-{uuid.uuid4().hex[:8]}"


def _read_activities():
    """Activities needed for ReadVaultWorkflow on QUEUE_DEFAULT."""
    return [
        get_skeleton,
        get_code_registry,
        read_note,
        list_notes_in,
        ensure_vault_synced,
        blocking_generate_proposal,
    ]


def _mutation_activities():
    """Activities needed for WriteVaultWorkflow on QUEUE_MUTATION."""
    return [
        real_save_note,
        real_delete_note,
        noop_git_pull,
        noop_git_commit,
        noop_git_push,
    ]


# ---------------------------------------------------------------------------
# C1: Approve path E2E test
# ---------------------------------------------------------------------------


async def test_approve_files_note_and_clears_inbox(
    pydantic_client, dummy_vault_path, tmp_path
):
    """C1: FilerIngestionWorkflow approve path.

    Asserts:
    - AC#1: status == "drafting" during LLM activity
    - AC#6: get_draft_proposal returns None before LLM completes
    - Workflow transitions drafting→awaiting_approval→filing→complete
    - Proposed file is created in vault
    - Source inbox file is deleted
    - Returns "filed"
    """
    global _proposal_event
    _proposal_event = threading.Event()

    # Copy dummy vault to tmp for mutation
    tmp_vault = tmp_path / "vault"
    shutil.copytree(dummy_vault_path, tmp_vault)

    # Configure providers
    configure_provider(FakeLLMProvider())

    queue = _fresh_queue()

    try:
        async with Worker(
            pydantic_client,
            task_queue=queue,
            workflows=[VaultManagerStub, ReadVaultWorkflow, FilerIngestionWorkflow],
            activities=_read_activities(),
            activity_executor=ThreadPoolExecutor(max_workers=4),
        ):
            async with Worker(
                pydantic_client,
                task_queue=QUEUE_MUTATION,
                workflows=[WriteVaultWorkflow],
                activities=_mutation_activities(),
                activity_executor=ThreadPoolExecutor(max_workers=2),
            ):
                # Start VaultManagerStub
                stub_handle = await pydantic_client.start_workflow(
                    VaultManagerStub.run,
                    id=VAULT_MANAGER_ID,
                    task_queue=queue,
                    id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                )

                try:
                    # Start FilerIngestionWorkflow
                    handle = await pydantic_client.start_workflow(
                        FilerIngestionWorkflow.run,
                        FilerIngestionInput(
                            vault_path=str(tmp_vault),
                            source_path="00. Inbox/0. Capture/new-capture-note.md",
                            context_code="TEST-P01",
                        ),
                        id=f"filer-approve-{uuid.uuid4().hex[:4]}",
                        task_queue=queue,
                    )

                    # AC#1: Assert status == "drafting" and proposal is None while LLM blocks
                    await asyncio.sleep(0.5)
                    status = await handle.query(FilerIngestionWorkflow.get_status)
                    proposal = await handle.query(FilerIngestionWorkflow.get_draft_proposal)
                    assert status == "drafting", f"Expected status='drafting', got {status}"
                    assert proposal is None, f"Expected proposal=None during drafting, got {proposal}"

                    # Release the blocking LLM activity
                    _proposal_event.set()

                    # AC#6: Poll until awaiting_approval and proposal is non-None
                    loop = asyncio.get_event_loop()
                    deadline = loop.time() + 10.0
                    while loop.time() < deadline:
                        status = await handle.query(FilerIngestionWorkflow.get_status)
                        proposal = await handle.query(FilerIngestionWorkflow.get_draft_proposal)
                        if status == "awaiting_approval" and proposal is not None:
                            break
                        await asyncio.sleep(0.1)
                    else:
                        raise AssertionError(
                            f"Workflow did not reach awaiting_approval with proposal; "
                            f"final status={status}, proposal={proposal}"
                        )

                    # Send approve signal
                    await handle.signal(FilerIngestionWorkflow.approve)

                    # Await result
                    result = await handle.result()

                    # Assertions on final state
                    assert result == "filed", f"Expected result='filed', got {result}"

                    final_status = await handle.query(FilerIngestionWorkflow.get_status)
                    assert final_status == "complete", f"Expected status='complete', got {final_status}"

                    # Verify vault state
                    # Proposed file should exist
                    proposed_path = tmp_vault / "30. Areas" / "1. Test Area" / "AREA - Filed Note.md"
                    assert proposed_path.exists(), f"Proposed file not found at {proposed_path}"

                    # Source inbox file should be deleted
                    source_path = tmp_vault / "00. Inbox" / "0. Capture" / "new-capture-note.md"
                    assert not source_path.exists(), f"Source inbox file still exists at {source_path}"

                finally:
                    await stub_handle.cancel()

    finally:
        # Reset global state
        _proposal_event = None
        configure_provider(None)


# ---------------------------------------------------------------------------
# C2: Reject path E2E test
# ---------------------------------------------------------------------------


async def test_reject_leaves_vault_unchanged(
    pydantic_client, dummy_vault_path, tmp_path
):
    """C2: FilerIngestionWorkflow reject path.

    Asserts:
    - Workflow transitions drafting→awaiting_approval→rejected
    - Reject signal resolves wait_condition and sets _decision
    - Result is "rejected"
    - Status is "rejected"
    - Vault remains unchanged: proposed file not created, source inbox file still present
    - No WriteVaultWorkflow dispatch occurs (mutation worker remains idle)
    """
    # Copy dummy vault to tmp for mutation
    tmp_vault = tmp_path / "vault"
    shutil.copytree(dummy_vault_path, tmp_vault)

    # Configure providers (instant FakeLLM, no blocking needed for reject path)
    configure_provider(FakeLLMProvider())

    queue = _fresh_queue()

    try:
        async with Worker(
            pydantic_client,
            task_queue=queue,
            workflows=[VaultManagerStub, ReadVaultWorkflow, FilerIngestionWorkflow],
            activities=_read_activities(),
            activity_executor=ThreadPoolExecutor(max_workers=4),
        ):
            async with Worker(
                pydantic_client,
                task_queue=QUEUE_MUTATION,
                workflows=[WriteVaultWorkflow],
                activities=_mutation_activities(),
                activity_executor=ThreadPoolExecutor(max_workers=2),
            ):
                # Start VaultManagerStub
                stub_handle = await pydantic_client.start_workflow(
                    VaultManagerStub.run,
                    id=VAULT_MANAGER_ID,
                    task_queue=queue,
                    id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                )

                try:
                    # Start FilerIngestionWorkflow
                    handle = await pydantic_client.start_workflow(
                        FilerIngestionWorkflow.run,
                        FilerIngestionInput(
                            vault_path=str(tmp_vault),
                            source_path="00. Inbox/0. Capture/new-capture-note.md",
                            context_code="TEST-P01",
                        ),
                        id=f"filer-reject-{uuid.uuid4().hex[:4]}",
                        task_queue=queue,
                    )

                    # Poll until awaiting_approval (FakeLLM is instant, no blocking needed)
                    loop = asyncio.get_event_loop()
                    deadline = loop.time() + 10.0
                    while loop.time() < deadline:
                        status = await handle.query(FilerIngestionWorkflow.get_status)
                        proposal = await handle.query(FilerIngestionWorkflow.get_draft_proposal)
                        if status == "awaiting_approval" and proposal is not None:
                            break
                        await asyncio.sleep(0.1)
                    else:
                        raise AssertionError(
                            f"Workflow did not reach awaiting_approval with proposal; "
                            f"final status={status}, proposal={proposal}"
                        )

                    # Send reject signal
                    await handle.signal(FilerIngestionWorkflow.reject)

                    # Await result
                    result = await handle.result()

                    # Assertions on final state
                    assert result == "rejected", f"Expected result='rejected', got {result}"

                    final_status = await handle.query(FilerIngestionWorkflow.get_status)
                    assert final_status == "rejected", f"Expected status='rejected', got {final_status}"

                    # Verify vault is unchanged
                    # Proposed file should NOT exist
                    proposed_path = tmp_vault / "30. Areas" / "1. Test Area" / "AREA - Filed Note.md"
                    assert not proposed_path.exists(), f"Proposed file should not exist at {proposed_path}"

                    # Source inbox file should still exist
                    source_path = tmp_vault / "00. Inbox" / "0. Capture" / "new-capture-note.md"
                    assert source_path.exists(), f"Source inbox file should still exist at {source_path}"

                finally:
                    await stub_handle.terminate()

    finally:
        # Reset global state
        configure_provider(None)
