---
type: bubble
status: pending
step_id: S14
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python Engineer refactoring a Chainlit application into a stateless Temporal Client.
**Objective:** Strip all direct vault access, LLM calls, and git operations from the Chainlit app. Replace them with Temporal Client SDK calls: start `CopilotSessionWorkflow` on session open, send Signals on user input, poll Queries for chat history. Also render pending `FilerIngestionWorkflow` proposals as approval cards.
**Constraints:**
- Python 3.12, Chainlit (latest stable)
- The Chainlit container must have ZERO knowledge of vault paths, git repos, or LLM API keys — it only knows the Temporal server address
- Chat history is owned by the workflow, not Chainlit session state — Chainlit reads it via Query on every re-render
- The Filer approval UI renders proposals from all running `FilerIngestionWorkflow` instances in `awaiting_approval` state
- `cl.Action` buttons (approve/reject) send Signals to the specific workflow instance

---

## 1. Context

**Feature:** TRD Section 6 Phase 4 (Client Integration — copilot-ui), TRD Section 4.6 (Workflow Interfaces), PRD Section 4 (The Copilot and The Filer use cases)
**Depends On:** S11 (FilerIngestionWorkflow), S12 (CopilotSessionWorkflow)
**Current State:** All workflows implemented. `apps/copilot-ui/` contains the old V1 Chainlit app with direct vault and LLM calls.
**Target State:** `apps/copilot-ui/app.py` is a pure Temporal Client. No `gitpython`, `google-generativeai`, or `frontmatter` imports exist in the copilot-ui package.

---

## 2. Input

- `obsidian-note-manager/src_v2/entrypoints/chainlit_app.py` — existing app to replace (read-only)
- `packages/shared/models.py` — `ChatMessage`, `FilingProposal`
- `packages/shared/workflow_names.py` — all Signal/Query constants
- `apps/vault-worker/workflows/copilot_session.py` — workflow interface reference

---

## 3. Required Output

- [ ] `apps/copilot-ui/app.py` — new Chainlit app (Temporal Client only)
- [ ] `apps/copilot-ui/temporal_client.py` — thin wrapper around `temporalio.client.Client` with helper methods
- [ ] `apps/copilot-ui/requirements.txt` — `chainlit`, `temporalio`, `pydantic` (no vault/LLM dependencies)
- [ ] `apps/copilot-ui/Dockerfile`
- [ ] `tests/unit/test_copilot_ui.py` — tests for `temporal_client.py` helper methods using a mock Temporal client

---

## 4. Acceptance Criteria

- [ ] On Chainlit session start (`@cl.on_chat_start`), check browser session storage for an existing `workflow_id`. If found, verify the workflow is still running (handle via Temporal client); reconnect and restore chat history via `get_history` Query. If not found (or workflow no longer running), start a new `CopilotSessionWorkflow` and store the new `workflow_id` in session storage. This survives browser refresh without losing conversation state.
- [ ] `vault_path` is read from the `VAULT_PATH` environment variable on the `copilot-ui` container — it is NOT passed from the user or derived in the UI. This is the one exception to "zero vault knowledge": the UI must know the path to tell the workflow where to look. Alternatively, if `CopilotSessionInput` is refactored to read `VAULT_PATH` from the worker's own env, this env var can be removed from the UI container entirely.
- [ ] On user message (`@cl.on_message`), an `approve` or `reject` Signal... wait — on user message, a `receive_message` Signal is sent to the running `CopilotSessionWorkflow`
- [ ] After sending the Signal, the app polls `get_history` Query until a new assistant message appears, then renders it to the user
- [ ] A `/approvals` command (or on every chat start) lists pending `FilerIngestionWorkflow` proposals and renders each as a `cl.Message` with `cl.Action` approve/reject buttons. **Note:** `list_pending_filer_proposals()` uses the Temporal Client's `list_workflows` API with a status filter — this requires Temporal Advanced Visibility configured with PostgreSQL (set in `docker-compose.prod.yml`). Without it, the filter silently returns no results. Verify this works end-to-end during the manual smoke test.
- [ ] Clicking approve sends `approve` Signal to the correct workflow instance; clicking reject sends `reject` Signal
- [ ] `apps/copilot-ui/requirements.txt` does NOT contain `gitpython`, `google-generativeai`, `frontmatter`, or `GitPython`
- [ ] `temporal_client.py` helper method tests pass (using mock Temporal client)

---

## 5. Scope Boundary

**May modify:** `apps/copilot-ui/app.py`, `apps/copilot-ui/temporal_client.py`, `apps/copilot-ui/requirements.txt`, `apps/copilot-ui/Dockerfile`, `tests/unit/test_copilot_ui.py`
**Must not modify:** `packages/shared/`, `apps/vault-worker/`, `tests/fixtures/`, any workflow or activity files

---

## 6. TDD Constraints

- Write `test_copilot_ui.py` for `temporal_client.py` helper methods using a mock before implementing the helpers
- The Chainlit lifecycle (`@cl.on_chat_start`, `@cl.on_message`) cannot be easily unit-tested — focus unit tests on `temporal_client.py`; E2E validation is manual

---

## 7. Step-by-Step Plan

1. Write `tests/unit/test_copilot_ui.py` testing `temporal_client.py` helpers: `start_copilot_session()`, `send_user_message()`, `get_chat_history()`, `list_pending_filer_proposals()`, `send_filer_decision()`. Use a mock Temporal client. Run — fail.
2. Implement `temporal_client.py` with the five helper methods. Pass tests. Commit.
3. Implement `apps/copilot-ui/app.py`:
   - `@cl.on_chat_start`: call `start_copilot_session()`, store workflow ID in session
   - `@cl.on_message`: call `send_user_message()`, poll `get_chat_history()` for new assistant message, display it
   - Approval card rendering via `list_pending_filer_proposals()` + `cl.Action` buttons
4. Write minimal `Dockerfile`. Write `requirements.txt` without vault/LLM dependencies.
5. Manual smoke test: start the full Docker Compose stack, open Chainlit, send one message, verify a response arrives.
6. Commit.

---

## 8. Reference Material

### temporal_client.py helper signatures

```python
from temporalio.client import Client
from shared.models import ChatMessage, FilingProposal
from shared.workflow_names import *

class CopilotTemporalClient:
    def __init__(self, client: Client): self.client = client

    async def start_copilot_session(self, session_id: str, vault_path: str) -> str:
        """Start CopilotSessionWorkflow. Returns workflow ID."""

    async def send_user_message(self, workflow_id: str, message: str) -> None:
        """Send receive_message Signal to running workflow."""

    async def get_chat_history(self, workflow_id: str) -> list[ChatMessage]:
        """Query get_history from running workflow."""

    async def list_pending_filer_proposals(self) -> list[tuple[str, FilingProposal]]:
        """List all FilerIngestionWorkflow instances in awaiting_approval state.
        Returns list of (workflow_id, FilingProposal) tuples."""

    async def send_filer_decision(self, workflow_id: str, approved: bool) -> None:
        """Send approve or reject Signal to FilerIngestionWorkflow."""
```

### Chainlit approval card pattern

```python
@cl.on_chat_start
async def start():
    # Show pending approvals on session start
    proposals = await temporal.list_pending_filer_proposals()
    for wf_id, proposal in proposals:
        actions = [
            cl.Action(name="approve", value=wf_id, label="Approve"),
            cl.Action(name="reject", value=wf_id, label="Reject"),
        ]
        await cl.Message(
            content=f"**Pending Filing:** `{proposal.source_path}` → `{proposal.proposed_path}`\n"
                    f"Reasoning: {proposal.reasoning}",
            actions=actions,
        ).send()

@cl.action_callback("approve")
async def on_approve(action: cl.Action):
    await temporal.send_filer_decision(action.value, approved=True)
    await cl.Message(content=f"Filed ✓").send()

@cl.action_callback("reject")
async def on_reject(action: cl.Action):
    await temporal.send_filer_decision(action.value, approved=False)
    await cl.Message(content=f"Rejected.").send()
```
