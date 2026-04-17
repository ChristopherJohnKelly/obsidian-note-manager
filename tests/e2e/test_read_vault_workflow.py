"""End-to-end tests for ReadVaultWorkflow.

Implements all acceptance criteria from OBSE-P5-S07.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pytest
import pytest_asyncio
import uuid
from temporalio import workflow
from temporalio.client import Client, WorkflowHandle
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from apps.vault_worker.activities.vault_io import (
    get_code_registry,
    get_skeleton,
    list_notes_in,
    read_note,
)
from packages.shared.models import VaultContext, VaultNote
from apps.vault_worker.workflows.read_vault import ReadVaultInput, ReadVaultWorkflow
from packages.shared.workflow_names import (
    QUEUE_DEFAULT,
    UPD_ENSURE_SYNCED,
    VAULT_MANAGER_ID,
)

# -----------------------------------------------------------------------------
# VaultManagerStub (inline stub for testing)
# -----------------------------------------------------------------------------

ensure_synced_call_count = 0


@workflow.defn
class VaultManagerStub:
    """Minimal stand-in for VaultManagerWorkflow. Accepts ensure_synced Updates
    and returns immediately. Used only in S07 tests; full implementation in S09."""

    @workflow.update(name=UPD_ENSURE_SYNCED)
    async def ensure_synced(self) -> None:
        global ensure_synced_call_count
        ensure_synced_call_count += 1
        print(f"ensure_synced called, count={ensure_synced_call_count}")

    @workflow.run
    async def run(self) -> None:
        # Stay alive long enough for tests to complete
        print("VaultManagerStub started")
        await asyncio.sleep(3600)
        print("VaultManagerStub finished")


# -----------------------------------------------------------------------------
# The real ReadVaultWorkflow and ReadVaultInput are imported from apps.vault_worker.workflows.read_vault
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# Test fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def reset_ensure_synced_count():
    global ensure_synced_call_count
    ensure_synced_call_count = 0


@pytest_asyncio.fixture
async def pydantic_client(temporal_client):
    """Client with pydantic data converter for Path serialization."""
    print("ENTERING pydantic_client fixture")
    print("pydantic_client fixture returning temporal_client (no converter)")
    return temporal_client


# -----------------------------------------------------------------------------
# Acceptance tests
# -----------------------------------------------------------------------------


async def test_read_vault_dispatches_ensure_synced(
    pydantic_client, dummy_vault_path, reset_ensure_synced_count
):
    """AC: ReadVaultWorkflow sends an ensure_synced Update to vault-manager."""
    global ensure_synced_call_count
    import uuid
    test_queue = f"test-read-vault-{uuid.uuid4().hex[:8]}"
    print(f"Starting test, pydantic_client={pydantic_client}, queue={test_queue}")
    print(f"Worker with workflows={[VaultManagerStub, ReadVaultWorkflow]}")
    async with Worker(
        pydantic_client,
        task_queue=test_queue,
        workflows=[VaultManagerStub, ReadVaultWorkflow],
        activities=[get_skeleton, get_code_registry, read_note, list_notes_in],
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        await asyncio.sleep(0.1)
        # Start the stub with the well-known ID
        await pydantic_client.start_workflow(
            VaultManagerStub.run,
            id=VAULT_MANAGER_ID,
            task_queue=test_queue,
        )
        result = await pydantic_client.execute_workflow(
            ReadVaultWorkflow.run,
            ReadVaultInput(vault_path=str(dummy_vault_path), context_code="TEST-P01"),
            id="read-test-1",
            task_queue=test_queue,
        )
    assert ensure_synced_call_count == 1
    assert result.skeleton


async def test_read_vault_returns_non_empty_skeleton(
    pydantic_client, dummy_vault_path, reset_ensure_synced_count
):
    """AC: The returned VaultContext contains a non-empty skeleton string."""
    global ensure_synced_call_count
    async with Worker(
        pydantic_client,
        task_queue=QUEUE_DEFAULT,
        workflows=[VaultManagerStub, ReadVaultWorkflow],
        activities=[get_skeleton, get_code_registry, read_note, list_notes_in],
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        await pydantic_client.start_workflow(
            VaultManagerStub.run,
            id=VAULT_MANAGER_ID,
            task_queue=QUEUE_DEFAULT,
        )
        result = await pydantic_client.execute_workflow(
            ReadVaultWorkflow.run,
            ReadVaultInput(vault_path=str(dummy_vault_path), context_code="TEST-P01"),
            id="read-test-2",
            task_queue=QUEUE_DEFAULT,
        )
    assert ensure_synced_call_count == 1
    assert result.skeleton
    assert isinstance(result.skeleton, str)
    assert len(result.skeleton) > 0


async def test_read_vault_returns_non_empty_code_registry(
    pydantic_client, dummy_vault_path, reset_ensure_synced_count
):
    """AC: The returned VaultContext contains a non-empty code_registry string."""
    global ensure_synced_call_count
    async with Worker(
        pydantic_client,
        task_queue=QUEUE_DEFAULT,
        workflows=[VaultManagerStub, ReadVaultWorkflow],
        activities=[get_skeleton, get_code_registry, read_note, list_notes_in],
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        await pydantic_client.start_workflow(
            VaultManagerStub.run,
            id=VAULT_MANAGER_ID,
            task_queue=QUEUE_DEFAULT,
        )
        result = await pydantic_client.execute_workflow(
            ReadVaultWorkflow.run,
            ReadVaultInput(vault_path=str(dummy_vault_path), context_code="TEST-P01"),
            id="read-test-3",
            task_queue=QUEUE_DEFAULT,
        )
    assert ensure_synced_call_count == 1
    assert result.code_registry
    assert isinstance(result.code_registry, str)
    assert len(result.code_registry) > 0


async def test_related_notes_filtered_by_context_code_folder(
    pydantic_client, dummy_vault_path, reset_ensure_synced_count
):
    """AC: VaultContext.related_notes contains only notes whose path starts with the folder corresponding to context_code."""
    global ensure_synced_call_count
    async with Worker(
        pydantic_client,
        task_queue=QUEUE_DEFAULT,
        workflows=[VaultManagerStub, ReadVaultWorkflow],
        activities=[get_skeleton, get_code_registry, read_note, list_notes_in],
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        await pydantic_client.start_workflow(
            VaultManagerStub.run,
            id=VAULT_MANAGER_ID,
            task_queue=QUEUE_DEFAULT,
        )
        result = await pydantic_client.execute_workflow(
            ReadVaultWorkflow.run,
            ReadVaultInput(vault_path=str(dummy_vault_path), context_code="TEST-P01"),
            id="read-test-4",
            task_queue=QUEUE_DEFAULT,
        )
    assert ensure_synced_call_count == 1
    # All related notes should be in the TEST-P01 folder
    prefix = "20. Projects/TEST-P01/"
    for note in result.related_notes:
        assert str(note.path).startswith(prefix), f"Note {note.path} not under {prefix}"


async def test_multiple_concurrent_reads(
    pydantic_client, dummy_vault_path, reset_ensure_synced_count
):
    """AC: Multiple simultaneous ReadVaultWorkflow executions complete without error."""
    global ensure_synced_call_count
    async with Worker(
        pydantic_client,
        task_queue=QUEUE_DEFAULT,
        workflows=[VaultManagerStub, ReadVaultWorkflow],
        activities=[get_skeleton, get_code_registry, read_note, list_notes_in],
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        await pydantic_client.start_workflow(
            VaultManagerStub.run,
            id=VAULT_MANAGER_ID,
            task_queue=QUEUE_DEFAULT,
        )
        results = await asyncio.gather(*[
            pydantic_client.execute_workflow(
                ReadVaultWorkflow.run,
                ReadVaultInput(vault_path=str(dummy_vault_path), context_code="TEST-P01"),
                id=f"read-test-parallel-{i}",
                task_queue=QUEUE_DEFAULT,
            )
            for i in range(5)
        ])
    # Each execution should have triggered its own ensure_synced Update
    assert ensure_synced_call_count == 5
    assert all(r.skeleton for r in results)
    assert all(r.code_registry for r in results)