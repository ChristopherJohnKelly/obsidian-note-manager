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


---

## cc-obsidian attempt — 2026-08-10T15:09:53Z

## Rejection Reason
Code quality (critical): parse_fix_body silently deletes body content when the LLM body opens with a Markdown `---` thematic break (and leaks raw YAML into the body on an unterminated fence), then commits and pushes the corrupted note; separately, configure_client() is never called in production, so the newly-registered ensure_vault_synced raises RuntimeError and — with no retry_policy at read_vault.py:42 — retries unboundedly, hanging ReadVault/NightWatchman/FilerIngestion workflows forever.

## Failed Check
pr-review-toolkit

## Attempt
2 of max 5 (escalates to status=support at 3)

## PR
#40 — step branch `pr/S18` @ 57aa0c5

## Files changed on step branch vs feature
- apps/copilot_ui/app.py
- apps/github_runner/trigger.py
- apps/vault_worker/__main__.py
- apps/vault_worker/core/night_watchman_parser.py
- apps/vault_worker/worker.py
- apps/vault_worker/workflows/night_watchman.py
- scripts/run_s18_tests.sh
- tests/e2e/test_night_watchman_parse.py
- tests/unit/test_pydantic_data_converter.py
- tests/unit/test_worker.py

## Next status
queued — step branch rebriefed to prepare commit + new CONTEXT; will be re-attempted automatically

## What to fix
Address the rejection reason above before re-attempting this step. If prior
attempt sections exist above, re-read them — the same check failing twice
means the prior guidance was not applied or was insufficient.


---

## cc-obsidian attempt — 2026-08-10T18:08:26Z

## Rejection Reason
AC4 unmet — parse_fix raises yaml.ParserError out of @workflow.run on malformed LLM YAML (confirmed: NightWatchmanWorkflow stuck in workflow-task retry loop), and still leaks raw YAML / deletes body content instead of skipping; AC5's on-disk byte-identity assertion is vacuous because save_note is stubbed

## Failed Check
serena

## Attempt
4 of max 5 (escalates to status=support at 3)

## PR
#40 — step branch `pr/S18` @ 8801a07

## Files changed on step branch vs feature
- apps/copilot_ui/app.py
- apps/github_runner/trigger.py
- apps/vault_worker/__main__.py
- apps/vault_worker/core/fix_parser.py
- apps/vault_worker/worker.py
- apps/vault_worker/workflows/night_watchman.py
- scripts/run_s18_tests.sh
- tests/e2e/test_night_watchman_write_back.py
- tests/unit/test_client_wiring.py
- tests/unit/test_worker.py

## Next status
support — halted for manual Opus steering; read prior sections of this file before resuming

## What to fix
Address the rejection reason above before re-attempting this step. If prior
attempt sections exist above, re-read them — the same check failing twice
means the prior guidance was not applied or was insufficient.


---

## cc-obsidian attempt — 2026-08-10T18:40:22Z

## Rejection Reason
Code quality (critical): [2026-08-10T18:40:17Z] [WARN ] pr-review-toolkit timed out for S18 — treating as PASS (non-blocking)
PRREVIEW:PASS

## Failed Check
pr-review-toolkit

## Attempt
2 of max 5 (escalates to status=support at 3)

## PR
#40 — step branch `pr/S18` @ edaa6b7

## Files changed on step branch vs feature
- apps/copilot_ui/app.py
- apps/github_runner/trigger.py
- apps/vault_worker/__main__.py
- apps/vault_worker/core/fix_parser.py
- apps/vault_worker/worker.py
- apps/vault_worker/workflows/night_watchman.py
- scripts/run_s18_tests.sh
- tests/e2e/test_night_watchman_write_back.py
- tests/unit/test_client_wiring.py
- tests/unit/test_fix_parser.py
- tests/unit/test_worker.py

## Next status
queued — step branch rebriefed to prepare commit + new CONTEXT; will be re-attempted automatically

## What to fix
Address the rejection reason above before re-attempting this step. If prior
attempt sections exist above, re-read them — the same check failing twice
means the prior guidance was not applied or was insufficient.


---

## cc-obsidian attempt — 2026-08-10T18:54:48Z

## Rejection Reason
apps/vault_worker/__main__.py:15 imports configure_provider from activities.llm_provider where it is not defined (it lives in activities.llm) — `python3 -m apps.vault_worker`, the production Dockerfile CMD, dies with ImportError before starting any Worker; the AC3 guard test only ast.parse()s the file so it passes on an unimportable module (0% coverage)

## Failed Check
serena

## Attempt
2 of max 5 (escalates to status=support at 3)

## PR
#40 — step branch `pr/S18` @ 3aa8bfd

## Files changed on step branch vs feature
- apps/copilot_ui/app.py
- apps/github_runner/trigger.py
- apps/vault_worker/__main__.py
- apps/vault_worker/core/fix_parser.py
- apps/vault_worker/worker.py
- apps/vault_worker/workflows/night_watchman.py
- scripts/run_s18_tests.sh
- tests/e2e/test_night_watchman_write_back.py
- tests/unit/test_client_wiring.py
- tests/unit/test_fix_parser.py
- tests/unit/test_worker.py

## Next status
queued — step branch rebriefed to prepare commit + new CONTEXT; will be re-attempted automatically

## What to fix
Address the rejection reason above before re-attempting this step. If prior
attempt sections exist above, re-read them — the same check failing twice
means the prior guidance was not applied or was insufficient.


---

## cc-obsidian attempt — 2026-08-10T19:05:42Z

## Rejection Reason


## Failed Check
serena

## Attempt
2 of max 5 (escalates to status=support at 3)

## PR
#40 — step branch `pr/S18` @ bc90c13

## Files changed on step branch vs feature
- apps/copilot_ui/app.py
- apps/github_runner/trigger.py
- apps/vault_worker/__main__.py
- apps/vault_worker/core/fix_parser.py
- apps/vault_worker/worker.py
- apps/vault_worker/workflows/night_watchman.py
- scripts/run_s18_tests.sh
- tests/e2e/test_night_watchman_write_back.py
- tests/unit/test_client_wiring.py
- tests/unit/test_fix_parser.py
- tests/unit/test_worker.py

## Next status
queued — step branch rebriefed to prepare commit + new CONTEXT; will be re-attempted automatically

## What to fix
Address the rejection reason above before re-attempting this step. If prior
attempt sections exist above, re-read them — the same check failing twice
means the prior guidance was not applied or was insufficient.


---

## cc-obsidian attempt — 2026-08-10T19:38:28Z

## Rejection Reason
Code quality (critical): parse_fix (apps/vault_worker/core/fix_parser.py:53) catches only yaml.YAMLError, so ordinary LLM frontmatter such as `created: 2025-02-30` raises ValueError (and deep nesting raises RecursionError) out of the unguarded call at night_watchman.py:93 inside @workflow.run — a workflow-task failure retried indefinitely, wedging NightWatchmanWorkflow; violates the module's own documented totality contract and is missed by test_never_raises_on_garbage

## Failed Check
pr-review-toolkit

## Attempt
2 of max 5 (escalates to status=support at 3)

## PR
#40 — step branch `pr/S18` @ b09a02d

## Files changed on step branch vs feature
- apps/copilot_ui/app.py
- apps/github_runner/trigger.py
- apps/vault_worker/__main__.py
- apps/vault_worker/core/fix_parser.py
- apps/vault_worker/worker.py
- apps/vault_worker/workflows/night_watchman.py
- scripts/run_s18_tests.sh
- tests/e2e/test_night_watchman_write_back.py
- tests/unit/test_client_wiring.py
- tests/unit/test_fix_parser.py
- tests/unit/test_worker.py

## Next status
queued — step branch rebriefed to prepare commit + new CONTEXT; will be re-attempted automatically

## What to fix
Address the rejection reason above before re-attempting this step. If prior
attempt sections exist above, re-read them — the same check failing twice
means the prior guidance was not applied or was insufficient.
