"""Test with unique queue."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import random

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
from packages.shared.workflow_names import UPD_ENSURE_SYNCED, VAULT_MANAGER_ID


@workflow.defn
class VaultManagerStub:
    @workflow.update(name=UPD_ENSURE_SYNCED)
    async def ensure_synced(self) -> None:
        print("ensure_synced called")

    @workflow.run
    async def run(self) -> None:
        await asyncio.sleep(0.5)


async def test_unique_queue(temporal_client, dummy_vault_path):
    """Use a unique queue to avoid collisions."""
    queue = f"test-queue-{random.randint(0, 10000)}"
    print(f"Using queue {queue}")
    async with Worker(
        temporal_client,
        task_queue=queue,
        workflows=[VaultManagerStub, ReadVaultWorkflow],
        activities=[get_skeleton, get_code_registry, read_note, list_notes_in],
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        await temporal_client.start_workflow(
            VaultManagerStub.run,
            id=VAULT_MANAGER_ID,
            task_queue=queue,
        )
        try:
            result = await temporal_client.execute_workflow(
                ReadVaultWorkflow.run,
                ReadVaultInput(vault_path=str(dummy_vault_path), context_code="TEST-P01"),
                id="unique-test",
                task_queue=queue,
            )
            print(f"Result: {result}")
        except Exception as e:
            print(f"Workflow failed: {e}")
            raise