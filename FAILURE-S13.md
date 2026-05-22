# FAILURE-S13 — 2026-05-22T17:18:05Z

## Rejection Reason
trigger.py hardcodes task_queue="obsidian-note-manager" instead of TRD-mandated "vault-default" (TRD §4.5); workflows would be dispatched to a queue no worker polls, breaking the github-runner→vault-worker contract.

## Failed Check
serena

## Attempt
2 of max 5 (escalates to status=support at 3)

## PR
#37 — step branch `pr/S13` @ b819365

## Files changed on step branch vs feature
- .github/workflows/ingest.yml
- .github/workflows/watchman.yml
- PLAN.md
- apps/github_runner/Dockerfile
- apps/github_runner/requirements.txt
- apps/github_runner/trigger.py
- scripts/run_s13_tests.sh
- tests/unit/test_trigger.py

## Next status
queued — will be re-attempted automatically

## What to fix
Address the rejection reason above before re-attempting this step. If prior
attempt sections exist above, re-read them — the same check failing twice
means the prior guidance was not applied or was insufficient.
