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
