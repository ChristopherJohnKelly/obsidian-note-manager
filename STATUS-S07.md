# STATUS-S07 — Current implementation state

**As of 2026-04-19T20:25:00Z (step branch HEAD):** `ReadVaultWorkflow` satisfies
TRD §4.6 and §7.4 by dispatching the `ensure_synced` **Update** on the
long-running `VaultManagerWorkflow` (well-known ID `vault-manager`) before any
read activity runs. The Update is executed via the canonical Temporal
activity-shim pattern because the Python SDK's `ExternalWorkflowHandle` does
not expose `execute_update`.

## Where to look

- `apps/vault_worker/workflows/read_vault.py:42` — `execute_activity(ensure_vault_synced, args=[VAULT_MANAGER_ID], ...)`
- `apps/vault_worker/activities/vault_manager_client.py:60` — `await handle.execute_update(UPD_ENSURE_SYNCED)`
- `tests/e2e/test_read_vault_workflow.py:56` — stub registers `@workflow.update(name=UPD_ENSURE_SYNCED)` only (no signal handler, no dual registration)
- `bubbles/OBSE-P5-S07-read-vault-workflow.md` — bubble mandates the activity-shim pattern
- `packages/shared/workflow_names.py:24` — `UPD_ENSURE_SYNCED = "ensure_synced"`; no `SIG_ENSURE_SYNCED`

## Historical artefacts to ignore

Earlier attempts tried a "signal-with-reply" handshake instead of the Update.
Those attempts were rejected by serena and are **not** the current
implementation. Any LEARNINGS.md entries dated before 2026-04-19T20:05:46Z
that mention `SIG_ENSURE_SYNCED`, `SIG_SYNC_ACK`, or a signal handshake are
marked **[SUPERSEDED]** — treat them as history, not current guidance.

## Verification

All 208 tests pass. Coverage 92.55%. See PR #28.
