---
type: bubble
status: pending
step_id: S19
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python Engineer making a Temporal workflow safe to point at a production Git repository.
**Objective:** Make `NightWatchmanWorkflow` deliver its fixes as a pull request against the vault's default branch, never as a push to that branch. Today it commits and pushes the fixes straight to `master` and then fails to open the PR.
**Constraints:**
- Read the real code before changing it. Open `night_watchman.py`, `write_vault.py`, `git_ops.py`, `github_ops.py` and `apps/vault_worker/__main__.py` first, and the bare-repo fixtures that `tests/unit/test_git_ops.py` and `tests/e2e/test_write_vault_workflow.py` already use.
- Existing callers of `WriteVaultWorkflow` (the Filer) must behave exactly as before. Any new field on `WriteVaultInput` is optional and defaults to today's behaviour.
- Activities stay synchronous `def` (LOOP.md constraint 1). No file or Git I/O inside `@workflow.run` (constraint 3).
- No live GitHub or network in tests. Use `tests/mocks/fake_github.py` and local bare repositories.

---

## 1. Context

**Feature:** TRD Section 4 (`NightWatchmanWorkflow`), PRD Section 7 risk "Branch protection gap": the Night Watchman must target a PR and never push directly to master.
**Depends On:** S18.
**Current State:** Found in the pre-deployment review of 1 Nov 2026.
- `NightWatchmanWorkflow` step 6 runs `WriteVaultWorkflow`, which commits on the clone's current branch (the vault default, `master`) and runs `git_push`, so up to 10 LLM-rewritten notes land on `master` with no review.
- Step 7 then calls `create_github_pr` with `head=pr_branch`, a branch nothing ever created or pushed, so GitHub would reject it.
- `configure_github_client()` is never called in `apps/vault_worker/__main__.py`, so in production `create_github_pr` raises `RuntimeError("GitHub client factory not configured ...")` after the push has already happened.
- `NightWatchmanInput.base_branch` and `CreatePRInput.base_branch` default to `"main"`. The vault repository's default branch is `master`.
- When no note produces a usable fix, the workflow still calls `create_github_pr`.
**Target State:** A Night Watchman run with fixes leaves the remote default branch untouched, pushes one new branch holding one commit of fixes, opens one PR from that branch into the default branch, and leaves the worker's clone back on the default branch with a clean working tree. A run with no fixes pushes nothing and opens no PR.

---

## 2. Input

- `apps/vault_worker/workflows/night_watchman.py`
- `apps/vault_worker/workflows/write_vault.py`
- `apps/vault_worker/activities/git_ops.py`
- `apps/vault_worker/activities/github_ops.py`
- `apps/vault_worker/__main__.py` and `apps/vault_worker/worker.py` (registration lists)
- `tests/mocks/fake_github.py`, `tests/conftest.py` (bare-repo fixtures)
- `LEARNINGS.md`, the S15 and S18 rejection entries in particular

---

## 3. Required Output

- [ ] Branch support in the write path: either an optional `branch` field on `WriteVaultInput` or a dedicated child workflow, plus whatever Git activities it needs (for example create-and-checkout a branch, push a named branch, return to the default branch)
- [ ] `night_watchman.py` writing fixes to a new branch and opening the PR from it
- [ ] `apps/vault_worker/__main__.py` configuring the production GitHub client (PyGithub or the existing client the activity expects; read `github_ops.py`)
- [ ] Default base branch `master` wherever a default exists
- [ ] Registration of any new activity or workflow in `worker.py`
- [ ] Tests for every acceptance criterion below
- [ ] `scripts/run_s19_tests.sh`

---

## 4. Acceptance Criteria

- [ ] **Default branch untouched.** A behavioural test runs `NightWatchmanWorkflow` in the Temporal test environment against a dummy-vault clone of a local bare repository, with the FakeLLM returning valid fixes. After the run, the bare repository's default branch points at the same commit as before the run.
- [ ] **Fixes on a branch.** In the same test, the bare repository holds a new branch whose single commit on top of the default branch contains the fixed notes, and only those notes.
- [ ] **Branch name is unique per run.** The branch name is derived from the workflow's own deterministic values (for example `librarian/night-watchman-<YYYY-MM-DD>` from `workflow.now()`, with the workflow run ID appended or another collision rule), so two runs on different days never reuse a branch with an open PR. The rule is documented in the workflow docstring and pinned by a test.
- [ ] **PR targets the default branch.** The FakeGitHubClient records exactly one `create_pull` call with `head` equal to the pushed branch and `base` equal to `master`.
- [ ] **Clone restored.** After the run, the worker's clone is checked out on the default branch with no staged, unstaged or untracked changes. A second test makes a write activity fail midway and asserts the same restoration (the clone is worker-owned, so discarding its uncommitted changes is acceptable).
- [ ] **No-op run.** With the FakeLLM returning unparseable output for every note, the run pushes no branch, makes no commit and makes no `create_pull` call.
- [ ] **Production wiring.** A test proves `apps/vault_worker/__main__.py` configures the GitHub client before the workers run. It must import the real module (S18 was rejected for an AST-only guard).
- [ ] **Filer unchanged.** The existing `FilerIngestionWorkflow` and `WriteVaultWorkflow` tests pass unmodified.
- [ ] The full suite passes with coverage ≥ 90%.

---

## 5. Scope Boundary

**May modify:** `apps/vault_worker/workflows/night_watchman.py`, `apps/vault_worker/workflows/write_vault.py`, `apps/vault_worker/activities/git_ops.py`, `apps/vault_worker/activities/github_ops.py`, `apps/vault_worker/__main__.py`, `apps/vault_worker/worker.py`, `apps/vault_worker/requirements.txt`, `tests/unit/`, `tests/e2e/`, `tests/mocks/fake_github.py` (extending it is fine), `scripts/run_s19_tests.sh`
**Must not modify:** signal and query names, `packages/shared/`, `apps/github_runner/`, `apps/copilot_ui/`, `.github/workflows/`, `docker-compose*.yml`, Dockerfiles, existing fixtures under `tests/fixtures/`

---

## 6. TDD Constraints

Write the "default branch untouched" test first and watch it fail against today's code (today the bare repository's default branch moves). Write the production-wiring test before touching `__main__.py` and watch it fail on the missing `configure_github_client` call.

---

## 7. Step-by-Step Plan

1. Read the bare-repo fixtures and the FakeGitHubClient.
2. Failing test: default branch untouched and fixes on a branch.
3. Add the branch-aware write path and any Git activities; register them. Green.
4. Failing test: PR head and base. Fix the defaults and the PR call. Green.
5. Failing tests: clone restored, including the mid-write failure. Implement the restoration (a `try`/`finally` in the workflow that runs a restore activity). Green.
6. Failing test: no-op run. Green.
7. Failing test: production wiring. Configure the client in `__main__.py`. Green.
8. Full suite and coverage.

---

## 8. Reference Material

The vault repository is `ChristopherJohnKelly/obsidian-notes`, default branch `master`. The V1 Night Watchman used a fixed branch `librarian/nightly-fix`; PR #7 from that branch has been open since March 2026, which is why S19 asks for a branch per run.

## Assumptions

- The worker's clone is owned by the worker and nothing else edits it, so restoring it can discard uncommitted changes. ✓ (TRD Section 7)
- `GITHUB_PAT` on vault-worker has `repo` scope and can push branches and open PRs.

## Open Questions

- [ ] Should the Night Watchman fix frontmatter as well as bodies? `fix_parser` strips the LLM's frontmatter and keeps the note's own, so Rule 1 (missing aliases and tags) can never be fixed. Out of scope for S19; raised for the operator.
