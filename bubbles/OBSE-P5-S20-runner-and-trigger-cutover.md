---
type: bubble
status: pending
step_id: S20
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior DevOps Engineer finishing the GitHub-to-Temporal trigger path so it works against the real vault repository.
**Objective:** Make the `github-runner` image a working self-hosted GitHub Actions runner that starts Temporal workflows through `trigger.py`, make `trigger.py` start one correctly-identified workflow per captured note, and provide the vault-side workflow files that will replace the V1 ones in `obsidian-notes`.
**Constraints:**
- Read before writing: `apps/github_runner/`, the root `Dockerfile` and `scripts/entrypoint.sh` and `scripts/token_fetcher.py` (the V1 runner registration that already works), `.github/workflows/build-push.yml`, `tests/unit/test_trigger.py`, `tests/unit/test_client_wiring.py`, and the input dataclasses in `night_watchman.py` and `filer_ingestion.py` as S19 left them.
- `trigger.py` must not import GitPython, `google-generativeai` or `frontmatter` (S13 criterion still holds).
- No live GitHub, Temporal server or network in tests. Mock the Temporal client as `test_trigger.py` already does; drive event parsing from JSON fixture files.
- Do not change any workflow's Python code. If a workflow input needs a field the trigger cannot supply, stop and record it in `FAILURE-S20.md` rather than editing the workflow.

---

## 1. Context

**Feature:** TRD Section 6 Phase 4 (github-runner Dumb Trigger) and Section 3A (container roster).
**Depends On:** S19 (the Night Watchman input and branch defaults it settles).
**Current State:** Found in the pre-deployment review of 1 Nov 2026.
- `apps/github_runner/Dockerfile` is `python:3.12-slim` with `CMD ["python3", "trigger.py"]`. It contains no GitHub Actions runner binary and no registration step. Under `restart: unless-stopped` it would exit with status 2 (missing `--workflow`) and loop. S13 asked for "runner binary + `temporalio` package only".
- `trigger.py` builds workflow IDs as `f"{workflow}-{RUN_ID or 'default'}"`. Nothing sets `RUN_ID`, so every run gets the same ID and a second captured note fails with `WorkflowAlreadyStartedError` while the first waits up to a week for approval.
- `.github/workflows/ingest.yml` reads `github.event.head_commit.modified[0]`. A new capture appears under `added`, not `modified`, and only the first file of the last commit is taken. A push of several notes, or several commits, loses all but one.
- `ingest.yml` and `watchman.yml` sit in this repository's `.github/workflows/`. Their triggers (pushes to `00. Inbox/0. Capture/`, and a nightly cron) only make sense in the vault repository `obsidian-notes`. Once this branch merges to `main`, `watchman.yml` would queue a job on this repo every night that no runner serves.
- Both files use `runs-on: self-hosted`, the same bare label as the V1 runners, and call `python3 trigger.py` by a relative path that will not resolve from the job's working directory.
- `trigger.py` reads `VAULT_PATH` from its environment and passes `""` when it is unset. The compose service does not set it (S21 adds it); the trigger should refuse to start a workflow with an empty vault path.
- `build-push.yml` builds the runner with `apps/github_runner/` as the Docker build context, so the image cannot copy `scripts/entrypoint.sh` today.
**Target State:** The runner image registers itself against `obsidian-notes` with a dedicated label and runs jobs; each job runs `trigger.py`, which starts one uniquely-identified `FilerIngestionWorkflow` per note added under Capture, or one `NightWatchmanWorkflow`; the vault-side workflow files are ready to copy into `obsidian-notes`.

---

## 2. Input

- `apps/github_runner/Dockerfile`, `requirements.txt`, `trigger.py`
- Root `Dockerfile`, `scripts/entrypoint.sh`, `scripts/token_fetcher.py`
- `.github/workflows/build-push.yml`, `ingest.yml`, `watchman.yml`
- `apps/vault_worker/workflows/night_watchman.py`, `filer_ingestion.py` (input dataclasses only)
- `tests/unit/test_trigger.py`, `tests/unit/test_client_wiring.py`, `tests/ci/`
- GitHub's documentation of the `push` event payload (`commits[].added`, `commits[].removed`) and of `GITHUB_EVENT_PATH` and `GITHUB_RUN_ID`

---

## 3. Required Output

- [ ] `apps/github_runner/Dockerfile`: Ubuntu base, GitHub Actions runner binary (x64, same version pin as the root `Dockerfile`), Python 3.12 with `temporalio`, `trigger.py` at a fixed absolute path, registration entrypoint
- [ ] `apps/github_runner/entrypoint.sh` (adapted from `scripts/entrypoint.sh`) registering with a dedicated label, default `obsidian-temporal`, configurable through `RUNNER_LABELS`
- [ ] `.github/workflows/build-push.yml` build context adjusted if the image needs files outside `apps/github_runner/`
- [ ] `trigger.py`: unique workflow IDs, event-file parsing, one Filer start per captured note, fail-fast on missing required environment
- [ ] `deploy/vault-workflows/ingest.yml` and `deploy/vault-workflows/watchman.yml`, plus a short `deploy/vault-workflows/README.md` saying they are copied into `obsidian-notes/.github/workflows/` at cutover and which V1 files they replace (`ingest.yml`, `maintenance.yml`)
- [ ] `.github/workflows/ingest.yml` and `.github/workflows/watchman.yml` removed from this repository
- [ ] Tests for every criterion below; `scripts/run_s20_tests.sh`

---

## 4. Acceptance Criteria

- [ ] **Runner image.** A structural test asserts the Dockerfile installs the Actions runner (`actions-runner-linux-x64-<version>` download), installs `temporalio`, copies `trigger.py` to an absolute path, and that its entrypoint runs the registration script rather than `trigger.py`. A test asserts the entrypoint passes `--labels` with `RUNNER_LABELS` defaulting to `obsidian-temporal`.
- [ ] **Unique IDs.** `trigger.py` builds IDs from `GITHUB_RUN_ID`. Filer IDs also include a stable digest of the note's path, so two notes in one push get different IDs, and a re-run of the same job for the same note reuses its ID and does not start a second Filer run. When `GITHUB_RUN_ID` is unset (a manual run), the ID falls back to a timestamp, never to a fixed string. Tests pin all three properties.
- [ ] **All captured notes.** Given a fixture `push` event with two commits that add three Markdown files under `00. Inbox/0. Capture/` (one with spaces in its name), one file elsewhere, and one capture file added then removed, `trigger.py --workflow FilerIngestionWorkflow --event-path <file>` starts exactly three workflows with `source_path` set to the vault-relative paths of the three surviving capture notes.
- [ ] **Single-path mode kept.** `--source-path "00. Inbox/0. Capture/note.md"` still starts one workflow (existing tests keep passing).
- [ ] **Fail fast.** With `VAULT_PATH` or `TEMPORAL_HOST` unset or empty, `trigger.py` exits 1 with a message naming the missing variable and starts nothing.
- [ ] **Night Watchman input.** `trigger.py --workflow NightWatchmanWorkflow` builds the input dataclass exactly as S19 left it, with the base branch read from `BASE_BRANCH` defaulting to `master`. A test fails if the dataclass gains a required field the trigger does not supply.
- [ ] **Vault-side workflows.** Tests parse both files under `deploy/vault-workflows/` and assert: `runs-on` includes `obsidian-temporal`; both have `workflow_dispatch`; `ingest.yml` triggers on pushes to `master` under `00. Inbox/0. Capture/**/*.md` and passes `$GITHUB_EVENT_PATH` to `trigger.py` by its absolute path; `watchman.yml` runs on `'0 2 * * *'`; neither checks out the vault.
- [ ] **Old files gone.** No workflow file in this repository's `.github/workflows/` triggers on `00. Inbox/` paths or runs `trigger.py`.
- [ ] README and `docs/deployment.md` describe the runner label and the cutover copy of `deploy/vault-workflows/`, and `tests/ci/test_readme_docs.py` still passes (update its expectations only where they encode the defects above).
- [ ] The full suite passes with coverage ≥ 90%.

---

## 5. Scope Boundary

**May modify:** `apps/github_runner/`, `.github/workflows/build-push.yml`, `.github/workflows/ingest.yml` (delete), `.github/workflows/watchman.yml` (delete), `deploy/vault-workflows/` (new), `README.md`, `docs/deployment.md`, `tests/unit/test_trigger.py`, `tests/unit/test_client_wiring.py`, `tests/ci/`, `tests/fixtures/github_events/` (new), `scripts/run_s20_tests.sh`
**Must not modify:** `apps/vault_worker/`, `apps/copilot_ui/`, `packages/`, `docker-compose*.yml` (S21), existing fixtures under `tests/fixtures/`, the root `Dockerfile` and `scripts/` (V1 rollback path)

---

## 6. TDD Constraints

Write the "all captured notes" test against the fixture event first and watch it fail (today's trigger has no event parsing). Write the unique-ID tests before changing the ID scheme and watch them fail on the `-default` suffix.

---

## 7. Step-by-Step Plan

1. Fixture events under `tests/fixtures/github_events/`.
2. Failing tests for event parsing, unique IDs and fail-fast. Implement in `trigger.py`. Green.
3. Failing structural tests for the Dockerfile and entrypoint. Build the image definition from the V1 runner pattern. Adjust the build context in `build-push.yml` if needed. Green.
4. Failing tests for `deploy/vault-workflows/`. Write the two files and the README; delete the old ones. Green.
5. Docs and doc tests.
6. Full suite and coverage.

---

## 8. Reference Material

The runner job inherits the runner process's environment, which is how `TEMPORAL_HOST`, `VAULT_PATH` and the PR settings set on the compose service reach `trigger.py`. `temporal-server:7233` is only reachable on the compose network, so the runner must run as a compose service, not on the host.

## Assumptions

- The production host is the x64 Ubuntu Docker host; the Raspberry Pi runner is retired at cutover.
- `GITHUB_PAT` is a classic PAT with `repo` scope (the V1 `token_fetcher.py` requirement).

## Open Questions

- [ ] Should a note re-saved in Capture (a `modified` entry) start a new Filer run? This bubble starts runs for `added` only. Raised for the operator.
