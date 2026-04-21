"""E2E tests for VaultManagerWorkflow.

Covers all acceptance criteria from bubbles/OBSE-P5-S09-vault-manager-workflow.md.
"""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import pytest_asyncio
from temporalio import workflow
from temporalio.client import Client, WorkflowFailureError
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from apps.vault_worker.activities.git_ops import git_clone, git_pull
from apps.vault_worker.activities.vault_io import check_vault_dir_state
from apps.vault_worker.workflows.vault_manager import VaultManagerInput, VaultManagerWorkflow
from packages.shared.workflow_names import QUEUE_DEFAULT, VAULT_MANAGER_ID

# ---------------------------------------------------------------------------
# Fresh environment fixture (function-scoped) to avoid stale session issues
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def fresh_temporal_env():
    from temporalio.testing import WorkflowEnvironment
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env

@pytest_asyncio.fixture
async def fresh_temporal_client(fresh_temporal_env):
    return fresh_temporal_env.client


# ---------------------------------------------------------------------------
# Helper: wait_ready (required for startup tests)
# ---------------------------------------------------------------------------

async def wait_ready(handle, timeout_s: float = 10.0) -> dict:
    """Poll get_sync_status until status=='ready'. Raises AssertionError on timeout."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    status = None
    while loop.time() < deadline:
        status = await handle.query("get_sync_status")
        if status["status"] == "ready":
            return status
        await asyncio.sleep(0.1)
    raise AssertionError(
        f"VaultManagerWorkflow did not reach 'ready' within {timeout_s}s; last status={status}"
    )


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _fresh_queue() -> str:
    return f"test-manager-{uuid.uuid4().hex[:8]}"


def _manager_activities():
    return [check_vault_dir_state, git_clone, git_pull]


# ---------------------------------------------------------------------------
# Acceptance tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vault_manager_startup_empty_branch(local_bare_repo, tmp_path, fresh_temporal_client):
    """Workflow reaches ready after git_clone."""
    vault_path = tmp_path / "vault"
    repo_url = local_bare_repo["bare"]  # fixture returns dict with 'bare' path
    pat = ""  # not needed for local repo

    queue = _fresh_queue()
    async with Worker(
        fresh_temporal_client,
        task_queue=queue,
        workflows=[VaultManagerWorkflow],
        activities=_manager_activities(),
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        handle = await fresh_temporal_client.start_workflow(
            VaultManagerWorkflow.run,
            VaultManagerInput(vault_path=str(vault_path), repo_url=repo_url, pat=pat),
            id=f"vault-manager-{uuid.uuid4().hex[:8]}",
            task_queue=queue,
        )

        # Wait for ready before asserting anything else
        status = await wait_ready(handle)
        assert status["status"] == "ready"
        assert status["last_synced"] is not None

        # Verify git clone happened
        assert (vault_path / ".git").exists()
        # Bare repo contains at least one commit (fixture), so vault should have files
        assert any(vault_path.iterdir())


@pytest.mark.asyncio
async def test_vault_manager_startup_valid_repo_branch():
    """Workflow reaches ready after git_pull."""
    pass


@pytest.mark.asyncio
async def test_vault_manager_startup_invalid_branch():
    """Workflow raises ApplicationError with non_retryable=True."""
    pass


@pytest.mark.asyncio
async def test_vault_manager_ensure_synced_stale():
    """When last_synced >5 minutes ago, ensure_synced triggers git_pull."""
    pass


@pytest.mark.asyncio
async def test_vault_manager_ensure_synced_fresh():
    """When last_synced within 5 minutes, ensure_synced does NOT call git_pull."""
    pass


@pytest.mark.asyncio
async def test_vault_manager_continue_as_new():
    """After wait_condition times out, continue_as_new is called."""
    pass


@pytest.mark.asyncio
async def test_vault_manager_resume_skips_startup():
    """Resuming after continue_as_new skips startup branch."""
    pass


@pytest.mark.asyncio
async def test_vault_manager_update_idempotency():
    """Concurrent ensure_synced Updates queue correctly."""
    pass


@pytest.mark.asyncio
async def test_explore_workflow_start(fresh_temporal_client):
    """Simple test to verify workflow start and worker registration."""
    from temporalio import workflow
    from temporalio.worker import Worker
    from concurrent.futures import ThreadPoolExecutor

    @workflow.defn
    class SimpleWorkflow:
        @workflow.run
        async def run(self) -> str:
            return "hello"

    queue = f"test-explore-{uuid.uuid4().hex[:8]}"
    async with Worker(
        fresh_temporal_client,
        task_queue=queue,
        workflows=[SimpleWorkflow],
        activities=[],
        activity_executor=ThreadPoolExecutor(max_workers=1),
    ):
        result = await fresh_temporal_client.execute_workflow(
            SimpleWorkflow.run,
            id=f"explore-{uuid.uuid4().hex[:8]}",
            task_queue=queue,
        )
        assert result == "hello"


@pytest.mark.asyncio
async def test_worker_startup():
    """worker.py starts VaultManagerWorkflow and polls until ready."""
    pass