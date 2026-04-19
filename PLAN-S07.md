# PLAN-S07 — ReadVaultWorkflow (Update-via-activity, TRD-aligned)

Implements the bubble at `bubbles/OBSE-P5-S07-read-vault-workflow.md`.

Prior attempts failed because:
- v1/v2 called `mgr.execute_update(...)` on an `ExternalWorkflowHandle`, which
  does not exist on the Python SDK.
- v3 redrafted the bubble to Signal-with-reply, diverging from TRD §4.6/§7.4,
  and serena rejected it ("uses signal instead of Update").

This plan uses the sanctioned Temporal pattern: an **activity shim** that holds
a Temporal `Client` and calls `execute_update` on `vault-manager`. The workflow
blocks on the activity; Update semantics are preserved.

## Test sequence

TDD order — write every test first, confirm all fail, then implement.

1. **test_dispatches_update_and_waits_for_completion**: start `VaultManagerStub`
   on ID `vault-manager` (with `@workflow.update(name=UPD_ENSURE_SYNCED)`), run
   `ReadVaultWorkflow`, assert `result.skeleton` non-empty and
   `stub_handle.query(call_count) == 1`. Proves Update dispatch + completion.
2. **test_workflow_fails_when_ensure_synced_update_raises**: start
   `FailingVaultManagerStub` whose Update raises
   `ApplicationError(non_retryable=True)`; assert `WorkflowFailureError` from
   `execute_workflow`. Proves failure propagation — do NOT proceed with reads
   against an unsynchronised vault.
3. **test_returns_non_empty_code_registry**: happy path, assert
   `result.code_registry` non-empty string.
4. **test_related_notes_filtered_by_context_code_folder**: assert every
   `note.path` in `result.related_notes` starts with the TEST-P01 folder prefix.
5. **test_multiple_concurrent_reads_each_dispatch_update**: 5 concurrent
   `ReadVaultWorkflow` runs; assert all complete, all non-empty skeleton, and
   `stub.call_count == 5`. Proves activity-level concurrency is safe.

## Implementation sequence

1. **Restore `packages/shared/workflow_names.py`:** ensure
   `UPD_ENSURE_SYNCED = "ensure_synced"` under Update names; remove any
   `SIG_ENSURE_SYNCED` / `SIG_SYNC_ACK` from prior attempts.
2. **Write `apps/vault_worker/activities/vault_manager_client.py`:**
   module-level `_client` + `configure_client(client)` injector, plus
   `@activity.defn async def ensure_vault_synced(manager_id: str) -> None`
   that calls
   `await client.get_workflow_handle(manager_id).execute_update(UPD_ENSURE_SYNCED)`.
3. **Write `tests/e2e/test_read_vault_workflow.py`:** the 5 tests above.
   `VaultManagerStub` declares `@workflow.update(name=UPD_ENSURE_SYNCED)` only
   — **no** `@workflow.signal`, **no** dual registration. Extend the
   `pydantic_client` fixture to call `configure_client(client)` on setup and
   `configure_client(None)` on teardown. Register `ensure_vault_synced` in
   `_read_activities()`.
4. **Write `apps/vault_worker/workflows/read_vault.py`:**
   - `ReadVaultInput` dataclass (`vault_path`, `context_code`)
   - `ReadVaultWorkflow` with a single `@workflow.run` that first awaits
     `workflow.execute_activity(ensure_vault_synced, args=[VAULT_MANAGER_ID], start_to_close_timeout=timedelta(minutes=5))`
     then runs the activity chain:
     `get_skeleton` → `get_code_registry` → `read_note` (root) →
     `list_notes_in` → `read_note` for each related (skip root).
   - No signal handlers, no `_synced` flag, no `_SYNC_TIMEOUT`.
   - No debug prints.
5. **Run `pytest tests/e2e/test_read_vault_workflow.py -v --tb=short`.**
   Fix failures. Keep the loop tight; avoid `test_explore_*` / `test_debug_*`.
6. **Run full coverage suite:** `pytest --cov=apps --cov=packages`.
   Confirm ≥90% threshold and no regressions in S01–S06 tests.
7. **Append LEARNINGS.md:** note (a) the Update-via-activity pattern as the
   sanctioned workaround for SDK-missing cross-workflow Update; (b) S09 must
   implement `@workflow.update(name=UPD_ENSURE_SYNCED)` (pull-if-stale logic).
8. **Commit on step branch; open PR against feature branch.** Commit clean —
   no debug scaffolding, no exploration tests.

## Known risks

- **Activity client binding**: the activity module holds a process-global
  `_client`. Tests must call `configure_client(pydantic_client)` in the
  `pydantic_client` fixture and reset it on teardown — otherwise test order
  determines pass/fail. Production wires the real worker's Client in
  startup code (future step).
- **Path serialization**: `VaultNote.path: Path` does not round-trip through
  the default data converter and caused hangs in prior attempts. Use
  `pydantic_data_converter` on the test Client (`pydantic_client` fixture
  replicates the prior attempt's working pattern).
- **Activity is `async def`**: Temporal runs async activities on the Worker's
  event loop directly (no ThreadPoolExecutor needed for that activity), but
  existing sync activities still require the `activity_executor` parameter.
  Keep the ThreadPoolExecutor on the Worker; it coexists fine with the async
  activity.
- **Update failure surface**: when the Update handler raises
  `ApplicationError(non_retryable=True)`, the activity sees the exception,
  fails, and the workflow fails. When the manager workflow is not running at
  all, the activity sees an RPC error (workflow not found). In the current
  negative test we target the former (well-defined contract); we don't need
  to test the latter because it's an ops concern, not a workflow contract.

## External dependencies

- None. The activity-shim pattern is standard Temporal usage; no Context7
  lookup required.

## Pre-PR verification checklist

- [ ] No `print()` in `read_vault.py`, `vault_manager_client.py`, or the test file
- [ ] `VaultManagerStub` has `@workflow.update(name=UPD_ENSURE_SYNCED)` and **no** `@workflow.signal(name=...)` for `ensure_synced`
- [ ] `FailingVaultManagerStub` declared and used in the failure test
- [ ] No `test_explore_*` / `test_debug_*` / `test_inline_*` files
- [ ] `UPD_ENSURE_SYNCED` present in `workflow_names.py`; no `SIG_ENSURE_SYNCED`/`SIG_SYNC_ACK` leftover
- [ ] `ensure_vault_synced` activity registered on every test Worker
- [ ] All 5 tests pass in a single clean `pytest` run
- [ ] Full suite coverage ≥ 90%
- [ ] `LEARNINGS.md` appended with the activity-shim lesson + S09 handshake contract note
