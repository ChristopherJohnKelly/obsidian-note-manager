---
type: bubble
status: pending
step_id: S01
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python Engineer setting up a new monorepo.
**Objective:** Create the complete folder structure, package configuration, and shared domain models for the `obsidian-automation` monorepo. This is a greenfield setup; no application logic is implemented here.
**Constraints:**
- Python 3.12
- Pydantic v2 (`pydantic>=2.0`)
- `temporalio` SDK (latest stable)
- All `pyproject.toml` files use `hatchling` as the build backend
- Do not implement any Temporal Workflows or Activities yet — only scaffolding and shared models

---

## 1. Context

**Feature:** TRD Section 5 (Monorepo Structure), Section 4.7 (Core Domain Models)
**Depends On:** None (greenfield)
**Current State:** An empty `obsidian-automation` GitHub repository exists with only a README.
**Target State:** A working monorepo skeleton with all packages installable in editable mode, shared domain models defined and tested, and a passing `pytest` run (even if only the model tests run).

---

## 2. Input

- `TRD - Temporal SOA Migration.md` — Section 4.7 for all model definitions
- `obsidian-note-manager/src_v2/core/domain/models.py` — existing models to migrate (read-only reference)

---

## 3. Required Output

- [ ] `packages/shared/pyproject.toml` — installable as `obsidian-shared`
- [ ] `packages/shared/__init__.py`
- [ ] `packages/shared/models.py` — all domain models from TRD Section 4.7
- [ ] `packages/shared/workflow_names.py` — workflow/signal/query name constants
- [ ] `apps/vault_worker/pyproject.toml` — depends on `obsidian-shared`
- [ ] `apps/vault_worker/__init__.py`
- [ ] `apps/copilot_ui/pyproject.toml` — depends on `obsidian-shared`
- [ ] `apps/github_runner/pyproject.toml` — depends on `obsidian-shared`
- [ ] `tests/pyproject.toml` or root `pyproject.toml` — test runner config, including a `[project.optional-dependencies] dev = [...]` block containing at minimum: `pytest`, `pytest-asyncio`, `pytest-cov`, `python-frontmatter`. **`pytest-asyncio` is required here** — S03 sets `asyncio_mode = "auto"` which is a `pytest-asyncio` setting and will fail silently if the package is absent.
- [ ] `tests/__init__.py`
- [ ] `tests/test_models.py` — unit tests for every model in `shared/models.py`

---

## 4. Acceptance Criteria

- [ ] `pip install -e packages/shared` completes without error
- [ ] `pip install -e apps/vault_worker` completes without error
- [ ] Every model in `shared/models.py` can be instantiated with minimal valid arguments
- [ ] Every model rejects clearly invalid input (e.g., wrong types) with a Pydantic validation error
- [ ] `pytest tests/test_models.py` passes with ≥ 90% coverage of `shared/models.py`
- [ ] `workflow_names.py` exports string constants for all workflow, signal, and query names defined in TRD Section 4.6

---

## 5. Scope Boundary

**May modify:** `packages/`, `apps/*/pyproject.toml`, `apps/*/__init__.py`, `tests/test_models.py`, root `pyproject.toml` / `pytest.ini`
**Must not modify:** Any application logic files (no `workflows/`, `activities/` yet)

---

## 6. TDD Constraints

- Write `tests/test_models.py` with all model tests BEFORE implementing `models.py`
- Tests must fail (ImportError or ValidationError) before implementation
- Implement models to pass tests — no extra fields beyond TRD spec
- Commit after all model tests are green
- Capture field validation intent in model docstrings

---

## 7. Step-by-Step Plan

1. Create the folder structure as per TRD Section 5. Create all `__init__.py` and `pyproject.toml` stubs.
2. Write `tests/test_models.py` — one test class per model, covering: valid instantiation, field defaults, Pydantic `extra="allow"` behaviour on `Frontmatter`, and rejection of invalid types.
3. Run `pytest` — confirm all model tests fail (models not yet implemented).
4. Implement `packages/shared/models.py` with all models from TRD Section 4.7.
5. Run `pytest` — confirm all model tests pass.
6. Implement `packages/shared/workflow_names.py` with constants for all names in TRD Section 4.6.
7. Write a test asserting all constants are non-empty strings and match the expected naming convention.

---

## 8. Reference Material

### Full model set (from TRD Section 4.7)

```python
# packages/shared/models.py
from pathlib import Path
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class Frontmatter(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str | None = None
    status: str | None = None
    title: str | None = None
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    code: str | None = None
    folder: str | None = None

class VaultNote(BaseModel):
    path: Path
    frontmatter: Frontmatter
    body: str = ""

class ValidationResult(BaseModel):
    path: Path
    score: int
    reasons: list[str] = Field(default_factory=list)

class CodeRegistryEntry(BaseModel):
    code: str
    name: str
    type: str = ""
    folder: str

class VaultContext(BaseModel):
    context_code: str
    root_note: VaultNote
    related_notes: list[VaultNote]
    skeleton: str
    code_registry: str

class FilingProposal(BaseModel):
    source_path: Path
    proposed_path: Path
    proposed_frontmatter: Frontmatter
    reasoning: str

class AuditProposal(BaseModel):
    target_path: Path
    proposed_content: str
    reasons: list[str]
    score: int

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tool_name: str | None = None
```

### Workflow name constants (from TRD Section 4.6)

```python
# packages/shared/workflow_names.py

# Workflow type names
VAULT_MANAGER_WORKFLOW = "VaultManagerWorkflow"
COPILOT_SESSION_WORKFLOW = "CopilotSessionWorkflow"
NIGHT_WATCHMAN_WORKFLOW = "NightWatchmanWorkflow"
FILER_INGESTION_WORKFLOW = "FilerIngestionWorkflow"
READ_VAULT_WORKFLOW = "ReadVaultWorkflow"
WRITE_VAULT_WORKFLOW = "WriteVaultWorkflow"

# Well-known workflow IDs (for addressing long-running singletons)
VAULT_MANAGER_ID = "vault-manager"

# Signals
SIG_RECEIVE_MESSAGE = "receive_message"
SIG_CANCEL_SESSION = "cancel_session"
SIG_APPROVE = "approve"
SIG_REJECT = "reject"

# Updates
UPD_ENSURE_SYNCED = "ensure_synced"

# Queries
QRY_GET_HISTORY = "get_history"
QRY_GET_STATUS = "get_status"
QRY_GET_SYNC_STATUS = "get_sync_status"
QRY_GET_DRAFT_PROPOSAL = "get_draft_proposal"
QRY_GET_PROGRESS = "get_progress"

# Task Queues
QUEUE_DEFAULT = "vault-default"
QUEUE_MUTATION = "vault-mutation-queue"
```
