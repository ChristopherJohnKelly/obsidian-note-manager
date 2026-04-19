"""E2E tests for ReadVaultWorkflow.

Covers all acceptance criteria from bubbles/OBSE-P5-S07-read-vault-workflow.md.
``ReadVaultWorkflow`` dispatches the TRD-specified ``ensure_synced`` Update to
``VaultManagerWorkflow`` via the ``ensure_vault_synced`` activity (activity
shim is required because ``ExternalWorkflowHandle`` has no ``execute_update``
on the Python SDK). Tests register a ``VaultManagerStub`` with a real
``@workflow.update`` handler — no signal or dual registrations.
"""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import pytest_asyncio
from temporalio import workflow
from temporalio.client import Client, WorkflowFailureError
from temporalio.common import WorkflowIDReusePolicy
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.exceptions import ApplicationError
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
from apps.vault_worker.workflows.read_vault import ReadVaultInput, ReadVaultWorkflow
from packages.shared.workflow_names import (
    QUEUE_DEFAULT,
    UPD_ENSURE_SYNCED,
    VAULT_MANAGER_ID,
)


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


@workflow.defn
class FailingVaultManagerStub:
    """VaultManager whose ensure_synced Update handler raises — simulates a
    failed pull or stale-check error, which must propagate to the caller."""

    @workflow.update(name=UPD_ENSURE_SYNCED)
    async def on_ensure_synced(self) -> None:
        raise ApplicationError("simulated pull failure", non_retryable=True)

    @workflow.run
    async def run(self) -> None:
        await asyncio.sleep(3600)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def pydantic_client(temporal_client: Client) -> Client:
    """Client with pydantic_data_converter — VaultNote.path is pathlib.Path
    which the default converter cannot round-trip. Also injects the client
    into the ensure_vault_synced activity."""
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
# Helpers
# ---------------------------------------------------------------------------


def _fresh_queue() -> str:
    return f"test-read-{uuid.uuid4().hex[:8]}"


def _read_activities():
    return [get_skeleton, get_code_registry, read_note, list_notes_in, ensure_vault_synced]


# ---------------------------------------------------------------------------
# Acceptance tests
# ---------------------------------------------------------------------------


async def test_dispatches_update_and_waits_for_completion(
    pydantic_client, dummy_vault_path
):
    """ReadVaultWorkflow executes the ensure_synced Update and blocks until
    the VaultManager handler returns. Proves Update dispatch + completion."""
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
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
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


async def test_workflow_fails_when_ensure_synced_update_raises(
    pydantic_client, dummy_vault_path
):
    """If the VaultManager ensure_synced handler fails (e.g. pull error),
    the ReadVaultWorkflow must fail — not silently proceed with reads
    against an unsynchronised vault."""
    queue = _fresh_queue()
    async with Worker(
        pydantic_client,
        task_queue=queue,
        workflows=[FailingVaultManagerStub, ReadVaultWorkflow],
        activities=_read_activities(),
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        stub_handle = await pydantic_client.start_workflow(
            FailingVaultManagerStub.run,
            id=VAULT_MANAGER_ID,
            task_queue=queue,
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
        )
        try:
            with pytest.raises(WorkflowFailureError):
                await pydantic_client.execute_workflow(
                    ReadVaultWorkflow.run,
                    ReadVaultInput(
                        vault_path=str(dummy_vault_path),
                        context_code="TEST-P01",
                    ),
                    id=f"read-fail-{uuid.uuid4().hex[:4]}",
                    task_queue=queue,
                )
        finally:
            await stub_handle.cancel()


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
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
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
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
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


async def test_multiple_concurrent_reads_each_dispatch_update(
    pydantic_client, dummy_vault_path
):
    """5 concurrent ReadVaultWorkflow runs must each succeed and each invoke
    the VaultManager Update handler exactly once (call_count == 5)."""
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
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
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
