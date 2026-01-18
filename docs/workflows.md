# Workflow Documentation

This document explains the GitHub Actions workflow configuration and how it integrates with the Obsidian Note Automation system.

## Workflow File: `ingest.yml`

**Location**: `.github/workflows/ingest.yml` (in your **Obsidian notes repository**)

**Purpose**: Automatically processes notes from the Capture folder when they are pushed to GitHub.

---

## Workflow Structure

```yaml
name: Obsidian Ingestion Pipeline

on:
  push:
    paths:
      - '00. Inbox/0. Capture/**/*.md'
    branches:
      - master

permissions:
  contents: write

jobs:
  librarian:
    runs-on: self-hosted
    steps:
      - name: Checkout Vault
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Run Librarian
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          OBSIDIAN_VAULT_ROOT: ${{ github.workspace }}
        run: |
          echo "📂 Starting Ingestion..."
          python3 /home/runner/src/main.py
```

---

## Trigger Configuration

### Event: `push`

The workflow triggers on Git push events.

### Path Filter: `'00. Inbox/0. Capture/**/*.md'`

**Purpose**: Only trigger when markdown files are added or modified in the Capture folder.

**Pattern Breakdown**:
- `00. Inbox/0. Capture/` - Specific directory path
- `**/*.md` - Recursive match for all `.md` files in subdirectories

**Examples of files that trigger**:
- ✅ `00. Inbox/0. Capture/my-note.md`
- ✅ `00. Inbox/0. Capture/subfolder/note.md`
- ❌ `00. Inbox/1. Review Queue/note.md` (different folder)
- ❌ `00. Inbox/0. Capture/file.txt` (not markdown)

### Branch Filter: `master`

**Purpose**: Only trigger on pushes to the `master` branch.

**Note**: Change to `main` if your default branch is `main`.

---

## Permissions

```yaml
permissions:
  contents: write
```

**Purpose**: Allows the workflow to commit and push changes back to the repository.

**Required For**: `GitOps.commit_and_push()` to work correctly.

**Scope**: Repository-level permission (not organization-level).

---

## Job: `librarian`

### Runner: `self-hosted`

**Purpose**: Execute the job on the self-hosted runner (Raspberry Pi) instead of GitHub-hosted runners.

**Label Matching**: 
- The runner must be registered with the `self-hosted` label
- Additional labels (`docker`, `pi`) are optional but can be used for more specific targeting

**Example with multiple labels**:
```yaml
runs-on: [self-hosted, docker]  # Optional: more specific targeting
```

---

## Steps

### Step 1: Checkout Vault

```yaml
- name: Checkout Vault
  uses: actions/checkout@v4
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
```

**Purpose**: Check out the repository code so the workflow can access files.

**What it does**:
- Downloads the repository to `${{ github.workspace }}` (typically `_work/{repo}/{repo}/`)
- Provides access to all files in the repository

**Token Configuration**:
- `token: ${{ secrets.GITHUB_TOKEN }}` - Uses GitHub's automatic token
- Required for push permissions (needed for later Git operations)
- Automatically provided by GitHub Actions

---

### Step 2: Run Librarian

```yaml
- name: Run Librarian
  env:
    GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
    OBSIDIAN_VAULT_ROOT: ${{ github.workspace }}
  run: |
    echo "📂 Starting Ingestion..."
    python3 /home/runner/src/main.py
```

**Purpose**: Execute the Python application to process notes.

**Environment Variables**:
- `GEMINI_API_KEY`: Loaded from repository secrets
  - Required by `LLMClient` to authenticate with Google Gemini API
  - Must be set in: Repository → Settings → Secrets and variables → Actions
- `OBSIDIAN_VAULT_ROOT`: Set to `github.workspace` (the checked-out repository path)
  - Required by `main.py` to locate the vault root
  - Used to find `00. Inbox/0. Capture/` and `00. Inbox/1. Review Queue/` folders

**Command**: `python3 /home/runner/src/main.py`
- **Important**: Uses absolute path `/home/runner/src/main.py`
- The code is installed in the Docker container, not in the checked-out repository
- Must match the container's file structure

---

## Workflow Execution Flow

1. **User Action**: User creates/edits a note in `00. Inbox/0. Capture/` and pushes to GitHub
2. **Trigger**: GitHub detects push matching path pattern `00. Inbox/0. Capture/**/*.md`
3. **Job Dispatch**: GitHub dispatches job to `self-hosted` runner
4. **Runner Receives**: Self-hosted runner picks up the job
5. **Checkout**: Runner checks out repository to workspace
6. **Execute**: Runner runs `python3 /home/runner/src/main.py` with environment variables
7. **Processing**: Python app scans, processes, and moves notes
8. **Commit**: Git operations commit and push changes
9. **Completion**: Workflow completes, processed notes are in `1. Review Queue/`

---

## Workflow Secrets

### Required Secrets

#### `GEMINI_API_KEY`

**Purpose**: Authenticate with Google Gemini API

**How to Set**:
1. Go to: Repository → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `GEMINI_API_KEY`
4. Value: Your Google Gemini API key (starts with `AIza...`)
5. Click "Add secret"

**Used In**: `Run Librarian` step environment variables

**Visibility**: Only accessible within workflows (never exposed in logs)

---

## Workflow Variables

### `${{ github.workspace }}`

**Purpose**: Path to the checked-out repository on the runner

**Value**: Typically `_work/{repo-owner}/{repo-name}/{repo-name}/`

**Used For**: Setting `OBSIDIAN_VAULT_ROOT` to tell the Python app where the vault is located

---

## Troubleshooting Workflows

### Workflow Not Triggering

**Check**:
1. ✅ Workflow file exists: `.github/workflows/ingest.yml` in obsidian-notes repository
2. ✅ Branch matches: File pushed to `master` branch
3. ✅ Path matches: File path exactly matches `00. Inbox/0. Capture/**/*.md`
4. ✅ File extension: File has `.md` extension

**Debug**:
- Check Actions tab: Even if not triggered, see if workflow appears
- Check branch: Ensure workflow file exists on `master` branch

---

### Workflow Fails Immediately

**Possible Causes**:
1. **Runner offline**: Check runner status in Settings → Actions → Runners
2. **Missing secrets**: Verify `GEMINI_API_KEY` secret exists
3. **Wrong path**: Ensure Python path is `/home/runner/src/main.py`

**Debug**:
```bash
# Check runner status
docker compose logs librarian-runner | grep -i "listening\|error"
```

---

### Workflow Succeeds But No Changes

**Possible Causes**:
1. **No files in Capture**: Verify files exist in `00. Inbox/0. Capture/`
2. **Git push failed**: Check workflow logs for Git errors
3. **Processing failed silently**: Check workflow logs for Python errors

**Debug**:
- Review workflow logs in Actions tab
- Check Git push step output
- Verify files were moved to `1. Review Queue/`

---

## Workflow Best Practices

### 1. Path-Specific Triggers

**Benefit**: Only runs when relevant files change, saving runner resources

**Current**: Triggers only on `00. Inbox/0. Capture/**/*.md`

### 2. Self-Hosted Runners

**Benefit**: 
- No GitHub Actions minutes usage
- Full control over execution environment
- Access to local resources if needed

**Trade-off**: 
- Requires maintaining infrastructure
- Less isolation than GitHub-hosted runners

### 3. Environment Variables

**Best Practice**: Never hardcode secrets in workflow files

**Current**: Uses `${{ secrets.GEMINI_API_KEY }}` for sensitive data

### 4. Permission Scope

**Principle**: Grant minimum required permissions

**Current**: `contents: write` - Required for Git push, but still scoped to repository

---

## Advanced Workflow Configurations

### Adding Manual Trigger

To allow manual workflow execution:

```yaml
on:
  push:
    paths:
      - '00. Inbox/0. Capture/**/*.md'
    branches:
      - master
  workflow_dispatch:  # Add this
```

Then users can trigger manually from Actions tab.

---

### Multiple Branches

To trigger on multiple branches:

```yaml
branches:
  - master
  - main
  - develop
```

---

### Excluding Certain Paths

To skip processing certain files:

```yaml
on:
  push:
    paths:
      - '00. Inbox/0. Capture/**/*.md'
    paths-ignore:
      - '00. Inbox/0. Capture/**/*test*.md'
```

---

## Workflow Monitoring

### Viewing Workflow Runs

1. Go to: Repository → Actions tab
2. Click on workflow name: "Obsidian Ingestion Pipeline"
3. Click on specific run to see logs

### Workflow Status

- 🟢 **Success**: Workflow completed successfully
- 🔴 **Failed**: Workflow encountered an error
- 🟡 **Queued**: Waiting for runner to become available
- 🔵 **In Progress**: Currently executing

---

## Related Documentation

- [Architecture Overview](./architecture.md) - System architecture
- [Setup Guide](./setup.md) - How to set up the workflow
- [Troubleshooting](./troubleshooting.md) - Common workflow issues
