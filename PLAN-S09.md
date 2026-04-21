# PLAN-S09 — VaultManagerWorkflow

## Test sequence
1. `test_check_vault_dir_state`: asserts `check_vault_dir_state` activity returns `"empty"` when vault_path does not exist or is empty directory; returns `"valid_repo"` when `.git` directory exists; returns `"invalid"` when directory non-empty without `.git`.
2. `test_vault_manager_startup_empty_branch`: workflow reaches `ready` status after calling `git_clone` activity; `get_sync_status` returns `last_synced` timestamp.
3. `test_vault_manager_startup_valid_repo_branch`: workflow reaches `ready` after calling `git_pull` activity; `last_synced` updated.
4. `test_vault_manager_startup_invalid_branch`: workflow raises `ApplicationError` with `non_retryable=True` and human-readable message; query after start fails.
5. `test_vault_manager_ensure_synced_stale`: when `last_synced` >5 minutes ago, `ensure_synced` Update triggers `git_pull` and updates `last_synced`.
6. `test_vault_manager_ensure_synced_fresh`: when `last_synced` within 5 minutes, `ensure_synced` does NOT call `git_pull`.
7. `test_vault_manager_continue_as_new`: after `workflow.wait_condition` times out (simulated via time-skipping environment), `continue_as_new` is called with `last_synced` preserved in `VaultManagerInput`.
8. `test_vault_manager_resume_skips_startup`: when `input.last_synced` is non‑None (resuming after `continue_as_new`), workflow skips startup branch and goes directly to `ready`.
9. `test_vault_manager_update_idempotency`: two concurrent `ensure_synced` Updates queue correctly (serialised by Temporal) and each observes the expected pull/no‑pull behaviour.
10. `test_worker_startup`: `worker.py` starts `VaultManagerWorkflow` with well‑known ID `vault-manager` and polls `get_sync_status` until `status=ready` before registering the main worker.

## Implementation sequence
1. `apps/vault_worker/activities/vault_io.py`: add synchronous `def check_vault_dir_state(vault_path: str) -> str` activity per bubble §8 reference.
2. `tests/unit/test_check_vault_dir_state.py`: write unit test covering three return states.
3. `apps/vault_worker/workflows/vault_manager.py`: create file with `VaultManagerInput` dataclass and `VaultManagerWorkflow` class skeleton (empty `run`, `ensure_synced`, `get_sync_status`).
4. `tests/e2e/test_vault_manager_workflow.py`: write all acceptance test stubs (listed above) using `wait_ready` helper for polling; tests will fail initially.
5. Implement startup phase in `VaultManagerWorkflow.run`: call `check_vault_dir_state` activity; branch to `git_clone` (empty), `git_pull` (valid_repo), or raise `ApplicationError` (invalid); set `self._last_synced = workflow.now()` and `self._status = "ready"`.
6. Implement `ensure_synced` Update handler: compare `workflow.now()` with `self._last_synced` using UTC‑aware datetime; call `git_pull` if stale >5 minutes; update `last_synced`.
7. Implement `get_sync_status` Query returning `{"status": self._status, "last_synced": self._last_synced.isoformat() if self._last_synced else None}`.
8. Implement `continue_as_new` logic: `workflow.wait_condition(lambda: self._update_count >= 1000, timeout=timedelta(days=1))` then `workflow.continue_as_new` with `last_synced` preserved; resume path (non‑None `last_synced` in input) skips startup.
9. Update `apps/vault_worker/worker.py`: add `VaultManagerWorkflow` to `default_worker` workflows list; add `check_vault_dir_state` to activities list; add startup logic that starts workflow with well‑known ID and polls until `ready` before returning worker list.
10. Ensure `apps/vault_worker/activities/vault_manager_client.py` is already configured (should be from S07) and its `configure_client` is called in `worker.py` before creating workers.

## Known risks
- **Timezone naive/aware datetime comparison**: using `datetime.now()` instead of `workflow.now()` leads to non‑determinism. Mitigation: always use `workflow.now()` inside workflow code.
- **Non‑deterministic file I/O in workflow**: accidentally calling `Path` or `os` inside `@workflow.run`. Mitigation: all filesystem inspection must go through `check_vault_dir_state` activity.
- **Test polling timeout**: if workflow fails to reach `ready` due to bug, test helper `wait_ready` may hang. Mitigation: set reasonable timeout (10s) and raise descriptive `AssertionError`.
- **Continue_as_new infinite loop**: if `wait_condition` condition never triggers, workflow may never `continue_as_new`. Mitigation: ensure `self._update_count` increments on each `ensure_synced` call and timeout of 1 day is safe.
- **Activity shim mismatch**: `ensure_vault_synced` activity expects `VaultManagerWorkflow` to implement Update handler with same name. Already defined in `workflow_names.py`. Ensure handler name matches `UPD_ENSURE_SYNCED`.
- **Worker startup deadlock**: if `VaultManagerWorkflow` fails to start (invalid vault), worker startup should exit with error. Need to handle `ApplicationError` and propagate.

## External dependencies
- Context7: No — bubble §8 provides full reference implementation for `check_vault_dir_state`, `VaultManagerWorkflow`, and worker startup pattern. Temporal SDK patterns are already known from previous steps (S03, S07).