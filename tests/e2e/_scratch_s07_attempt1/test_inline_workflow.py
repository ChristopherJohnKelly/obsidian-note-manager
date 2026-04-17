"""Test inline workflow."""

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
from packages.shared.models import VaultContext, VaultNote
from packages.shared.workflow_names import QUEUE_DEFAULT, UPD_ENSURE_SYNCED, VAULT_MANAGER_ID


@dataclass
class SimpleInput:
    vault_path: str
    context_code: str


@workflow.defn
class SimpleWorkflow:
    @workflow.run
    async def run(self, input: SimpleInput) -> VaultContext:
        workflow.logger.info("SimpleWorkflow running")
        raise RuntimeError("SimpleWorkflow error")


async def test_inline_workflow(temporal_client, dummy_vault_path):
    """Test that an inline workflow runs."""
    async with Worker(
        temporal_client,
        task_queue=QUEUE_DEFAULT,
        workflows=[SimpleWorkflow],
        activities=[get_skeleton, get_code_registry, read_note, list_notes_in],
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        try:
            result = await temporal_client.execute_workflow(
                SimpleWorkflow.run,
                SimpleInput(vault_path=str(dummy_vault_path), context_code="TEST-P01"),
                id="inline-test",
                task_queue=QUEUE_DEFAULT,
            )
            print(f"Result: {result}")
        except Exception as e:
            print(f"Workflow failed as expected: {e}")
            return
        assert False, "Workflow should have failed"