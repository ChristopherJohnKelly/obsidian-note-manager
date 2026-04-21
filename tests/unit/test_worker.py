"""Unit tests for vault_worker.worker.create_workers registration.

Validates that the two-queue Worker wiring matches the TRD §4.5 contract:
- vault-default: VaultManagerWorkflow + read-only activities + check_vault_dir_state (S09)
- vault-mutation-queue: WriteVaultWorkflow + write activities (S08),
  max_concurrent_workflow_tasks=1, max_concurrent_activities=1

Note: Temporal bridge forbids multiple Worker registrations on the same
task queue within one client. All assertions share a single
create_workers() call.
"""

from __future__ import annotations

import pytest

from apps.vault_worker.worker import (
    create_workers,
    start_vault_manager,
    vault_input_from_env,
)
from apps.vault_worker.workflows.vault_manager import (
    VaultManagerInput,
    VaultManagerWorkflow,
)
from packages.shared.workflow_names import QUEUE_DEFAULT, QUEUE_MUTATION


pytestmark = pytest.mark.asyncio


async def test_create_workers_registers_default_and_mutation_queues(temporal_client):
    """TRD §4.5: two-Worker wiring — default queue (VaultManager + reads, S09)
    + serialised mutation queue (S08)."""
    workers = create_workers(temporal_client)

    assert len(workers) == 2

    default_worker, mutation_worker = workers

    assert default_worker.task_queue == QUEUE_DEFAULT
    assert mutation_worker.task_queue == QUEUE_MUTATION

    mutation_config = mutation_worker.config()
    assert mutation_config["max_concurrent_workflow_tasks"] == 1
    assert mutation_config["max_concurrent_activities"] == 1

    # S09: default worker must host VaultManagerWorkflow and check_vault_dir_state
    default_config = default_worker.config()
    workflow_classes = {
        w if isinstance(w, type) else type(w) for w in default_config["workflows"]
    }
    assert VaultManagerWorkflow in workflow_classes

    activity_names = set()
    for a in default_config["activities"]:
        defn = getattr(a, "__temporal_activity_definition", None)
        activity_names.add(defn.name if defn is not None else a.__name__)
    assert "check_vault_dir_state" in activity_names


async def test_vault_input_from_env_reads_required_env_vars(monkeypatch):
    """vault_input_from_env pulls VAULT_PATH, REPO_URL, GITHUB_PAT from the environment."""
    monkeypatch.setenv("VAULT_PATH", "/vault")
    monkeypatch.setenv("REPO_URL", "https://example.test/repo.git")
    monkeypatch.setenv("GITHUB_PAT", "secret-pat")

    vault_input = vault_input_from_env()
    assert vault_input == VaultManagerInput(
        vault_path="/vault",
        repo_url="https://example.test/repo.git",
        pat="secret-pat",
    )


async def test_start_vault_manager_signature_exists():
    """start_vault_manager(client, vault_input) is callable and async."""
    import inspect

    assert inspect.iscoroutinefunction(start_vault_manager)
    sig = inspect.signature(start_vault_manager)
    assert list(sig.parameters) == ["client", "vault_input"]
