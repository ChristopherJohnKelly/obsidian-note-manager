---
type: bubble
status: pending
step_id: S07
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python Engineer implementing a Temporal child workflow.
**Objective:** Implement `ReadVaultWorkflow` — the shared read handler that all parent workflows use to gather vault context. It runs on the `vault-default` queue and enforces a pull-if-stale sync policy by requesting it from `VaultManagerWorkflow`.
**Constraints:**
- Python 3.12
- Workflow code must be 100% deterministic — no file I/O or time calls inside `@workflow.run`; delegate everything to Activities
- `ReadVaultWorkflow` does **not** implement pull-if-stale logic itself. It dispatches a `ensure_synced` **Signal** to `VaultManagerWorkflow` (well-known ID `vault-manager`) carrying its own workflow ID, then blocks on `workflow.wait_condition` until it receives a `sync_ack` Signal back. `VaultManagerWorkflow` owns the `last_synced` state and decides whether a `git_pull` is needed. This prevents concurrent read workflows from triggering simultaneous pulls.
- **Why Signal-with-reply and not Update:** the Temporal Python SDK's `ExternalWorkflowHandle` exposes only `.signal()` and `.cancel()` — there is no `.execute_update()` for cross-workflow calls. Update semantics are emulated via a request-Signal + reply-Signal pair with the caller's workflow ID acting as the reply address.
- Must run on `QUEUE_DEFAULT` (`vault-default`)

---

## 1. Context

**Feature:** TRD Section 4 (Child Workflows — ReadVaultWorkflow), Section 4.5 (Queue Configuration), Section 7.4 (Sync Policies)
**Depends On:** S04 (Vault I/O Activities), S05 (Git Operations Activities)
**Testing note:** `ReadVaultWorkflow` signals the running `vault-manager` workflow. Tests register a minimal `VaultManagerStub` workflow (defined inline in the test file) with the well-known ID `vault-manager`. This stub handles the `ensure_synced` Signal by immediately signalling `sync_ack` back to the requester — sufficient to prove integration without requiring S09 to be complete.
**Current State:** All Activities (vault I/O, git ops) implemented and tested. Prior S07 attempts failed because the original spec called for `mgr.execute_update(...)` which does not exist on `ExternalWorkflowHandle`; this revision replaces that with a correct Signal-with-reply pattern.
**Target State:** `ReadVaultWorkflow` implemented, runnable via the Temporal test environment, with tests proving the dispatch + ack handshake and correct context assembly.

---

## 2. Input

- `apps/vault-worker/activities/vault_io.py`
- `apps/vault-worker/activities/git_ops.py`
- `packages/shared/models.py` — `VaultContext`, `VaultNote`
- `packages/shared/workflow_names.py` — queue, signal, and workflow name constants (you will add `SIG_ENSURE_SYNCED` and `SIG_SYNC_ACK`; remove or deprecate `UPD_ENSURE_SYNCED`)
- `tests/conftest.py`

---

## 3. Required Output

- [ ] `apps/vault-worker/workflows/read_vault.py` — `ReadVaultWorkflow`
- [ ] `tests/e2e/test_read_vault_workflow.py`
- [ ] `packages/shared/workflow_names.py` — add `SIG_ENSURE_SYNCED = "ensure_synced"` and `SIG_SYNC_ACK = "sync_ack"`; drop `UPD_ENSURE_SYNCED`

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

---

## 4. Acceptance Criteria

- [ ] `ReadVaultWorkflow` sends a `SIG_ENSURE_SYNCED` Signal to the workflow with ID `vault-manager` before executing any read Activities. The signal payload is the caller's own workflow ID (`workflow.info().workflow_id`).
- [ ] `ReadVaultWorkflow` declares a `@workflow.signal(name=SIG_SYNC_ACK)` handler that flips an instance flag, and the `run` method blocks on `workflow.wait_condition(lambda: self._synced, timeout=timedelta(minutes=5))` before invoking any read Activities. If the ack never arrives, the workflow must fail with a `TimeoutError` — it must not proceed with reads.
- [ ] The stub's `SIG_ENSURE_SYNCED` handler is called exactly once per `ReadVaultWorkflow` execution, verified via a `@workflow.query` on the stub returning `call_count`.
- [ ] The returned `VaultContext` contains a non-empty `skeleton` string.
- [ ] The returned `VaultContext` contains a non-empty `code_registry` string.
- [ ] `VaultContext.related_notes` contains only notes whose path starts with the folder corresponding to `context_code`.
- [ ] Multiple simultaneous `ReadVaultWorkflow` executions complete without error and the stub records `call_count == 5` after 5 concurrent runs (proves each caller is independently ack'd by its correct reply address).

---

## 5. Scope Boundary

**May modify:**
- `apps/vault-worker/workflows/read_vault.py`
- `tests/e2e/test_read_vault_workflow.py`
- `packages/shared/workflow_names.py` (constant additions/removal only — see §3)

**Must not modify:** Activity files, other `packages/shared/` modules, `tests/fixtures/`, `tests/conftest.py`.

---

## 6. TDD Constraints

- Write all tests in `test_read_vault_workflow.py` before implementing the workflow.
- Use `temporalio.testing.WorkflowEnvironment.start_time_skipping()` (via the existing `temporal_env`/`temporal_client` fixtures in `conftest.py`).
- The parallel execution test (5 concurrent `ReadVaultWorkflow` runs) must be written before implementation.
- **Do not** register a `@workflow.update` handler on `VaultManagerStub`. The test stub must exercise the Signal pathway exactly as production will — any matching `@workflow.update` handler would mask the contract and will cause serena rejection.
- **Do not** leave `print()` or other debug scaffolding in `read_vault.py` at commit time.

---

## 7. Step-by-Step Plan

1. Update `packages/shared/workflow_names.py`: remove `UPD_ENSURE_SYNCED`; add `SIG_ENSURE_SYNCED = "ensure_synced"` and `SIG_SYNC_ACK = "sync_ack"`.
2. Write `tests/e2e/test_read_vault_workflow.py` covering all acceptance criteria. Define `VaultManagerStub` inline (see Reference Material). Tests fail (workflow not defined).
3. Define `ReadVaultInput` dataclass and the `ReadVaultWorkflow` class skeleton, including the `SIG_SYNC_ACK` handler and `_synced` flag. Tests still fail (workflow body empty).
4. Implement the Signal dispatch to `vault-manager` (carrying `workflow.info().workflow_id`) and the `wait_condition` block. Pass the dispatch + ack test and the `call_count == 1` assertion.
5. Implement the Activity execution chain: `get_skeleton` → `get_code_registry` → `read_note` (root note) → `list_notes_in` (related notes). Pass context assembly tests.
6. Pass parallel execution test (5 concurrent callers, assert `call_count == 5`).
7. Commit.

---

## 8. Reference Material

### Workflow signal-with-reply pattern

```python
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

from apps.vault_worker.activities.vault_io import (
    get_code_registry,
    get_skeleton,
    list_notes_in,
    read_note,
)
from packages.shared.models import VaultContext
from packages.shared.workflow_names import (
    SIG_ENSURE_SYNCED,
    SIG_SYNC_ACK,
    VAULT_MANAGER_ID,
)


@dataclass
class ReadVaultInput:
    vault_path: str
    context_code: str


@workflow.defn
class ReadVaultWorkflow:
    def __init__(self) -> None:
        self._synced: bool = False

    @workflow.signal(name=SIG_SYNC_ACK)
    async def on_sync_ack(self) -> None:
        self._synced = True

    @workflow.run
    async def run(self, input: ReadVaultInput) -> VaultContext:
        # 1. Request sync from VaultManagerWorkflow. We pass our own workflow
        #    ID as the reply address; the manager signals SIG_SYNC_ACK back
        #    once it has confirmed the vault is fresh (pulling if stale).
        mgr = workflow.get_external_workflow_handle(VAULT_MANAGER_ID)
        await mgr.signal(SIG_ENSURE_SYNCED, workflow.info().workflow_id)

        # 2. Block until the ack arrives. Fail fast if the manager never
        #    responds — do not proceed with reads against a potentially
        #    stale vault.
        await workflow.wait_condition(
            lambda: self._synced,
            timeout=timedelta(minutes=5),
        )

        # 3. Now safe to read.
        skeleton = await workflow.execute_activity(
            get_skeleton,
            args=[input.vault_path],
            schedule_to_close_timeout=timedelta(minutes=1),
        )
        # ... continue with get_code_registry, read_note, list_notes_in, assemble VaultContext ...
```

### VaultManagerStub for testing (defined inline in the test file)

The stub must handle `SIG_ENSURE_SYNCED` by sending `SIG_SYNC_ACK` back to the requester whose ID was passed as the payload. It must **not** register a `@workflow.update` handler — doing so masks the Signal contract and causes serena rejection.

```python
import asyncio
from temporalio import workflow
from packages.shared.workflow_names import (
    SIG_ENSURE_SYNCED,
    SIG_SYNC_ACK,
    VAULT_MANAGER_ID,
)


@workflow.defn
class VaultManagerStub:
    """Minimal stand-in for VaultManagerWorkflow. Ack's SIG_ENSURE_SYNCED by
    signalling SIG_SYNC_ACK back to the requester. Used only in S07 tests;
    full implementation in S09."""

    def __init__(self) -> None:
        self._call_count: int = 0

    @workflow.signal(name=SIG_ENSURE_SYNCED)
    async def on_ensure_synced(self, requester_id: str) -> None:
        self._call_count += 1
        # In production, sync-state logic (check last_synced, git_pull if stale)
        # happens here. The stub skips straight to ack.
        requester = workflow.get_external_workflow_handle(requester_id)
        await requester.signal(SIG_SYNC_ACK)

    @workflow.query
    def call_count(self) -> int:
        return self._call_count

    @workflow.run
    async def run(self) -> None:
        # Stay alive long enough for tests to complete
        await asyncio.sleep(3600)
```

### Dispatch + ack test

```python
async def test_read_vault_dispatches_and_waits_for_ack(
    temporal_client, dummy_vault_path
):
    import uuid
    queue = f"test-read-{uuid.uuid4().hex[:8]}"

    async with Worker(
        temporal_client,
        task_queue=queue,
        workflows=[VaultManagerStub, ReadVaultWorkflow],
        activities=[get_skeleton, get_code_registry, read_note, list_notes_in],
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        stub_handle = await temporal_client.start_workflow(
            VaultManagerStub.run,
            id=VAULT_MANAGER_ID,
            task_queue=queue,
        )
        try:
            result = await temporal_client.execute_workflow(
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

### Parallel execution test pattern

```python
async def test_multiple_concurrent_reads_each_get_their_own_ack(
    temporal_client, dummy_vault_path
):
    async with Worker(
        temporal_client,
        task_queue=QUEUE_DEFAULT,
        workflows=[VaultManagerStub, ReadVaultWorkflow],
        activities=[get_skeleton, get_code_registry, read_note, list_notes_in],
        activity_executor=ThreadPoolExecutor(max_workers=4),
    ):
        stub_handle = await temporal_client.start_workflow(
            VaultManagerStub.run,
            id=VAULT_MANAGER_ID,
            task_queue=QUEUE_DEFAULT,
        )
        try:
            results = await asyncio.gather(*[
                temporal_client.execute_workflow(
                    ReadVaultWorkflow.run,
                    ReadVaultInput(
                        vault_path=str(dummy_vault_path),
                        context_code="TEST-P01",
                    ),
                    id=f"read-test-parallel-{i}",
                    task_queue=QUEUE_DEFAULT,
                )
                for i in range(5)
            ])
            assert len(results) == 5
            assert all(r.skeleton for r in results)
            call_count = await stub_handle.query(VaultManagerStub.call_count)
            assert call_count == 5
        finally:
            await stub_handle.cancel()
```

### Timeout behaviour test (optional but recommended)

If the manager never signals back (e.g., it's not running), `ReadVaultWorkflow` must fail — not hang and not silently proceed with reads. Exercise this by running `ReadVaultWorkflow` without starting the stub at all and asserting the execute_workflow call raises (via WorkflowFailureError wrapping a TimeoutError).
