---
type: bubble
status: pending
step_id: S10
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python Engineer implementing a cron-triggered audit workflow.
**Objective:** Implement `NightWatchmanWorkflow` — the nightly vault audit. It reads the vault, scores all files, takes the top 10 violators, generates fix proposals via LLM, and opens a GitHub Pull Request.
**Constraints:**
- Python 3.12
- Workflow code is deterministic — sorting, scoring comparison, and list slicing are all deterministic operations and may live in the workflow; non-deterministic work (file reads, LLM calls) delegates to Activities
- GitHub PR creation is a new Activity `create_github_pr` in a new `apps/vault_worker/activities/github_ops.py` — it uses the `PyGithub` library. `PyGithub` is synchronous and blocking; define the Activity as a **synchronous `def` function** so Temporal runs it in the ThreadPoolExecutor.
- PR creation must be tested with a mock GitHub client (no real API calls in tests)
- The workflow processes fix proposals sequentially (one LLM call at a time) to avoid hammering the API

---

## 1. Context

**Feature:** TRD Section 4 (NightWatchmanWorkflow), PRD Section 4 (Night Watchman use case)
**Depends On:** S06 (LLM Activities), S07 (ReadVaultWorkflow), S08 (WriteVaultWorkflow)
**Testing note:** `NightWatchmanWorkflow` calls `ReadVaultWorkflow`, which sends an `ensure_synced` Update to `vault-manager`. E2E tests must register a `VaultManagerStub` (defined in `test_night_watchman_workflow.py`, same pattern as B07) and start it with ID `vault-manager` before running the workflow under test.
**Current State:** All Activities and child workflows implemented. No orchestrator workflows yet.
**Target State:** Full `NightWatchmanWorkflow` E2E test passing against Dummy Vault + Fake LLM, producing a mocked GitHub PR payload.

---

## 2. Input

- `apps/vault_worker/workflows/read_vault.py`
- `apps/vault_worker/workflows/write_vault.py`
- `apps/vault_worker/activities/llm.py`
- `apps/vault_worker/activities/vault_io.py`
- `packages/shared/models.py` — `ValidationResult`, `AuditProposal`
- `tests/fixtures/dummy_vault/` — Dummy Vault with known violations
- `tests/mocks/fake_llm.py`

---

## 3. Required Output

- [ ] `apps/vault_worker/activities/github_ops.py` — `create_github_pr` Activity
- [ ] `tests/mocks/fake_github.py` — `FakeGitHubClient` with mock PR creation
- [ ] `apps/vault_worker/workflows/night_watchman.py` — `NightWatchmanWorkflow`
- [ ] `tests/e2e/test_night_watchman_workflow.py`

**Workflow interface:**

```python
@dataclass
class NightWatchmanInput:
    vault_path: str
    repo_owner: str    # e.g. "ChristopherJohnKelly"
    repo_name: str     # e.g. "obsidian-notes"
    github_token: str
    pr_branch: str     # e.g. "watchman/2026-04-06"

@workflow.defn
class NightWatchmanWorkflow:
    @workflow.run
    async def run(self, input: NightWatchmanInput) -> dict: ...
    # returns {"proposals_generated": int, "pr_url": str}

    @workflow.query
    def get_progress(self) -> dict: ...
    # returns {"files_scanned": int, "proposals_generated": int}
```

---

## 4. Acceptance Criteria

- [ ] Against the Dummy Vault, the workflow identifies exactly the files with score > 0 (as per the B02 score table)
- [ ] Only the top 10 highest-scoring files are processed (Dummy Vault has fewer than 10 violations; test with a Dummy Vault extension that has ≥ 10 violations to prove the cap)
- [ ] A `generate_fix` Activity is called for each selected file
- [ ] Fix proposals are written to a branch and a PR is created via `create_github_pr`
- [ ] `get_progress` query reflects the current count during execution (test with time-skipping)
- [ ] If a single `generate_fix` call fails after 3 retries, the workflow continues processing remaining files (fault isolation)
- [ ] Full E2E test passes using Fake LLM + Fake GitHub, without touching production vault or real APIs

---

## 5. Scope Boundary

**May modify:** `apps/vault_worker/workflows/night_watchman.py`, `apps/vault_worker/activities/github_ops.py`, `tests/mocks/fake_github.py`, `tests/e2e/test_night_watchman_workflow.py`
**Must not modify:** `apps/vault_worker/workflows/read_vault.py`, `apps/vault_worker/workflows/write_vault.py`, LLM/git/vault_io Activity files, `packages/shared/`

---

## 6. TDD Constraints

- Write the full E2E test before implementing the workflow
- Write `fake_github.py` before `github_ops.py`
- The fault-isolation test (one failing LLM call, rest succeed) must be written and passing

---

## 7. Step-by-Step Plan

1. Write `tests/mocks/fake_github.py` — `FakeGitHubClient` that records PR creation calls. Write `test_create_github_pr` unit test. Implement `github_ops.py`. Pass. Commit.
2. Write the full E2E test in `test_night_watchman_workflow.py`. Run — fail.
3. Implement `NightWatchmanWorkflow`: (a) call `ReadVaultWorkflow` to get vault context; (b) call `scan_vault` Activity; (c) sort by score, take top 10; (d) for each, call `generate_fix` Activity (with fault isolation via try/except); (e) write proposals to a branch via `WriteVaultWorkflow`; (f) call `create_github_pr` Activity.
4. Implement the `get_progress` query using workflow state variables updated after each file is processed.
5. Run E2E test — pass. Run fault-isolation test — pass.
6. Commit.

---

## 8. Reference Material

### Fault-isolated fix generation loop

```python
proposals = []
for result in sorted_results[:10]:
    try:
        fix = await workflow.execute_activity(
            generate_fix,
            args=[note, result.reasons, context],  # note: VaultNote, context: VaultContext
            schedule_to_close_timeout=timedelta(minutes=5),
            retry_policy=LLM_RETRY_POLICY,  # imported from apps/vault_worker/activities/llm.py
        )
        proposals.append(fix)
    except ActivityError:
        # Log and continue — one failure must not abort the whole run
        workflow.logger.warning(f"Fix generation failed for {result.path}, skipping")
    self._progress["proposals_generated"] = len(proposals)
```

### FakeGitHubClient pattern

```python
# tests/mocks/fake_github.py
class FakePR:
    html_url = "https://github.com/fake/repo/pull/1"

class FakeGitHubClient:
    def __init__(self):
        self.prs_created = []

    def create_pull(self, *, title, body, head, base) -> FakePR:
        self.prs_created.append({"title": title, "head": head})
        return FakePR()
```
