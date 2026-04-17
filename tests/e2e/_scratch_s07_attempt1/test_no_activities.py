"""Test workflow without activities."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from temporalio import workflow
from temporalio.worker import Worker

from packages.shared.models import VaultContext, VaultNote, Frontmatter
from pathlib import Path


@dataclass
class SimpleInput:
    vault_path: str
    context_code: str


@workflow.defn
class SimpleWorkflow:
    @workflow.run
    async def run(self, input: SimpleInput) -> VaultContext:
        workflow.logger.info("SimpleWorkflow running")
        # Return a dummy VaultContext with minimal data
        note = VaultNote(
            path=Path("dummy.md"),
            frontmatter=Frontmatter(),
            body=""
        )
        return VaultContext(
            context_code=input.context_code,
            root_note=note,
            related_notes=[note],
            skeleton="",
            code_registry="",
        )


async def test_no_activities(temporal_client, dummy_vault_path):
    """Workflow without activities."""
    async with Worker(
        temporal_client,
        task_queue="test-queue-no-act",
        workflows=[SimpleWorkflow],
        activities=[],  # no activities
    ):
        result = await temporal_client.execute_workflow(
            SimpleWorkflow.run,
            SimpleInput(vault_path=str(dummy_vault_path), context_code="TEST-P01"),
            id="no-act-test",
            task_queue="test-queue-no-act",
        )
        print(f"Result: {result}")
        assert result.context_code == "TEST-P01"