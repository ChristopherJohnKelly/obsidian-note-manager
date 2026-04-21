"""E2E tests for VaultManagerWorkflow.

Covers all acceptance criteria from bubbles/OBSE-P5-S09-vault-manager-workflow.md.

Key constraint (see FAILURE-S09.md): ``client.start_workflow`` returns as soon
as Temporal accepts the workflow — NOT when the workflow reaches ``ready``.
Every startup-branch test therefore routes through ``wait_ready`` before
making any state assertions.
"""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from temporalio import activity
from temporalio.client import WorkflowExecutionStatus, WorkflowFailureError
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from apps.vault_worker.workflows.vault_manager import (
    VaultManagerInput,
    VaultManagerWorkflow,
)
from packages.shared.workflow_names import UPD_ENSURE_SYNCED


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def isolated_temporal_env():
    """A function-scoped time-skipping Temporal env.

    The session-scoped env accumulates history across 200+ tests; by the time
    it is used for virtual-time sleeps longer than a few minutes, the bridge's
    30s RPC timeout on ``unlock_time_skipping_with_sleep`` fires. Tests that
    depend on ``env.sleep`` (stale threshold, continue_as_new) get a fresh
    env so time-skipping is not slowed by accumulated state.
    """
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


@pytest_asyncio.fixture
async def isolated_temporal_client(isolated_temporal_env):
    return isolated_temporal_env.client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def wait_ready(handle, timeout_s: float = 10.0) -> dict:
    """Poll ``get_sync_status`` until status=='ready'.

    ``client.start_workflow`` does not wait for activities to run — asserting
    ``status == 'ready'`` immediately after it returns is the test-writing bug
    that caused five prior rejections on S09. Every test that needs post-startup
    state MUST route through this helper first.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    status = None
    while loop.time() < deadline:
        status = await handle.query("get_sync_status")
        if status["status"] == "ready":
            return status
        await asyncio.sleep(0.1)
    raise AssertionError(
        f"VaultManagerWorkflow did not reach 'ready' within {timeout_s}s; "
        f"last status={status}"
    )


def _fresh_queue() -> str:
    return f"test-vm-{uuid.uuid4().hex[:8]}"


def _fresh_id() -> str:
    return f"vault-manager-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Mock activities — counts calls so tests can verify dispatch behaviour
# ---------------------------------------------------------------------------


class _Counters:
    """Per-test counters shared with mock activities via closure."""

    def __init__(self) -> None:
        self.clone_calls: list[tuple[str, str, str]] = []
        self.pull_calls: list[str] = []
        self.check_calls: list[str] = []
        self.check_returns: str = "empty"


def _make_mock_activities(counters: _Counters, *, make_dot_git_on_clone: bool = True):
    """Return mock activities registered under the real names the workflow dispatches."""

    @activity.defn(name="check_vault_dir_state")
    def mock_check(vault_path: str) -> str:
        counters.check_calls.append(vault_path)
        return counters.check_returns

    @activity.defn(name="git_clone")
    def mock_clone(repo_url: str, target_path: str, pat: str) -> None:
        counters.clone_calls.append((repo_url, target_path, pat))
        if make_dot_git_on_clone:
            from pathlib import Path

            p = Path(target_path)
            p.mkdir(parents=True, exist_ok=True)
            (p / ".git").mkdir(exist_ok=True)

    @activity.defn(name="git_pull")
    def mock_pull(vault_path: str) -> None:
        counters.pull_calls.append(vault_path)

    return [mock_check, mock_clone, mock_pull]


# ---------------------------------------------------------------------------
# Acceptance tests
# ---------------------------------------------------------------------------


async def test_vault_manager_startup_empty_branch(temporal_client, tmp_path):
    """State 'empty' → git_clone runs → status becomes 'ready'."""
    counters = _Counters()
    counters.check_returns = "empty"
    queue = _fresh_queue()
    vault_path = tmp_path / "vault"

    async with Worker(
        temporal_client,
        task_queue=queue,
        workflows=[VaultManagerWorkflow],
        activities=_make_mock_activities(counters),
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        handle = await temporal_client.start_workflow(
            VaultManagerWorkflow.run,
            VaultManagerInput(
                vault_path=str(vault_path),
                repo_url="https://example.test/repo.git",
                pat="fake-pat",
            ),
            id=_fresh_id(),
            task_queue=queue,
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
        )
        try:
            status = await wait_ready(handle)
        finally:
            try:
                await handle.terminate()
            except Exception:
                pass

    assert status["status"] == "ready"
    assert status["last_synced"] is not None
    assert len(counters.clone_calls) == 1
    assert counters.clone_calls[0][1] == str(vault_path)
    assert not counters.pull_calls


async def test_vault_manager_startup_valid_repo_branch(temporal_client, tmp_path):
    """State 'valid_repo' → git_pull runs → status becomes 'ready'."""
    counters = _Counters()
    counters.check_returns = "valid_repo"
    queue = _fresh_queue()

    async with Worker(
        temporal_client,
        task_queue=queue,
        workflows=[VaultManagerWorkflow],
        activities=_make_mock_activities(counters),
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        handle = await temporal_client.start_workflow(
            VaultManagerWorkflow.run,
            VaultManagerInput(
                vault_path=str(tmp_path / "vault"),
                repo_url="https://example.test/repo.git",
                pat="fake-pat",
            ),
            id=_fresh_id(),
            task_queue=queue,
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
        )
        try:
            status = await wait_ready(handle)
        finally:
            try:
                await handle.terminate()
            except Exception:
                pass

    assert status["status"] == "ready"
    assert status["last_synced"] is not None
    assert not counters.clone_calls
    assert len(counters.pull_calls) == 1


async def test_vault_manager_startup_invalid_branch(temporal_client, tmp_path):
    """State 'invalid' → workflow fails with non-retryable ApplicationError."""
    counters = _Counters()
    counters.check_returns = "invalid"
    queue = _fresh_queue()

    with pytest.raises(WorkflowFailureError) as exc_info:
        async with Worker(
            temporal_client,
            task_queue=queue,
            workflows=[VaultManagerWorkflow],
            activities=_make_mock_activities(counters),
            activity_executor=ThreadPoolExecutor(max_workers=4),
        ):
            await temporal_client.execute_workflow(
                VaultManagerWorkflow.run,
                VaultManagerInput(
                    vault_path=str(tmp_path / "vault"),
                    repo_url="https://example.test/repo.git",
                    pat="fake-pat",
                ),
                id=_fresh_id(),
                task_queue=queue,
                id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
            )

    cause = exc_info.value.cause
    assert isinstance(cause, ApplicationError)
    assert cause.non_retryable
    assert "VAULT_PATH" in str(cause)
    assert not counters.clone_calls
    assert not counters.pull_calls


async def test_vault_manager_ensure_synced_fresh(temporal_client, tmp_path):
    """When last_synced is within 5 min, ensure_synced does NOT call git_pull."""
    counters = _Counters()
    counters.check_returns = "valid_repo"
    queue = _fresh_queue()

    async with Worker(
        temporal_client,
        task_queue=queue,
        workflows=[VaultManagerWorkflow],
        activities=_make_mock_activities(counters),
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        handle = await temporal_client.start_workflow(
            VaultManagerWorkflow.run,
            VaultManagerInput(
                vault_path=str(tmp_path / "vault"),
                repo_url="https://example.test/repo.git",
                pat="fake-pat",
            ),
            id=_fresh_id(),
            task_queue=queue,
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
        )
        try:
            await wait_ready(handle)
            startup_pulls = len(counters.pull_calls)
            await handle.execute_update(UPD_ENSURE_SYNCED)
        finally:
            try:
                await handle.terminate()
            except Exception:
                pass

    # Startup already pulled; the Update saw a fresh last_synced and did not re-pull.
    assert len(counters.pull_calls) == startup_pulls == 1


async def test_vault_manager_ensure_synced_stale(
    isolated_temporal_client, isolated_temporal_env, tmp_path
):
    """When last_synced > 5 min ago, ensure_synced calls git_pull."""
    counters = _Counters()
    counters.check_returns = "valid_repo"
    queue = _fresh_queue()

    async with Worker(
        isolated_temporal_client,
        task_queue=queue,
        workflows=[VaultManagerWorkflow],
        activities=_make_mock_activities(counters),
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        handle = await isolated_temporal_client.start_workflow(
            VaultManagerWorkflow.run,
            VaultManagerInput(
                vault_path=str(tmp_path / "vault"),
                repo_url="https://example.test/repo.git",
                pat="fake-pat",
            ),
            id=_fresh_id(),
            task_queue=queue,
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
        )
        try:
            first = await wait_ready(handle)
            first_iso = first["last_synced"]
            assert len(counters.pull_calls) == 1
            # Advance virtual time past the 5-minute staleness threshold.
            await isolated_temporal_env.sleep(timedelta(minutes=6))
            await handle.execute_update(UPD_ENSURE_SYNCED)
            status_after = await handle.query("get_sync_status")
        finally:
            try:
                await handle.terminate()
            except Exception:
                pass

    assert len(counters.pull_calls) == 2
    assert status_after["last_synced"] != first_iso
    t_first = datetime.fromisoformat(first_iso)
    t_after = datetime.fromisoformat(status_after["last_synced"])
    assert t_after > t_first


async def test_get_sync_status_returns_iso_last_synced(temporal_client, tmp_path):
    """get_sync_status returns UTC-aware ISO string (no naive datetime)."""
    counters = _Counters()
    counters.check_returns = "valid_repo"
    queue = _fresh_queue()

    async with Worker(
        temporal_client,
        task_queue=queue,
        workflows=[VaultManagerWorkflow],
        activities=_make_mock_activities(counters),
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        handle = await temporal_client.start_workflow(
            VaultManagerWorkflow.run,
            VaultManagerInput(
                vault_path=str(tmp_path / "vault"),
                repo_url="https://example.test/repo.git",
                pat="fake-pat",
            ),
            id=_fresh_id(),
            task_queue=queue,
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
        )
        try:
            status = await wait_ready(handle)
        finally:
            try:
                await handle.terminate()
            except Exception:
                pass

    parsed = datetime.fromisoformat(status["last_synced"])
    assert parsed.tzinfo is not None


async def test_vault_manager_resume_skips_startup(temporal_client, tmp_path):
    """A workflow resumed with non-None last_synced skips clone/pull."""
    counters = _Counters()
    counters.check_returns = "invalid"  # would fail startup if branch ran
    queue = _fresh_queue()
    preserved_iso = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc).isoformat()

    async with Worker(
        temporal_client,
        task_queue=queue,
        workflows=[VaultManagerWorkflow],
        activities=_make_mock_activities(counters),
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        handle = await temporal_client.start_workflow(
            VaultManagerWorkflow.run,
            VaultManagerInput(
                vault_path=str(tmp_path / "vault"),
                repo_url="https://example.test/repo.git",
                pat="fake-pat",
                last_synced=preserved_iso,
            ),
            id=_fresh_id(),
            task_queue=queue,
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
        )
        try:
            status = await wait_ready(handle)
        finally:
            try:
                await handle.terminate()
            except Exception:
                pass

    assert status["status"] == "ready"
    assert status["last_synced"] == preserved_iso
    assert not counters.check_calls
    assert not counters.clone_calls
    assert not counters.pull_calls


async def test_vault_manager_continue_as_new(
    isolated_temporal_client, isolated_temporal_env, tmp_path
):
    """After wait_condition times out, workflow continues-as-new with last_synced preserved."""
    counters = _Counters()
    counters.check_returns = "valid_repo"
    queue = _fresh_queue()
    wf_id = _fresh_id()

    async with Worker(
        isolated_temporal_client,
        task_queue=queue,
        workflows=[VaultManagerWorkflow],
        activities=_make_mock_activities(counters),
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        handle = await isolated_temporal_client.start_workflow(
            VaultManagerWorkflow.run,
            VaultManagerInput(
                vault_path=str(tmp_path / "vault"),
                repo_url="https://example.test/repo.git",
                pat="fake-pat",
            ),
            id=wf_id,
            task_queue=queue,
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
        )
        try:
            first = await wait_ready(handle)
            first_iso = first["last_synced"]
            initial_run_id = handle.first_execution_run_id
            # Advance virtual time past the 1-day continue_as_new timeout.
            await isolated_temporal_env.sleep(timedelta(days=1, minutes=1))
            # The original run should reach CONTINUED_AS_NEW status; poll for it.
            original = isolated_temporal_client.get_workflow_handle(
                wf_id, run_id=initial_run_id
            )
            deadline = asyncio.get_event_loop().time() + 15.0
            orig_status = None
            while asyncio.get_event_loop().time() < deadline:
                desc = await original.describe()
                orig_status = desc.status
                if orig_status == WorkflowExecutionStatus.CONTINUED_AS_NEW:
                    break
                await asyncio.sleep(0.2)
            assert orig_status == WorkflowExecutionStatus.CONTINUED_AS_NEW, (
                f"original run did not continue_as_new (status={orig_status})"
            )
            # The resumed run (fresh handle without run_id pins to latest) should
            # carry last_synced across without re-running startup activities.
            current = isolated_temporal_client.get_workflow_handle(wf_id)
            resumed = await wait_ready(current)
            assert resumed["last_synced"] == first_iso
        finally:
            try:
                await isolated_temporal_client.get_workflow_handle(wf_id).terminate()
            except Exception:
                pass

    # Only one startup cycle's worth of clone/pull — the resumed run skipped startup.
    assert len(counters.pull_calls) == 1
    assert not counters.clone_calls


async def test_vault_manager_update_idempotency(
    isolated_temporal_client, isolated_temporal_env, tmp_path
):
    """Concurrent ensure_synced Updates serialise: only the first sees 'stale'."""
    counters = _Counters()
    counters.check_returns = "valid_repo"
    queue = _fresh_queue()

    async with Worker(
        isolated_temporal_client,
        task_queue=queue,
        workflows=[VaultManagerWorkflow],
        activities=_make_mock_activities(counters),
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        handle = await isolated_temporal_client.start_workflow(
            VaultManagerWorkflow.run,
            VaultManagerInput(
                vault_path=str(tmp_path / "vault"),
                repo_url="https://example.test/repo.git",
                pat="fake-pat",
            ),
            id=_fresh_id(),
            task_queue=queue,
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
        )
        try:
            await wait_ready(handle)
            assert len(counters.pull_calls) == 1  # startup pull
            # Advance past staleness so the first concurrent Update pulls.
            await isolated_temporal_env.sleep(timedelta(minutes=6))
            await asyncio.gather(*[
                handle.execute_update(UPD_ENSURE_SYNCED) for _ in range(5)
            ])
        finally:
            try:
                await handle.terminate()
            except Exception:
                pass

    # Expect exactly 2 pulls: one from startup + one from the first concurrent
    # Update that observed staleness. The other four saw a fresh timestamp.
    assert len(counters.pull_calls) == 2
