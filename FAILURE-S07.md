# FAILURE-S07 — Ralph attempt 1 (manual steering by Opus 4.7, 2026-04-17)

## Original rejection reason
Ralph (DeepSeek V3.2 on cc-ralph) spent 50+ wall-clock minutes on S07 and was
manually terminated. The committed workflow body (`apps/vault_worker/workflows/read_vault.py`
@ edc1286) is a stub that literally ends with `raise RuntimeError("stop")` —
no `ensure_synced` dispatch, no activity calls, no `VaultContext` construction.
The full test file in `tests/e2e/test_read_vault_workflow.py` is written (all
five acceptance-criteria tests + `VaultManagerStub`), but every test would
deadlock or time out against the stub. Ralph then spiralled into five
exploratory scratch tests under `tests/e2e/_scratch_s07_attempt1/` trying to
localise what it perceived as a "workflow doesn't dispatch" bug, rather than
reading the S04 LEARNING that already documents the actual blocker.

## Root cause
The `temporal_client` fixture in `tests/conftest.py:36-37` returns
`temporal_env.client` with **no `data_converter` configured** — it uses
Temporal's default JSON converter. The spec's target return type is
`VaultContext`, which contains `VaultNote` (`packages/shared/models.py:30-35`)
whose `path: Path` field is not serialisable by the default converter.
`LEARNINGS.md:24` (from S04) records this exact trap: "`VaultNote.path: Path`
is not JSON serializable with Temporal's default converter — for integration
tests returning Pydantic models with Path fields, use `list[str]` return
activities […] to avoid needing `pydantic_data_converter`". S04 side-stepped
the problem by calling `list_notes_in` (returns `list[str]`); S07 cannot
side-step because its contractual return type *is* `VaultContext`. Both the
Worker (activity result payloads) and the Client (workflow input/result
payloads) therefore need `pydantic_data_converter`. Ralph never reached this
diagnosis — its scratch tests all swap workflows, queues, and return types
without ever touching data-converter configuration.

## Concrete next-attempt instructions
1. Delete `tests/e2e/_scratch_s07_attempt1/` — those are preserved only for
   this steering analysis and must not ship.
2. Delete the stub `raise RuntimeError("stop")` body in
   `apps/vault_worker/workflows/read_vault.py` and implement
   `ReadVaultWorkflow.run` end-to-end:
   - Call `workflow.get_external_workflow_handle(VAULT_MANAGER_ID)` and
     `await mgr.execute_update(UPD_ENSURE_SYNCED)` before any read activity.
   - Execute activities in order: `get_skeleton(vault_path)` → `get_code_registry(vault_path)`
     → resolve the context-code folder (`20. Projects/{context_code}/`) via
     the registry entries → `read_note(vault_path, root_rel_path)` for the
     root note → `list_notes_in(vault_path, folder)` then `read_note` per
     entry for `related_notes`. Use `schedule_to_close_timeout=timedelta(minutes=1)`.
   - The `code_registry` field on `VaultContext` is a `str`; fold the
     `list[CodeRegistryEntry]` returned by `get_code_registry` into a
     formatted string inside the workflow (deterministic string op, allowed
     in workflow code).
   - Return a fully populated `VaultContext`.
3. In `tests/e2e/test_read_vault_workflow.py`, do **not** use
   `temporal_client` directly for the workflow calls — build a second Client
   at test scope wrapping the env's service client, with
   `data_converter=pydantic_data_converter`. Construct the `Worker` with
   that same pydantic-aware client so activity-result payloads round-trip
   cleanly.
4. Run the full e2e suite (`pytest tests/e2e/test_read_vault_workflow.py -v`)
   — all five acceptance tests must pass, including the 5-way parallel test.
5. Re-run the whole suite (`pytest`) to confirm no regression and that the
   90% coverage threshold still holds.
6. Commit only `apps/vault_worker/workflows/read_vault.py`,
   `tests/e2e/test_read_vault_workflow.py` (and the deletion of the scratch
   directory). Do not touch `tests/conftest.py`, `packages/shared/`, or any
   activity file — the scope boundary forbids it.

## Files to read before starting
- `bubbles/OBSE-P5-S07-read-vault-workflow.md` — authoritative acceptance
  criteria, scope boundary, and reference snippets (esp. section 8).
- `LEARNINGS.md:24-26` — S04 entry documenting the Path/default-converter
  trap and that `data_converter` goes on the `Client`, not the `Worker`.
- `packages/shared/models.py` — `VaultNote.path: Path` (line 33) and
  `VaultContext.{root_note,related_notes,code_registry}` (lines 55-62)
  confirm the exact serialisation surface.
- `apps/vault_worker/activities/vault_io.py` — return types of
  `get_skeleton` (str), `get_code_registry` (`list[CodeRegistryEntry]` — note:
  workflow must convert to string for `VaultContext.code_registry`),
  `read_note` (`VaultNote | None`), `list_notes_in` (`list[str]`).
- `tests/unit/test_vault_io.py:294-296` — precedent for the
  `from temporalio.contrib.pydantic import pydantic_data_converter` import.
- `tests/conftest.py:30-37` — shows exactly what the fixtures provide
  (and what they deliberately do NOT configure).
- `packages/shared/workflow_names.py` — `VAULT_MANAGER_ID`,
  `UPD_ENSURE_SYNCED`, `QUEUE_DEFAULT` constants.

## Specific symbol or interface to use
`temporalio.contrib.pydantic.pydantic_data_converter` — the canonical
Temporal SDK helper. Verified present at
`/home/claude/.local/lib/python3.12/site-packages/temporalio/contrib/pydantic.py:122`.

Use it via the `Client(service_client, *, data_converter, namespace)`
constructor (see `temporalio/client.py:233-258`). In-test pattern:

```python
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

pydantic_client = Client(
    service_client=temporal_client.service_client,
    namespace=temporal_client.namespace,
    data_converter=pydantic_data_converter,
)
# use pydantic_client for both Worker(...) and {start,execute}_workflow
```

## What Ralph tried that didn't work
(Order: inferred chronologically from content. All five files were preserved
in a single `chore:` commit 0b428a6 so filesystem timestamps don't establish
order; the sequence below reflects the natural debugging progression from
"confirm the workflow runs at all" outward.)

- `test_debug_read_vault.py` — hypothesis: `ReadVaultWorkflow` doesn't dispatch
  at all. Two variants: (a) with no `VaultManagerStub` registered, expecting
  an exception; (b) with the stub. Did not resolve because the real problem
  is not dispatch — it is that the stub'd workflow body is `raise
  RuntimeError("stop")`, so the workflow DID dispatch but then errored, and
  the surfaced error was buried under a pytest-asyncio timeout that Ralph
  interpreted as a hang.
- `test_inline_workflow.py` — hypothesis: maybe the problem is the
  `ReadVaultWorkflow` class itself. Replaced with an inline `SimpleWorkflow`
  that also `raise RuntimeError(...)`. Did not resolve because this proves
  a tautology — a workflow that raises, raises. It said nothing about the
  actual serialisation blocker.
- `test_queue_issue.py` — hypothesis: workers on `QUEUE_DEFAULT` are
  colliding with prior test workers. Switched to a `test-queue-{random}`.
  Did not resolve because queue contention was never the issue; the hang
  reproduces on any queue once the workflow's return type contains
  `VaultNote.path`.
- `test_no_activities.py` — hypothesis: maybe the activities are causing
  the hang. Built a `VaultContext` inline inside the workflow with no
  activity calls. Did not resolve — this is actually the test that was
  *closest* to exposing the Path-serialisation bug (returning a real
  `VaultContext` over the default converter), but Ralph used a fresh
  `test-queue-no-act` queue on a worker with `activities=[]`, and never
  inspected the payload failure on the return path.
- `test_string_return.py` — hypothesis: regress all the way to "does the
  Temporal test env work at all?" Returned `str`. Did not resolve because
  — predictably — strings serialise fine; this confirmed the infrastructure
  was healthy and the bug was type-specific, but Ralph did not make the
  inferential leap from "str works, VaultContext doesn't" to
  "Path field not supported by default converter".

## Recommended action
GUIDANCE. The fix is well-scoped: one workflow body + one local-Client
construction in the test file. The scope boundary forbids modifying
`tests/conftest.py`, so the pydantic-aware Client is built inside the test
file — acceptable duplication for S07, and the same shape can be reused
by S08+.

Note for the user: if future workflow-returning-Pydantic-with-Path bubbles
(S08 WriteVault, S09 VaultManager, etc.) repeat this pattern, consider a
small follow-up bubble to move `pydantic_data_converter` into the
`temporal_client` fixture in `tests/conftest.py` — that is genuinely
cross-cutting infrastructure and does not belong per-workflow. This is
not necessary to ship S07.
