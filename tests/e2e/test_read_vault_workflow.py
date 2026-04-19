"""E2E tests for ReadVaultWorkflow.

Covers all acceptance criteria from bubbles/OBSE-P5-S07-read-vault-workflow.md
against the signal-with-reply contract (SIG_ENSURE_SYNCED request,
SIG_SYNC_ACK reply).
"""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
import pytest_asyncio
from temporalio import workflow
from temporalio.client import Client, WorkflowFailureError
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from apps.vault_worker.activities.vault_io import (
    get_code_registry,
    get_skeleton,
    list_notes_in,
    read_note,
)
from apps.vault_worker.workflows.read_vault import ReadVaultInput, ReadVaultWorkflow
from packages.shared.workflow_names import (
    QUEUE_DEFAULT,
    SIG_ENSURE_SYNCED,
    SIG_SYNC_ACK,
    VAULT_MANAGER_ID,
)


# ---------------------------------------------------------------------------
# Inline stub — minimal stand-in for VaultManagerWorkflow (full impl in S09)
# ---------------------------------------------------------------------------


@workflow.defn
class VaultManagerStub:
    """Ack's SIG_ENSURE_SYNCED by signalling SIG_SYNC_ACK back to the requester."""

    def __init__(self) -> None:
        self._call_count: int = 0

    @workflow.signal(name=SIG_ENSURE_SYNCED)
    async def on_ensure_synced(self, requester_id: str) -> None:
        self._call_count += 1
        requester = workflow.get_external_workflow_handle(requester_id)
        await requester.signal(SIG_SYNC_ACK)

    @workflow.query
    def call_count(self) -> int:
        return self._call_count

    @workflow.run
    async def run(self) -> None:
        await asyncio.sleep(3600)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def pydantic_client(temporal_client: Client) -> Client:
    """Client with pydantic_data_converter — VaultNote.path is pathlib.Path
    which the default converter cannot round-trip."""
    return Client(
        service_client=temporal_client.service_client,
        namespace=temporal_client.namespace,
        data_converter=pydantic_data_converter,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_queue() -> str:
    return f"test-read-{uuid.uuid4().hex[:8]}"


def _read_activities():
    return [get_skeleton, get_code_registry, read_note, list_notes_in]


# ---------------------------------------------------------------------------
# Acceptance tests
# ---------------------------------------------------------------------------


async def test_dispatches_and_waits_for_ack(pydantic_client, dummy_vault_path):
    """ReadVaultWorkflow signals vault-manager and blocks until ack arrives."""
    queue = _fresh_queue()
    async with Worker(
        pydantic_client,
        task_queue=queue,
        workflows=[VaultManagerStub, ReadVaultWorkflow],
        activities=_read_activities(),
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        stub_handle = await pydantic_client.start_workflow(
            VaultManagerStub.run,
            id=VAULT_MANAGER_ID,
            task_queue=queue,
        )
        try:
            result = await pydantic_client.execute_workflow(
                ReadVaultWorkflow.run,
                ReadVaultInput(
                    vault_path=str(dummy_vault_path),
                    context_code="TEST-P01",
                ),
                id=f"read-dispatch-{uuid.uuid4().hex[:4]}",
                task_queue=queue,
            )
            call_count = await stub_handle.query(VaultManagerStub.call_count)
        finally:
            await stub_handle.cancel()

    assert call_count == 1
    assert result.skeleton


async def test_workflow_fails_if_ack_never_arrives(
    pydantic_client, dummy_vault_path, monkeypatch
):
    """Without a running vault-manager, the workflow must fail — not hang,
    and not silently proceed with reads against an unsynchronised vault."""
    monkeypatch.setattr(ReadVaultWorkflow, "_SYNC_TIMEOUT", timedelta(seconds=3))

    queue = _fresh_queue()
    async with Worker(
        pydantic_client,
        task_queue=queue,
        workflows=[VaultManagerStub, ReadVaultWorkflow],
        activities=_read_activities(),
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        # Intentionally do NOT start VaultManagerStub — no one will ack.
        with pytest.raises(WorkflowFailureError):
            await pydantic_client.execute_workflow(
                ReadVaultWorkflow.run,
                ReadVaultInput(
                    vault_path=str(dummy_vault_path),
                    context_code="TEST-P01",
                ),
                id=f"read-timeout-{uuid.uuid4().hex[:4]}",
                task_queue=queue,
            )


async def test_returns_non_empty_code_registry(pydantic_client, dummy_vault_path):
    queue = _fresh_queue()
    async with Worker(
        pydantic_client,
        task_queue=queue,
        workflows=[VaultManagerStub, ReadVaultWorkflow],
        activities=_read_activities(),
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        stub_handle = await pydantic_client.start_workflow(
            VaultManagerStub.run,
            id=VAULT_MANAGER_ID,
            task_queue=queue,
        )
        try:
            result = await pydantic_client.execute_workflow(
                ReadVaultWorkflow.run,
                ReadVaultInput(
                    vault_path=str(dummy_vault_path),
                    context_code="TEST-P01",
                ),
                id=f"read-registry-{uuid.uuid4().hex[:4]}",
                task_queue=queue,
            )
        finally:
            await stub_handle.cancel()

    assert result.code_registry
    assert isinstance(result.code_registry, str)


async def test_related_notes_filtered_by_context_code_folder(
    pydantic_client, dummy_vault_path
):
    """related_notes contains only notes whose path starts with the TEST-P01 folder."""
    queue = _fresh_queue()
    async with Worker(
        pydantic_client,
        task_queue=queue,
        workflows=[VaultManagerStub, ReadVaultWorkflow],
        activities=_read_activities(),
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        stub_handle = await pydantic_client.start_workflow(
            VaultManagerStub.run,
            id=VAULT_MANAGER_ID,
            task_queue=queue,
        )
        try:
            result = await pydantic_client.execute_workflow(
                ReadVaultWorkflow.run,
                ReadVaultInput(
                    vault_path=str(dummy_vault_path),
                    context_code="TEST-P01",
                ),
                id=f"read-filter-{uuid.uuid4().hex[:4]}",
                task_queue=queue,
            )
        finally:
            await stub_handle.cancel()

    prefix = "20. Projects/TEST-P01/"
    assert result.related_notes, "expected at least one related note"
    for note in result.related_notes:
        assert str(note.path).startswith(prefix), (
            f"note {note.path!r} not under {prefix!r}"
        )


async def test_multiple_concurrent_reads_each_get_their_own_ack(
    pydantic_client, dummy_vault_path
):
    """5 concurrent ReadVaultWorkflow runs must each succeed and trigger
    exactly one ensure_synced handler call (call_count == 5), proving the
    reply-address routing works per caller."""
    async with Worker(
        pydantic_client,
        task_queue=QUEUE_DEFAULT,
        workflows=[VaultManagerStub, ReadVaultWorkflow],
        activities=_read_activities(),
        activity_executor=ThreadPoolExecutor(max_workers=8),
    ):
        stub_handle = await pydantic_client.start_workflow(
            VaultManagerStub.run,
            id=VAULT_MANAGER_ID,
            task_queue=QUEUE_DEFAULT,
        )
        try:
            results = await asyncio.gather(*[
                pydantic_client.execute_workflow(
                    ReadVaultWorkflow.run,
                    ReadVaultInput(
                        vault_path=str(dummy_vault_path),
                        context_code="TEST-P01",
                    ),
                    id=f"read-parallel-{i}-{uuid.uuid4().hex[:4]}",
                    task_queue=QUEUE_DEFAULT,
                )
                for i in range(5)
            ])
            call_count = await stub_handle.query(VaultManagerStub.call_count)
        finally:
            await stub_handle.cancel()

    assert len(results) == 5
    assert all(r.skeleton for r in results)
    assert all(r.code_registry for r in results)
    assert call_count == 5
