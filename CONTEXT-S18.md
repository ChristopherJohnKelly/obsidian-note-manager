---
step_id: S18
step_slug: integration-hardening
feature_branch: feat/OBSE-P5-temporal-soa-migration
bubble_ref: OBSE-P5-S18-integration-hardening.md
attempts: 0
bubble_hash: 4d548e4c824c413ee8480a77de556244d001d733c027644f842fda1349cd8ff6
---
## Goal
See the bubble body below (`OBSE-P5-S18-integration-hardening.md`) — the bubble carries the
canonical goal statement for this step.

## Files in scope
See the bubble body below for declared scope. Ralph's PLAN must mirror it
into `bubble_scope`.

## Red-green-refactor checklist
Derived from the bubble body's cycle list below. Ralph's PLAN turns each
into a `## CYCLE Cn` section.

## Bubble (verbatim)

---
type: bubble
status: pending
step_id: S18
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python Engineer wiring a Temporal system together for production.
**Objective:** Close the three integration gaps that keep the individually-verified workflows from running end-to-end: (1) register every workflow and activity with a Worker; (2) use the pydantic data converter on every production Temporal client; (3) make NightWatchmanWorkflow parse LLM output instead of destroying notes with raw marker text.
**Constraints:**
- Read the real definitions before registering or calling anything — every prior convergence failure in this feature came from writing what "should" exist instead of what does. Enumerate workflows/activities by opening the workflow files, not from memory.
- Do not change any workflow's public interface (signal/query names, input dataclasses) — clients built in S13/S14 depend on them.
- The FakeLLM and dummy vault from S02/S03 exist precisely for behavioural tests like these — use them; no live LLM or network in tests.

---

## 1. Context

**Feature:** TRD Section 6 (all phases) — integration layer.
**Depends On:** S10 (NightWatchman), S11 (FilerIngestion), S12 (CopilotSession), S15 (CI).
**Current State:** Every workflow passes its own unit tests, but the system cannot run end-to-end. Discovered by PR review during S15: `worker.py` registers neither `FilerIngestionWorkflow` nor `CopilotSessionWorkflow` (nor their activities `ensure_vault_synced`, `generate_chat_response`); the three production clients (`apps/vault_worker/__main__.py`, `apps/copilot_ui/app.py`, `apps/github_runner/trigger.py`) omit the pydantic data converter, so pydantic payloads cannot serialize; and `NightWatchmanWorkflow` step 5 stores `generate_fix`'s raw `%%FILE%%...%%END%%` marker output verbatim as the note body with an empty `Frontmatter()` — committing and pushing destroyed notes.
**Target State:** A single worker process serves every workflow; every production client can round-trip pydantic payloads; a NightWatchman run writes parsed, frontmatter-preserving notes.

---

## 2. Input

- `apps/vault_worker/worker.py` — existing registration lists (read them)
- `apps/vault_worker/workflows/` — all workflow definitions (enumerate from source)
- `apps/vault_worker/activities/` — all activity definitions (enumerate from source)
- `apps/vault_worker/workflows/night_watchman.py` — step 5 write-back defect
- `apps/vault_worker/activities/llm.py` — `generate_fix` docstring documents the `%%FILE%%...%%END%%` marker contract
- `apps/copilot_ui/app.py`, `apps/copilot_ui/temporal_client.py`, `apps/github_runner/trigger.py`, `apps/vault_worker/__main__.py` — the production client connections
- `tests/fixtures/` — FakeLLM and dummy vault from S02/S03

---

## 3. Required Output

- [ ] `apps/vault_worker/worker.py` — complete registration
- [ ] Pydantic data converter on all four production `Client.connect` sites
- [ ] `night_watchman.py` (and/or a parsing helper under `apps/vault_worker/core/`) — parsed write-back
- [ ] Behavioural tests for all three fixes

---

## 4. Acceptance Criteria

- [ ] `worker.py`'s workers, between them, register every `@workflow.defn` class under `apps/vault_worker/workflows/` and every `@activity.defn` under `apps/vault_worker/activities/` that any registered workflow invokes. A test MUST enumerate workflow/activity definitions from the source modules and assert each is present in a registration list — so a future unregistered workflow fails the suite, not production.
- [ ] `FilerIngestionWorkflow` and `CopilotSessionWorkflow` are registered on the task queue their clients dispatch to (read the client code for the queue names; do not guess).
- [ ] All four production `Client.connect` calls pass the Temporal pydantic data converter (`temporalio.contrib.pydantic`). A test MUST assert each call site passes it (structural inspection of the modules is acceptable where a live connection is untestable).
- [ ] `NightWatchmanWorkflow` no longer writes `generate_fix` output verbatim: the marker format is parsed; the written note's frontmatter is the note's existing frontmatter (preserved or explicitly merged), never an empty default; unparseable LLM output for a note skips that note (logged) rather than writing garbage. A behavioural test MUST run the workflow in the Temporal test environment with the FakeLLM returning marker-wrapped content and assert: the written body contains no `%%FILE%%`/`%%END%%` markers, and the original frontmatter fields survive.
- [ ] A second behavioural test MUST assert the skip path: FakeLLM returns malformed output → the note on disk is byte-identical to before the run.
- [ ] The full suite passes with coverage ≥ 90%.

---

## 5. Scope Boundary

**May modify:** `apps/vault_worker/worker.py`, `apps/vault_worker/__main__.py`, `apps/vault_worker/workflows/night_watchman.py`, `apps/vault_worker/core/`, `apps/copilot_ui/app.py`, `apps/copilot_ui/temporal_client.py`, `apps/github_runner/trigger.py`, `tests/unit/`, `tests/e2e/`, `scripts/run_s18_tests.sh`
**Must not modify:** workflow public interfaces (signal/query names, input dataclasses), `packages/shared/`, `.github/workflows/`, Dockerfiles, `tests/fixtures/` existing fixtures (adding new ones is fine), `tests/ci/`

---

## 6. TDD Constraints

All three fixes are behaviourally testable in the existing Temporal test environment (S03) with the FakeLLM (S02). Write the failing behavioural test first for each fix. The registration-completeness test is structural (enumerate-and-assert) and must be written so it fails today for the two missing workflows before the fix lands.

---

## 7. Step-by-Step Plan

1. Registration test: enumerate `@workflow.defn`/`@activity.defn` from source; assert coverage by `create_workers`. Watch it fail on the two missing workflows. Fix `worker.py`. Green.
2. Converter test: assert all four client call sites pass the pydantic converter. Watch it fail. Add the converter. Green.
3. NightWatchman parse test: FakeLLM returns marker-wrapped content; assert no markers in the written body and frontmatter preserved. Watch it fail (today it writes marker soup with empty frontmatter). Implement the parse (helper under `core/` if it needs unit tests of its own). Green.
4. Skip-path test: malformed FakeLLM output → note untouched. Green.
5. Full suite + coverage.

---

## 8. Reference Material

`generate_fix`'s docstring (activities/llm.py): "Returns raw LLM response with %%FILE%%...%%END%% markers." The marker format is the contract to parse — read how the FakeLLM emits it in the fixtures before writing the parser.

## Steering from prior steps
- [S04] Temporal's default converter can't serialize `VaultNote.path: Path`; pydantic types require `pydantic_data_converter` on the Client — applicable here because AC3 mandates the converter on all four production `Client.connect` sites so pydantic payloads round-trip.
- [S06] The vault-worker `%%FILE%%...%%END%%` marker format is NOT src_v2's `%%FILE: path%%` — do not copy the old parser — applicable here because the NightWatchman parse fix must implement the correct current-format parser, not the legacy one.
- [S06] `FakeLLMProvider.FAKE_FIX` contains `{original_path}` as a literal placeholder (not str-formatted); tests should assert `%%FILE%%`/`%%END%%` presence, not path values — applicable here because the parse behavioural test uses FakeLLM's marker-wrapped output and must assert on markers/frontmatter, not path substitution.
- [S07] Workflows returning pydantic models with `Path` fields hang unless the client is configured with `pydantic_data_converter` — applicable here because production clients dispatching these workflows currently omit it, which is exactly AC3.
- [S08] Mock activities can be registered under production names via `@activity.defn(name="save_note")` so workflows pick them up transparently — applicable here because the NightWatchman behavioural tests must intercept vault writes without editing workflow code.
- [S08] `create_workers(client)` may only be called once per client — the Temporal bridge forbids overlapping registrations on the same task queue, so all worker-registration assertions must be combined into a single test — applicable here because AC1 adds a registration-enumeration test that shares the session client with other worker-registration tests.
- [S09] Same one-`create_workers`-per-client constraint (bridge rejects re-registration on the same queue) — applicable here because the new enumerate-and-assert registration test must not spawn a second worker on `vault-default`/`vault-mutation-queue`.
- [S13:C-] Trigger sites must dispatch to `vault-default` (TRD §4.5), not `obsidian-note-manager`, or workflows land on a queue no worker polls — applicable here because AC2 requires reading each client's queue name and registering `FilerIngestionWorkflow`/`CopilotSessionWorkflow` on the queue the clients actually dispatch to.
- [S15:C-] `apps.vault_worker.worker` has no `__main__` guard and the trigger's queue name diverged from the worker's, so the documented run path was non-functional — applicable here because S18's worker/client wiring must produce an actually runnable end-to-end system, not just green tests.
- [S15:C-] NightWatchmanWorkflow was verified to overwrite notes with raw marker text and empty frontmatter, then commit and push (data loss) — applicable here because AC4/AC5 exist specifically to make the parse-and-preserve fix behaviourally provable and the skip path byte-identical.
- [Orchestration] One `pytest` at a time; check `ps aux | grep pytest` before starting; `pytest-timeout` isn't installed so `--timeout=N` is silently ignored — applicable here because S18 runs the full suite plus new behavioural tests and prior stuck-subprocess incidents in this feature came from parallel invocations.
- [Orchestration] Scratch/debug tests must be prefixed `test_explore_*` (or `test_debug_*`, etc.); >3 such files in a session triggers wind-down — applicable here because parsing/marker-format investigation may tempt exploratory tests during the parse-helper implementation.
