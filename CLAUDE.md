# CLAUDE.md — Obsidian Note Manager

Project-specific guidance for all Claude Code sessions in this repo. The agentic
loop's nodes run with this file in context automatically; keep it durable and concise.

## Running tests

- Use `python3 -m pytest`. Bare `pytest` is **not** on PATH, and `python` is **not**
  on PATH — only `python3` is.
- Test runner scripts under `scripts/` MUST invoke `python3 -m pytest` (with the
  project's coverage/timeout flags).

## Architecture

- System design: `architecture.md` (repo root). Canonical spec: `TRD.md`.
- Temporal-based SOA: Workflows orchestrate and stay deterministic; Activities
  perform all I/O and non-determinism.

## Temporal SDK rules (violating these fails review)

- Activities are synchronous `def`, never `async def` (Temporal runs them in a
  thread pool).
- No file I/O, `random`, or wall-clock time inside `@workflow.run` — delegate to
  Activities.
- Apply `RetryPolicy` at the call site (`workflow.execute_activity(..., retry_policy=...)`),
  not on `@activity.defn`.
- A workflow composes other workflows via `workflow.execute_child_workflow(...)`;
  it never calls another component's vault-mutating Activities (e.g. `save_note`,
  `delete_note`) directly.
- The Temporal Python SDK package is `temporalio` (not `temporallib`).

## Tooling

- For Temporal SDK questions (signals, queries, child workflows, determinism,
  time-skipping tests), use the `temporal-developer` skill (Skill tool) before
  guessing the API.
- For current third-party library docs, use context7: `resolve-library-id` then
  `query-docs`.
