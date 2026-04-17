"""Debug test for ReadVaultWorkflow."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pytest
from temporalio import workflow
from temporalio.worker import Worker

from apps.vault_worker.activities.vault_io import (
    get_code_registry,
    get_skeleton,
    list_notes_in,
    read_note,
)
from apps.vault_worker.workflows.read_vault import ReadVaultInput, ReadVaultWorkflow
from packages.shared.workflow_names import QUEUE_DEFAULT, UPD_ENSURE_SYNCED, VAULT_MANAGER_ID


@workflow.defn
class VaultManagerStub:
    @workflow.update(name=UPD_ENSURE_SYNCED)
    async def ensure_synced(self) -> None:
        print("ensure_synced called")

    @workflow.run
    async def run(self) -> None:
        await asyncio.sleep(0.5)


async def test_debug_no_stub(temporal_client, dummy_vault_path):
    """Test without stub to see if workflow runs."""
    async with Worker(
        temporal_client,
        task_queue=QUEUE_DEFAULT,
        workflows=[ReadVaultWorkflow],
        activities=[get_skeleton, get_code_registry, read_note, list_notes_in],
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        try:
            result = await temporal_client.execute_workflow(
                ReadVaultWorkflow.run,
                ReadVaultInput(vault_path=str(dummy_vault_path), context_code="TEST-P01"),
                id="debug-test",
                task_queue=QUEUE_DEFAULT,
            )
            print(f"Result: {result}")
        except Exception as e:
            print(f"Workflow failed as expected: {e}")
            # Expect failure because vault-manager doesn't exist
            return
        assert False, "Workflow should have failed"


async def test_debug_with_stub(temporal_client, dummy_vault_path):
    """Test with stub."""
    async with Worker(
        temporal_client,
        task_queue=QUEUE_DEFAULT,
        workflows=[VaultManagerStub, ReadVaultWorkflow],
        activities=[get_skeleton, get_code_registry, read_note, list_notes_in],
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        await temporal_client.start_workflow(
            VaultManagerStub.run,
            id=VAULT_MANAGER_ID,
            task_queue=QUEUE_DEFAULT,
        )
        try:
            result = await temporal_client.execute_workflow(
                ReadVaultWorkflow.run,
                ReadVaultInput(vault_path=str(dummy_vault_path), context_code="TEST-P01"),
                id="debug-test-2",
                task_queue=QUEUE_DEFAULT,
            )
            print(f"Result: {result}")
        except Exception as e:
            print(f"Workflow failed: {e}")
            raise