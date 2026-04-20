---
type: bubble
status: pending
step_id: S07
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python Engineer implementing a Temporal child workflow.
**Objective:** Implement `ReadVaultWorkflow` — the shared read handler that all parent workflows use to gather vault context. It runs on the `vault-default` queue and enforces a pull-if-stale sync policy by requesting it from `VaultManagerWorkflow` via the TRD-specified `ensure_synced` Update.
**Constraints:**
- Python 3.12
- Workflow code must be 100% deterministic — no file I/O or time calls inside `@workflow.run`; delegate everything to Activities
- `ReadVaultWorkflow` does **not** implement pull-if-stale logic itself. It dispatches the `ensure_synced` **Update** to `VaultManagerWorkflow` (well-known ID `vault-manager`) and blocks until the Update handler returns. `VaultManagerWorkflow` owns the `last_synced` state and decides whether a `git_pull` is needed. This matches TRD §4.6 and §7.4 exactly.
- **SDK limitation + sanctioned workaround:** the Temporal Python SDK's `workflow.get_external_workflow_handle()` exposes only `.signal()` and `.cancel()` — there is no cross-workflow `execute_update` on `ExternalWorkflowHandle`. The standard Temporal pattern for this is an **Activity shim**: an activity that holds a Temporal `Client` and calls `client.get_workflow_handle(manager_id).execute_update(UPD_ENSURE_SYNCED)`. The activity runs outside the workflow sandbox and can hold the client; the workflow blocks on the activity, which blocks on the Update. Update semantics (strong completion, propagated errors) are preserved.
- Must run on `QUEUE_DEFAULT` (`vault-default`)

---

## 1. Context

**Feature:** TRD Section 4 (Child Workflows — ReadVaultWorkflow), Section 4.5 (Queue Configuration), Section 7.4 (Sync Policies)
**Depends On:** S04 (Vault I/O Activities), S05 (Git Operations Activities)
**Testing note:** `ReadVaultWorkflow` invokes the `ensure_vault_synced` activity, which in turn calls `execute_update` on `vault-manager`. Tests register a minimal `VaultManagerStub` workflow (defined inline in the test file) with the well-known ID `vault-manager`. This stub declares a `@workflow.update(name=UPD_ENSURE_SYNCED)` handler that increments a counter and returns — sufficient to prove integration without requiring S09 to be complete. Tests also register `ensure_vault_synced` on the Worker's activity list and inject the test Client via `configure_client(pydantic_client)`.
**Current State:** All Activities (vault I/O, git ops) implemented and tested. Prior S07 attempts failed by either (a) calling `mgr.execute_update(...)` on an `ExternalWorkflowHandle` (does not exist) or (b) replacing the Update with a Signal-with-reply pair (diverges from TRD §4.6/§7.4). The activity-shim pattern is the TRD-compliant resolution.
**Target State:** `ReadVaultWorkflow` implemented, runnable via the Temporal test environment, with tests proving the Update dispatch + completion and correct context assembly.

---

## 2. Input

- `apps/vault_worker/activities/vault_io.py`
- `apps/vault_worker/activities/git_ops.py`
- `packages/shared/models.py` — `VaultContext`, `VaultNote`
- `packages/shared/workflow_names.py` — queue, update, and workflow name constants (`UPD_ENSURE_SYNCED` must be present)
- `tests/conftest.py`

---

## 3. Required Output

- [ ] `apps/vault_worker/workflows/read_vault.py` — `ReadVaultWorkflow`
- [ ] `apps/vault_worker/activities/vault_manager_client.py` — `ensure_vault_synced` activity + `configure_client()` injector
- [ ] `tests/e2e/test_read_vault_workflow.py`
- [ ] `packages/shared/workflow_names.py` — `UPD_ENSURE_SYNCED = "ensure_synced"` present

**Workflow interface:**

```python
@dataclass
class ReadVaultInput:
    vault_path: str
    context_code: str  # e.g. "OBSE-P1" — scopes the related_notes
    # No last_synced field — sync state is owned by VaultManagerWorkflow

@workflow.defn
class ReadVaultWorkflow:
    @workflow.run
    async def run(self, input: ReadVaultInput) -> VaultContext: ...
```

**Activity interface:**

```python
@activity.defn
async def ensure_vault_synced(manager_id: str) -> None:
    """Call execute_update(UPD_ENSURE_SYNCED) on the manager via a Temporal
    Client. Blocks until the Update handler returns."""
```

---

## 4. Acceptance Criteria

- [ ] `ReadVaultWorkflow` invokes the `ensure_vault_synced` activity with `VAULT_MANAGER_ID` as the argument before executing any read Activities.
- [ ] The `ensure_vault_synced` activity calls `client.get_workflow_handle(manager_id).execute_update(UPD_ENSURE_SYNCED)` and blocks until the Update completes. The workflow must wait on this activity and must not proceed on failure.
- [ ] The stub's `@workflow.update(name=UPD_ENSURE_SYNCED)` handler is called exactly once per `ReadVaultWorkflow` execution, verified via a `@workflow.query` on the stub returning `call_count`.
- [ ] If the VaultManager's `ensure_synced` handler raises (e.g. pull failure), the `ReadVaultWorkflow` must fail — it must not proceed with reads against an unsynchronised vault. Test via a `FailingVaultManagerStub` whose Update handler raises `ApplicationError(non_retryable=True)`.
- [ ] The returned `VaultContext` contains a non-empty `skeleton` string.
- [ ] The returned `VaultContext` contains a non-empty `code_registry` string.
- [ ] `VaultContext.related_notes` contains only notes whose path starts with the folder corresponding to `context_code`.
- [ ] Multiple simultaneous `ReadVaultWorkflow` executions complete without error and the stub records `call_count == 5` after 5 concurrent runs.

---

## 5. Scope Boundary

**May modify:**
- `apps/vault_worker/workflows/read_vault.py`
- `apps/vault_worker/activities/vault_manager_client.py` (new)
- `tests/e2e/test_read_vault_workflow.py`
- `packages/shared/workflow_names.py` (ensure `UPD_ENSURE_SYNCED` present; any leftover `SIG_ENSURE_SYNCED`/`SIG_SYNC_ACK` from prior attempts must be removed)

**Must not modify:** other activity files, other `packages/shared/` modules, `tests/fixtures/`, `tests/conftest.py`.

---

## 6. TDD Constraints

- Write all tests in `test_read_vault_workflow.py` before implementing the workflow.
- Use `temporalio.testing.WorkflowEnvironment.start_time_skipping()` (via the existing `temporal_env`/`temporal_client` fixtures in `conftest.py`).
- The parallel execution test (5 concurrent `ReadVaultWorkflow` runs) must be written before implementation.
- **Do** register a `@workflow.update(name=UPD_ENSURE_SYNCED)` handler on `VaultManagerStub` — that is the TRD contract, and tests must exercise it exactly as production will.
- **Do not** register a `@workflow.signal(name=...)` handler on `VaultManagerStub` for `ensure_synced`. Dual registrations mask the contract and will cause serena rejection.
- **Do not** leave `print()` or other debug scaffolding in `read_vault.py` or the activity at commit time.
- No `test_explore_*`, `test_debug_*`, or `test_inline_*` files in the final commit.

---

## 7. Step-by-Step Plan

1. Ensure `packages/shared/workflow_names.py` has `UPD_ENSURE_SYNCED = "ensure_synced"` in the Update names section (remove any stale `SIG_ENSURE_SYNCED`/`SIG_SYNC_ACK` from prior attempts).
2. Write `apps/vault_worker/activities/vault_manager_client.py` with `configure_client()` + `_get_client()` injection and the `ensure_vault_synced` activity.
3. Write `tests/e2e/test_read_vault_workflow.py` covering all acceptance criteria. Define `VaultManagerStub` (happy) and `FailingVaultManagerStub` (update raises) inline. The `pydantic_client` fixture must call `configure_client(client)` so the activity can reach the test server. Tests fail (workflow not defined).
4. Define `ReadVaultInput` dataclass and the `ReadVaultWorkflow` skeleton. Tests still fail (workflow body empty).
5. Implement the activity call and the Activity chain: `ensure_vault_synced` → `get_skeleton` → `get_code_registry` → `read_note` (root note) → `list_notes_in` (related notes). Pass all tests.
6. Commit.

---

## 8. Reference Material

### Activity shim

```python
from temporalio import activity
from temporalio.client import Client
from packages.shared.workflow_names import UPD_ENSURE_SYNCED

_client: Client | None = None


def configure_client(client: Client | None) -> None:
    global _client
    _client = client


def _get_client() -> Client:
    if _client is None:
        raise RuntimeError("Temporal Client not configured.")
    return _client


@activity.defn
async def ensure_vault_synced(manager_id: str) -> None:
    client = _get_client()
    handle = client.get_workflow_handle(manager_id)
    await handle.execute_update(UPD_ENSURE_SYNCED)
```

### Workflow

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.vault_worker.activities.vault_io import (
        get_code_registry,
        get_skeleton,
        list_notes_in,
        read_note,
    )
    from apps.vault_worker.activities.vault_manager_client import (
        ensure_vault_synced,
    )
    from packages.shared.models import VaultContext
    from packages.shared.workflow_names import VAULT_MANAGER_ID


@dataclass
class ReadVaultInput:
    vault_path: str
    context_code: str


@workflow.defn
class ReadVaultWorkflow:
    @workflow.run
    async def run(self, input: ReadVaultInput) -> VaultContext:
        await workflow.execute_activity(
            ensure_vault_synced,
            args=[VAULT_MANAGER_ID],
            start_to_close_timeout=timedelta(minutes=5),
        )

        skeleton = await workflow.execute_activity(
            get_skeleton,
            args=[input.vault_path],
            schedule_to_close_timeout=timedelta(minutes=1),
        )
        # ... continue with get_code_registry, read_note, list_notes_in, assemble VaultContext ...
```

### VaultManagerStub (happy) and FailingVaultManagerStub (raises) for testing

```python
import asyncio
from temporalio import workflow
from temporalio.exceptions import ApplicationError
from packages.shared.workflow_names import UPD_ENSURE_SYNCED, VAULT_MANAGER_ID


@workflow.defn
class VaultManagerStub:
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
    @workflow.update(name=UPD_ENSURE_SYNCED)
    async def on_ensure_synced(self) -> None:
        raise ApplicationError("simulated pull failure", non_retryable=True)

    @workflow.run
    async def run(self) -> None:
        await asyncio.sleep(3600)
```

### Dispatch + completion test

```python
async def test_dispatches_update_and_waits_for_completion(
    pydantic_client, dummy_vault_path
):
    import uuid
    queue = f"test-read-{uuid.uuid4().hex[:8]}"

    async with Worker(
        pydantic_client,
        task_queue=queue,
        workflows=[VaultManagerStub, ReadVaultWorkflow],
        activities=[get_skeleton, get_code_registry, read_note, list_notes_in,
                    ensure_vault_synced],
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
                id="read-test-1",
                task_queue=queue,
            )
            call_count = await stub_handle.query(VaultManagerStub.call_count)
            assert call_count == 1
            assert result.skeleton
        finally:
            await stub_handle.cancel()
```

### Failure propagation test

If `ensure_synced` raises on the manager side, `ReadVaultWorkflow` must fail — exercise via `FailingVaultManagerStub` running on the well-known ID, and assert `execute_workflow(ReadVaultWorkflow.run, ...)` raises `WorkflowFailureError`.
