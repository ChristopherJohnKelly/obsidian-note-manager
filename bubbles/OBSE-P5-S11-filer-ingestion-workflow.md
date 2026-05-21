---
type: bubble
status: pending
step_id: S11
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python Engineer implementing a long-running HITL workflow.
**Objective:** Implement `FilerIngestionWorkflow` — the inbox-to-vault filing workflow with a Chainlit-driven Human-In-The-Loop approval pause. The workflow generates a proposal, exposes it via a Query, blocks on an `approve` or `reject` Signal, and files on approval.
**Constraints:**
- Python 3.12
- The HITL pause uses `workflow.wait_condition()` — the workflow is genuinely blocked (not polling) until a Signal arrives
- HITL timeout is 1 week (`timedelta(weeks=1)`) — after which the workflow terminates without filing
- Workflow code is deterministic — no file I/O, random, or time calls in `@workflow.run` directly
- The source inbox file must be removed after successful filing (as part of the same `WriteVaultWorkflow` call)

---

## 1. Context

**Feature:** TRD Section 4 (FilerIngestionWorkflow), TRD Section 4.6 (Workflow Interface Specifications), PRD Section 4 (The Filer use case)
**Depends On:** S06 (LLM Activities), S07 (ReadVaultWorkflow), S08 (WriteVaultWorkflow)
**Testing note:** `FilerIngestionWorkflow` calls `ReadVaultWorkflow`, which sends an `ensure_synced` Update to `vault-manager`. All three E2E tests must register a `VaultManagerStub` (same pattern as B07/B10) and start it with ID `vault-manager` before running the workflow under test.
**Current State:** NightWatchmanWorkflow implemented (S10). Child workflows and all Activities available.
**Target State:** Full `FilerIngestionWorkflow` E2E passing: one test covering approve path (note filed, inbox cleared), one covering reject path (vault unchanged), one covering timeout (vault unchanged after 1 week skipped).

---

## 2. Input

- `apps/vault_worker/workflows/read_vault.py`
- `apps/vault_worker/workflows/write_vault.py`
- `apps/vault_worker/activities/llm.py`
- `packages/shared/models.py` — `FilingProposal`
- `packages/shared/workflow_names.py` — Signal/Query name constants
- `tests/fixtures/dummy_vault/00. Inbox/0. Capture/new-capture-note.md` — test input

---

## 3. Required Output

- [ ] `apps/vault_worker/workflows/filer_ingestion.py` — `FilerIngestionWorkflow`
- [ ] `tests/e2e/test_filer_ingestion_workflow.py` — four tests: three path tests (approve, reject, timeout) plus one structural dispatch test (`test_approve_dispatches_via_write_vault_workflow`, see §6)

**Workflow interface (from TRD Section 4.6):**

```python
@dataclass
class FilerIngestionInput:
    vault_path: str
    source_path: str    # relative path of the inbox file

@workflow.defn
class FilerIngestionWorkflow:
    @workflow.run
    async def run(self, input: FilerIngestionInput) -> str: ...
    # returns "filed", "rejected", or "expired"

    @workflow.signal
    async def approve(self) -> None: ...

    @workflow.signal
    async def reject(self) -> None: ...

    @workflow.query
    def get_draft_proposal(self) -> dict | None: ...
    # returns serialised FilingProposal or None while drafting

    @workflow.query
    def get_status(self) -> str: ...
    # "drafting" | "awaiting_approval" | "filing" | "complete" | "rejected" | "expired"
```

---

## 4. Acceptance Criteria

- [ ] After workflow starts, `get_status` returns `"drafting"` while the LLM Activity runs
- [ ] After LLM Activity completes, `get_status` returns `"awaiting_approval"` and `get_draft_proposal` returns a non-None `FilingProposal`
- [ ] **Approve path:** Sending `approve` Signal → `get_status` transitions to `"filing"` then `"complete"`; the proposed file exists in the vault; the source inbox file no longer exists; workflow returns `"filed"`
- [ ] **Reject path:** Sending `reject` Signal → `get_status` is `"rejected"`; vault is unchanged; workflow returns `"rejected"`
- [ ] **Timeout path:** Using time-skipping, advance 1 week + 1 second → workflow returns `"expired"`; vault is unchanged
- [ ] `get_draft_proposal` returns `None` before the LLM Activity completes (tested with `start_time_skipping`)
- [ ] **Dispatch via child workflow (ARCHITECTURAL — non-negotiable):** the approve path MUST perform the write by executing `WriteVaultWorkflow` as a child workflow (`await workflow.execute_child_workflow(WriteVaultWorkflow.run, ...)`), carrying both the save (proposed path) and the delete (source inbox path) in that single call. `FilerIngestionWorkflow` MUST NOT call the `save_note` or `delete_note` Activities directly, and reads MUST go via `ReadVaultWorkflow` — never direct Activity calls. `FilerIngestionWorkflow` is a coordinator that composes child workflows; it owns no direct vault I/O. This is pinned by a structural test (see §3, §6) and is the reason a prior attempt was rejected.

---

## 5. Scope Boundary

**May modify:** `apps/vault_worker/workflows/filer_ingestion.py`, `tests/e2e/test_filer_ingestion_workflow.py`
**Must not modify:** `apps/vault_worker/workflows/read_vault.py`, `apps/vault_worker/workflows/write_vault.py`, Activity files, `packages/shared/`, `tests/fixtures/`

---

## 6. TDD Constraints

- Write all three path tests (approve, reject, timeout) before any implementation
- The timeout test, using `WorkflowEnvironment.start_time_skipping()`, must be implemented correctly — this is the key Temporal capability being validated
- Test the `get_draft_proposal` Query returning `None` before LLM completes (use time-skipping to pause mid-execution)
- **Structural dispatch test (`test_approve_dispatches_via_write_vault_workflow`):** register a recording `WriteVaultWorkflow` stub in the test module (same pattern as the `VaultManagerStub`) that records the input it receives and performs the save+delete itself so the behavioural approve-path assertions still hold; assert the stub was invoked exactly once, with the proposed save path and the source-inbox delete path. This test MUST fail if `FilerIngestionWorkflow` bypasses the child workflow and calls the `save_note`/`delete_note` Activities directly. Consult the `temporal-developer` skill for the correct way to assert child-workflow dispatch in a time-skipping test environment.

---

## 7. Step-by-Step Plan

1. Write all four E2E tests (approve, reject, timeout, structural dispatch). Run — fail (workflow not defined).
2. Define the `FilerIngestionWorkflow` class with Signal/Query handlers and status management via instance variables (`_status`, `_proposal`, `_approved`).
3. Implement the `run` method: read context (via `ReadVaultWorkflow`, not direct Activities) → LLM proposal → set `_proposal` → set `_status="awaiting_approval"` → `await workflow.wait_condition(lambda: self._approved is not None, timeout=timedelta(weeks=1))`.
4. On `approve`: dispatch the write by `await workflow.execute_child_workflow(WriteVaultWorkflow.run, ...)` carrying save (proposed path) + delete (source path) in that single call — never call `save_note`/`delete_note` Activities directly.
5. On `reject` or timeout: return without writing.
6. Pass approve test → commit. Pass reject test → commit. Pass timeout test → commit. Pass structural dispatch test → commit.

---

## 8. Reference Material

### HITL wait pattern

```python
import asyncio
from datetime import timedelta
from temporalio import workflow

@workflow.defn
class FilerIngestionWorkflow:
    def __init__(self):
        self._status = "drafting"
        self._proposal: dict | None = None
        self._decision: str | None = None  # "approve" | "reject"

    @workflow.signal
    async def approve(self) -> None:
        self._decision = "approve"

    @workflow.signal
    async def reject(self) -> None:
        self._decision = "reject"

    @workflow.query
    def get_status(self) -> str:
        return self._status

    @workflow.query
    def get_draft_proposal(self) -> dict | None:
        return self._proposal

    @workflow.run
    async def run(self, input: FilerIngestionInput) -> str:
        # ... generate proposal via child workflows + LLM ...
        self._status = "awaiting_approval"

        timed_out = not await workflow.wait_condition(
            lambda: self._decision is not None,
            timeout=timedelta(weeks=1),
        )

        if timed_out:
            self._status = "expired"
            return "expired"
        elif self._decision == "reject":
            self._status = "rejected"
            return "rejected"
        else:
            self._status = "filing"
            # Dispatch the write as a CHILD WORKFLOW — never call
            # save_note/delete_note Activities directly from here.
            # await workflow.execute_child_workflow(
            #     WriteVaultWorkflow.run,
            #     WriteVaultInput(operations=[save(proposed_path), delete(source_path)]),
            #     id=...,
            #     task_queue=QUEUE_DEFAULT,
            # )
            self._status = "complete"
            return "filed"
```

### Timeout test with time-skipping

```python
async def test_filer_expires_after_one_week(temporal_client):
    async with WorkflowEnvironment.start_time_skipping() as env:
        client = env.client
        async with Worker(client, ...):
            handle = await client.start_workflow(
                FilerIngestionWorkflow.run,
                FilerIngestionInput(...),
                id="filer-timeout-test",
                task_queue=QUEUE_DEFAULT,
            )
            # Skip 1 week + 1 second
            await env.sleep(timedelta(weeks=1, seconds=1))
            result = await handle.result()
    assert result == "expired"
```
