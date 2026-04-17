"""Test workflow returning string."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from temporalio import workflow
from temporalio.worker import Worker


@dataclass
class SimpleInput:
    vault_path: str
    context_code: str


@workflow.defn
class SimpleWorkflow:
    @workflow.run
    async def run(self, input: SimpleInput) -> str:
        workflow.logger.info("SimpleWorkflow running")
        return f"ok {input.context_code}"


async def test_string_return(temporal_client, dummy_vault_path):
    """Workflow returning string."""
    async with Worker(
        temporal_client,
        task_queue="test-queue-string",
        workflows=[SimpleWorkflow],
        activities=[],
    ):
        result = await temporal_client.execute_workflow(
            SimpleWorkflow.run,
            SimpleInput(vault_path=str(dummy_vault_path), context_code="TEST-P01"),
            id="string-test",
            task_queue="test-queue-string",
        )
        print(f"Result: {result}")
        assert result == "ok TEST-P01"