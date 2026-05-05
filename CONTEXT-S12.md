---
step_id: S12
step_slug: copilot-session-workflow
feature_branch: feat/OBSE-P5-temporal-soa-migration
bubble_ref: OBSE-P5-S12-copilot-session-workflow.md
attempts: 1
bubble_hash: c5e56ef8b30d07440850389bf91fdee203ec414da9121c652b5751a921ec446e
---
## Goal
See the bubble body below (`OBSE-P5-S12-copilot-session-workflow.md`) — the bubble carries the
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
step_id: S12
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python AI Engineer implementing a stateful ReAct agent as a Temporal Workflow.
**Objective:** Implement `CopilotSessionWorkflow` — a long-running workflow where one Chainlit session = one workflow execution. The workflow runs a hand-rolled ReAct agent loop driven by user message Signals. Chat history lives in the workflow state; Chainlit is stateless and reads it via Query.
**Constraints:**
- Python 3.12
- Hand-rolled ReAct loop — do not use LangChain, LangGraph, or any agent framework
- The LLM Activity returns either a direct response string or a structured tool-call (parsed from the LLM output)
- Tool calls are dispatched as child workflow calls (`ReadVaultWorkflow`) or Activity calls
- Workflow must handle concurrent Signals safely — only one ReAct iteration runs at a time
- Do not implement all tools in this bubble — implement `get_skeleton` and `get_code_registry` as a baseline; add remaining tools in the corresponding integration Bubble (B14)

---

## 1. Context

**Feature:** TRD Section 4 (CopilotSessionWorkflow, ReAct Agent), TRD Section 4.6 (Workflow Interface Specifications), PRD Section 4 (The Copilot use case)
**Depends On:** S06 (LLM Activities), S07 (ReadVaultWorkflow)
**Current State:** All child workflows and Activities implemented. Filer workflow implemented (S11).
**Target State:** `CopilotSessionWorkflow` E2E passing: single-turn response test, tool-use test (LLM requests `get_skeleton`, result appended to history), multi-turn test.

---

## 2. Input

- `apps/vault_worker/workflows/read_vault.py`
- `apps/vault_worker/activities/llm.py`
- `apps/vault_worker/activities/vault_io.py`
- `packages/shared/models.py` — `ChatMessage`, `VaultContext`
- `packages/shared/workflow_names.py` — Signal/Query name constants
- `tests/mocks/fake_llm.py` — extend with `generate_react_response()` (direct and tool-call variants)

---

## 3. Required Output

- [ ] `apps/vault_worker/activities/llm.py` — add `generate_chat_response(messages: list[ChatMessage]) -> str` Activity. This is a new synchronous `def` Activity (same `def` rule as other LLM Activities). `generate_proposal` and `generate_fix` are for structured vault operations; `generate_chat_response` is the general-purpose ReAct loop LLM call. Add corresponding `FakeLLMProvider` method to `tests/mocks/fake_llm.py`.
- [ ] `apps/vault_worker/workflows/copilot_session.py` — `CopilotSessionWorkflow` with ReAct loop
- [ ] `apps/vault_worker/core/react_parser.py` — parses LLM output into `DirectResponse | ToolCall`
- [ ] `tests/unit/test_react_parser.py`
- [ ] `tests/e2e/test_copilot_session_workflow.py` — three tests (single-turn, tool-use, multi-turn)

**Workflow interface (from TRD Section 4.6):**

```python
@dataclass
class CopilotSessionInput:
    vault_path: str
    session_id: str

@workflow.defn
class CopilotSessionWorkflow:
    @workflow.run
    async def run(self, input: CopilotSessionInput) -> None: ...
    # runs until cancel_session Signal or external termination

    @workflow.signal
    async def receive_message(self, message: dict) -> None: ...
    # message is a serialised ChatMessage

    @workflow.signal
    async def cancel_session(self) -> None: ...

    @workflow.query
    def get_history(self) -> list[dict]: ...

    @workflow.query
    def get_status(self) -> str: ...
    # "idle" | "thinking" | "complete"
```

---

## 4. Acceptance Criteria

- [ ] `react_parser.py` correctly distinguishes a direct LLM response from a tool-call response given two fixture strings
- [ ] **Single-turn test:** Send one message → LLM returns direct response → `get_history` contains user message + assistant response → `get_status` returns `"idle"` (ready for next message)
- [ ] **Tool-use test:** Send one message → Fake LLM returns tool-call for `get_skeleton` → skeleton is retrieved → LLM is called again with skeleton in context → final response appended to history
- [ ] **Multi-turn test:** Send three messages sequentially; all six messages (user + assistant pairs) appear in `get_history` in correct order
- [ ] `cancel_session` Signal causes workflow to exit cleanly; `get_status` returns `"complete"`
- [ ] Concurrent Signals (two messages sent simultaneously) are queued and processed sequentially

---

## 5. Scope Boundary

**May modify:** `apps/vault_worker/activities/llm.py` (add `generate_chat_response` only), `apps/vault_worker/workflows/copilot_session.py`, `apps/vault_worker/core/react_parser.py`, `tests/unit/test_react_parser.py`, `tests/e2e/test_copilot_session_workflow.py`, `tests/mocks/fake_llm.py` (extend only, do not break existing tests)
**Must not modify:** `apps/vault_worker/workflows/read_vault.py`, `apps/vault_worker/workflows/write_vault.py`, `packages/shared/`, other workflow files, other Activity files

---

## 6. TDD Constraints

- Write and pass `test_react_parser.py` first — the parser is pure logic with no Temporal dependencies
- Write E2E tests before implementing the workflow
- The tool-use test must use the Fake LLM returning a tool-call string; implement the parser to handle it; only then implement the tool dispatch

---

## 7. Step-by-Step Plan

1. Design the tool-call format: a simple convention such as `TOOL: get_skeleton\nARGS: {}` in the LLM response. Write `react_parser.py` to split LLM output into `DirectResponse` or `ToolCall`. Write and pass `test_react_parser.py`. Commit.
2. Extend `FakeLLMProvider` with `generate_react_response(mode: "direct" | "tool_call")` returning the appropriate format.
3. Write all three E2E tests. Run — fail.
4. Implement `CopilotSessionWorkflow`: main loop waits for `receive_message` Signal; on receipt, runs one ReAct iteration; appends to `_history`; returns to idle.
5. Implement the ReAct iteration: call `generate_text` LLM Activity → parse → if tool call dispatch to appropriate Activity/child workflow → append tool result to history → call LLM again → append final response.
6. Pass single-turn → commit. Pass tool-use → commit. Pass multi-turn → commit.

---

## 8. Reference Material

### ReAct loop structure (hand-rolled)

```python
async def _run_react_iteration(self, user_message: str, vault_path: str):
    """Run one full ReAct iteration: prompt → (optional tool) → response."""
    self._status = "thinking"
    history_ctx = self._build_prompt(self._history + [user_message])

    raw_response = await workflow.execute_activity(
        generate_chat_response, args=[self._history],  # list[ChatMessage]; imported from llm.py
        schedule_to_close_timeout=timedelta(minutes=2),
    )

    parsed = parse_react_response(raw_response)

    if isinstance(parsed, ToolCall):
        tool_result = await self._dispatch_tool(parsed, vault_path)
        # Second LLM call with tool result
        augmented_ctx = history_ctx + f"\nTOOL RESULT: {tool_result}"
        raw_response = await workflow.execute_activity(
            generate_text, args=[augmented_ctx],
            schedule_to_close_timeout=timedelta(minutes=2),
        )

    self._history.append({"role": "assistant", "content": raw_response})
    self._status = "idle"
```

### Tool-call format convention

```
To invoke a tool, the LLM outputs:
TOOL: <tool_name>
ARGS: <json_args>

Example:
TOOL: get_skeleton
ARGS: {}

react_parser.py detects the "TOOL:" prefix and returns a ToolCall dataclass.
Any other output is treated as a DirectResponse.
```

### Signal-safe main loop

```python
@workflow.run
async def run(self, input: CopilotSessionInput) -> None:
    while not self._cancelled:
        await workflow.wait_condition(
            lambda: len(self._pending_messages) > 0 or self._cancelled
        )
        if self._cancelled:
            break
        msg = self._pending_messages.pop(0)
        await self._run_react_iteration(msg["content"], input.vault_path)
    self._status = "complete"
```

## Steering from prior steps
- [S03] Use `WorkflowEnvironment.start_time_skipping()` (not `start_local`) for in-process Temporal tests — applicable here because S12's three E2E tests run against the test fixture environment.
- [S03] Sync `def` Activities need `activity_executor=ThreadPoolExecutor(...)` on the Worker — applicable here because `generate_chat_response` is a new sync `def` LLM Activity that the test Worker must register.
- [S03] Session-scoped `pytest_asyncio` fixtures require `asyncio_mode = "auto"` in pyproject.toml — applicable here because the long-running session workflow tests share the session client/env fixtures.
- [S04] Python package path is `apps/vault_worker/` (underscore); the hyphenated dir is Docker-only — applicable here because the bubble's `Required Output` lists `apps/vault_worker/workflows/copilot_session.py` and `core/react_parser.py`.
- [S04] Use `from packages.shared.models import ...` (the editable install adds `packages/shared` to sys.path) — applicable here because the workflow imports `ChatMessage` and `VaultContext` from `packages/shared/models.py`.
- [S04/S07] Pydantic models with `Path` fields are not JSON-serialisable under Temporal's default converter; needs `pydantic_data_converter` or string-only returns — applicable here because the ReAct tool dispatch invokes `ReadVaultWorkflow` as a child workflow whose return crosses the boundary.
- [S06] LLM Activities use module-level `_provider` + `configure_provider()` with an autouse fixture that injects `FakeLLMProvider` and resets after each test — applicable here because `generate_chat_response` must follow the same testability pattern and the bubble extends `FakeLLMProvider` with `generate_react_response`.
- [S06] FakeLLM placeholders like `{original_path}` are literal — assert on format markers, not substituted values — applicable here because the tool-call fixture string (`TOOL: get_skeleton\nARGS: {}`) must be matched on its prefix, not interpolated content.
- [S08] Mock activities for E2E tests must register under the real activity names via `@activity.defn(name="...")` — applicable here because the tool-use E2E test dispatches real tools (`get_skeleton`, `get_code_registry`) by name but exercises them through fakes.
- [S08] `create_workers(client)` may only run once per client — Temporal forbids re-registering the same task queue — applicable here because the E2E suite reuses the session client to register workers spanning default/mutation queues.
- [S09] `workflow.wait_condition(..., timeout=…)` raises `asyncio.TimeoutError`; must be caught explicitly — applicable here because the bubble's main loop uses `wait_condition` to await pending messages or cancel.
- [S09] Python `@workflow.update`/handler coroutines interleave at `await` points and are NOT serialised by default — applicable here because the bubble's "concurrent Signals are processed sequentially" AC requires the explicit `_pending_messages` queue + single-iteration main-loop pattern (or an `asyncio.Lock`) rather than relying on handler serialisation.
- [S09] Use `handle.terminate()` (not `cancel()`) to clean up long-running workflows in test teardown — applicable here because `CopilotSessionWorkflow` runs `while not self._cancelled` with `wait_condition` and will leak timer state across tests if only cancelled.
- [Orchestration] Scratch/debug tests must use `test_explore_*` (or `test_debug_*`, etc.) prefixes; >3 such files in a session triggers wind-down — applicable here because S12's TDD path (parser unit → 3 E2E tests) is rabbit-hole-prone if signal serialisation or tool dispatch misbehaves.
- [Orchestration] One `pytest` invocation at a time; check `ps aux | grep pytest` before starting and `pkill -f "pytest tests/"` to clear stuck runs — applicable here because S12 has multiple test phases (parser, then per-AC E2E commits) and prior parallel pytest runs caused hangs.
- [Persistent] `.gitignore` is append-only — never modify existing entries — applicable here because new test artefacts (e.g. transient session files) may tempt edits to existing patterns.

## Prior failures
### Attempt 1
## Prior failures

