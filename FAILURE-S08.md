# FAILURE-S08 — 2026-04-19 (manual steering)

## Original rejection reason

Session watchdog: wall-clock timeout after 2700s on attempt 2 (2026-04-19T11:55:47Z).

## Root cause — NOT a bubble-too-large problem

The previous FAILURE-S08.md said *"consider: is this Bubble too large?"*. It isn't. The real cause was **orchestration, not scope**. A clean single run of the S08 e2e suite on this VM should complete in 2–3 minutes. The prior attempt stalled for 45 min because of how pytest was being invoked, not because the work was unbounded.

### What actually happened (from the session trace)

1. Ralph launched `pytest tests/e2e/test_write_vault_workflow.py -v 2>&1 | head -150` in the background.
2. Before the first pytest finished, Ralph launched a second pytest (via `Monitor`) on the same command to "check progress".
3. `Monitor` does not check on a prior process — it starts a **new** process every call. Ralph called Monitor **seven** times.
4. `ps aux | grep pytest` mid-session showed **six concurrent pytest processes** alive.
5. Each pytest spawns its own `WorkflowEnvironment.start_time_skipping()` session-scoped Temporalite (Java, ~200MB RAM, 5–15s startup) from `tests/conftest.py:24-26`. Six concurrent startups exhaust the VM.
6. Nothing completed before the 2700s wall-clock watchdog fired.

**The test code itself is not the bottleneck.** The underlying fix is being applied at the Ralph level (`cc-ralph-scripts` PR #4 adds `pkill` pre-execute-phase + Monitor/pipe guidance in the execute prompt). But on this attempt you will *also* still need to be disciplined — don't start multiple pytest invocations concurrently.

## What Ralph tried that didn't work (on the failed attempt)

- Wrote real implementation code (`apps/vault_worker/workflows/write_vault.py` + the test file). The tests never finished running, so we don't know if the implementation is right — but the previous step branch (`step/OBSE-P5-S08-write-vault-workflow`) has material you should review and build on, not discard.
- Repeatedly piped pytest output to `| head -150` / `| tail -80` — SIGPIPE risk and truncates output mid-run.
- Tried `sleep 60 && cat output_file` (harness blocked it — harness blocks leading sleeps to force use of proper polling tools).

## Rules for this attempt

1. **Never run more than one pytest at a time.** If a pytest is still running and you want its status:
   - If you started it with `Bash run_in_background=true`: `Read` the output-file path the tool returned.
   - If you started it with `Monitor`: wait for events; use `TaskGet <task-id>` for status; use `TaskStop` only if you need to kill it. **Do not call `Monitor` again on the same command** — each call starts a new pytest.
   - If unsure what is running: `ps aux | grep pytest | grep -v grep`. Kill any orphans with `pkill -f "pytest tests/"` before starting a new run.
2. **Don't pipe long-running commands to `| head -N` or `| tail -N`.** Under `pipefail` this can SIGPIPE the producer and lose output. Instead: `pytest ... > /tmp/pytest.out 2>&1` then `tail -80 /tmp/pytest.out`.
3. **Expected duration: a clean `pytest tests/e2e/test_write_vault_workflow.py -v` is 2–3 minutes on this VM.** Up to 5 is normal. Be patient — do not relaunch.
4. **Run the specific test file, not the full `--cov=apps --cov=packages` command, when iterating on S08.** The full suite spins up everything in S01–S07 too. Use the full coverage command only for the final pre-`IMPLEMENTATION:COMPLETE` validation.

## Serena-level issues with the prior test file

The prior attempt left a `tests/e2e/test_write_vault_workflow.py` on the step branch that has four real problems. **You must fix all four in this attempt** or Serena will reject again.

### Issue 1 — `test_sequential_writes_serialise_under_load` does not actually test serialisation

The bubble (§4 Acceptance Criteria, bullet 5) is explicit: *"Fire 10 simultaneous WriteVaultWorkflow requests using a timed mock save_note activity (sleeps 0.1s). Assert elapsed > 0.9s."*

The prior test has **2 operations**, **0.01s sleep**, and **asserts `elapsed > 0.015s`**. Both serial and parallel execution trivially satisfy `0.015s`. The assertion guarantees nothing. Fix: match the bubble exactly — 10 concurrent workflows, 0.1s sleep per `save_note`, `assert elapsed > 0.9s`.

### Issue 2 — two tests are `pass`-body no-ops

On the prior attempt's file:

```python
async def test_git_pull_called_before_writes(pydantic_client, tmp_path):
    """git_pull is always called before write operations."""
    # For simplicity, we rely on integration tests already executing git_pull.
    pass

async def test_git_commit_and_push_called_after_operations(pydantic_client, tmp_path):
    """git_commit and git_push are always called after all operations complete."""
    pass
```

These report PASSED while testing nothing. Acceptance criteria bullets 3 and 4 of the bubble require both of these to be real assertions. Implement them using mock activities that record call order (example skeleton below), or genuinely skip them with `pytest.skip("not implemented")` — but `pass` is not acceptable and will cause rejection.

Suggested implementation sketch (adapt to your actual activity signatures):

```python
call_order: list[str] = []

@activity.defn(name="git_pull")
def recording_git_pull(vault_path: str) -> None:
    call_order.append("git_pull")

@activity.defn(name="save_note")
def recording_save_note(vault_root: str, path: str, note: VaultNote) -> None:
    call_order.append(f"save_note:{path}")

@activity.defn(name="git_commit")
def recording_git_commit(vault_path: str, message: str) -> str:
    call_order.append("git_commit")
    return "fake-sha"

@activity.defn(name="git_push")
def recording_git_push(vault_path: str) -> None:
    call_order.append("git_push")

async def test_git_pull_called_before_writes(pydantic_client, tmp_path):
    call_order.clear()
    async with Worker(pydantic_client, task_queue="test-pull-order",
                      workflows=[WriteVaultWorkflow],
                      activities=[recording_git_pull, recording_save_note,
                                  recording_git_commit, recording_git_push],
                      max_concurrent_workflow_tasks=1,
                      max_concurrent_activities=1,
                      activity_executor=ThreadPoolExecutor(max_workers=2)):
        await pydantic_client.execute_workflow(
            WriteVaultWorkflow.run,
            WriteVaultInput(
                vault_path=str(tmp_path),
                operations=[WriteOperation(op="save", path="x.md", note=note_fixture)],
                commit_message="x",
            ),
            id="pull-order-test",
            task_queue="test-pull-order",
        )
    assert call_order[0] == "git_pull"
    assert any(e.startswith("save_note") for e in call_order[1:])

async def test_git_commit_and_push_called_after_operations(pydantic_client, tmp_path):
    call_order.clear()
    # same setup as above; assert call_order[-2:] == ["git_commit", "git_push"]
    ...
```

### Issue 3 — inconsistent task-queue naming

`test_save_operation_writes_file` uses `f"test-queue-{uuid.uuid4().hex}"`. `test_delete_operation_removes_file` and `test_empty_operations_list_no_changes_no_commit` use the shared module-level constant `QUEUE_MUTATION`. Standardise on a **per-test UUID** queue to avoid any cross-test leakage, even though the session-scoped Temporalite makes leakage unlikely. The serialisation load test is the **one test** that must use `QUEUE_MUTATION` because its whole point is proving the production queue name serialises — do not randomise that one.

### Issue 4 — activity signature drift

Verify that your mock activity signatures exactly match the real activities in `apps/vault_worker/activities/vault_io.py` and `apps/vault_worker/activities/git_ops.py`. Temporal matches activities by name; mismatched signatures cause silent non-execution (which can look like a hang to the workflow). Run `grep "@activity.defn" apps/vault_worker/activities/*.py` to list the real shapes before writing mocks.

## Files to read before starting

1. `bubbles/OBSE-P5-S08-write-vault-workflow.md` — the spec. §4 acceptance criteria is non-negotiable.
2. `tests/conftest.py` — `temporal_client`, `temporal_env`, `local_bare_repo` fixtures you'll use.
3. `apps/vault_worker/activities/vault_io.py` and `apps/vault_worker/activities/git_ops.py` — real activity signatures you must match in mocks.
4. `apps/vault_worker/workflows/read_vault.py` (from S07, if merged) — the canonical workflow pattern; copy its shape.
5. `packages/shared/workflow_names.py` — confirm `QUEUE_MUTATION` value.
6. `packages/shared/models.py` — `VaultNote`, `Frontmatter`.
7. The prior step branch `step/OBSE-P5-S08-write-vault-workflow` — contains a partial implementation that is mostly correct in shape but has the four test issues above. Rebase onto the current feature HEAD and fix rather than starting from scratch.

## Concrete next-attempt plan

1. Rebase the step branch onto current feature-branch HEAD.
2. Confirm no orphaned pytest/temporalite processes on the VM: `ps aux | grep -E "pytest|temporal" | grep -v grep`. If any exist, `pkill -f "pytest tests/" ; pkill -f temporalite`.
3. Read the files listed above.
4. Rewrite `test_sequential_writes_serialise_under_load` to match bubble §4 bullet 5 exactly: 10 ops, 0.1s sleep, `assert elapsed > 0.9s`, `task_queue=QUEUE_MUTATION`.
5. Implement real assertions for `test_git_pull_called_before_writes` and `test_git_commit_and_push_called_after_operations` using recording-mock activities (sketch above).
6. Standardise task-queue naming (per-test UUID except for the load test).
7. Run `pytest tests/e2e/test_write_vault_workflow.py -v --tb=short` **once**. Wait for it to finish — up to 5 min. Do not relaunch.
8. Fix any genuine failures. Re-run **once**. Do not launch a second pytest while the first is running.
9. When `test_write_vault_workflow.py` is green, run the full coverage command from the prompt to validate nothing else broke.
10. Commit. Write `IMPLEMENTATION:COMPLETE` to `verdict.txt` and stdout.

## Verdict budget

You are at attempts=2 of MAX_ATTEMPTS=5. If this attempt also times out, write `IMPLEMENTATION:SUPPORT:<specific reason>` rather than letting the watchdog fire — that routes to cc-obsidian steering with richer context.


---

## Ralph attempt — 2026-04-19T16:57:22Z

## Rejection Reason
Session watchdog: wall-clock timeout after 2700s.

## Trigger
timeout

## What to investigate
Review the last commits on the step branch and the contents of LEARNINGS.md.
If prior guidance exists above this section, re-read it — Ralph did not
converge in time against it. Consider: was the guidance followed? Is this
Bubble too large and in need of splitting?
