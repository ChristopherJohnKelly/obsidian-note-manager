"""E2E tests for FilerIngestionWorkflow.

FilerIngestionWorkflow orchestrates inbox note filing: read → generate proposal →
await approval signal → write vault.
"""

from __future__ import annotations

import asyncio
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest_asyncio
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.contrib.pydantic import pydantic_data_converter
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
    generate_proposal,
)
from apps.vault_worker.workflows.filer_ingestion import (
    FilerIngestionInput,
    FilerIngestionWorkflow,
)
from apps.vault_worker.workflows.read_vault import ReadVaultInput, ReadVaultWorkflow
from apps.vault_worker.workflows.write_vault import (
    WriteVaultWorkflow,
)
from apps.vault_worker.core.response_parser import parse_llm_response
from packages.shared.models import VaultNote, Frontmatter, FilingProposal
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
# Mock activities for external dependencies
# ---------------------------------------------------------------------------


@activity.defn(name="git_pull")
def noop_git_pull(vault_path: str) -> None:
    pass


@activity.defn(name="git_commit")
def noop_git_commit(vault_path: str, message: str) -> str:
    return "fake-sha-0123456789abcdef0123456789abcdef01234567"


@activity.defn(name="git_push")
def noop_git_push(vault_path: str) -> None:
    pass


@activity.defn(name="save_note")
def real_save_note(vault_root: str, path: str, note: VaultNote) -> None:
    """Real save_note that writes to disk."""
    note_path = Path(vault_root) / path
    note_path.parent.mkdir(parents=True, exist_ok=True)

    # Write frontmatter (YAML)
    fm_lines = ["---"]
    fm_dict = note.frontmatter.model_dump(exclude_none=True, exclude_unset=True)
    for key, value in fm_dict.items():
        if isinstance(value, list):
            fm_lines.append(f"{key}:")
            for item in value:
                fm_lines.append(f"  - {item}")
        else:
            fm_lines.append(f"{key}: {value}")
    fm_lines.append("---")

    # Write body
    content = "\n".join(fm_lines) + "\n" + note.body
    note_path.write_text(content)


@activity.defn(name="delete_note")
def real_delete_note(vault_root: str, path: str) -> None:
    """Real delete_note that removes file from disk."""
    note_path = Path(vault_root) / path
    if note_path.exists():
        note_path.unlink()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def pydantic_client(temporal_client: Client) -> Client:
    """Client with pydantic_data_converter."""
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


# ---------------------------------------------------------------------------
# Acceptance tests
# ---------------------------------------------------------------------------


async def test_approve_path_files_note_and_clears_inbox(pydantic_client, dummy_vault_path, tmp_path):
    """FilerIngestionWorkflow happy-path: draft proposal → await approval → file note.

    - Copy dummy_vault_path to tmp_path / "vault" for mutation
    - Build pydantic_client and configure FakeLLMProvider
    - Register two Workers: QUEUE_DEFAULT (read + filer), QUEUE_MUTATION (write)
    - Start VaultManagerStub to handle ensure_synced Update
    - Start FilerIngestionWorkflow with inbox note
    - Poll status until "awaiting_approval"
    - Send approve signal
    - Assert result == "filed"
    - Assert proposed file exists at target path (FakeLLMProvider's hardcoded path)
    - Assert source inbox file is deleted
    - Query final status and proposal
    """
    from apps.vault_worker.activities.llm import configure_provider

    # Copy dummy_vault to a temporary mutable vault
    tmp_vault = tmp_path / "vault"
    shutil.copytree(dummy_vault_path, tmp_vault)

    # Create source inbox note for filing
    inbox_dir = tmp_vault / "00. Inbox" / "0. Capture"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    inbox_note = inbox_dir / "new-capture-note.md"
    inbox_note.write_text(
        "---\n"
        "title: New Capture\n"
        "---\n"
        "# New Capture\n"
        "This is a note to be filed."
    )

    # Configure LLM provider
    fake_llm = FakeLLMProvider()
    configure_provider(fake_llm)

    default_queue = QUEUE_DEFAULT
    mutation_queue = QUEUE_MUTATION

    try:
        # Start both workers
        async with Worker(
            pydantic_client,
            task_queue=default_queue,
            workflows=[VaultManagerStub, ReadVaultWorkflow, FilerIngestionWorkflow],
            activities=[
                get_code_registry,
                get_skeleton,
                read_note,
                list_notes_in,
                ensure_vault_synced,
                generate_proposal,
            ],
            activity_executor=ThreadPoolExecutor(max_workers=4),
        ):
            async with Worker(
                pydantic_client,
                task_queue=mutation_queue,
                workflows=[WriteVaultWorkflow],
                activities=[
                    real_save_note,
                    real_delete_note,
                    noop_git_pull,
                    noop_git_commit,
                    noop_git_push,
                ],
                activity_executor=ThreadPoolExecutor(max_workers=2),
            ):
                # Start VaultManagerStub
                stub_handle = await pydantic_client.start_workflow(
                    VaultManagerStub.run,
                    id=VAULT_MANAGER_ID,
                    task_queue=default_queue,
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
                        task_queue=default_queue,
                    )

                    # Poll status until awaiting_approval (with timeout)
                    import time
                    deadline = time.time() + 30
                    while time.time() < deadline:
                        status = await handle.query("get_status")
                        if status == "awaiting_approval":
                            break
                        # Best-effort: try to get draft proposal (may be None or dict)
                        try:
                            proposal = await handle.query("get_draft_proposal")
                        except Exception:
                            pass
                        await asyncio.sleep(0.5)
                    else:
                        raise AssertionError(
                            f"FilerIngestionWorkflow did not reach 'awaiting_approval' within 30s; "
                            f"last status={status}"
                        )

                    # Send approve signal
                    await handle.signal(FilerIngestionWorkflow.approve)

                    # Await result
                    result = await handle.result()
                    assert result == "filed", f"Expected result='filed', got {result}"

                    # Assert proposed file exists at target path (FakeLLMProvider hardcoded path)
                    proposed_path = tmp_vault / "30. Areas" / "1. Test Area" / "AREA - Filed Note.md"
                    assert proposed_path.exists(), f"Proposed file does not exist at {proposed_path}"

                    # Assert source inbox file is deleted
                    assert not inbox_note.exists(), f"Source inbox file still exists at {inbox_note}"

                    # Query final status and proposal
                    final_status = await handle.query("get_status")
                    assert final_status == "complete", f"Expected final status='complete', got {final_status}"

                    final_proposal = await handle.query("get_draft_proposal")
                    assert final_proposal is not None, "Expected final proposal to be non-None dict"
                    assert isinstance(final_proposal, dict), f"Expected dict, got {type(final_proposal)}"

                finally:
                    await stub_handle.cancel()

    finally:
        configure_provider(None)
