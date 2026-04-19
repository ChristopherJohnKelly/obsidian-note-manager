# FAILURE-S07 — 2026-04-19T10:09:47Z

## Rejection Reason
Session watchdog: wall-clock timeout after 2700s.

## Trigger
timeout

## What to investigate
Review the last commits on the step branch and the contents of LEARNINGS.md.
The previous attempt was making forward motion but did not converge in time.
Consider: is this Bubble too large? Does it need to be split?


---

## cc-obsidian attempt — 2026-04-19T14:44:52Z

## Rejection Reason
ReadVaultWorkflow uses `mgr.signal()` instead of `execute_update` (violates AC1+AC2); test stub registers matching `@workflow.signal` handler to mask the bug; parallel test count assertion removed; debug prints left in workflow body.

## Failed Check
serena

## Attempt
2 of max 5 (escalates to status=support at 3)

## PR
#27 — step branch `step/OBSE-P5-S07-read-vault-workflow` @ 144dbb9

## Files changed on step branch vs feature
- FAILURE-S07.md
- FAILURE-S08.md
- LEARNINGS.md
- PLAN-S07.md
- PLAN.md
- apps/vault-worker
- apps/vault-worker/__init__.py
- apps/vault-worker/activities/__init__.py
- apps/vault-worker/activities/git_ops.py
- apps/vault-worker/pyproject.toml
- apps/vault_worker/workflows/read_vault.py
- architecture.md
- docs/README.md
- docs/api-reference.md
- docs/architecture.md
- docs/code-registry.md
- docs/components.md
- docs/ingest-deployment.md
- docs/setup.md
- docs/troubleshooting.md

## Next status
queued — will be re-attempted automatically

## What to fix
Address the rejection reason above before re-attempting this step. If prior
attempt sections exist above, re-read them — the same check failing twice
means the prior guidance was not applied or was insufficient.
