# LEARNINGS.md — OBSE-P5 Temporal SOA Migration

Feed-forward knowledge between Ralph sessions. Append-only — do not modify existing entries.

<!-- Ralph appends entries here after each successful step, before opening the PR. -->
<!-- Format: ## S{XX} — {YYYY-MM-DD} / ### What I learned / ### Why it matters for future steps -->

## S03 — Temporal Test Environment — 2026-04-14
- `WorkflowEnvironment.start_time_skipping()` is the correct in-process environment (not `start_local()` which needs a server)
- Sync `def` activities (not `async def`) require `activity_executor=ThreadPoolExecutor(...)` in the Worker constructor
- Session-scoped `pytest_asyncio` fixtures need `asyncio_mode = "auto"` in pyproject.toml
- Coverage threshold of 90% fails if no production code exists — the full test suite (not just smoke test) must run to hit packages/shared coverage
- `apps/copilot-ui/app.py` must be in `omit` list before threshold check or Chainlit's app entrypoint inflates miss count

## S03 — Temporal Test Environment — 2026-04-14 (verified)
- All four fixtures in conftest.py (temporal_env, temporal_client, dummy_vault_path, fake_llm) confirmed working
- Sync `def` ping_activity with `activity_executor=ThreadPoolExecutor(max_workers=2)` in Worker is the correct pattern
- Full test suite (161 tests) hits 100% coverage on packages/shared; running only smoke test gives 0% (not enough)
- `asyncio_mode = "auto"` in pyproject.toml is required for session-scoped async fixtures to work

## S04 — Vault IO Activities — 2026-04-14
- Python package for `apps/vault-worker` must be `apps/vault_worker/` (underscore, not hyphen) — Python can't import hyphenated directory names; the hyphened dir is for Docker context only
- `from packages.shared.models import ...` is the correct local import path (not `from shared.models`) — the editable install `.pth` adds `packages/shared` to sys.path, not `packages`
- `VaultNote.path: Path` is not JSON serializable with Temporal's default converter — for integration tests returning Pydantic models with Path fields, use `list[str]` return activities (e.g., `list_notes_in`) to avoid needing `pydantic_data_converter` on the Worker
- Rule 2 (code mismatch) must be skipped when Rule 3 (bad title) fires on the same file — otherwise generic-named files get double-penalised (30→80)
- `Worker` in Temporal SDK v1.x takes no `data_converter` kwarg — the data converter is set on the `Client`, not the `Worker`
- Full test suite (184 tests) hits 91.3% total coverage; running only test_vault_io.py gives 83% because `workflow_names.py` misses its coverage from other tests

## Persistent pattern — gitignore corruption
- NEVER modify existing .gitignore entries — only append new lines
- The `=*` pattern must be added as a NEW line, not appended to an existing entry
- Correct: add a blank line then `=*` at the end of .gitignore
- Wrong: change `.venv/` to `.venv/=*`
- This mistake has occurred on S01 and S03 — treat .gitignore as append-only
