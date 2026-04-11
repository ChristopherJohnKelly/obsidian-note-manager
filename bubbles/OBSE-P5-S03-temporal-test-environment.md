---
type: bubble
status: pending
step_id: S03
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python Engineer configuring a Temporal test environment.
**Objective:** Wire `temporalio.testing.WorkflowEnvironment` into pytest so that all subsequent Workflow and Activity tests can run in-process, in milliseconds, without a live Temporal server.
**Constraints:**
- Python 3.12
- Use `temporalio.testing.WorkflowEnvironment` (not a real Temporal server)
- The environment must be shared across the test session (session-scoped fixture) for performance
- All fixtures must be composable — later bubbles will add their own fixtures that build on top of these

---

## 1. Context

**Feature:** TRD Section 6, Phase 0 (Test Harness)
**Depends On:** S01 (shared models), S02 (Dummy Vault, Fake LLM)
**Current State:** Shared models and test fixtures exist. No Temporal test infrastructure yet.
**Target State:** `pytest` runs with a `WorkflowEnvironment` fixture available to all tests. A smoke test proves a trivial no-op Activity executes correctly in the environment.

---

## 2. Input

- `packages/shared/models.py`
- `tests/fixtures/dummy_vault/` — fixture files from S02
- `tests/mocks/fake_llm.py` — from S02

---

## 3. Required Output

- [ ] `tests/conftest.py` — shared pytest fixtures:
  - `temporal_env` (session-scoped `WorkflowEnvironment`)
  - `temporal_client` (derived from `temporal_env`)
  - `dummy_vault_path` (Path to `tests/fixtures/dummy_vault/`)
  - `fake_llm` (instance of `FakeLLMProvider`)
- [ ] `tests/e2e/test_smoke.py` — smoke test proving the environment works: runs a trivial `@activity.defn` and asserts its return value via a minimal Workflow
- [ ] Updated `pyproject.toml` (or `pytest.ini`) with `asyncio_mode = "auto"` and coverage config (≥ 90% threshold, excluding `tests/` and `apps/*/main.py`)

---

## 4. Acceptance Criteria

- [ ] `pytest tests/e2e/test_smoke.py` passes without a live Temporal server
- [ ] The smoke test executes in under 5 seconds
- [ ] `temporal_client` fixture is accessible from any test file by importing from `conftest`
- [ ] `dummy_vault_path` fixture returns a `Path` that exists and contains at least 12 `.md` files
- [ ] Coverage reporting is active; `pytest --cov` produces a report

---

## 5. Scope Boundary

**May modify:** `tests/conftest.py`, `tests/e2e/test_smoke.py`, root `pyproject.toml` / `pytest.ini`
**Must not modify:** `packages/`, `apps/`, fixture files in `tests/fixtures/`

---

## 6. TDD Constraints

- Write the smoke test first; it must fail with an import error before `conftest.py` is created
- Implement `conftest.py` fixtures; smoke test must pass
- No production Workflow or Activity logic in this bubble — the smoke test uses a trivial inline Activity only

---

## 7. Step-by-Step Plan

1. Write `tests/e2e/test_smoke.py`: define an inline `@activity.defn` that returns `"ok"`, a minimal `@workflow.defn` that executes it, and an async test that uses the `temporal_client` fixture to run the workflow and assert the result.
2. Run — fails (fixtures not found). Implement `tests/conftest.py` with the four fixtures.
3. Configure `asyncio_mode = "auto"` in `pyproject.toml` (required by `temporalio`). **Verify `pytest-asyncio` is present in the dev dependencies** — it was added in S01's root `pyproject.toml`. If absent, `asyncio_mode` is silently ignored and all async tests will hang or error with no useful message.
4. Run — smoke test passes.
5. Add coverage configuration: `[tool.pytest.ini_options] addopts = "--cov=apps --cov=packages --cov-fail-under=0"`. (Threshold starts at 0; it will be raised to 90 when real code exists.)
6. Commit.

---

## 8. Reference Material

### conftest.py skeleton

```python
import pytest
import pytest_asyncio
from pathlib import Path
from temporalio.testing import WorkflowEnvironment
from temporalio.client import Client
from tests.mocks.fake_llm import FakeLLMProvider

@pytest.fixture(scope="session")
def dummy_vault_path() -> Path:
    return Path(__file__).parent / "fixtures" / "dummy_vault"

@pytest.fixture(scope="session")
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider()

@pytest_asyncio.fixture(scope="session")
async def temporal_env():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env

@pytest_asyncio.fixture(scope="session")
async def temporal_client(temporal_env: WorkflowEnvironment) -> Client:
    return temporal_env.client
```

### Smoke test pattern

```python
import pytest
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.worker import Worker

@activity.defn
async def ping_activity() -> str:
    return "pong"

@workflow.defn
class PingWorkflow:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(
            ping_activity,
            schedule_to_close_timeout=timedelta(seconds=5),
        )

async def test_smoke(temporal_client):
    async with Worker(temporal_client, task_queue="test-queue",
                      workflows=[PingWorkflow], activities=[ping_activity]):
        result = await temporal_client.execute_workflow(
            PingWorkflow.run, id="smoke-test", task_queue="test-queue"
        )
    assert result == "pong"
```

### pyproject.toml additions

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "--cov=apps --cov=packages --cov-report=term-missing"

[tool.coverage.run]
omit = ["tests/*", "*/main.py", "*/__init__.py"]
```
