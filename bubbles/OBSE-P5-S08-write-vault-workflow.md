---
type: bubble
status: pending
step_id: S08
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python Engineer implementing the serialised write handler for the vault.
**Objective:** Implement `WriteVaultWorkflow` on the `vault-mutation-queue` with `max_concurrent_activities=1`. This is the critical concurrency boundary — all vault mutations must funnel through this single queue. Prove the sequential guarantee with a load test.
**Constraints:**
- Python 3.12
- The Worker for this workflow is configured with `max_concurrent_workflow_tasks=1` and `max_concurrent_activities=1`
- Workflow code is deterministic — no direct file I/O in `@workflow.run`
- Must always `git_pull` before writing and `git_commit`+`git_push` after
- Operations supported in this bubble: `save_note` and `delete_note` only

---

## 1. Context

**Feature:** TRD Section 4 (Child Workflows — WriteVaultWorkflow), Section 4.5 (Queue Configuration)
**Depends On:** S04 (Vault I/O Activities), S05 (Git Operations Activities)
**Current State:** ReadVaultWorkflow implemented (S07). All Activities available.
**Target State:** `WriteVaultWorkflow` implemented on a dedicated single-concurrency queue, with a passing load test proving sequential execution under parallel demand.

---

## 2. Input

- `apps/vault_worker/activities/vault_io.py`
- `apps/vault_worker/activities/git_ops.py`
- `packages/shared/models.py` — `VaultNote`
- `packages/shared/workflow_names.py` — `QUEUE_MUTATION`

---

## 3. Required Output

- [ ] `apps/vault_worker/workflows/write_vault.py` — `WriteVaultWorkflow`
- [ ] `tests/e2e/test_write_vault_workflow.py` — including sequential-guarantee load test

**Workflow interface:**

```python
@dataclass
class WriteOperation:
    op: Literal["save", "delete"]
    path: str
    note: VaultNote | None = None  # required for "save"

@dataclass
class WriteVaultInput:
    vault_path: str
    operations: list[WriteOperation]
    commit_message: str

@workflow.defn
class WriteVaultWorkflow:
    @workflow.run
    async def run(self, input: WriteVaultInput) -> str: ...  # returns commit SHA
```

---

## 4. Acceptance Criteria

- [ ] A `save` operation writes the file; a subsequent `read_note` Activity call returns the saved content
- [ ] A `delete` operation removes the file; a subsequent `read_note` returns `None`
- [ ] `git_pull` is always called before write operations
- [ ] `git_commit` and `git_push` are always called after all operations complete
- [ ] **Sequential guarantee:** Fire 10 simultaneous `WriteVaultWorkflow` requests using a timed mock `save_note` activity (sleeps 0.1s). Capture total elapsed time with `time.monotonic()` *outside* `asyncio.gather()`. Assert elapsed > 0.9s — if the queue serialises correctly, 10 × 0.1s ≈ 1.0s; if they run in parallel (broken), elapsed ≈ 0.1s. Also assert all 10 complete without error.
- [ ] An empty `operations` list results in no file changes and no git commit

---

## 5. Scope Boundary

**May modify:** `apps/vault_worker/workflows/write_vault.py`, `tests/e2e/test_write_vault_workflow.py`, `apps/vault_worker/worker.py` (to register the mutation-queue worker)
**Must not modify:** `apps/vault_worker/workflows/read_vault.py`, Activity files, `packages/shared/`

---

## 6. TDD Constraints

- Write the sequential-guarantee load test FIRST — before any implementation. It will fail immediately (workflow not defined) but the test logic must be correct
- The load test is the most important test in this bubble; do not defer it
- Commit the test before implementation so the failure is captured in git history

---

## 7. Step-by-Step Plan

1. Write the full `test_write_vault_workflow.py` including the 10-concurrent-writes load test. Commit (failing).
2. Define `WriteOperation`, `WriteVaultInput` dataclasses in `apps/vault_worker/workflows/write_vault.py`.
3. Implement `WriteVaultWorkflow.run`: pull → iterate operations → push → return SHA.
4. In `apps/vault_worker/worker.py`, register a second `Worker` instance on `QUEUE_MUTATION` with `max_concurrent_workflow_tasks=1, max_concurrent_activities=1`.
5. Run individual save/delete tests — pass.
6. Run the 10-concurrent-writes load test — pass and verify serialisation.
7. Commit.

---

## 8. Reference Material

### WriteVaultWorkflow skeleton

```python
# apps/vault_worker/workflows/write_vault.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.vault_worker.activities.vault_io import save_note, delete_note
    from apps.vault_worker.activities.git_ops import git_pull, git_commit, git_push
    from packages.shared.models import VaultNote


@dataclass
class WriteOperation:
    op: Literal["save", "delete"]
    path: str
    note: VaultNote | None = None  # required when op == "save"


@dataclass
class WriteVaultInput:
    vault_path: str
    operations: list[WriteOperation]
    commit_message: str


@workflow.defn
class WriteVaultWorkflow:
    @workflow.run
    async def run(self, input: WriteVaultInput) -> str:
        if not input.operations:
            return ""  # No-op: empty operations → no pull, no commit

        await workflow.execute_activity(
            git_pull,
            args=[input.vault_path],
            schedule_to_close_timeout=timedelta(minutes=5),
        )

        for op in input.operations:
            if op.op == "save":
                assert op.note is not None
                await workflow.execute_activity(
                    save_note,
                    args=[input.vault_path, op.path, op.note],
                    schedule_to_close_timeout=timedelta(minutes=1),
                )
            elif op.op == "delete":
                await workflow.execute_activity(
                    delete_note,
                    args=[input.vault_path, op.path],
                    schedule_to_close_timeout=timedelta(minutes=1),
                )

        sha = await workflow.execute_activity(
            git_commit,
            args=[input.vault_path, input.commit_message],
            schedule_to_close_timeout=timedelta(minutes=1),
        )
        await workflow.execute_activity(
            git_push,
            args=[input.vault_path],
            schedule_to_close_timeout=timedelta(minutes=5),
        )
        return sha
```

### Mutation-queue Worker registration

```python
# apps/vault_worker/worker.py
write_worker = Worker(
    client,
    task_queue=QUEUE_MUTATION,
    workflows=[WriteVaultWorkflow],
    activities=[save_note, delete_note, git_pull, git_commit, git_push],
    max_concurrent_workflow_tasks=1,
    max_concurrent_activities=1,
)
```

### Sequential guarantee load test

The serialisation test uses mock activities registered under the **same names** as the real ones (via `@activity.defn(name=...)`). `WriteVaultWorkflow` calls activities by name, so it picks up the mocks transparently — no changes to the workflow code.

`t0` is captured **outside** `asyncio.gather()` to measure true wall-clock elapsed time across all 10 executions. If the queue serialises correctly, elapsed ≈ 10 × 0.1s = 1.0s. If Temporal runs them in parallel (broken), elapsed ≈ 0.1s.

**Test-env accommodations (do not leak into production Worker config — see TRD §4.5):**

- **Client:** Use a `pydantic_client` fixture (Client wrapped with `pydantic_data_converter` — same pattern S07 uses). `VaultNote.path` is a `pathlib.Path`, which the default converter cannot round-trip (see S07 LEARNINGS 2026-04-16).
- **`max_cached_workflows=0` on the test Worker:** The SDK requires `max_concurrent_workflow_tasks ≥ 2` when `max_cached_workflows` is nonzero (default 1000). Setting `max_cached_workflows=0` on the test Worker avoids a cache-slot / task-slot deadlock under 10 concurrent gathers. The production Worker runs against a real Temporal server (not the time-skipping test harness) and keeps the default cache — do not change TRD §4.5.
- **`activity_executor=ThreadPoolExecutor(...)`:** Required because `save_note`, `delete_note`, and `git_*` are sync `def` (S03 LEARNINGS). The `max_workers` must be ≥ `max_concurrent_activities` (here: 1).

```python
import asyncio, time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
import pytest_asyncio
from temporalio import activity
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker
from packages.shared.models import VaultNote, Frontmatter
from packages.shared.workflow_names import QUEUE_MUTATION

# Mock activities with the same registered names as the real implementations.
# WriteVaultWorkflow dispatches by name, so these are picked up transparently.

@activity.defn(name="save_note")
def timed_save_note(vault_root: str, path: str, note: VaultNote) -> None:
    """Sleeps 0.1s to make serialisation mathematically measurable."""
    time.sleep(0.1)

@activity.defn(name="git_pull")
def noop_git_pull(vault_path: str) -> None: pass

@activity.defn(name="git_commit")
def noop_git_commit(vault_path: str, message: str) -> str: return "fake-sha"

@activity.defn(name="git_push")
def noop_git_push(vault_path: str) -> None: pass

SERIALISATION_TEST_ACTIVITIES = [
    timed_save_note, noop_git_pull, noop_git_commit, noop_git_push
]


# Fixture — VaultNote.path is pathlib.Path; default converter can't round-trip it.
@pytest_asyncio.fixture
async def pydantic_client(temporal_client):
    return Client(
        service_client=temporal_client.service_client,
        namespace=temporal_client.namespace,
        data_converter=pydantic_data_converter,
    )


async def test_sequential_writes_serialise_under_load(pydantic_client, tmp_path):
    """Prove the vault-mutation-queue serialises concurrent WriteVaultWorkflow requests.

    Each write includes a 0.1s timed mock activity.
    Serial execution (correct): total elapsed ≥ 1.0s
    Parallel execution (broken): total elapsed ≈ 0.1s
    """
    vault = tmp_path / "vault"
    vault.mkdir()

    note = VaultNote(path=Path("note.md"), frontmatter=Frontmatter(title="T"), body="b")

    async with Worker(
        pydantic_client,
        task_queue=QUEUE_MUTATION,
        workflows=[WriteVaultWorkflow],
        activities=SERIALISATION_TEST_ACTIVITIES,
        max_concurrent_workflow_tasks=1,
        max_concurrent_activities=1,
        max_cached_workflows=0,  # test-env only; see "Test-env accommodations" above
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        t0 = time.monotonic()  # Outside gather — measures true total wall-clock time
        await asyncio.gather(*[
            pydantic_client.execute_workflow(
                WriteVaultWorkflow.run,
                WriteVaultInput(
                    vault_path=str(vault),
                    operations=[WriteOperation(op="save", path=f"note_{i}.md", note=note)],
                    commit_message=f"write {i}",
                ),
                id=f"write-serial-{i}",
                task_queue=QUEUE_MUTATION,
            )
            for i in range(10)
        ])
        elapsed = time.monotonic() - t0

    # Serial: ≥ 1.0s. Parallel (broken queue): ≈ 0.1s.
    assert elapsed > 0.9, (
        f"Writes appear to have run in parallel (elapsed {elapsed:.2f}s). "
        "Check vault-mutation-queue max_concurrent_workflow_tasks=1 is set."
    )
```
