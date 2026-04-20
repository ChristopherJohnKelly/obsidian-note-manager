---
type: bubble
status: pending
step_id: S13
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior DevOps Engineer refactoring a GitHub Actions self-hosted runner into a minimal Temporal trigger client.
**Objective:** Strip all vault logic from the `github-runner` container and replace it with a thin Python script (`trigger.py`) that uses the Temporal Python Client to start the appropriate workflow. The container only needs the GitHub Actions runner binary and the `temporalio` package.
**Constraints:**
- Python 3.12
- `trigger.py` must support starting `NightWatchmanWorkflow` and `FilerIngestionWorkflow` by name (via `--workflow` CLI argument). **Do not include `VaultManagerWorkflow`** — it starts automatically when the vault-worker container starts and is never triggered externally.
- No vault I/O, no Gemini calls, no `GitPython` in this container
- The existing `.github/workflows/*.yml` files are modified to call `trigger.py` instead of the old Python scripts; the vault is no longer checked out by the runner
- The runner Dockerfile is rebuilt from scratch to be minimal

---

## 1. Context

**Feature:** TRD Section 6 Phase 4 (Client Integration — github-runner Dumb Trigger), TRD Section 3A (Container Diagram)
**Depends On:** S10 (NightWatchmanWorkflow), S11 (FilerIngestionWorkflow), S12 (CopilotSessionWorkflow)
**Current State:** All workflows and activities implemented and tested. The existing runner container still contains the full V1 vault-processing logic.
**Target State:** `apps/github_runner/` contains a minimal Dockerfile and `trigger.py`. The existing GitHub Actions YAML files delegate to `trigger.py`. The old entrypoints (`ingest_runner.py`, `cron_runner.py`) are no longer called by the runner.

---

## 2. Input

- `packages/shared/workflow_names.py` — workflow name constants
- `packages/shared/models.py` — input dataclass types for each workflow
- `obsidian-note-manager/src_v2/entrypoints/ingest_runner.py` — current runner to be replaced (read-only)
- `obsidian-note-manager/src_v2/entrypoints/cron_runner.py` — current cron runner to be replaced (read-only)
- `obsidian-note-manager/.github/workflows/` — existing YAML files to adapt (read-only reference)

---

## 3. Required Output

- [ ] `apps/github_runner/trigger.py` — Temporal Client script
- [ ] `apps/github_runner/Dockerfile` — minimal image (runner binary + `temporalio` package only)
- [ ] `apps/github_runner/requirements.txt` — `temporalio`, `python-dotenv`
- [ ] `.github/workflows/ingest.yml` — updated to call `trigger.py --workflow FilerIngestionWorkflow --source-path ${{ ... }}`
- [ ] `.github/workflows/watchman.yml` — new/updated scheduled workflow calling `trigger.py --workflow NightWatchmanWorkflow`
- [ ] `tests/unit/test_trigger.py` — tests for `trigger.py` CLI logic using a mock Temporal client

---

## 4. Acceptance Criteria

- [ ] `python trigger.py --workflow NightWatchmanWorkflow` starts the correct Temporal workflow and exits 0
- [ ] `python trigger.py --workflow FilerIngestionWorkflow --source-path "00. Inbox/0. Capture/note.md"` starts `FilerIngestionWorkflow` with the correct input
- [ ] `python trigger.py --workflow UnknownWorkflow` exits 1 with a clear error message
- [ ] `trigger.py` does not import `gitpython`, `google-generativeai`, or `frontmatter` — confirm with `pip show` in the test
- [ ] The updated `ingest.yml` no longer checks out the `obsidian-notes` repository content (only needs runner repo for `trigger.py`)
- [ ] `watchman.yml` runs on a `schedule: cron` of `'0 2 * * *'` (02:00 UTC nightly)

---

## 5. Scope Boundary

**May modify:** `apps/github_runner/`, `.github/workflows/ingest.yml`, `.github/workflows/watchman.yml`, `tests/unit/test_trigger.py`
**Must not modify:** `apps/vault_worker/`, `apps/copilot_ui/`, `packages/`, `tests/fixtures/`, any workflow Python files

---

## 6. TDD Constraints

- Write `test_trigger.py` with a mock Temporal client before implementing `trigger.py`
- The "unknown workflow exits 1" test must be written and failing before implementation
- Test that correct workflow input dataclasses are constructed from CLI arguments

---

## 7. Step-by-Step Plan

1. Write `tests/unit/test_trigger.py` — mock `temporalio.client.Client`, assert correct `start_workflow` calls for each workflow type. Run — fail.
2. Implement `trigger.py`: parse `--workflow` and optional args; construct the correct input dataclass; call `client.start_workflow()`. Return exit code 0 on success, 1 on error.
3. Pass all trigger tests. Commit.
4. Write minimal `Dockerfile`: base Ubuntu image, install GitHub Actions runner binary, install Python 3.12 + `temporalio`. Copy `trigger.py`.
5. Update `ingest.yml` and `watchman.yml`. Remove all vault checkout steps and `src_v2` calls.
6. Commit.

---

## 8. Reference Material

### trigger.py skeleton

```python
#!/usr/bin/env python3
"""Temporal workflow trigger — the only job of the github-runner container."""
import argparse, asyncio, os, sys
from temporalio.client import Client
from shared.models import NightWatchmanInput, FilerIngestionInput
from shared.workflow_names import (
    NIGHT_WATCHMAN_WORKFLOW, FILER_INGESTION_WORKFLOW, QUEUE_DEFAULT
)

WORKFLOWS = {
    # Only externally-triggered workflows. VaultManagerWorkflow is auto-started
    # by vault-worker on startup and must never be triggered from here.
    NIGHT_WATCHMAN_WORKFLOW: NightWatchmanInput,
    FILER_INGESTION_WORKFLOW: FilerIngestionInput,
}

async def main(args):
    if args.workflow not in WORKFLOWS:
        print(f"Unknown workflow: {args.workflow}", file=sys.stderr)
        sys.exit(1)

    client = await Client.connect(os.environ["TEMPORAL_HOST"])
    # Build input from args, start workflow
    ...

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--source-path", default=None)
    asyncio.run(main(parser.parse_args()))
```

### Updated ingest.yml structure

```yaml
name: Trigger Filer Workflow
on:
  push:
    paths:
      - '00. Inbox/0. Capture/**/*.md'
    branches: [master]

jobs:
  trigger:
    runs-on: self-hosted
    steps:
      - name: Trigger FilerIngestionWorkflow
        env:
          TEMPORAL_HOST: ${{ secrets.TEMPORAL_HOST }}
          GITHUB_PAT: ${{ secrets.GITHUB_PAT }}
        run: |
          python trigger.py \
            --workflow FilerIngestionWorkflow \
            --source-path "${{ github.event.commits[0].added[0] }}"
```
