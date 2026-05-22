---
step_id: S11
step_slug: filer-ingestion-workflow
feature_branch: feat/OBSE-P5-temporal-soa-migration
bubble_ref: OBSE-P5-S11-filer-ingestion-workflow.md
attempts: 1
bubble_hash: 283997df1e69e85b4990661aa9fb15f85e303064e5b1401601e987c873aa41b1
---
## Goal
See the bubble body below (`OBSE-P5-S11-filer-ingestion-workflow.md`) — the bubble carries the
canonical goal statement for this step.

## Files in scope
See the bubble body below for declared scope. Ralph's PLAN must mirror it
into `bubble_scope`.

## Red-green-refactor checklist
Derived from the bubble body's cycle list below. Ralph's PLAN turns each
into a `## CYCLE Cn` section.

## Bubble (verbatim)

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

## Steering from prior steps
- [S03] `WorkflowEnvironment.start_time_skipping()` is the right in-process environment for Temporal tests — applicable here because the timeout test and the "draft_proposal is None before LLM completes" test both rely on time-skipping.
- [S03] Sync `def` activities need `activity_executor=ThreadPoolExecutor(...)` on the test Worker — applicable here because the E2E tests register sync LLM/vault activities alongside the FilerIngestionWorkflow.
- [S03] `asyncio_mode = "auto"` is required for session-scoped async fixtures — applicable here because the new E2E module reuses the shared `temporal_client` / `temporal_env` fixtures.
- [S04] `VaultNote.path: Path` is not JSON-serialisable with Temporal's default converter; prefer `list[str]` returns or configure `pydantic_data_converter` — applicable here because FilerIngestionWorkflow consumes `ReadVaultWorkflow` output before the LLM call.
- [S06] LLM Activities use a module-level `_provider` + `configure_provider()` injector and an autouse FakeLLMProvider fixture — applicable here because the approve/reject/timeout/dispatch tests must inject a deterministic proposal without real Gemini calls.
- [S06] Importing the retry policy inside `@workflow.run` (or accepting the sandbox UserWarning) avoids sandbox import errors — applicable here because FilerIngestionWorkflow calls the LLM activity with `LLM_RETRY_POLICY` at the call site.
- [S07] When the SDK lacks a cross-workflow Update primitive, use an activity shim — do NOT rewrite the TRD contract — applicable here because FilerIngestionWorkflow's `ReadVaultWorkflow` child still depends on the Update-via-activity-shim path; don't "fix" it by switching to signals.
- [S07] Test stubs must register `@workflow.update(name=UPD_ENSURE_SYNCED)` only, with no signal handler shadowing it — applicable here because all three behavioural tests register a `VaultManagerStub` and must mirror that exact handshake.
- [S09] `workflow.wait_condition(..., timeout=…)` RAISES `asyncio.TimeoutError` on expiry — does NOT return False — applicable here because the bubble's reference snippet uses `timed_out = not await workflow.wait_condition(...)`, which will fail the workflow instead of returning `"expired"`; wrap in try/except `asyncio.TimeoutError`.
- [S09] Session-scoped time-skipping `WorkflowEnvironment` accumulates history; virtual sleeps longer than a few minutes after 200+ tests hit the bridge's 30s RPC timeout — applicable here because the 1-week-skip timeout test needs a function-scoped fresh env to avoid `RPCError: Timeout expired`.
- [S09] Use `handle.terminate()` (not `handle.cancel()`) to clean up long-running wait_condition workflows in test teardown — applicable here because the approve/reject/timeout tests leave a workflow blocked on `wait_condition` if a signal is never sent.
- [S09] `create_workers(client)` can only run once per client because Temporal forbids overlapping Worker registrations on the same task queue — applicable here because each E2E test must reuse a single worker setup or build per-test workers on uuid queues, not call `create_workers` repeatedly on the session client.
- [Pytest] One pytest invocation at a time; check for stuck processes before launching another — applicable here because the four E2E tests are long-running (LLM + time-skip) and overlapping runs corrupt the shared time-skipping env.
- [Exploratory tests] Name scratch/debug tests `test_explore_*` / `test_debug_*` and stay under 3 such files to avoid wind-down — applicable here because the structural dispatch test will likely need iterative experiments to assert child-workflow invocation under time-skipping.
- [S11:C1] Prior attempt was rejected for not asserting AC#1 (status=="drafting" during LLM) and AC#6 (`get_draft_proposal` returns `None` before LLM completes); the approve test queried but discarded the value — applicable here because both assertions must be written explicitly, using time-skipping to pause mid-LLM, and the approve test must assert (not just call) `get_draft_proposal`.

## Prior failures
### Attempt 1
## Prior failures (attempt 2/5, FAIL:pingpong on C4 structural dispatch test)

