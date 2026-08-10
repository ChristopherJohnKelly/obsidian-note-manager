"""Unit tests for vault_worker.worker registration constants.

AC1 (S18/C1): worker.py must expose DEFAULT_WORKFLOWS, MUTATION_WORKFLOWS,
DEFAULT_ACTIVITIES, MUTATION_ACTIVITIES, MUTATION_MAX_CONCURRENT_WORKFLOW_TASKS,
MUTATION_MAX_CONCURRENT_ACTIVITIES as module-level constants used by create_workers().

No Worker construction — constants are inspected directly to avoid Temporal bridge
leaks (constructing Workers in unit tests caused cross-cycle bridge conflicts; see
S18 plan for full diagnosis).
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import pytest

import apps.vault_worker.activities
import apps.vault_worker.workflows
from apps.vault_worker.worker import (
    DEFAULT_ACTIVITIES,
    DEFAULT_WORKFLOWS,
    MUTATION_ACTIVITIES,
    MUTATION_MAX_CONCURRENT_ACTIVITIES,
    MUTATION_MAX_CONCURRENT_WORKFLOW_TASKS,
    MUTATION_WORKFLOWS,
    create_workers,
    start_vault_manager,
    vault_input_from_env,
)
from apps.vault_worker.workflows.vault_manager import (
    VaultManagerInput,
    VaultManagerWorkflow,
)
from apps.vault_worker.workflows.write_vault import WriteVaultWorkflow
from packages.shared.workflow_names import QUEUE_DEFAULT, QUEUE_MUTATION


pytestmark = pytest.mark.asyncio


async def test_create_workers_registers_default_and_mutation_queues():
    """TRD §4.5: constants enumerate all registered workflows and activities.

    No Worker construction — inspect module-level constants to avoid bridge leaks.
    S08 steering: all worker-registration assertions in this single test function.
    """
    # Spot-check known workflow membership
    assert VaultManagerWorkflow in DEFAULT_WORKFLOWS
    assert WriteVaultWorkflow in MUTATION_WORKFLOWS

    # Spot-check known activity membership
    default_activity_names = {
        a.__temporal_activity_definition.name for a in DEFAULT_ACTIVITIES
    }
    assert "check_vault_dir_state" in default_activity_names

    # Mutation-queue concurrency caps (TRD §4.5 / S08)
    assert MUTATION_MAX_CONCURRENT_WORKFLOW_TASKS == 1
    assert MUTATION_MAX_CONCURRENT_ACTIVITIES == 1

    # --- Exhaustive enumeration: every @workflow.defn must be registered ---
    all_registered_workflows = set(DEFAULT_WORKFLOWS) | set(MUTATION_WORKFLOWS)
    discovered_workflow_classes = set()
    for mod_info in pkgutil.iter_modules(apps.vault_worker.workflows.__path__):
        if mod_info.name.startswith("__"):
            continue
        mod = importlib.import_module(f"apps.vault_worker.workflows.{mod_info.name}")
        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if getattr(obj, "__temporal_workflow_definition", None):
                discovered_workflow_classes.add(obj)

    for cls in discovered_workflow_classes:
        assert cls in all_registered_workflows, (
            f"@workflow.defn class {cls.__name__} is defined under "
            f"apps.vault_worker.workflows but is missing from "
            f"DEFAULT_WORKFLOWS and MUTATION_WORKFLOWS"
        )

    # --- Exhaustive enumeration: every @activity.defn must be registered ---
    all_registered_activity_names = {
        a.__temporal_activity_definition.name
        for a in DEFAULT_ACTIVITIES + MUTATION_ACTIVITIES
    }
    discovered_activity_names = set()
    for mod_info in pkgutil.iter_modules(apps.vault_worker.activities.__path__):
        if mod_info.name.startswith("__"):
            continue
        mod = importlib.import_module(f"apps.vault_worker.activities.{mod_info.name}")
        for _name, obj in inspect.getmembers(mod):
            if callable(obj) and getattr(obj, "__temporal_activity_definition", None):
                discovered_activity_names.add(obj.__temporal_activity_definition.name)

    for act_name in discovered_activity_names:
        assert act_name in all_registered_activity_names, (
            f"@activity.defn '{act_name}' is defined under "
            f"apps.vault_worker.activities but is missing from "
            f"DEFAULT_ACTIVITIES and MUTATION_ACTIVITIES"
        )


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
    assert inspect.iscoroutinefunction(start_vault_manager)
    sig = inspect.signature(start_vault_manager)
    assert list(sig.parameters) == ["client", "vault_input"]
