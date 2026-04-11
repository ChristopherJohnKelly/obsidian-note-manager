---
type: bubble
status: pending
step_id: S05
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python/DevOps Engineer implementing Git operations as Temporal Activities.
**Objective:** Implement `git_clone`, `git_pull`, `git_commit`, and `git_push` as Temporal Activities. These are the only Activities that touch the Git remote; all other vault I/O goes through the vault_io Activities.
**Constraints:**
- Python 3.12
- Use `GitPython` (`gitpython`) library, consistent with `src_v2`
- All Activities must be **synchronous `def` functions** (not `async def`). GitPython is a fully synchronous, blocking library — `clone_from`, `pull`, `commit`, and `push` can each block for several seconds. Defining the Activity as `def` causes Temporal to run it in a `ThreadPoolExecutor` automatically, keeping the asyncio event loop free during long git operations. Do not convert to `async def` — it would stall the worker and prevent heartbeats and signal processing for the duration of the call.
- PAT is injected via environment variable `GITHUB_PAT` — never hardcoded
- Tests must use a local bare repository as the remote (no real GitHub calls)
- Each Activity is idempotent where possible: `git_pull` on a clean repo is safe to call multiple times

---

## 1. Context

**Feature:** TRD Section 4 (Git Operations Activities), Section 7 (Vault Synchronisation Strategy)
**Depends On:** S03 (Temporal test environment)
**Current State:** Temporal test environment configured. Vault I/O Activities implemented (S04, may run in parallel with this bubble).
**Target State:** All four Git Activities implemented and tested against a local bare repo (no network calls in tests).

---

## 2. Input

- `tests/conftest.py` — `temporal_client` fixture
- `obsidian-note-manager/src_v2` — no direct git ops module exists; git was called via `GitPython` in entrypoints (read-only reference)
- TRD Section 7 — sync policy contract that these Activities must fulfil

---

## 3. Required Output

- [ ] `apps/vault-worker/activities/git_ops.py` — four Activities
- [ ] `tests/unit/test_git_ops.py` — tests using a local bare repo fixture

**Activities to implement:**

| Activity | Input | Output |
| :--- | :--- | :--- |
| `git_clone(repo_url: str, target_path: str, pat: str)` | Remote URL, local path, PAT | `None` |
| `git_pull(vault_path: str)` | Local repo path | `None` |
| `git_commit(vault_path: str, message: str)` | Local repo path + commit message | `str` (commit SHA) |
| `git_push(vault_path: str)` | Local repo path | `None` |

---

## 4. Acceptance Criteria

- [ ] `git_clone` creates a local clone; the directory contains a `.git` folder and the expected files
- [ ] `git_pull` on a repo where the remote has a new commit pulls that commit successfully
- [ ] `git_pull` on an already up-to-date repo completes without error
- [ ] `git_commit` creates a commit with the specified message; returns the commit SHA
- [ ] `git_commit` on a repo with no staged changes raises a clear error (not a silent no-op)
- [ ] `git_push` pushes commits to the remote; the remote's HEAD advances
- [ ] All tests use only local bare repositories — no real network calls

---

## 5. Scope Boundary

**May modify:** `apps/vault-worker/activities/git_ops.py`, `tests/unit/test_git_ops.py`, `tests/conftest.py` (to add `local_bare_repo` fixture)
**Must not modify:** `apps/vault-worker/activities/vault_io.py`, `packages/`, `tests/fixtures/`

---

## 6. TDD Constraints

- Write `tests/unit/test_git_ops.py` stubs before any Activity implementation
- Add a `local_bare_repo` pytest fixture in `conftest.py` that creates a temporary bare repo using `tmp_path` and `GitPython`
- Implement Activities one at a time: write test → implement → pass → commit

---

## 7. Step-by-Step Plan

1. Add `local_bare_repo` fixture to `tests/conftest.py`: creates a temp bare repo, clones it to a working directory, and yields both paths. Teardown removes both.
2. Write test stubs for all four Activities in `tests/unit/test_git_ops.py`. Tests fail.
3. Implement `git_clone`. Pass its test. Commit.
4. Implement `git_pull`. Pass its test (requires setting up a new commit on the bare remote after initial clone). Commit.
5. Implement `git_commit` (stages all changed files, commits). Pass its test. Commit.
6. Implement `git_push`. Pass its test (verify bare remote HEAD advances). Commit.

---

## 8. Reference Material

### Activity pattern with environment variable

```python
import os
from temporalio import activity
from git import Repo

@activity.defn
def git_clone(repo_url: str, target_path: str, pat: str) -> None:
    """Clone repo_url to target_path using PAT authentication.
    
    Synchronous def: Temporal runs this in a ThreadPoolExecutor automatically.
    Do not convert to async def — GitPython is blocking and clone can take seconds.
    """
    authed_url = repo_url.replace("https://", f"https://{pat}@")
    Repo.clone_from(authed_url, target_path)

@activity.defn
def git_pull(vault_path: str) -> None:
    """Synchronous def — see git_clone docstring for rationale."""
    repo = Repo(vault_path)
    repo.remotes.origin.pull()
```

### Local bare repo fixture pattern

```python
@pytest.fixture
def local_bare_repo(tmp_path):
    bare = tmp_path / "remote.git"
    Repo.init(str(bare), bare=True)
    working = tmp_path / "working"
    repo = Repo.clone_from(str(bare), str(working))
    # Create initial commit
    (working / "README.md").write_text("init")
    repo.index.add(["README.md"])
    repo.index.commit("init")
    repo.remotes.origin.push("master:master")
    return {"bare": bare, "working": working, "repo": repo}
```
