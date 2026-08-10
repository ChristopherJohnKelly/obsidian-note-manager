# FAILURE-S18 — 2026-08-10T14:03:50Z

## Rejection Reason
Code quality (critical): parse_fix_body returns '' (not None) for an empty %%FILE%% block, bypassing the `if body is None` skip guard at night_watchman.py:107 and overwriting the note with an empty body — confirmed end-to-end via save_note dispatch; the frontmatter-strip regex also deletes real body content when it opens with a `---` rule

## Failed Check
pr-review-toolkit

## Attempt
1 of max 5 (escalates to status=support at 3)

## PR
#40 — step branch `pr/S18` @ 95d50ef

## Files changed on step branch vs feature
- PLAN.md
- apps/copilot_ui/app.py
- apps/github_runner/trigger.py
- apps/vault_worker/__main__.py
- apps/vault_worker/core/night_watchman_parser.py
- apps/vault_worker/worker.py
- apps/vault_worker/workflows/night_watchman.py
- scripts/run_s18_tests.sh
- tests/e2e/test_night_watchman_parse.py
- tests/e2e/test_night_watchman_skip.py
- tests/unit/test_pydantic_converter_wired.py
- tests/unit/test_worker.py

## Next status
queued — step branch rebriefed to prepare commit + new CONTEXT; will be re-attempted automatically

## What to fix
Address the rejection reason above before re-attempting this step. If prior
attempt sections exist above, re-read them — the same check failing twice
means the prior guidance was not applied or was insufficient.
