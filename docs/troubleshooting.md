# Troubleshooting Guide

This guide helps you diagnose and fix common issues with the Obsidian Note Automation system.

## Table of Contents

- [Runner Not Appearing in GitHub](#runner-not-appearing-in-github)
- [Runner Shows as Offline](#runner-shows-as-offline)
- [Workflow Not Triggering](#workflow-not-triggering)
- [Workflow Fails with "No such file or directory"](#workflow-fails-with-no-such-file-or-directory)
- [Gemini API Errors](#gemini-api-errors)
- [Git Push Fails](#git-push-fails)
- [Runner Registration Token Errors](#runner-registration-token-errors)
- [Container Won't Start](#container-wont-start)

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

# Rebuild and start
docker compose build
docker compose up -d
```

---

## Runner Shows as Offline

**Symptoms**: Runner appears in GitHub UI but shows as "Offline" (gray) instead of "Idle" (green)

> 🔧 **For Raspberry Pi-specific offline issues**, see the comprehensive [Pi Offline Troubleshooting Guide](troubleshooting-pi-offline.md)

**Possible Causes**:

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

### 3. Network Issues

**Check**:
```bash
docker compose exec librarian-runner curl -s https://api.github.com | head -3
```

**Solution**: Verify network connectivity and firewall settings

---

## Workflow Not Triggering

**Symptoms**: Pushing files to `00. Inbox/0. Capture/` doesn't trigger workflow

**Possible Causes**:

### 1. Workflow File in Wrong Location

**Check**: The workflow file must be in your **Obsidian notes repository** (not this code repository)

**Solution**: Verify `.github/workflows/ingest.yml` exists in your obsidian-notes repository

### 2. Wrong Branch

**Check**: The workflow triggers on `master` branch (or your configured branch)

**Solution**: Ensure you're pushing to the correct branch:
```bash
git branch  # Check current branch
git push origin master  # Push to master
```

### 3. Path Pattern Not Matching

**Check**: File path must match exactly:
- Path: `00. Inbox/0. Capture/**/*.md`
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

**Symptoms**: Workflow runs but fails with `python3: can't open file 'src/main.py': No such file or directory`

**Cause**: Workflow is trying to run `src/main.py` from the checked-out workspace, but the code is at `/home/runner/src/main.py` in the container

**Solution**: Ensure workflow uses absolute path:
```yaml
run: |
  python3 /home/runner/src/main.py  # Correct
  # NOT: python3 src/main.py
```

**Check**: Verify your `.github/workflows/ingest.yml` in obsidian-notes repository uses the correct path

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

## Git Push Fails

**Symptoms**: Processing succeeds but commit/push fails with error 128 or authentication errors

**Possible Causes**:

### 1. Missing GITHUB_TOKEN

**Check**: Workflow should have:
```yaml
- name: Checkout Vault
  uses: actions/checkout@v4
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
```

**Solution**: Ensure checkout action includes `token: ${{ secrets.GITHUB_TOKEN }}`

### 2. Insufficient Permissions

**Check**: Workflow needs `contents: write` permission:
```yaml
permissions:
  contents: write
```

**Solution**: Add `permissions` block to workflow if missing

### 3. Git Configuration Issues

**Symptoms**: Error like "Git operation failed" or "fatal: could not read Username"

**Solution**: The runner uses GitHub Actions' built-in authentication via `GITHUB_TOKEN`. Ensure:
- Workflow has `contents: write` permission
- Checkout action uses `token: ${{ secrets.GITHUB_TOKEN }}`
- Repository settings allow GitHub Actions to write to repository

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

### 3. PAT Not Installed (Fine-Grained)

**If using fine-grained PAT** (not recommended):
- Fine-grained PATs must be installed/authorized for the repository
- Go to: Repository → Settings → Secrets and variables → Actions → Fine-grained personal access tokens

**Better Solution**: Use Classic PAT (see above)

---

## Container Won't Start

**Symptoms**: `docker compose up` fails or container exits immediately

### 1. Missing Environment Variables

**Check**: Verify `.env` file exists and has required variables:
```bash
cat .env | grep -E "GITHUB_PAT|REPO_URL|GEMINI_API_KEY"
```

**Solution**: Create or update `.env` file with required variables

### 2. Docker Not Running

**Check**:
```bash
docker ps
```

**Solution**: Start Docker daemon:
```bash
sudo systemctl start docker
```

### 3. Port Conflicts

**Check**: No port conflicts (runner doesn't use exposed ports, but check for other issues)

**Solution**: Check for other containers or services using resources

### 4. Build Errors

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
# Test Gemini API
docker compose exec librarian-runner python3 src/test_gemini.py

# Test note processing
docker compose exec librarian-runner python3 src/run_manual.py /path/to/note.md /vault/root
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
| "No such file or directory: 'src/main.py'" | Wrong path in workflow | Use `/home/runner/src/main.py` |
| "Runner connect error: session already exists" | Stale session | Remove runner from GitHub, restart container |
| "Git operation failed: exit code(128)" | Git authentication issue | Check `GITHUB_TOKEN` and permissions |
