# FAILURE-S08 — Ralph attempt 1 (manual steering by Opus 4.7, 2026-04-17)

## Original rejection reason
Ralph verdict: IMPLEMENTATION:BLOCKED:VaultNote serialization issue; Path
not JSON serializable with default Temporal converter.
Attempt duration: ~44 minutes (no rabbit-hole pattern this time; Ralph
identified the issue directly from S07 LEARNINGS but could not fix it).
Commit: f1d0bc7 on step/OBSE-P5-S08-write-vault-workflow.

## Relationship to S07
Same root cause class as S07 (`VaultNote.path: Path` not serialisable by
Temporal's default JSON converter), but a **separate fix site**: the
FAILURE-S07.md remedy is per-test-file (construct a local `Client` wrapping
`temporal_env.client.service_client` with `data_converter=pydantic_data_converter`)
because the scope boundary on S07 forbids touching `tests/conftest.py`.
S08's scope boundary (bubble §5) likewise forbids `packages/shared/` and
activity files, and by extension should not touch conftest either. So S08
inherits the pattern from FAILURE-S07 but must apply it independently in
`tests/e2e/test_write_vault_workflow.py`. S08 also has a slightly different
serialisation surface than S07: S07 fails on the workflow **return** path
(VaultNote inside VaultContext), whereas S08 crosses the boundary on the
workflow **input** path (VaultNote inside `WriteVaultInput.operations[].note`)
**and** on the activity-argument path (`save_note(vault_root, path, note)`).
A single `pydantic_data_converter` on the Client covers all three — Worker
inherits the converter from the Client at `Worker(client, ...)` construction.
S08 does **not** need to wait for S07 to merge; the fix is independently
applicable per-file.

## Root cause
Ralph's diff at `tests/e2e/test_write_vault_workflow.py:41-104` reinvents
the wheel: a hand-rolled `PathPydanticPayloadConverter(PayloadConverter)`
subclass plus `CompositePayloadConverter(custom_converter, default_converter)`,
wired into a fresh `Client(connection=..., data_converter=...)`. This fails
for two independent reasons. First, the constructor keyword is wrong — per
`temporalio/client.py:233-244` the signature is `Client(service_client, *,
namespace, data_converter, …)`; there is no `connection` parameter, so the
fixture raises `TypeError` before a single workflow starts. Second, even
had the constructor call worked, the custom `PayloadConverter` subclass is
structurally wrong: it inherits directly from `PayloadConverter` (an
`EncodingPayloadConverter`-composing type), raises `TypeError` for anything
that isn't a `Path` or `BaseModel`, and cannot round-trip the `dataclass`es
`WriteVaultInput` / `WriteOperation` (lines 73, 90-91) — those would be
thrown to the composite's fallback, which per Ralph's own composite ordering
is `DefaultPayloadConverter`, which then cannot serialise any contained
`Path`. The canonical fix already exists at
`/home/claude/.local/lib/python3.12/site-packages/temporalio/contrib/pydantic.py:122`
(`pydantic_data_converter`) and was prescribed verbatim in FAILURE-S07.md's
"Specific symbol or interface to use" section; Ralph ignored it.

## Concrete next-attempt instructions
1. Delete the entire hand-rolled fixture block at
   `tests/e2e/test_write_vault_workflow.py:37-104` (the
   `PathPydanticPayloadConverter` class and the
   `temporal_client_with_pydantic` fixture).
2. Replace it with a fixture that uses the canonical
   `pydantic_data_converter`, using the exact pattern from FAILURE-S07.md:
   ```python
   import pytest_asyncio
   from temporalio.client import Client
   from temporalio.contrib.pydantic import pydantic_data_converter

   @pytest_asyncio.fixture
   async def pydantic_client(temporal_client):
       return Client(
           service_client=temporal_client.service_client,
           namespace=temporal_client.namespace,
           data_converter=pydantic_data_converter,
       )
   ```
   Keep this fixture strictly local to `test_write_vault_workflow.py`
   — do not move it to `tests/conftest.py` (out of scope per bubble §5;
   cross-cutting hoist is a follow-up bubble).
3. Rename every `temporal_client_with_pydantic` reference in the test file
   to `pydantic_client` (both fixture parameter names and call sites).
   Affected test functions: `test_sequential_writes_serialise_under_load`
   (line 136), `test_save_operation_writes_file` (186),
   `test_delete_operation_removes_file` (221),
   `test_git_pull_called_before_writes` (274),
   `test_git_commit_and_push_called_after_operations` (281),
   `test_empty_operations_list_no_changes_no_commit` (286). Pass
   `pydantic_client` into both `Worker(...)` and `execute_workflow(...)` in
   each test — Worker inherits the Client's data_converter automatically,
   so the same client handles both workflow I/O and activity arg/result
   payloads.
4. Keep the `activity_executor=ThreadPoolExecutor(max_workers=2)` in the
   serialisation-load-test Worker at line 153. Per LEARNINGS.md:10 (S03),
   sync-`def` activities (save_note et al. are all sync per
   `apps/vault_worker/activities/vault_io.py:162,173`) require an explicit
   thread-pool executor. Apply the same `activity_executor=ThreadPoolExecutor(...)`
   kwarg to the three integration-test Workers (lines ~199, 235, 255, 297)
   — they currently lack it and will hang once the Path-serialisation
   blocker is cleared. Import: `from concurrent.futures import ThreadPoolExecutor`
   (already present at line 13).
5. Do **not** modify `apps/vault_worker/workflows/write_vault.py` — the
   current implementation (reviewed at
   `apps/vault_worker/workflows/write_vault.py:1-112`) is well-formed:
   correct empty-operations short-circuit, pull-before-write, per-op
   dispatch, commit→push ordering, SHA return. All bubble acceptance
   criteria §4 are satisfied by this body once the tests can actually
   serialise their inputs.
6. Run `pytest tests/e2e/test_write_vault_workflow.py -v` — all 6 tests
   must pass. The load test's `elapsed > 0.9` assertion is the
   critical-path check for the sequential-queue guarantee.
7. Run `pytest` full suite — coverage threshold (≥90%) must still hold;
   no regression expected since changes are confined to one test file.
8. Commit only the updated `tests/e2e/test_write_vault_workflow.py` (and
   optionally a one-line LEARNINGS.md update replacing the current stub at
   line 110 with an accurate entry). Do not touch `tests/conftest.py`,
   `packages/shared/`, activity files, or `read_vault.py` — all
   forbidden by bubble §5.

## Files to read before starting
- `FAILURE-S07.md` (on feat/OBSE-P5-temporal-soa-migration) — relevant
  because it prescribes the exact `pydantic_data_converter` + local Client
  pattern to use, with the correct `Client(service_client=..., namespace=...,
  data_converter=pydantic_data_converter)` signature that Ralph's attempt
  got wrong.
- `/home/claude/.local/lib/python3.12/site-packages/temporalio/contrib/pydantic.py:1-14`
  — the module docstring shows canonical usage.
- `/home/claude/.local/lib/python3.12/site-packages/temporalio/client.py:233-244`
  — authoritative Client constructor signature; proves
  `connection=` is not a parameter.
- `LEARNINGS.md:10,17` (S03 entries) — confirms the
  `activity_executor=ThreadPoolExecutor` requirement for sync-`def`
  activities, needed for the integration tests that use real
  `save_note`/`delete_note`/git_*.
- `bubbles/OBSE-P5-S08-write-vault-workflow.md:79-82` (scope boundary)
  — confirms conftest.py is off-limits.
- `apps/vault_worker/activities/vault_io.py:162,173` — confirms
  `save_note` and `delete_note` are sync `def` (→ need thread-pool
  executor).

## Specific symbol or interface to use
`temporalio.contrib.pydantic.pydantic_data_converter`. Already resolved
in FAILURE-S07.md; not a new discovery.

Exact in-test pattern (copy verbatim, change only fixture name):
```python
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

@pytest_asyncio.fixture
async def pydantic_client(temporal_client):
    return Client(
        service_client=temporal_client.service_client,
        namespace=temporal_client.namespace,
        data_converter=pydantic_data_converter,
    )
```

## What Ralph tried that didn't work
Commit f1d0bc7 (92 insertions, 18 deletions) did two things:

1. Added a custom `PathPydanticPayloadConverter(PayloadConverter)` and a
   `temporal_client_with_pydantic` fixture that constructs
   `Client(connection=temporal_env.client.service_client,
   data_converter=data_converter)`. This is broken twice over:
   (a) `Client.__init__` has no `connection` parameter — the correct
       keyword is `service_client` (verified at client.py:235). Ralph's
       fixture therefore raises `TypeError` at fixture-resolution time,
       before any test executes.
   (b) Even if (a) were fixed, the custom converter raises `TypeError` on
       any non-`Path`/non-`BaseModel` value, which would block serialisation
       of the workflow-input `dataclass` (`WriteVaultInput`, `WriteOperation`)
       entirely. The composite's default-converter fallback then cannot
       serialise nested `Path` fields, so the same hang recurs at a
       different frame. The canonical `pydantic_data_converter` handles
       dataclasses, Pydantic models, and Path transparently.
2. Added a `LEARNINGS.md` entry (line 110) that correctly identifies the
   symptom but loses the prescribed fix. This entry is stale relative to
   FAILURE-S07.md and should be replaced when S08 lands, not kept alongside.

Ralph also added `activity_executor=ThreadPoolExecutor(max_workers=2)` to
the load-test Worker (line 153) — this part was *correct* (per S03
LEARNINGS line 10) and should be retained; it is unrelated to the
serialisation blocker but prevents a separate sync-activity hang that
would surface once the serialisation blocker is cleared.

## Recommended action
GUIDANCE. The fix is mechanical: one import, one 6-line fixture
replacing ~65 lines of broken custom code, plus a rename across six test
functions. The workflow body itself is already correct — this is purely
a test-scaffolding issue, identical in shape to S07's remedy.

## Sequencing note
S08 does **not** need to wait for S07 to merge. FAILURE-S07.md's fix is
per-test-file, not shared infrastructure — nothing lands in `conftest.py`,
so S07 merging does not pre-configure S08's test environment. The two
bubbles apply the same `pydantic_data_converter` + local-Client pattern
independently at their respective test sites. Ralph can retry S08
immediately once this guidance is delivered; S07 and S08 can be developed
and merged in either order, with the understanding that a follow-up
bubble (post-S09) may hoist the duplicated fixture into `tests/conftest.py`
as genuine cross-cutting infrastructure — that hoist is out of scope for
both S07 and S08.
