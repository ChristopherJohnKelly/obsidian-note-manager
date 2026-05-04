---
step_id: S11
step_slug: filer-ingestion-workflow
feature_branch: feat/OBSE-P5-temporal-soa-migration
bubble_ref: OBSE-P5-S11-filer-ingestion-workflow.md
attempts: 0
bubble_hash: 796cee708970c30cd2aef5ec327f4df871f648b8f42e6e331479784e524895ac
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
- [ ] `tests/e2e/test_filer_ingestion_workflow.py` — three path tests

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

---

## 5. Scope Boundary

**May modify:** `apps/vault_worker/workflows/filer_ingestion.py`, `tests/e2e/test_filer_ingestion_workflow.py`
**Must not modify:** `apps/vault_worker/workflows/read_vault.py`, `apps/vault_worker/workflows/write_vault.py`, Activity files, `packages/shared/`, `tests/fixtures/`

---

## 6. TDD Constraints

- Write all three path tests (approve, reject, timeout) before any implementation
- The timeout test, using `WorkflowEnvironment.start_time_skipping()`, must be implemented correctly — this is the key Temporal capability being validated
- Test the `get_draft_proposal` Query returning `None` before LLM completes (use time-skipping to pause mid-execution)

---

## 7. Step-by-Step Plan

1. Write all three E2E tests. Run — fail (workflow not defined).
2. Define the `FilerIngestionWorkflow` class with Signal/Query handlers and status management via instance variables (`_status`, `_proposal`, `_approved`).
3. Implement the `run` method: read context → LLM proposal → set `_proposal` → set `_status="awaiting_approval"` → `await workflow.wait_condition(lambda: self._approved is not None, timeout=timedelta(weeks=1))`.
4. On `approve`: dispatch `WriteVaultWorkflow` with save (proposed path) + delete (source path) operations.
5. On `reject` or timeout: return without writing.
6. Pass approve test → commit. Pass reject test → commit. Pass timeout test → commit.

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
            # ... dispatch WriteVaultWorkflow ...
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
- [S03] `WorkflowEnvironment.start_time_skipping()` is the correct in-process env (not `start_local()`) — applicable here because all three E2E tests run under time-skipping and the timeout path depends on virtual-time advance.
- [S03] Sync `def` activities need `activity_executor=ThreadPoolExecutor(...)` on the Worker — applicable here because the test Worker must register the LLM activity (sync) alongside the workflow.
- [S04] `VaultNote.path: Path` is not JSON-serialisable with Temporal's default converter — applicable here because the workflow consumes ReadVaultWorkflow output containing Path fields, so the test client must be wired with `pydantic_data_converter`.
- [S06] LLM Activities use module-level `_provider` + `configure_provider()` with an autouse fixture injecting `FakeLLMProvider` — applicable here because the "drafting" phase invokes the LLM activity and tests need a deterministic `FilingProposal` payload.
- [S07] When the SDK lacks a cross-workflow primitive the TRD mandates, use an activity shim rather than rewriting the contract — applicable here because ReadVaultWorkflow (a child of this workflow) reaches `vault-manager` through the Update-via-activity shim that the stub must satisfy.
- [S07] `VaultManagerStub` must register `@workflow.update(name=UPD_ENSURE_SYNCED)` ONLY, no signal handler under the same name — applicable here because all three tests start a stub at id `vault-manager` and the testing note explicitly says to follow the B07/B10 pattern.
- [S07] Don't dual-register signal+update handlers to mask a contract violation — applicable here because the stub design temptation recurs whenever ReadVaultWorkflow is exercised.
- [Exploratory test naming] Scratch/debug tests must use `test_explore_/test_debug_/test_inline_…` prefixes; >3 such files in a session triggers wind-down — applicable here because the timeout-path test is the trickiest TDD piece and any throwaway probes must be named to avoid escalation.
- [S08] Mock activities for an E2E test must be registered under the real names via `@activity.defn(name="save_note")` etc. — applicable here because the approve path delegates to WriteVaultWorkflow which dispatches `save_note` and `delete_file` by name.
- [S08] WriteVaultWorkflow is dispatched on `QUEUE_MUTATION`, not a per-test queue — applicable here because the approve path's child WriteVaultWorkflow needs a Worker listening on `QUEUE_MUTATION` to make progress.
- [S08] `create_workers(client)` can only be called once per client (bridge forbids re-registering the same task queue) — applicable here because three tests share the session `temporal_client` and must consolidate worker setup.
- [S09] `workflow.wait_condition(..., timeout=…)` RAISES `asyncio.TimeoutError` — it does NOT return a falsy "timed_out" — applicable here because the bubble's reference snippet uses `not await workflow.wait_condition(...)`; the real implementation must wrap in `try/except asyncio.TimeoutError` or the workflow ends FAILED instead of returning `"expired"`.
- [S09] Session-scoped time-skipping `WorkflowEnvironment` accumulates virtual-time history; long virtual-time sleeps (minutes+) after 200+ prior tests time out with `RPCError: Timeout expired` — applicable here because the timeout test advances virtual time by 1 week + 1 second and likely needs a function-scoped fresh env.
- [S09] Use `handle.terminate()` (not `handle.cancel()`) in test teardown for long-running `wait_condition` workflows — applicable here because the approve/reject tests must cleanly tear down the HITL pause so subsequent tests don't inherit timer state.
- [Pytest orchestration] One pytest invocation at a time; check for stuck processes before launching — applicable here because the timeout test is slow under time-skipping and a stale pytest from a prior cycle would silently corrupt results.
