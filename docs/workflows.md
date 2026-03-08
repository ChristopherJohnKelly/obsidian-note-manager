# Workflow Documentation

This document explains the GitHub Actions workflow configuration and how it integrates with the Obsidian Note Automation system.

## Workflow Source and Deployment

**Important**: Workflow files are **templates** stored in `obsidian-note-manager/example/workflows/`. They **must be copied** to your target Obsidian vault repository's `.github/workflows/` directory to function.

The obsidian-note-manager repository does not run these workflows. They run in your obsidian-notes (vault) repository.

```bash
# From your obsidian-notes repository
mkdir -p .github/workflows
cp /path/to/obsidian-note-manager/example/workflows/ingest.yml .github/workflows/
cp /path/to/obsidian-note-manager/example/workflows/maintenance.yml .github/workflows/
git add .github/workflows/
git commit -m "Add Obsidian automation workflows"
git push
```

---

## Workflow: ingest.yml

**Location in vault repo**: `.github/workflows/ingest.yml`

**Purpose**: Event-driven ingestion. Processes new notes from Capture, files approved proposals from Review Queue.

### Structure

```yaml
name: Obsidian Ingestion Pipeline

on:
  push:
    paths:
      - '00. Inbox/0. Capture/**/*.md'
      - '00. Inbox/1. Review Queue/**/*.md'
    branches:
      - master
  workflow_dispatch:

permissions:
  contents: write

jobs:
  librarian:
    runs-on: self-hosted
    steps:
      - name: Checkout Vault
        uses: actions/checkout@v4

      - name: Run Librarian (Filer & Ingestion)
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          OBSIDIAN_VAULT_ROOT: ${{ github.workspace }}
        run: |
          echo "📂 Starting Ingestion and Filer pipeline..."
          python3 -m src_v2.entrypoints.ingest_runner

      - name: Configure Git
        run: |
          git config user.name "Obsidian Librarian"
          git config user.email "librarian@automation.local"

      - name: Commit and push changes
        run: |
          git add -A
          git diff --staged --quiet || git commit -m "🤖 Librarian: Vault organization [skip ci]"
          git push
```

### Triggers

- **push**: Paths `00. Inbox/0. Capture/**/*.md` or `00. Inbox/1. Review Queue/**/*.md` on `master`
- **workflow_dispatch**: Manual trigger from Actions tab

### Key Points

- **Run command**: `python3 -m src_v2.entrypoints.ingest_runner` (the application is pre-installed in the Docker container)
- **Git**: Python does not perform Git operations. The workflow's "Configure Git" and "Commit and push changes" steps handle all Git operations.
- **OBSIDIAN_VAULT_ROOT**: Set to `${{ github.workspace }}` (the checked-out vault)

---

## Workflow: maintenance.yml

**Location in vault repo**: `.github/workflows/maintenance.yml`

**Purpose**: Asynchronous automation (Night Watchman). Runs vault audit, Code Registry update, fix proposals.

### Structure

```yaml
name: Night Watchman Maintenance

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2:00 AM UTC
  workflow_dispatch:

jobs:
  maintain:
    runs-on: self-hosted
    steps:
      - name: Checkout Vault
        uses: actions/checkout@v4

      - name: Run Night Watchman (Registry & Audit)
        env:
          OBSIDIAN_VAULT_ROOT: ${{ github.workspace }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          python3 -m src_v2.entrypoints.cron_runner

      - name: Commit and Push Changes
        run: |
          git config user.name "github-actions-runner"
          git config user.email "runner@obsidian-note-manager.local"
          git add .
          git commit -m "chore: automated vault maintenance (Code Registry)" || exit 0
          git push
```

### Triggers

- **schedule**: Daily at 02:00 UTC
- **workflow_dispatch**: Manual trigger

### Key Points

- **Run command**: `python3 -m src_v2.entrypoints.cron_runner`
- **Git**: Workflow steps perform commit and push (Python mutates files only)

---

## Permissions

```yaml
permissions:
  contents: write
```

**Purpose**: Allows the workflow to commit and push changes back to the repository.

**Required For**: The workflow's Git steps to push successfully.

---

## Job Configuration

### Runner: `self-hosted`

**Purpose**: Execute the job on the self-hosted runner (e.g. Raspberry Pi in Docker) instead of GitHub-hosted runners.

**Label Matching**: The runner must be registered with the `self-hosted` label.

---

## Workflow Execution Flow

### Ingestion (ingest.yml)

1. **User Action**: User creates/edits a note in Capture or Review Queue and pushes to GitHub
2. **Trigger**: GitHub detects push matching path pattern
3. **Job Dispatch**: GitHub dispatches job to `self-hosted` runner
4. **Checkout**: Runner checks out vault to workspace
5. **Execute**: Runner runs `python3 -m src_v2.entrypoints.ingest_runner`
6. **Processing**: Python app files approved proposals, processes new notes, writes to Review Queue
7. **Git**: Workflow steps run `git add`, `git commit`, `git push`
8. **Completion**: Workflow completes

### Maintenance (maintenance.yml)

1. **Trigger**: Scheduled cron or manual dispatch
2. **Checkout**: Runner checks out vault
3. **Execute**: Runner runs `python3 -m src_v2.entrypoints.cron_runner`
4. **Processing**: Python app scans vault, updates Code Registry, generates fix proposals
5. **Git**: Workflow steps run `git add`, `git commit`, `git push`

---

## Workflow Secrets

### GEMINI_API_KEY

**Purpose**: Authenticate with Google Gemini API

**How to Set**:
1. Go to: Repository → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `GEMINI_API_KEY`
4. Value: Your Google Gemini API key (starts with `AIza...`)

---

## Troubleshooting Workflows

### Workflow Not Triggering

**Check**:
1. Workflow file exists in **obsidian-notes** repo: `.github/workflows/ingest.yml` or `maintenance.yml`
2. Branch matches (e.g. `master`)
3. Path matches (for ingest: `00. Inbox/0. Capture/**/*.md` or `00. Inbox/1. Review Queue/**/*.md`)
4. File extension: `.md`

### Workflow Fails Immediately

**Possible Causes**:
1. **Runner offline**: Check runner status in Settings → Actions → Runners
2. **Missing secrets**: Verify `GEMINI_API_KEY` secret exists
3. **Wrong command**: Ensure workflow uses `python3 -m src_v2.entrypoints.ingest_runner` or `python3 -m src_v2.entrypoints.cron_runner` (not `src/main.py`)

### Workflow Succeeds But No Changes

**Possible Causes**:
1. **No files in Capture**: Verify files exist in `00. Inbox/0. Capture/`
2. **Git push failed**: Check workflow logs for the "Commit and push" step
3. **Processing failed silently**: Check workflow logs for Python errors

See [Troubleshooting Guide](./troubleshooting.md) for detailed diagnostics.

---

## Related Documentation

- [Architecture Overview](./architecture.md) - System architecture and GitOps boundary
- [Setup Guide](./setup.md) - How to set up the workflow
- [Ingest Deployment](./ingest-deployment.md) - Deployment steps for ingestion
- [Troubleshooting](./troubleshooting.md) - Common workflow issues
