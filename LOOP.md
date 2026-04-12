# Loop Bootstrap — OBSE-P5 Temporal SOA Migration

## Feature Branch
feat/OBSE-P5-temporal-soa-migration

## Plan
See `PLAN.md` on this branch.

## Instructions
- Poll interval: 5 minutes when waiting for cc-obsidian review
- Max attempts per step: 3
- Branch prefix: `step/OBSE-P5-`
- PR target: `feat/OBSE-P5-temporal-soa-migration`
- TDD discipline: required (see Bubble spec for each step)
- On HALT: write `HALT.md` with full context, stop loop
- On COMPLETE: write `COMPLETE.md`, stop loop

## Test Command
```bash
pytest --cov=apps --cov=packages --cov-fail-under=90
```

## Context
- TRD: `TRD.md` (in repo root on feature branch)
- Bubble specs: `bubbles/OBSE-P5-S{XX}-{name}.md`
- Learnings from prior steps: `LEARNINGS.md`

## Key Architectural Constraints

Read these before starting any step. Violating them will cause Serena to reject the PR.

**1. All Activities are synchronous `def` functions — never `async def`.**
Temporal runs Activities in a `ThreadPoolExecutor`. Using `async def` will block the event loop.
This applies to all Activities in `vault_io.py`, `git_ops.py`, `llm.py`, and `github_ops.py`.

**2. Retry policies belong at the call site, not the decorator.**
`@activity.defn` does not accept `retry_policy`. Apply `RetryPolicy` inside
`workflow.execute_activity(...)` at the workflow call site.

**3. No file I/O inside `@workflow.run`.**
`Path.exists()`, `Path.iterdir()`, `open()` etc. inside a workflow method violates
Temporal's determinism requirement. All file I/O must be delegated to Activities.

**4. `workflow.now()` returns a UTC-aware datetime.**
Comparing it to a naive datetime causes a `TypeError`. Guard any naive datetime
loaded from state with: `dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt`.

**5. VaultManagerWorkflow is auto-started — never trigger it externally.**
The vault-worker container starts it on startup. It is a long-running coordinator with
well-known ID `vault-manager`. `ReadVaultWorkflow` sends `ensure_synced` Updates to it
via `workflow.get_external_workflow_handle(VAULT_MANAGER_ID)`.

**6. Advanced Visibility requires PostgreSQL.**
`list_workflows` with status/type filters only works when Temporal is configured with
`VISIBILITY_DB_PLUGIN=postgres12`. Do not assume SQLite visibility in tests.

**7. Coverage omit list.**
`apps/copilot-ui/app.py` Chainlit lifecycle hooks are untestable. Add to `[tool.coverage.run] omit`
in `pyproject.toml` before the 90% threshold check.

## Git Protocol

PLAN.md is the state machine. All reads and writes to PLAN.md must happen
while checked out on the feature branch. Follow this sequence precisely:

### Claiming a step
1. git checkout feat/OBSE-P5-temporal-soa-migration
2. git pull origin feat/OBSE-P5-temporal-soa-migration
3. Edit PLAN.md — set status=in-progress, Claimed By=ralph@{timestamp}
4. git add PLAN.md && git commit -m "chore: claim {SXX} [ralph]"
5. git push origin feat/OBSE-P5-temporal-soa-migration
   ← push BEFORE creating the step branch
6. git checkout -b step/OBSE-P5-{SXX}-{name}
   ← branch from the claim commit; PLAN.md on this branch is intentionally stale

### After implementation — opening PR
1. git push origin step/OBSE-P5-{SXX}-{name}
2. gh pr create --base feat/OBSE-P5-temporal-soa-migration --title "[OBSE-P5-{SXX}] {name}" --body "Closes step {SXX}"
3. git checkout feat/OBSE-P5-temporal-soa-migration
4. git pull origin feat/OBSE-P5-temporal-soa-migration
5. Edit PLAN.md — set status=review, PR=#N
6. git add PLAN.md && git commit -m "chore: {SXX} open for review [ralph]"
7. git push origin feat/OBSE-P5-temporal-soa-migration

### On failure
1. git checkout feat/OBSE-P5-temporal-soa-migration
2. git pull origin feat/OBSE-P5-temporal-soa-migration
3. Write FAILURE-{SXX}.md, edit PLAN.md
4. git add -A && git commit -m "chore: {SXX} failed attempt {N} [ralph]"
5. git push origin feat/OBSE-P5-temporal-soa-migration

## Per-Step Context Loading

At the start of each step, read:
1. `PLAN.md` — confirm step status and dependencies
2. `LEARNINGS.md` — check for relevant prior discoveries
3. `TRD.md` — the authoritative spec; Serena verifies against it
4. `bubbles/OBSE-P5-S{XX}-{name}.md` — the step's acceptance criteria, scope, and TDD constraints

Do not read other bubbles unless a dependency question arises.
