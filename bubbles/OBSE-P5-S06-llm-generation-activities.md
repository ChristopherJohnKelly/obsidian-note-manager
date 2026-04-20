---
type: bubble
status: pending
step_id: S06
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python Engineer migrating LLM operations to Temporal Activities.
**Objective:** Implement `generate_proposal` and `generate_fix` as Temporal Activities. Both must be testable via the Fake LLM without real API calls.
**Constraints:**
- Python 3.12
- The real implementation uses `google-generativeai` (Gemini); the Activity must accept an injectable LLM provider for testability
- All Activities are **synchronous `def` functions** (not `async def`). The Gemini synchronous client makes a blocking network call that can take several seconds. Defining as `def` causes Temporal to run it in a `ThreadPoolExecutor` automatically. Do not use `async def`.
- **Retry policies are applied at the `workflow.execute_activity()` call site, not at the `@activity.defn` decorator.** Define `LLM_RETRY_POLICY` as a module-level constant in `llm.py` so downstream Workflows can import and apply it. B06 validates the retry policy works by using a minimal test Workflow that passes the policy to `execute_activity()`.
- The `%%FILE%%` response format from src_v2 must be preserved — downstream consumers depend on it

---

## 1. Context

**Feature:** TRD Section 4 (LLM Generation Activities)
**Depends On:** S03 (Temporal test environment), S04 (vault_io for context loading)
**Current State:** Vault I/O Activities exist. No LLM Activities yet.
**Target State:** Both LLM Activities implemented, tested with Fake LLM, and correctly applying retry policies.

---

## 2. Input

- `packages/shared/models.py` — `FilingProposal`, `AuditProposal`, `VaultContext`
- `tests/mocks/fake_llm.py` — Fake LLM responses
- `obsidian-note-manager/src_v2/use_cases/proposal_service.py` — prompt construction logic (read-only)
- `obsidian-note-manager/src_v2/infrastructure/llm/adapters.py` — Gemini adapter (read-only)
- `obsidian-note-manager/src_v2/core/response_parser.py` — `%%FILE%%` parser (read-only, may reuse directly)

---

## 3. Required Output

- [ ] `apps/vault_worker/activities/llm.py` — two Activities with retry policies
- [ ] `apps/vault_worker/activities/llm_provider.py` — `GeminiProvider` (real) and an abstract base; `FakeLLMProvider` in tests implements the same base
- [ ] `apps/vault_worker/core/response_parser.py` — copied/migrated from `src_v2` (the parser is pure logic, no framework dependencies)
- [ ] `tests/unit/test_llm_activities.py` — tests using Fake LLM

**Activities:**

| Activity | Input | Output |
| :--- | :--- | :--- |
| `generate_proposal(context: VaultContext, source_body: str)` | Vault context + raw note body | `str` (raw LLM response with `%%FILE%%` markers) |
| `generate_fix(note: VaultNote, reasons: list[str], context: VaultContext)` | Note + audit reasons + context | `str` (raw LLM response with `%%FILE%%` markers) |

---

## 4. Acceptance Criteria

- [ ] `generate_proposal` called with `FakeLLMProvider` returns a string containing `%%FILE%%` and `%%END%%`
- [ ] `generate_fix` called with a Rule 2 violation note and `FakeLLMProvider` returns a valid fix response
- [ ] `LLM_RETRY_POLICY` is defined in `llm.py` (max 3 attempts, 1s initial interval, 2.0 backoff coefficient, non-retryable on `ValueError`) and applied via `execute_activity(..., retry_policy=LLM_RETRY_POLICY)` in the test Workflow — not at the `@activity.defn` decorator
- [ ] A test simulating a transient failure (first call raises `RuntimeError`, second succeeds) verifies the retry policy fires correctly using `temporalio.testing`
- [ ] `response_parser.py` correctly extracts file paths and content from a `%%FILE%%`-formatted response (test with both Fake LLM output and a hand-crafted fixture)

---

## 5. Scope Boundary

**May modify:** `apps/vault_worker/activities/llm.py`, `apps/vault_worker/activities/llm_provider.py`, `apps/vault_worker/core/response_parser.py`, `tests/unit/test_llm_activities.py`
**Must not modify:** `tests/mocks/fake_llm.py` (interface is fixed from S02), `packages/shared/`, vault_io or git_ops Activities

---

## 6. TDD Constraints

- Write all tests in `test_llm_activities.py` before implementing the Activities
- The retry test must be written before implementing the retry policy — verify the test fails when no retry policy is set, then add the policy
- `response_parser.py` tests must be written and passing before any Activity uses the parser

---

## 7. Step-by-Step Plan

1. Copy `response_parser.py` from `src_v2/core/` into `apps/vault_worker/core/`. Write `tests/unit/test_response_parser.py`. Run — tests should pass (this is pure logic with no framework dependencies).
2. Define the abstract LLM provider base in `llm_provider.py`. Verify `FakeLLMProvider` from `tests/mocks/` implements the same interface (if not, align them).
3. Write `tests/unit/test_llm_activities.py` covering all acceptance criteria. Run — tests fail (Activities not implemented).
4. Implement `generate_proposal` with retry policy. Pass its tests.
5. Implement `generate_fix` with retry policy. Pass its tests.
6. Implement `GeminiProvider` (real Gemini adapter, injected via env var `GEMINI_API_KEY`). This has no unit tests — it is validated in the final manual E2E test only.

---

## 8. Reference Material

### Activity and retry policy definition

```python
from datetime import timedelta
from temporalio import activity
from temporalio.common import RetryPolicy
from packages.shared.models import VaultContext, VaultNote

# Defined here so downstream Workflows can import and apply it at execute_activity() call site.
# Do NOT pass this to @activity.defn — that decorator does not accept retry policies.
LLM_RETRY_POLICY = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    non_retryable_error_types=["ValueError"],
)

@activity.defn
def generate_proposal(context: VaultContext, source_body: str) -> str:
    """Generate a filing proposal. Returns raw LLM response with %%FILE%% markers.

    Synchronous def: Temporal runs this in a ThreadPoolExecutor automatically.
    The LLM provider makes a blocking network call — do not use async def.
    Retry policy is applied by the calling Workflow via execute_activity(), not here.
    """
    ...

@activity.defn
def generate_fix(note: VaultNote, reasons: list[str], context: VaultContext) -> str:
    """Generate a fix proposal for a Night Watchman violation. Returns %%FILE%% response.

    Synchronous def — see generate_proposal docstring for rationale.
    """
    ...
```

### Retry test pattern using Temporal test environment

The retry policy is set inside a test Workflow that calls `execute_activity()` — this is the only place Temporal respects it.

```python
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.worker import Worker
from apps.vault_worker.activities.llm import LLM_RETRY_POLICY

call_count = 0

@activity.defn
def flaky_generate() -> str:
    global call_count
    call_count += 1
    if call_count < 2:
        raise RuntimeError("transient failure")
    return "%%FILE%%\npath: test.md\n---\n---\n%%END%%"

@workflow.defn
class RetryTestWorkflow:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(
            flaky_generate,
            schedule_to_close_timeout=timedelta(seconds=10),
            retry_policy=LLM_RETRY_POLICY,
        )

async def test_generate_retries_on_transient_failure(temporal_client):
    global call_count
    call_count = 0
    async with Worker(temporal_client, task_queue="test-q",
                      workflows=[RetryTestWorkflow], activities=[flaky_generate]):
        result = await temporal_client.execute_workflow(
            RetryTestWorkflow.run, id="retry-test", task_queue="test-q"
        )
    assert call_count == 2
```

### %%FILE%% format (from src_v2)

```
%%FILE%%
path: 30. Areas/1. Test Area/AREA - Note.md
---
frontmatter: yaml here
---
body content here
%%END%%
```
