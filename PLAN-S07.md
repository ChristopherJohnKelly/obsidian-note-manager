# PLAN-S07 — ReadVaultWorkflow (signal-with-reply revision)

Implements the revised bubble at `bubbles/OBSE-P5-S07-read-vault-workflow.md`.
Prior attempts failed because the spec mandated `mgr.execute_update(...)`
which does not exist on `ExternalWorkflowHandle`. Spec now uses a
request-Signal + reply-Signal pattern; this plan follows that.

## Test sequence

TDD order — write every test first, confirm all fail, then implement.

1. **test_dispatches_and_waits_for_ack**: start `VaultManagerStub` on ID `vault-manager`, run `ReadVaultWorkflow` with `context_code="TEST-P01"`, assert `result.skeleton` is non-empty and `stub_handle.query(VaultManagerStub.call_count) == 1`. Proves dispatch + ack roundtrip.
2. **test_workflow_fails_if_ack_never_arrives**: do NOT start the stub; invoke `ReadVaultWorkflow` with a short (e.g. 3s) `_SYNC_TIMEOUT` override, assert `WorkflowFailureError` wrapping `TimeoutError`. Proves fail-fast.
3. **test_returns_non_empty_code_registry**: normal happy path, assert `result.code_registry` non-empty string.
4. **test_related_notes_filtered_by_context_code_folder**: assert every `note.path` in `result.related_notes` starts with the TEST-P01 folder prefix.
5. **test_multiple_concurrent_reads_each_get_their_own_ack**: 5 concurrent `ReadVaultWorkflow` executions; assert all complete, all have non-empty skeleton, and `stub.call_count == 5`. Proves reply routing works per caller.

## Implementation sequence

1. **Prepare step branch.** Reset `step/OBSE-P5-S07-read-vault-workflow` to the current `feat/OBSE-P5-temporal-soa-migration` HEAD (drops the dual-handler / signal-workaround cruft from prior attempts). Carry `PLAN-S07.md` forward.
2. **Update `packages/shared/workflow_names.py`:** remove `UPD_ENSURE_SYNCED`; add `SIG_ENSURE_SYNCED = "ensure_synced"` and `SIG_SYNC_ACK = "sync_ack"`.
3. **Write `tests/e2e/test_read_vault_workflow.py`** with `VaultManagerStub` (signal handler only — **no** `@workflow.update`, **no** dual registration) and the five tests above. Confirm all fail with "workflow not defined"-style errors.
4. **Write `apps/vault_worker/workflows/read_vault.py`:**
   - `ReadVaultInput` dataclass (`vault_path`, `context_code`)
   - `ReadVaultWorkflow` with: `__init__` sets `self._synced = False`; `@workflow.signal(name=SIG_SYNC_ACK)` flips `_synced`; `@workflow.run` signals `SIG_ENSURE_SYNCED` to `VAULT_MANAGER_ID` carrying `workflow.info().workflow_id`, then `workflow.wait_condition(lambda: self._synced, timeout=self._SYNC_TIMEOUT)`, then activity chain: `get_skeleton` → `get_code_registry` → `read_note` (root) → `list_notes_in` → `read_note` for each related.
   - No debug prints. No state beyond `_synced`. `_SYNC_TIMEOUT = timedelta(minutes=5)` as a class attribute so tests can override via monkeypatch.
5. **Run `pytest tests/e2e/test_read_vault_workflow.py -v --tb=short` ONCE.** Wait for completion (≤2 min). Fix failures, re-run once. Do not relaunch concurrently.
6. **Run full coverage suite:** `pytest --cov=apps --cov=packages`. Confirm ≥90% threshold and no regressions in S01–S06 tests.
7. **Append LEARNINGS.md:** note that S09 `VaultManagerWorkflow` must implement the `SIG_ENSURE_SYNCED` handler (do sync logic, signal `SIG_SYNC_ACK` back to requester).
8. **Commit on step branch; open PR against feature branch.** Keep the commit free of debug scaffolding and exploration tests.

## Known risks

- **Temporal sandbox determinism**: use an instance attribute (`self._synced`) for the ack flag. A module-level global would break replay determinism and cause sandbox warnings.
- **Sandbox import warnings** when importing activities into the workflow module: wrap in `with workflow.unsafe.imports_passed_through():` only if it blocks anything. Non-fatal warnings are acceptable — don't rabbit-hole on them.
- **Path serialization**: `VaultNote.path: Path` does not round-trip through the default data converter and caused hangs in S07 attempt 1. Use `pydantic_data_converter` on the test client (same `pydantic_client` fixture pattern the prior attempt landed on — replicate it cleanly, single-purpose).
- **Negative-test timeout tuning**: `test_workflow_fails_if_ack_never_arrives` must override `_SYNC_TIMEOUT` to ~3s via monkeypatch or subclass, otherwise the test sits for 5 minutes. Keep production default at 5 minutes.
- **Concurrent reads**: manager processes signal handlers sequentially on its single-threaded event loop, so `call_count += 1` is race-safe. Reply signals target distinct `workflow_id`s, so no crosstalk. No extra coordination needed.
- **Activity signature drift**: before writing the workflow, run `grep "@activity.defn" apps/vault_worker/activities/*.py` to confirm current `get_skeleton` / `get_code_registry` / `read_note` / `list_notes_in` signatures match what the tests pass.
- **Rabbit-hole pattern** (from `LEARNINGS.md`): if I find myself writing `test_explore_*`, `test_debug_*`, or `test_inline_*` files, stop and re-read the bubble. Committed tests only.

## External dependencies

- None. The SDK-capability question that blocked prior attempts is already answered in the revised bubble (`ExternalWorkflowHandle` has `.signal()` + `.cancel()` only). No Context7 lookup required.

## Pre-PR verification checklist

- [ ] No `print()` in `read_vault.py` or the test file
- [ ] No `@workflow.update` handler anywhere in the test file
- [ ] No `test_explore_*` / `test_debug_*` / `test_inline_*` files
- [ ] `SIG_ENSURE_SYNCED` + `SIG_SYNC_ACK` added; `UPD_ENSURE_SYNCED` removed
- [ ] All 5 tests pass in a single clean `pytest` run
- [ ] Full suite coverage ≥ 90%
- [ ] `LEARNINGS.md` appended with the S09 handshake contract note
