---
type: bubble
status: pending
step_id: S07
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python Engineer implementing a Temporal child workflow.
**Objective:** Implement `ReadVaultWorkflow` — the shared read handler that all parent workflows use to gather vault context. It runs on the `vault-default` queue and enforces a pull-if-stale sync policy.
**Constraints:**
- Python 3.12
- Workflow code must be 100% deterministic — no file I/O or time calls inside `@workflow.run`; delegate everything to Activities
- `ReadVaultWorkflow` does **not** implement pull-if-stale logic itself. It sends an `ensure_synced` Update to `VaultManagerWorkflow` (well-known ID `vault-manager`) and blocks until the Update returns. `VaultManagerWorkflow` owns the `last_synced` state and decides whether a `git_pull` is needed. This prevents concurrent read workflows from triggering simultaneous pulls.
- Must run on `QUEUE_DEFAULT` (`vault-default`)

---

## 1. Context

**Feature:** TRD Section 4 (Child Workflows — ReadVaultWorkflow), Section 4.5 (Queue Configuration), Section 7.4 (Sync Policies)
**Depends On:** S04 (Vault I/O Activities), S05 (Git Operations Activities)
**Testing note:** `ReadVaultWorkflow` sends an `ensure_synced` Update to the running `vault-manager` workflow. Tests register a minimal `VaultManagerStub` workflow (defined inline in the test file) with the well-known ID `vault-manager`. This stub handles the Update and returns immediately — it is sufficient to prove `ReadVaultWorkflow` integration without requiring B09 to be complete.
**Current State:** All Activities (vault I/O, git ops) implemented and tested.
**Target State:** `ReadVaultWorkflow` implemented, runnable via the Temporal test environment, with tests proving the pull-if-stale policy and correct context assembly.

---

## 2. Input

- `apps/vault-worker/activities/vault_io.py`
- `apps/vault-worker/activities/git_ops.py`
- `packages/shared/models.py` — `VaultContext`, `VaultNote`
- `packages/shared/workflow_names.py` — queue and workflow name constants
- `tests/conftest.py`

---

## 3. Required Output

- [ ] `apps/vault-worker/workflows/read_vault.py` — `ReadVaultWorkflow`
- [ ] `tests/e2e/test_read_vault_workflow.py`

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

- [ ] `ReadVaultWorkflow` sends an `ensure_synced` Update to the workflow with ID `vault-manager` before executing any read Activities
- [ ] The workflow blocks until the `ensure_synced` Update returns before proceeding (verified by asserting the stub's Update handler was called)
- [ ] The returned `VaultContext` contains a non-empty `skeleton` string
- [ ] The returned `VaultContext` contains a non-empty `code_registry` string
- [ ] `VaultContext.related_notes` contains only notes whose path starts with the folder corresponding to `context_code`
- [ ] Multiple simultaneous `ReadVaultWorkflow` executions complete without error (parallel execution test: 5 concurrent runs)

---

## 5. Scope Boundary

**May modify:** `apps/vault-worker/workflows/read_vault.py`, `tests/e2e/test_read_vault_workflow.py`
**Must not modify:** Activity files, `packages/shared/`, `tests/fixtures/`, `tests/conftest.py`

---

## 6. TDD Constraints

- Write all tests in `test_read_vault_workflow.py` before implementing the workflow
- Use `temporalio.testing.WorkflowEnvironment.start_time_skipping()` to simulate time for the stale-sync policy test
- The parallel execution test must be written before implementation

---

## 7. Step-by-Step Plan

1. Write `tests/e2e/test_read_vault_workflow.py` covering all acceptance criteria. Define `VaultManagerStub` inline in the test file (see Reference Material). Tests fail (workflow not defined).
2. Define `ReadVaultInput` dataclass and the `ReadVaultWorkflow` class skeleton. Tests still fail (workflow body empty).
3. Implement the `ensure_synced` Update dispatch to `vault-manager`. Implement the Activity execution chain: `get_skeleton` → `get_code_registry` → `read_note` (root note) → `list_notes_in` (related notes). Pass Update dispatch test.
4. Pass context assembly tests.
5. Pass parallel execution test (5 concurrent workers on `vault-default` queue).
6. Commit.

---

## 8. Reference Material

### ensure_synced Update dispatch (replaces pull-if-stale logic)

```python
from datetime import timedelta
from temporalio import workflow
from packages.shared.workflow_names import VAULT_MANAGER_ID, UPD_ENSURE_SYNCED

@workflow.run
async def run(self, input: ReadVaultInput) -> VaultContext:
    # Delegate sync decision to VaultManagerWorkflow — it owns last_synced state.
    # This blocks until VaultManagerWorkflow confirms the vault is fresh
    # (pulling if stale, no-op if recent). Do not call git_pull directly here.
    mgr = workflow.get_external_workflow_handle(VAULT_MANAGER_ID)
    await mgr.execute_update(UPD_ENSURE_SYNCED)

    # Read activities run after sync is confirmed
    skeleton = await workflow.execute_activity(
        get_skeleton, args=[input.vault_path],
        schedule_to_close_timeout=timedelta(minutes=1),
    )
    ...
```

### VaultManagerStub for testing (defined inline in test file)

The test must start a `VaultManagerStub` with the well-known ID `vault-manager` before running `ReadVaultWorkflow`. This stub handles the `ensure_synced` Update and returns immediately — it does not test pull-if-stale logic (that is covered in B09).

```python
from temporalio import workflow
from packages.shared.workflow_names import VAULT_MANAGER_ID, UPD_ENSURE_SYNCED

ensure_synced_call_count = 0

@workflow.defn
class VaultManagerStub:
    """Minimal stand-in for VaultManagerWorkflow. Accepts ensure_synced Updates
    and returns immediately. Used only in B07 tests; full implementation in B09."""

    @workflow.update
    async def ensure_synced(self) -> None:
        global ensure_synced_call_count
        ensure_synced_call_count += 1

    @workflow.run
    async def run(self) -> None:
        # Stay alive long enough for tests to complete
        await asyncio.sleep(3600)

async def test_read_vault_dispatches_ensure_synced(temporal_client, dummy_vault_path):
    global ensure_synced_call_count
    ensure_synced_call_count = 0

    async with Worker(temporal_client, task_queue=QUEUE_DEFAULT,
                      workflows=[VaultManagerStub, ReadVaultWorkflow],
                      activities=[get_skeleton, get_code_registry, read_note, list_notes_in]):
        # Start the stub with the well-known ID
        await temporal_client.start_workflow(
            VaultManagerStub.run, id=VAULT_MANAGER_ID, task_queue=QUEUE_DEFAULT
        )
        result = await temporal_client.execute_workflow(
            ReadVaultWorkflow.run,
            ReadVaultInput(vault_path=str(dummy_vault_path), context_code="TEST-P01"),
            id="read-test-1", task_queue=QUEUE_DEFAULT,
        )
    assert ensure_synced_call_count == 1
    assert result.skeleton
```

### Parallel execution test pattern

```python
async def test_multiple_concurrent_reads(temporal_client, dummy_vault_path):
    async with Worker(temporal_client, task_queue=QUEUE_DEFAULT,
                      workflows=[VaultManagerStub, ReadVaultWorkflow],
                      activities=[get_skeleton, get_code_registry, read_note, list_notes_in]):
        await temporal_client.start_workflow(
            VaultManagerStub.run, id=VAULT_MANAGER_ID, task_queue=QUEUE_DEFAULT
        )
        results = await asyncio.gather(*[
            temporal_client.execute_workflow(
                ReadVaultWorkflow.run,
                ReadVaultInput(vault_path=str(dummy_vault_path), context_code="TEST-P01"),
                id=f"read-test-{i}", task_queue=QUEUE_DEFAULT,
            )
            for i in range(5)
        ])
    assert all(r.skeleton for r in results)
```
