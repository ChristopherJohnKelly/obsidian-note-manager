# PLAN-S08 — WriteVaultWorkflow (manual-steering revision)

Implements the bubble at `bubbles/OBSE-P5-S08-write-vault-workflow.md`.
Ralph attempted this 4 times; all timed out under the session watchdog.
Root cause was orchestration (concurrent pytest spawn loop), not scope.
The previous step branch already contains a workflow + test file that are
~80% correct — this plan rebases that material and fixes the four
specific issues called out in `FAILURE-S08.md`.

## Test sequence

TDD order — confirm all tests fail (or assert wrongly) before implementing fixes.

1. **test_save_operation_writes_file**: single `WriteOperation(op="save", ...)`; assert file exists at `tmp_path / "x.md"` after workflow completes and contains expected body. Per-test UUID queue.
2. **test_delete_operation_removes_file**: pre-create file via real `save_note`, then run workflow with `WriteOperation(op="delete", ...)`; assert file gone. **Per-test UUID queue** (currently uses `QUEUE_MUTATION` — must change).
3. **test_empty_operations_list_no_changes_no_commit**: workflow with `operations=[]`; assert returns `""` (empty SHA), assert no `git_commit` was called via recording mock. **Per-test UUID queue** (currently uses `QUEUE_MUTATION` — must change).
4. **test_git_pull_called_before_writes**: recording-mock activities collect `call_order: list[str]`; assert `call_order[0] == "git_pull"` and at least one `save_note:*` follows. Per-test UUID queue.
5. **test_git_commit_and_push_called_after_operations**: same recording-mock pattern; assert `call_order[-2:] == ["git_commit", "git_push"]`. Per-test UUID queue.
6. **test_sequential_writes_serialise_under_load**: bubble §4 bullet 5 verbatim. Fire 10 concurrent `WriteVaultWorkflow` requests using a timed mock `save_note` (sleeps 0.1s); `assert elapsed > 0.9s`. **Must use `task_queue=QUEUE_MUTATION`** (currently uses uuid — must change). This is the one test that proves the production queue's `max_concurrent_*=1` config serialises writes.

## Implementation sequence

1. **Rebase step branch onto `feat/OBSE-P5-temporal-soa-migration` HEAD.** The existing material (`apps/vault_worker/workflows/write_vault.py`, `tests/e2e/test_write_vault_workflow.py`, two-worker `apps/vault_worker/worker.py`) is mostly correct and worth keeping. Resolve any conflicts cleanly.
2. **Verify VM is clean before any pytest run:** `ps aux | grep -E "pytest|temporal" | grep -v grep`. If any orphans exist, `pkill -f "pytest tests/" ; pkill -f temporalite` and re-check.
3. **Verify real activity signatures** before touching mocks: `grep "@activity.defn" apps/vault_worker/activities/*.py`. Confirmed shapes (do not drift in mocks):
   - `save_note(vault_root: str, path: str, note: VaultNote) -> None`
   - `delete_note(vault_root: str, path: str) -> None`
   - `git_pull(vault_path: str) -> None`
   - `git_commit(vault_path: str, message: str) -> str`
   - `git_push(vault_path: str) -> None`
4. **Clean up `apps/vault_worker/workflows/write_vault.py`:** remove the four leftover `workflow.logger.info(...)` debug calls (lines 60, 72, 85, 93, 104, 112 in the current file). Keep workflow logic as-is — empty-ops short-circuit → `git_pull` → for each op `save_note`/`delete_note` → `git_commit` → `git_push` → return SHA.
5. **Fix queue naming in `tests/e2e/test_write_vault_workflow.py`:**
   - `test_delete_operation_removes_file`: change `task_queue=QUEUE_MUTATION` → per-test UUID
   - `test_empty_operations_list_no_changes_no_commit`: change `task_queue=QUEUE_MUTATION` → per-test UUID
   - `test_sequential_writes_serialise_under_load`: change `f"load-test-{uuid.uuid4().hex}"` → `QUEUE_MUTATION`. The whole point of this test is proving the production queue serialises.
6. **Fix the no-op tests** (`test_git_pull_called_before_writes`, `test_git_commit_and_push_called_after_operations`): the prior attempt already replaced `pass` with real recording-mock assertions — verify those assertions exist and are not commented out. If the recording-mock activities have leftover `print(...)` debug statements, remove them.
7. **Run `pytest tests/e2e/test_write_vault_workflow.py -v --tb=short` ONCE.** Wait for completion (≤5 min). Do not relaunch concurrently. If still running after 5 min, use `Read` on the output file — never start a parallel pytest.
8. **Fix any genuine failures.** Re-run **once**. Maximum 2 pytest invocations total in any iteration.
9. **Run full coverage suite:** `pytest --cov=apps --cov=packages --cov-fail-under=90`. Confirm ≥90% threshold and no regressions in S01–S07 tests.
10. **Append `LEARNINGS.md`** with the post-mortem note: pytest-orchestration discipline (one at a time), `Monitor`-spawns-fresh-process gotcha, and confirmation that the `max_concurrent_*=1` worker config + `QUEUE_MUTATION` is the actual serialisation guarantee being asserted.
11. **Commit on step branch; open PR against feature branch.** Body should reference FAILURE-S08.md issues 1–4 and confirm each is fixed.

## Known risks

- **Path serialization**: `VaultNote.path: Path` does not round-trip through the default data converter. Use `pydantic_data_converter` on the test client via the `pydantic_client` fixture (already established in S07). Without it, `save_note` activities silently hang.
- **Activity signature drift in mocks**: Temporal matches activities by `name=`, but the function signature must match what the workflow passes. A drifted mock causes silent non-execution that looks like a workflow hang. Re-grep before writing.
- **`activity_executor=ThreadPoolExecutor`**: all `save_note` / `delete_note` / `git_*` activities are sync `def`. Worker must pass `activity_executor=ThreadPoolExecutor(max_workers=2)` or sync activities will not run. The current worker code does this correctly — preserve when rebasing.
- **Load test queue is non-negotiable**: `QUEUE_MUTATION` is the only queue with `max_concurrent_workflow_tasks=1` + `max_concurrent_activities=1` configured on the worker. A uuid queue gets default concurrency and the serialisation assertion becomes meaningless. Per-test UUID for everything *except* the load test.
- **Pytest orchestration discipline (the actual root cause of all 4 prior failures)**: never run more than one pytest at a time. `Monitor` starts a NEW process on every call — never use it to "check on" a running pytest. To check status of a `Bash run_in_background=true` job, `Read` the output-file path that the tool returned. To check status of a `Monitor` job, wait for events; use `TaskGet` for status. If unsure what is running: `ps aux | grep pytest | grep -v grep`, `pkill -f "pytest tests/"` before starting a new run.
- **Don't pipe long-running pytest to `| head` or `| tail`**: under `pipefail` this can SIGPIPE the producer and lose output. Always: `pytest ... > /tmp/pytest.out 2>&1` then `tail -80 /tmp/pytest.out` after completion.
- **Expected duration**: clean `pytest tests/e2e/test_write_vault_workflow.py -v` is 2–3 min on this VM (5 min worst case). The full coverage suite is 5–8 min. Be patient — premature relaunches were the failure mode.
- **Rabbit-hole pattern** (from S07 LEARNINGS): if I find myself writing `test_explore_*`, `test_debug_*`, or `test_inline_*` files, stop and re-read the bubble. Committed tests only.

## External dependencies

- None. All Temporal SDK behaviours used here (sync activities via `ThreadPoolExecutor`, `pydantic_data_converter`, `max_concurrent_*=1` for serialisation) are already proven in merged S04/S05/S06 work.

## Pre-PR verification checklist

- [ ] No `workflow.logger.info(...)` debug calls in `write_vault.py`
- [ ] No `print()` in `write_vault.py` or the test file
- [ ] No `pass`-body tests; no `test_explore_*` / `test_debug_*` / `test_inline_*` files
- [ ] `test_sequential_writes_serialise_under_load` uses `task_queue=QUEUE_MUTATION`, 10 ops, 0.1s sleep, `assert elapsed > 0.9s`
- [ ] `test_delete_operation_removes_file` and `test_empty_operations_list_no_changes_no_commit` use per-test UUID queues
- [ ] All mock activity signatures match the real `@activity.defn` signatures verified in step 3
- [ ] All 6 tests pass in a single clean `pytest tests/e2e/test_write_vault_workflow.py -v` run
- [ ] Full coverage suite passes with `--cov-fail-under=90` and no S01–S07 regressions
- [ ] `LEARNINGS.md` appended with pytest-orchestration discipline note
