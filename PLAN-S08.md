# PLAN-S08 — WriteVaultWorkflow (post-fix, wrapping up)

Implements `bubbles/OBSE-P5-S08-write-vault-workflow.md` (amended
2026-04-20, commit `3a43b3b` on `feat/OBSE-P5-temporal-soa-migration`).
Ralph attempted S08 four times and timed out under the session
watchdog; Opus-local took over, diagnosed the load-test hang, amended
the bubble with the fix, and got all 6 tests green. Remaining work is
coverage verification, LEARNINGS append, and PR.

This plan supersedes the prior probe-driven version. The debugging
phase is complete.

## Resolution summary

The load-test hang was a Temporal SDK constraint, not an implementation
bug. Per the SDK: *"`max_concurrent_workflow_tasks` must be at least 2
if `max_cached_workflows` is nonzero."* `max_cached_workflows` defaults
to 1000, so pairing `max_concurrent_workflow_tasks=1` with the default
cache deadlocks the Worker under concurrent load — one task slot, many
cache slots, no way to evict.

**Fix:** add `max_cached_workflows=0` to the load-test Worker only.
Production Worker (TRD §4.5) keeps the default cache and uses a real
Temporal server, so it is unaffected.

The bubble was amended (feat commit `3a43b3b`) to document this plus
two related test-env accommodations:

- `pydantic_client` fixture — required for `VaultNote.path` (pathlib)
  round-trip; mirrors S07
- `max_cached_workflows=0` on the test-env Worker — fixes the deadlock
- `activity_executor=ThreadPoolExecutor(...)` — required for sync `def`
  activities (S03 LEARNINGS)

No TRD change required. §4.5, §4.6, and §7 Phase 2 all hold as written.

## Current state (step/OBSE-P5-S08-write-vault-workflow)

All 6 tests green in a single clean run (`/tmp/pytest-all6.out`,
2.92s):

```
test_save_operation_writes_file                        PASSED
test_delete_operation_removes_file                     PASSED
test_git_pull_called_before_writes                     PASSED
test_git_commit_and_push_called_after_operations       PASSED
test_empty_operations_list_no_changes_no_commit        PASSED
test_sequential_writes_serialise_under_load            PASSED
```

Implementation is aligned with bubble §8:

- `WriteOperation`, `WriteVaultInput` are `@dataclass`
- Activities dispatched by function reference
- Timeouts: `timedelta(minutes=5)` for `git_pull`/`git_push`,
  `timedelta(minutes=1)` for others
- `worker.py` registers two Workers (`QUEUE_DEFAULT` read-only +
  `QUEUE_MUTATION` with `max_concurrent_*=1`)

Files in working tree, uncommitted:

- `apps/vault_worker/workflows/write_vault.py`
- `apps/vault_worker/workflows/__init__.py`
- `apps/vault_worker/worker.py`
- `tests/e2e/test_write_vault_workflow.py`

## Remaining work

### 1. Full coverage suite

```
pytest --cov=apps --cov=packages --cov-fail-under=90
```

Must pass at ≥90% with no S01–S07 regressions. S08 adds one new
workflow file and its tests; coverage should hold.

### 2. Append LEARNINGS.md

Add two entries under a 2026-04-20 S08 heading:

- **`max_cached_workflows=0` required with `max_concurrent_workflow_tasks=1`
  in tests.** SDK constraint: the latter must be ≥2 when the former is
  nonzero. Default cache is 1000. Symptom: Worker hangs indefinitely
  at 0% CPU under concurrent load, no exception. Production config
  unaffected (real Temporal server keeps default cache).
- **Pytest orchestration discipline** (root cause of all four Ralph
  timeouts): never run more than one pytest at a time; never call
  `Monitor` on a running pytest (each call starts a fresh process);
  use `Read` on the output file returned by `Bash run_in_background=true`;
  `pkill -f "pytest tests/"` before any new run if `ps aux | grep
  pytest | grep -v grep` shows anything. This is a cc-obsidian
  orchestration lesson, not a Temporal lesson — flag it for the
  orchestration layer.

### 3. Commit on step/OBSE-P5-S08-write-vault-workflow

Single commit with all four working-tree files. Suggested message:

```
feat(S08): WriteVaultWorkflow on vault-mutation-queue

Implements WriteVaultWorkflow per bubble OBSE-P5-S08:
- save/delete operations serialised through QUEUE_MUTATION
- git_pull before, git_commit + git_push after
- empty-ops short-circuit (no pull, no commit)
- returns commit SHA

Load test proves the production Worker config (max_concurrent_*=1)
serialises 10 concurrent writes. Test-env Worker requires
max_cached_workflows=0 per SDK constraint (see LEARNINGS 2026-04-20).

Closes FAILURE-S08 issues 1–4.
```

### 4. Open PR against feat/OBSE-P5-temporal-soa-migration

PR body should reference `FAILURE-S08.md` issues 1–4 and confirm each
is fixed, plus link the amended bubble commit (`3a43b3b`) and the
LEARNINGS entries.

## Sequence

1. Run `pytest --cov=apps --cov=packages --cov-fail-under=90` — verify ≥90%.
2. Append `LEARNINGS.md` with the two entries above.
3. Stage + commit on `step/OBSE-P5-S08-write-vault-workflow`.
4. Push branch.
5. Open PR against `feat/OBSE-P5-temporal-soa-migration`.

## Known risks

- **Coverage regression in untouched areas**: unlikely (no shared
  files modified), but `--cov-fail-under=90` may surface a pre-existing
  gap on another step. If so, note it in the PR and flag to steering —
  do not paper over with exclusions.
- **LEARNINGS merge conflict**: S09 (claimed by Ralph on feat) may be
  writing to `LEARNINGS.md` concurrently. Rebase cleanly before PR if
  the feat branch has advanced.

## Definition of done

- All 6 S08 tests green in a single clean run (verified).
- Full `--cov-fail-under=90` suite green.
- LEARNINGS.md updated with both entries.
- Branch committed, pushed, PR open.
- Bubble amendment committed on feat (`3a43b3b` — done).

---

# HISTORICAL (for context, kept intentionally terse)

Debugging path was: probes D → B → A → C → E. Probe D
(`pydantic_client` vs `temporal_client`) failed fast with
`PosixPath is not JSON serializable` — confirmed `pydantic_client` is
required (not the suspected problem, but the bubble needed to document
it). Probe B (`max_cached_workflows=0`) passed in 1.68s — root cause
found. Probes A/C/E not needed.

Prior plan's "possible bubble amendments A/B/C" collapsed to just B
(plus a pydantic_client / ThreadPoolExecutor reminder for
completeness). All three were folded into the single bubble amendment
at `3a43b3b`.
