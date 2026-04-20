"""Unit tests for vault_worker.worker.create_workers registration (OBSE-P5-S08).

Validates that the two-queue Worker wiring matches the TRD §4.5 contract:
- vault-default: read-only activities, no workflows, default concurrency
- vault-mutation-queue: WriteVaultWorkflow + write activities,
  max_concurrent_workflow_tasks=1, max_concurrent_activities=1

Note: Temporal bridge forbids multiple Worker registrations on the same
task queue within one client. All assertions share a single
create_workers() call.
"""

from __future__ import annotations

import pytest

from apps.vault_worker.worker import create_workers
from packages.shared.workflow_names import QUEUE_DEFAULT, QUEUE_MUTATION


pytestmark = pytest.mark.asyncio


async def test_create_workers_registers_default_and_mutation_queues(temporal_client):
    """TRD §4.5: two-Worker wiring — default read queue + serialised mutation queue."""
    workers = create_workers(temporal_client)

    assert len(workers) == 2

    default_worker, mutation_worker = workers

    assert default_worker.task_queue == QUEUE_DEFAULT
    assert mutation_worker.task_queue == QUEUE_MUTATION

    mutation_config = mutation_worker.config()
    assert mutation_config["max_concurrent_workflow_tasks"] == 1
    assert mutation_config["max_concurrent_activities"] == 1
