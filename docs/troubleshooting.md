# Troubleshooting Guide

This guide helps you diagnose and fix common issues with the Obsidian Note Automation system.

## Table of Contents

- [Runner Not Appearing in GitHub](#runner-not-appearing-in-github)
- [Runner Shows as Offline](#runner-shows-as-offline)
- [Workflow Not Triggering](#workflow-not-triggering)
- [Workflow Fails with "No such file or directory"](#workflow-fails-with-no-such-file-or-directory)
- [Git / Workflow Issues](#git--workflow-issues)
- [Gemini API Errors](#gemini-api-errors)
- [Runner Registration Token Errors](#runner-registration-token-errors)
- [Runner Update / Docker Issues](#runner-update--docker-issues)
- [Container Won't Start](#container-wont-start)
- [General Debugging Tips](#general-debugging-tips)

---

## Runner Not Appearing in GitHub

**Symptoms**: Runner doesn't show up in GitHub → Settings → Actions → Runners

**Possible Causes**:

### 1. Registration Token Expired (Legacy Method)

**If using `GITHUB_TOKEN` (legacy)**:
- Registration tokens expire after 1 hour
- Container restart after expiration requires a new token

**Solution**:
- Get a fresh token from GitHub → Settings → Actions → Runners → New self-hosted runner
- Update `.env` file with new `GITHUB_RUNNER_TOKEN`
- Restart container: `docker compose restart librarian-runner`

**Better Solution**: Switch to using `GITHUB_PAT` (recommended) - see [Runner Registration Token Errors](#runner-registration-token-errors)

### 2. Invalid Repository URL

**Check**:
```bash
docker compose logs librarian-runner | grep -i "error\|invalid\|404"
```

**Solution**: Verify `REPO_URL` in `.env` matches your repository:
```bash
# Should be: https://github.com/owner/repo
REPO_URL=https://github.com/christopherjohnkelly/obsidian-notes
```

### 3. Permission Denied

**Symptoms**: Error like "Access to the path '/home/runner/.runner' is denied"

**Solution**:
```bash
# Stop and remove container
docker compose down

# Remove volumes if they exist
docker compose down -v

# Rebuild and start (from repo root)
docker compose build
docker compose up -d
```

---

## Runner Shows as Offline

**Symptoms**: Runner appears in GitHub UI but shows as "Offline" (gray) instead of "Idle" (green)

### 1. Container Not Running

**Check**:
```bash
docker compose ps
```

**Solution**: Start the container:
```bash
docker compose up -d
```

### 2. Runner Lost Connection

**Symptoms**: Runner was online but disconnected, logs show "Listening for Jobs" but GitHub shows offline

**Solution**:
1. **Remove runner from GitHub**:
   - Go to: Settings → Actions → Runners
   - Click three dots (⋯) → Remove runner
2. **Restart container** (it will re-register automatically):
   ```bash
   docker compose restart librarian-runner
   ```

### 3. Network Connectivity Issues

The runner may connect initially but lose connection due to network issues.

**Diagnostics**:
```bash
# Check if container can reach GitHub API
docker compose exec librarian-runner curl -v https://api.github.com 2>&1 | head -20

# Check DNS resolution
docker compose exec librarian-runner nslookup api.github.com

# Test runner service endpoint
docker compose exec librarian-runner curl -v https://pipelinesghubeus6.actions.githubusercontent.com 2>&1 | head -20
```

**What to look for**:
- Connection timeout errors
- DNS resolution failures
- SSL/TLS certificate errors
- Firewall blocking outbound HTTPS (443)

### 4. Runner Process Not Running

The container may be running but the Runner.Listener process may have crashed.

**Diagnostics**:
```bash
# Check if Runner.Listener process is running
docker compose exec librarian-runner ps aux | grep -E "Runner|run.sh"

# Should show:
# runner  X  ... /bin/bash ./run.sh
# runner  Y  ... /home/runner/bin/Runner.Listener run

# If process is missing, check recent logs
docker compose logs librarian-runner --tail=100 | grep -i "error\|crash\|exit"
```

**Solution**: If process is missing, restart the container:
```bash
docker compose restart librarian-runner
```

### 5. Firewall or Proxy Issues

Raspberry Pi may have firewall rules blocking outbound connections.

**Diagnostics**:
```bash
# Check firewall status (on Raspberry Pi host, not container)
sudo ufw status
sudo iptables -L -n | grep -i drop

# Check if port 443 is blocked
docker compose exec librarian-runner nc -zv api.github.com 443

# Test from host (not container)
curl -v https://api.github.com | head -5
```

**Solution** (if outbound HTTPS blocked):
```bash
sudo ufw allow out 443/tcp
```

### 6. Time Synchronization Issues

GitHub requires accurate system time for SSL/TLS connections.

**Diagnostics**:
```bash
# Check container time
docker compose exec librarian-runner date

# Check host time
date

# Compare with GitHub API time
curl -I https://api.github.com 2>&1 | grep -i date
```

**Solution**: If time is off, sync on Raspberry Pi:
```bash
sudo timedatectl set-ntp true
sudo systemctl restart systemd-timesyncd
```

### 7. DNS Resolution Issues

**Diagnostics**:
```bash
# Test DNS from container
docker compose exec librarian-runner nslookup api.github.com
docker compose exec librarian-runner nslookup pipelinesghubeus6.actions.githubusercontent.com

# Check container's DNS servers
docker compose exec librarian-runner cat /etc/resolv.conf
```

**Solution**: If DNS fails, add to `docker-compose.yml`:
```yaml
dns:
  - 8.8.8.8
  - 8.8.4.4
```

Or restart Docker network:
```bash
docker compose down
docker network prune
docker compose up -d
```

### 8. Runner Session State (Stale Session)

**Solution**: Remove runner and force fresh registration:

```bash
# 1. Remove runner from GitHub UI
#    Settings → Actions → Runners → Remove runner

# 2. Stop and remove container (deletes .runner file)
docker compose down

# 3. Start fresh (from repo root)
docker compose up -d

# 4. Wait 30-60 seconds for registration
docker compose logs -f librarian-runner
```

**Expected**:
- `🔑 Fetching registration token using PAT...`
- `✅ Runner Configured. Listening for jobs...`
- `√ Connected to GitHub`
- `Listening for Jobs`

---

## Workflow Not Triggering

**Symptoms**: Pushing files to `00. Inbox/0. Capture/` doesn't trigger workflow

**Possible Causes**:

### 1. Workflow File in Wrong Location

**Check**: The workflow file must be in your **Obsidian notes repository** (not this code repository)

**Solution**: Copy workflow templates from `obsidian-note-manager/example/workflows/` to your vault repo `.github/workflows/`. Verify `.github/workflows/ingest.yml` exists in your obsidian-notes repository.

### 2. Wrong Branch

**Check**: The workflow triggers on `master` branch (or your configured branch)

**Solution**: Ensure you're pushing to the correct branch:
```bash
git branch  # Check current branch
git push origin master  # Push to master
```

### 3. Path Pattern Not Matching

**Check**: File path must match exactly:
- Path: `00. Inbox/0. Capture/**/*.md` or `00. Inbox/1. Review Queue/**/*.md`
- Case-sensitive
- Must be `.md` files

**Solution**: Verify file path matches exactly (including spaces and case)

### 4. Workflow Not on Target Branch

**Solution**: Ensure `.github/workflows/ingest.yml` exists on the `master` branch:
```bash
git checkout master
git pull origin master
ls .github/workflows/ingest.yml  # Should exist
```

---

## Workflow Fails with "No such file or directory"

**Symptoms**: Workflow runs but fails with `python3: can't open file 'src/main.py': No such file or directory` or similar

**Cause**: Workflow is using legacy path. The application is now run as a Python module.

**Solution**: Ensure workflow uses the correct module invocation:
```yaml
run: |
  python3 -m src_v2.entrypoints.ingest_runner
```

**Check**: Verify your `.github/workflows/ingest.yml` in obsidian-notes repository uses `python3 -m src_v2.entrypoints.ingest_runner` (ingestion) or `python3 -m src_v2.entrypoints.cron_runner` (maintenance).

---

## Git / Workflow Issues

**Symptoms**: Workflow completes successfully but the repository doesn't show any changes.

- ✅ Workflow is triggered correctly
- ✅ Runner picks up the job
- ✅ Job completes with "success" status
- ❌ Repository has no new commits
- ❌ Files are not moved from Capture to Review Queue

### Root Cause Hypotheses

1. **No files found**: Capture folder is empty (or files already processed)
2. **Processing fails silently**: Files found but processing throws exceptions
3. **Git operations fail**: Processing succeeds but workflow's commit/push step fails
4. **Wrong workspace**: Code is running in wrong directory
5. **Git authentication**: Push fails due to permission issues

### Diagnostic Steps

**Step 1: Check Workflow Logs (GitHub Actions)**

1. Go to: Repository → **Actions** tab
2. Click on the latest workflow run
3. Click on the **"Run Librarian"** or **"Run Night Watchman"** step
4. **Review the output** - look for:
   - `Filed X note(s) from Review Queue`
   - `Ingested X note(s) from Capture`
   - `Commit and push changes` step output

**Step 2: Check Workspace State (Inside Container)**

```bash
# SSH into Raspberry Pi, then:
docker compose exec librarian-runner bash

# Find workspace (path varies by job)
cd _work/*/obsidian-notes/obsidian-notes/ 2>/dev/null || echo "No workspace"

# Check Capture folder
ls -la "00. Inbox/0. Capture/" 2>/dev/null

# Check Review Queue
ls -la "00. Inbox/1. Review Queue/" 2>/dev/null

# Check Git status
git status
git diff --name-only
git log --oneline -5
```

**Interpretation**:
- Files still in Capture → Not processed
- Files in Review Queue but `git status` shows changes → Processed but workflow's commit step didn't run or failed
- Recent commits but not on GitHub → Push failed

**Step 3: Verify Workflow Git Steps**

The Python application does **not** perform Git operations. The workflow must include explicit commit and push steps:

```yaml
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

Ensure the workflow has `contents: write` permission and checkout uses `token: ${{ secrets.GITHUB_TOKEN }}`.

### Common Git/Workflow Issues

**Issue: "Capture folder is empty"**

- Verify file is in `00. Inbox/0. Capture/`
- Check file extension is `.md` (case-sensitive)
- Ensure file was committed and pushed before workflow ran

**Issue: Processing fails silently**

- Check for traceback in workflow logs
- Verify `GEMINI_API_KEY` secret is set
- Check for file read/write permission issues

**Issue: Commit step skipped**

- The workflow uses `git diff --staged --quiet || git commit` - if no changes, commit is skipped (expected)
- If Python made changes but commit didn't run, verify `OBSIDIAN_VAULT_ROOT` is set to `${{ github.workspace }}`

---

## Gemini API Errors

**Symptoms**: Processing fails with API errors or "GEMINI_API_KEY not set"

### 1. Missing API Key

**Check**:
```bash
# In workflow logs, check for:
# "Error: GEMINI_API_KEY environment variable not set"
```

**Solution**: Verify GitHub Secret is set:
1. Go to: Repository → Settings → Secrets and variables → Actions
2. Ensure `GEMINI_API_KEY` secret exists
3. Verify workflow references it: `${{ secrets.GEMINI_API_KEY }}`

### 2. Invalid API Key

**Symptoms**: API returns 401 Unauthorized

**Solution**:
1. Verify API key at [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Ensure key starts with `AIza...`
3. Regenerate key if necessary
4. Update GitHub Secret with new key

### 3. API Quota Exceeded

**Symptoms**: API returns 429 Too Many Requests

**Solution**:
- Check your Google Cloud quota limits
- Wait for quota reset
- Consider upgrading API tier if needed

---

## Runner Registration Token Errors

**Symptoms**: Error like "Forbidden: PAT may not have required permissions" or "Resource not accessible by personal access token"

### 1. Fine-Grained PAT (Not Supported)

**Error**: "Resource not accessible by personal access token"

**Cause**: Fine-grained PATs don't support the runner registration token API endpoint

**Solution**: Use a **Classic PAT** instead:
1. Go to: GitHub → Settings → Developer settings → Personal access tokens → **Tokens (classic)**
2. Generate new token with `repo` scope
3. Update `.env` with Classic PAT

### 2. Missing `repo` Scope

**Error**: "Forbidden: PAT may not have required permissions"

**Solution**: Ensure Classic PAT has `repo` scope:
1. Go to token settings
2. Check `repo` scope (full control)
3. Save and regenerate if needed

---

## Runner Update / Docker Issues

**Symptoms**: Runner fails after attempting auto-update, exiting with error code 127 on `run-helper.sh` line 36.

**Root Cause**: Exit code 127 means "command not found" - the runner update downloaded wrong architecture or missing dependencies.

### Solution: Update Dockerfile to Match Auto-Update Version

**Step 1**: Check what version the runner is trying to update to:
```bash
docker compose logs librarian-runner | grep -i "runner version\|downloading\|update"
```

**Step 2**: Update `Dockerfile` to use that version:
```dockerfile
ARG RUNNER_VERSION="2.331.0"  # Match the version runner wants
```

**Step 3**: Rebuild and restart (from repo root):
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

**Why this works**: Starting with the target version prevents the auto-update from running, avoiding the update bug.

### Clean Reinstall (If Above Doesn't Work)

```bash
# 1. Remove runner from GitHub UI: Settings → Actions → Runners → Remove

# 2. Clean up
docker compose down -v
docker system prune -f

# 3. Rebuild (after updating RUNNER_VERSION in Dockerfile)
docker compose build --no-cache
docker compose up -d
```

---

## Container Won't Start

**Symptoms**: `docker compose up` fails or container exits immediately

### 1. Missing Environment Variables

**Check**: Verify `.env` file exists at repo root and has required variables:
```bash
cat .env | grep -E "GITHUB_PAT|REPO_URL|GEMINI_API_KEY"
```

**Solution**: Copy `.env.example` to `.env` and fill in values. Run from repo root.

### 2. Docker Not Running

**Check**:
```bash
docker ps
```

**Solution**: Start Docker daemon:
```bash
sudo systemctl start docker
```

### 3. Build Errors

**Check logs**:
```bash
docker compose build 2>&1 | tail -50
```

**Solution**: Review build errors and fix Dockerfile or dependencies

---

## General Debugging Tips

### View Container Logs

```bash
# Follow logs in real-time
docker compose logs -f librarian-runner

# View last 100 lines
docker compose logs --tail=100 librarian-runner

# Check for errors
docker compose logs librarian-runner | grep -i error
```

### Check Runner Status

```bash
# Inside container
docker compose exec librarian-runner ps aux | grep Runner

# Check .runner config
docker compose exec librarian-runner cat .runner
```

### Test Manually

```bash
# Run ingestion pipeline manually (from repo root, with vault checked out in workspace)
docker compose exec librarian-runner python3 -m src_v2.entrypoints.ingest_runner

# Run maintenance scan manually
docker compose exec librarian-runner python3 -m src_v2.entrypoints.cron_runner
```

### Check Network Connectivity

```bash
# Test GitHub API
docker compose exec librarian-runner curl -s https://api.github.com | head -3

# Test Gemini API endpoint
docker compose exec librarian-runner curl -s https://generativelanguage.googleapis.com | head -3
```

---

## Getting Help

If you've tried the solutions above and still have issues:

1. **Check logs**: `docker compose logs librarian-runner`
2. **Check GitHub Actions logs**: Repository → Actions → Failed workflow → View logs
3. **Verify configuration**: Ensure all environment variables and secrets are correct
4. **Review documentation**: Check [Setup Guide](./setup.md) and [Architecture Overview](./architecture.md)

---

## Common Error Messages Reference

| Error Message | Cause | Solution |
|--------------|-------|----------|
| "REPO_URL is not set" | Missing environment variable | Add `REPO_URL` to `.env` |
| "GEMINI_API_KEY environment variable not set" | Missing API key | Set GitHub Secret `GEMINI_API_KEY` |
| "Forbidden: PAT may not have required permissions" | PAT missing `repo` scope or fine-grained PAT | Use Classic PAT with `repo` scope |
| "Resource not accessible by personal access token" | Fine-grained PAT | Switch to Classic PAT |
| "No such file or directory: 'src/main.py'" | Legacy path in workflow | Use `python3 -m src_v2.entrypoints.ingest_runner` |
| "Runner connect error: session already exists" | Stale session | Remove runner from GitHub, restart container |
| "Git operation failed: exit code(128)" | Git authentication issue | Check `GITHUB_TOKEN` and `contents: write` permission |
