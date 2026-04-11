---
type: bubble
status: pending
step_id: S04
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python Engineer migrating vault I/O logic to Temporal Activities.
**Objective:** Extract the vault read/write/scan operations from `src_v2/infrastructure/file_system/adapters.py` and expose them as individual Temporal `@activity.defn` functions in `apps/vault-worker/activities/vault_io.py`. Each Activity must be independently testable against the Dummy Vault.
**Constraints:**
- Python 3.12
- Each Activity is a **synchronous `def` function** (not `async def`, not a class method). `pathlib` and `python-frontmatter` are blocking I/O libraries. Defining the Activity as `def` causes Temporal to execute it automatically in a `ThreadPoolExecutor`, keeping the asyncio event loop free. Do not use `async def` — it would block the event loop during file reads and prevent the worker from processing signals or picking up other tasks.
- Activities receive and return only serialisable types (Pydantic models, primitives, `str` paths — not `Path` objects in return values unless serialised)
- Do not call `git` from vault I/O Activities — git is in a separate Activity module (S05)
- Reuse the audit scoring logic from `src_v2` verbatim where possible; do not redesign it

---

## 1. Context

**Feature:** TRD Section 4 (Activities), Section 4.7 (Domain Models)
**Depends On:** S03 (Temporal test environment running)
**Current State:** Temporal test environment configured. No Activities implemented yet.
**Target State:** All vault I/O Activities implemented, individually tested against the Dummy Vault, with ≥ 90% coverage of `vault_io.py`.

---

## 2. Input

- `packages/shared/models.py` — `VaultNote`, `Frontmatter`, `ValidationResult`, `CodeRegistryEntry`
- `tests/fixtures/dummy_vault/` — test against this, never production vault
- `obsidian-note-manager/src_v2/infrastructure/file_system/adapters.py` — source logic to migrate (read-only)
- `tests/conftest.py` — `temporal_client`, `dummy_vault_path` fixtures

---

## 3. Required Output

- [ ] `apps/vault-worker/activities/vault_io.py` — all Activities below, each decorated with `@activity.defn`
- [ ] `tests/unit/test_vault_io.py` — unit tests for every Activity

**Activities to implement:**

| Activity | Input | Output |
| :--- | :--- | :--- |
| `read_note(vault_root: str, path: str)` | Vault root + relative path | `VaultNote \| None` |
| `save_note(vault_root: str, path: str, note: VaultNote)` | Vault root + path + note | `None` |
| `delete_note(vault_root: str, path: str)` | Vault root + relative path | `None` |
| `list_notes_in(vault_root: str, directory: str)` | Vault root + directory | `list[str]` (relative paths) |
| `read_raw(vault_root: str, path: str)` | Vault root + relative path | `str \| None` |
| `scan_vault(vault_root: str)` | Vault root | `list[ValidationResult]` |
| `validate_note(vault_root: str, path: str)` | Vault root + relative path | `ValidationResult \| None` |
| `get_skeleton(vault_root: str)` | Vault root | `str` |
| `get_code_registry(vault_root: str)` | Vault root | `list[CodeRegistryEntry]` |

---

## 4. Acceptance Criteria

- [ ] `read_note` returns a `VaultNote` with correct frontmatter for every clean fixture file
- [ ] `read_note` returns `None` for a non-existent path
- [ ] `save_note` writes a file; subsequent `read_note` returns the same content
- [ ] `delete_note` removes a file; subsequent `read_note` returns `None`
- [ ] `scan_vault` on Dummy Vault returns the expected scores for all 11 non-excluded files (see B02 score table)
- [ ] `scan_vault` excludes files under `00. Inbox/` and any other excluded directories
- [ ] `validate_note` on a code-mismatch file returns `ValidationResult` with `score=50`
- [ ] `get_skeleton` returns a non-empty string containing `[[` wiki-link targets
- [ ] `get_code_registry` returns at least one `CodeRegistryEntry` for the `TEST-P01` project
- [ ] All Activities are registered with the Temporal worker in a smoke integration test

---

## 5. Scope Boundary

**May modify:** `apps/vault-worker/activities/vault_io.py`, `tests/unit/test_vault_io.py`
**Must not modify:** `packages/shared/`, `tests/fixtures/`, `tests/conftest.py`, `tests/mocks/`

---

## 6. TDD Constraints

- Write `tests/unit/test_vault_io.py` with all test stubs (one per acceptance criterion) before writing any Activity code
- Tests must fail with `ImportError` initially
- Implement Activities one at a time: write test → implement Activity → pass test → commit
- Do not implement the next Activity until the current one's tests are green

---

## 7. Step-by-Step Plan

1. Create `apps/vault-worker/activities/__init__.py` and `apps/vault-worker/activities/vault_io.py` (empty stubs).
2. Write all test stubs in `tests/unit/test_vault_io.py`. Each test uses `dummy_vault_path` fixture as vault root. Tests fail (functions not implemented).
3. Implement Activities in dependency order: `read_note` → `save_note` → `delete_note` → `list_notes_in` → `read_raw` (these are pure I/O). Pass their tests. Commit.
4. Implement `validate_note` and `scan_vault` (require scoring logic from `src_v2`). Port the `_validate_note` rules directly. Pass their tests. Commit.
5. Implement `get_skeleton` and `get_code_registry`. Pass their tests. Commit.
6. Write an integration test that registers all Activities with a Temporal worker and executes `read_note` via the Temporal client (not direct call) to verify Activity registration.

---

## 8. Reference Material

### Activity signature pattern

```python
from temporalio import activity
from shared.models import VaultNote, ValidationResult, CodeRegistryEntry

@activity.defn
def read_note(vault_root: str, path: str) -> VaultNote | None:
    """Read a note from vault_root/path. Returns None if not found.
    
    Synchronous def: Temporal runs this in a ThreadPoolExecutor automatically.
    Do not convert to async def — pathlib is blocking I/O.
    """
    ...
```

### Audit scoring rules to port (from src_v2)

```python
BAD_TITLES = frozenset({"untitled", "meeting", "note", "call"})
EXCLUDED_DIRS = frozenset({"99. System", "00. Inbox", ".git", ".obsidian", ".trash"})

# Rule 1: missing aliases AND tags → +10
# Rule 2: filename stem doesn't start with expected project code → +50
#          EXCEPTION: skip Rule 2 if Rule 3 also fires on the same file.
#          A generic-named file predictably lacks a code prefix — both firing
#          would double-penalise the same underlying condition.
# Rule 3: filename stem.lower() in BAD_TITLES → +20
```

### Test pattern using dummy vault

```python
import pytest
from pathlib import Path
from apps.vault_worker.activities.vault_io import read_note

# Activities are synchronous def functions — call them directly, no await needed.
# (When Temporal executes them via a Worker, it handles the thread pool internally.)
def test_read_note_returns_vault_note(dummy_vault_path):
    result = read_note(str(dummy_vault_path), "20. Projects/TEST-P01/TEST-P01 - Project Root.md")
    assert result is not None
    assert result.frontmatter.code == "TEST-P01"

def test_read_note_returns_none_for_missing(dummy_vault_path):
    result = read_note(str(dummy_vault_path), "does/not/exist.md")
    assert result is None
```
