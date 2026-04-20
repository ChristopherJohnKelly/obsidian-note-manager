# FAILURE-S09 — Corrective Guidance (READ FIRST, before touching any file)

This is an operator-seeded reseed. The previous 5 attempts failed for a reason
cc-ralph never diagnosed. The attempt counter has been reset to 0; this is a
clean retry with explicit steering.

## The actual bug (was never in the workflow)

Every failed attempt got stuck on an e2e test that asserted the workflow's
status *immediately* after `start_workflow()` returned. That assertion fails
with:

    AssertionError: assert 'initialising' == 'ready'

That error is a **test-writing bug**, not a workflow bug.

`client.start_workflow()` returns as soon as Temporal accepts and schedules
the workflow. It does **not** wait for any activity to run. The workflow
correctly transitions `initialising → ready` only *after*
`check_vault_dir_state` and `git_clone`/`git_pull` complete — which takes
real wall-clock time in e2e.

**The fix is in the test, not the workflow.** Every test that checks
post-startup state must poll `get_sync_status` until `status == "ready"`
before asserting anything else.

## Prior attempts — DO NOT REPEAT

| # | What cc-ralph did                                                    | Why it was wrong                                                                   |
|---|----------------------------------------------------------------------|------------------------------------------------------------------------------------|
| 1 | Rewrote `vault_manager.py` 8× chasing the assertion                  | Workflow is correct; bubble §8 is the canonical shape. Rewrites burned the budget. |
| 2 | Changed `@workflow.update ensure_synced` from `async def` to `def`   | Update handler body awaits `execute_activity` — must stay `async def`.             |
| 3 | Spin loop on the same failing test, same diagnosis                   | Never questioned the premise. If the same assertion fails twice, the test is wrong. |
| 4 | Edited a hyphenated path (`apps/vault-worker/`)                      | That directory was removed in S17. Canonical path is `apps/vault_worker/`.         |
| 5 | Added `print(...)` inside `@workflow.run`                            | Non-deterministic — forbidden in workflow code. Use `workflow.logger` only.        |

## The fix pattern (mirror the bubble's §8 worker-startup polling into tests)

Add a helper at the top of `tests/e2e/test_vault_manager_workflow.py`
(or, if reused across files, a new `tests/e2e/conftest.py` — NOT
`tests/conftest.py`, which is read-only per §5 Scope Boundary):

```python
import asyncio

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
```

Every startup-branch test follows this shape:

```python
async def test_vault_manager_startup_empty_branch(local_bare_repo, tmp_path, ...):
    # 1. Start workflow with empty vault_path
    await env.client.start_workflow(
        VaultManagerWorkflow.run,
        VaultManagerInput(vault_path=str(tmp_path / "vault"), repo_url=..., pat=...),
        id="vault-manager",
        task_queue=QUEUE_DEFAULT,
    )
    handle = env.client.get_workflow_handle("vault-manager")

    # 2. MUST wait for ready before asserting state
    status = await wait_ready(handle)
    assert status["status"] == "ready"
    assert status["last_synced"] is not None

    # 3. Only now assert downstream effects (filesystem, activity calls, etc.)
    assert (tmp_path / "vault" / ".git").exists()
```

For the `"invalid"` fatal-error branch: there is no `ready` to wait for.
Instead, expect `WorkflowFailureError` with an `ApplicationError` cause when
you query or try to observe completion. Poll briefly for the failure, or use
`handle.result()` with a short timeout — pick whichever the Temporal Python
SDK offers that works here; do NOT just query once and assume it'll be
`ready` or already-failed.

## Hard rules (auto-reject if violated)

1. **Do not rewrite `apps/vault_worker/workflows/vault_manager.py` beyond what
   bubble §8 specifies.** If you've edited it more than twice in one session
   without a test shape changing, STOP and re-read this file.
2. **`@workflow.update` handlers stay `async def`** whenever the body awaits.
3. **No `print`, `datetime.now()`, `Path(...)`, `os.*` inside
   `@workflow.run` / `@workflow.update` / `@workflow.query`.** Use
   `workflow.now()`, `workflow.logger`, and delegate filesystem work to
   `check_vault_dir_state`.
4. **Do not touch `apps/vault-worker/`** — deleted in S17. Canonical path is
   `apps/vault_worker/`.
5. **Do not modify** `tests/conftest.py`, `packages/shared/`, or existing
   Activity files (bubble §5 Scope Boundary).

## Self-escalation heuristic

If after **two attempts** the same test still fails with
`'initialising' == 'ready'` (or any variant of "workflow not at expected
state immediately after start"), you are on the wrong track. Write:

    IMPLEMENTATION:BLOCKED:test-polling-not-applied:<test_name>

and exit. Do **not** add `asyncio.sleep()` without a deadline, do **not**
add `pytest.skip`, do **not** rewrite the workflow. Escalating is the
correct move — this file will be updated with more steering.

---
