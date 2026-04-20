---
type: bubble
status: pending
step_id: S09
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python/DevOps Engineer implementing a long-running vault coordinator workflow.
**Objective:** Implement `VaultManagerWorkflow` — the workflow that starts on `vault-worker` startup, validates and initialises the vault, then runs indefinitely as the sole coordinator for vault sync state. It accepts `ensure_synced` Updates from `ReadVaultWorkflow` and decides whether a `git_pull` is needed based on the `last_synced` timestamp it owns.
**Constraints:**
- Python 3.12
- Workflow code is 100% deterministic — **no file I/O, no `Path` operations, no `os` calls inside `@workflow.run` or Update/Query handlers.** All filesystem inspection must go through Activities. Violating this causes a non-determinism error in Temporal's replay sandbox.
- Three startup branches: clone (empty dir), pull (existing repo), or fatal error (anything else) — determined via a new `check_vault_dir_state` Activity, not inline file I/O
- The workflow runs indefinitely after init; use `workflow.continue_as_new()` daily (or after 1,000 Updates) to prevent history bloat
- The `ensure_synced` Update must use only `workflow.now()` for time comparisons (never `datetime.now()` — that is non-deterministic)

---

## 1. Context

**Feature:** TRD Section 7.3 (VaultManagerWorkflow — Startup + Long-Running Coordinator), Section 4 (Parent Workflows), Section 4.6 (Workflow Interface Specifications)
**Depends On:** S04 (Vault I/O Activities — `vault_io.py` will receive `check_vault_dir_state`), S05 (Git Operations Activities)
**Current State:** All Activities implemented. No startup/coordinator workflow yet.
**Target State:** `VaultManagerWorkflow` implemented with tests covering all three startup branches, the `ensure_synced` Update (both stale and fresh paths), and the `continue_as_new` transition. `vault-worker` startup script runs this workflow and waits for it to reach `ready` status before accepting other work.

---

## 2. Input

- `apps/vault_worker/activities/vault_io.py` — add `check_vault_dir_state` here
- `apps/vault_worker/activities/git_ops.py` — `git_clone`, `git_pull`
- `packages/shared/workflow_names.py` — `VAULT_MANAGER_WORKFLOW`, `VAULT_MANAGER_ID`, `UPD_ENSURE_SYNCED`, `QRY_GET_SYNC_STATUS`
- `tests/conftest.py` — `local_bare_repo` fixture (from S05)

---

## 3. Required Output

- [ ] `apps/vault_worker/activities/vault_io.py` — add `check_vault_dir_state` Activity
- [ ] `apps/vault_worker/workflows/vault_manager.py` — `VaultManagerWorkflow`
- [ ] `tests/unit/test_check_vault_dir_state.py` — unit tests for the new Activity
- [ ] `tests/e2e/test_vault_manager_workflow.py`
- [ ] Update `apps/vault_worker/worker.py` — startup script starts `VaultManagerWorkflow` and waits for `status=ready` before accepting other work

**Workflow interface:**

```python
@dataclass
class VaultManagerInput:
    vault_path: str        # from VAULT_PATH env var
    repo_url: str          # from REPO_URL env var
    pat: str               # from GITHUB_PAT env var
    last_synced: str | None = None  # ISO UTC string; None = first run, set on continue_as_new

@workflow.defn
class VaultManagerWorkflow:
    @workflow.update
    async def ensure_synced(self) -> None: ...  # called by ReadVaultWorkflow

    @workflow.query
    def get_sync_status(self) -> dict: ...  # {"status": str, "last_synced": str | None}

    @workflow.run
    async def run(self, input: VaultManagerInput) -> None: ...  # runs indefinitely
```

---

## 4. Acceptance Criteria

**`check_vault_dir_state` Activity:**
- [ ] Returns `"empty"` when `vault_path` does not exist or is an empty directory
- [ ] Returns `"valid_repo"` when `vault_path` contains a `.git` directory
- [ ] Returns `"invalid"` when `vault_path` is non-empty and has no `.git` directory

**Startup phase:**
- [ ] When state is `"empty"`, `git_clone` Activity is called; workflow reaches `ready` status
- [ ] When state is `"valid_repo"`, `git_pull` Activity is called; workflow reaches `ready` status
- [ ] When state is `"invalid"`, `ApplicationError` is raised with `non_retryable=True` and a clear human-readable message
- [ ] `get_sync_status` query returns `{"status": "ready", "last_synced": <iso string>}` after successful init

**`ensure_synced` Update:**
- [ ] When `last_synced` is more than 5 minutes ago, `git_pull` Activity is called and `last_synced` is updated to `workflow.now()`
- [ ] When `last_synced` is within 5 minutes, `git_pull` is NOT called
- [ ] The `last_synced` value used in the comparison is always UTC-aware — no `TypeError` from naive/aware datetime subtraction (see Reference Material)
- [ ] Concurrent `ensure_synced` Updates queue correctly — Temporal serialises Update handlers within a workflow

**`continue_as_new`:**
- [ ] After `workflow.wait_condition` times out (simulated in tests via time-skipping environment), `continue_as_new` is called with `last_synced` preserved in `VaultManagerInput`
- [ ] A resumed workflow (non-None `last_synced` in input) skips the startup branch and goes directly to `ready`

**Worker startup:**
- [ ] `worker.py` starts `VaultManagerWorkflow` with well-known ID `vault-manager` and polls `get_sync_status` until `status=ready` before registering the main worker

---

## 5. Scope Boundary

**May modify:** `apps/vault_worker/activities/vault_io.py` (add `check_vault_dir_state` only), `apps/vault_worker/workflows/vault_manager.py`, `tests/unit/test_check_vault_dir_state.py`, `tests/e2e/test_vault_manager_workflow.py`, `apps/vault_worker/worker.py`
**Must not modify:** `packages/shared/`, `apps/vault_worker/activities/git_ops.py`, other Activity files, `tests/fixtures/`, `tests/conftest.py`

---

## 6. TDD Constraints

- Write `test_check_vault_dir_state.py` and all `test_vault_manager_workflow.py` stubs before implementing anything
- The fatal error test and the `ensure_synced` stale/fresh tests are the most important — write these first
- Use time-skipping `WorkflowEnvironment` for the `continue_as_new` test (skip forward 24+ hours)
- Use the `local_bare_repo` fixture for clone/pull startup tests; use `tmp_path` with a non-repo directory for the fatal error test

---

## 7. Step-by-Step Plan

1. Add `check_vault_dir_state(vault_path: str) -> str` to `vault_io.py` as a synchronous `def` Activity. Write and pass `test_check_vault_dir_state.py`. Commit.
2. Write all `test_vault_manager_workflow.py` stubs (startup branches, ensure_synced stale/fresh, continue_as_new, idempotency). Run — fail.
3. Implement `VaultManagerWorkflow` startup phase: call `check_vault_dir_state` Activity → branch to `git_clone`, `git_pull`, or `ApplicationError`. Set `self._last_synced = workflow.now()` and `self._status = "ready"`. Pass startup tests. Commit.
4. Implement `ensure_synced` Update handler with timezone-safe comparison. Pass stale/fresh tests. Commit.
5. Implement `get_sync_status` Query. Pass query test.
6. Implement `continue_as_new` logic: `workflow.wait_condition(..., timeout=timedelta(days=1))` then `workflow.continue_as_new(...)`. Implement resume path (non-None `last_synced` in input skips startup). Pass continue_as_new test. Commit.
7. Update `worker.py`: start `VaultManagerWorkflow` with ID `vault-manager`; poll `get_sync_status` until `status=ready`; then start the main worker. Commit.

---

## 8. Reference Material

### check_vault_dir_state Activity (synchronous def — file I/O belongs here, NOT in the workflow)

```python
# apps/vault_worker/activities/vault_io.py
from pathlib import Path
from temporalio import activity

@activity.defn
def check_vault_dir_state(vault_path: str) -> str:
    """Inspect vault_path and return its state.
    
    Returns: 'empty' | 'valid_repo' | 'invalid'
    
    Synchronous def: uses pathlib (blocking I/O). Temporal runs in ThreadPoolExecutor.
    This Activity exists solely so the workflow never touches the filesystem directly.
    """
    vault = Path(vault_path)
    if not vault.exists() or not any(vault.iterdir()):
        return "empty"
    if (vault / ".git").exists():
        return "valid_repo"
    return "invalid"
```

### VaultManagerWorkflow (full pattern)

```python
# apps/vault_worker/workflows/vault_manager.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from temporalio import workflow
from temporalio.exceptions import ApplicationError
from packages.shared.workflow_names import VAULT_MANAGER_WORKFLOW, UPD_ENSURE_SYNCED

@dataclass
class VaultManagerInput:
    vault_path: str
    repo_url: str
    pat: str
    last_synced: str | None = None  # ISO UTC string; None = first run

@workflow.defn(name=VAULT_MANAGER_WORKFLOW)
class VaultManagerWorkflow:
    def __init__(self) -> None:
        self._last_synced: datetime | None = None
        self._status: str = "initialising"
        self._update_count: int = 0

    @workflow.update(name=UPD_ENSURE_SYNCED)
    async def ensure_synced(self) -> None:
        """Called by ReadVaultWorkflow before reading. Pulls if stale (> 5 min)."""
        self._update_count += 1
        if self._status != "ready":
            raise ApplicationError("Vault not yet initialised", non_retryable=True)

        now = workflow.now()  # UTC-aware — always use this, never datetime.now()
        stale = self._last_synced is None or (now - self._last_synced) > timedelta(minutes=5)
        if stale:
            await workflow.execute_activity(
                "git_pull",
                args=[self._input.vault_path],
                schedule_to_close_timeout=timedelta(minutes=5),
            )
            self._last_synced = workflow.now()

    @workflow.query
    def get_sync_status(self) -> dict:
        return {
            "status": self._status,
            "last_synced": self._last_synced.isoformat() if self._last_synced else None,
        }

    @workflow.run
    async def run(self, input: VaultManagerInput) -> None:
        self._input = input

        if input.last_synced is not None:
            # Resuming after continue_as_new — restore last_synced from input.
            # The string was produced by workflow.now().isoformat(), so it is always
            # UTC-aware (contains "+00:00"). fromisoformat() parses it correctly.
            # Guard with replace(tzinfo=timezone.utc) in case of any legacy naive strings.
            dt = datetime.fromisoformat(input.last_synced)
            self._last_synced = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            self._status = "ready"
        else:
            # First run — initialise vault
            state = await workflow.execute_activity(
                "check_vault_dir_state",
                args=[input.vault_path],
                schedule_to_close_timeout=timedelta(minutes=1),
            )
            if state == "empty":
                await workflow.execute_activity(
                    "git_clone",
                    args=[input.repo_url, input.vault_path, input.pat],
                    schedule_to_close_timeout=timedelta(minutes=10),
                )
            elif state == "valid_repo":
                await workflow.execute_activity(
                    "git_pull",
                    args=[input.vault_path],
                    schedule_to_close_timeout=timedelta(minutes=5),
                )
            else:
                raise ApplicationError(
                    f"VAULT_PATH '{input.vault_path}' is non-empty and not a git repo. "
                    "Remove or correct VAULT_PATH before starting the worker.",
                    non_retryable=True,
                )
            self._last_synced = workflow.now()
            self._status = "ready"

        # Running phase: handle ensure_synced Updates indefinitely.
        # continue_as_new daily (or after 1,000 updates) to prevent history bloat.
        await workflow.wait_condition(
            lambda: self._update_count >= 1000,
            timeout=timedelta(days=1),
        )
        workflow.continue_as_new(VaultManagerInput(
            vault_path=input.vault_path,
            repo_url=input.repo_url,
            pat=input.pat,
            last_synced=self._last_synced.isoformat() if self._last_synced else None,
        ))
```

### Worker startup pattern

```python
# apps/vault_worker/worker.py
import asyncio, os
from temporalio.client import Client
from packages.shared.workflow_names import VAULT_MANAGER_ID, VAULT_MANAGER_WORKFLOW, QUEUE_DEFAULT

async def main():
    client = await Client.connect("localhost:7233")

    # Start VaultManagerWorkflow with well-known ID.
    # Use start_workflow (not execute_workflow) — it runs indefinitely.
    await client.start_workflow(
        VAULT_MANAGER_WORKFLOW,
        VaultManagerInput(
            vault_path=os.environ["VAULT_PATH"],
            repo_url=os.environ["REPO_URL"],
            pat=os.environ["GITHUB_PAT"],
        ),
        id=VAULT_MANAGER_ID,
        task_queue=QUEUE_DEFAULT,
    )

    # Poll until ready before accepting other work
    handle = client.get_workflow_handle(VAULT_MANAGER_ID)
    while True:
        status = await handle.query("get_sync_status")
        if status["status"] == "ready":
            break
        await asyncio.sleep(1)

    print("Vault ready. Starting workers.")
    async with Worker(client, task_queue=QUEUE_DEFAULT, ...):
        await asyncio.Event().wait()
```
