# Troubleshooting: Workflow Succeeds But Repository Not Updated

This guide helps diagnose why a workflow completes successfully but the repository doesn't show any changes.

## Symptoms

- ✅ Workflow is triggered correctly
- ✅ Runner picks up the job
- ✅ Job completes with "success" status
- ❌ Repository has no new commits
- ❌ Files are not moved from Capture to Review Queue
- ❌ No changes appear in Git

## Root Cause Hypotheses

1. **No files found**: Capture folder is empty (or files already processed)
2. **Processing fails silently**: Files found but processing throws exceptions that are caught
3. **Git operations fail**: Processing succeeds but commit/push fails silently
4. **Wrong workspace**: Code is running in wrong directory
5. **Git authentication**: Push fails due to permission issues

## Diagnostic Steps

### Step 1: Check Workflow Logs (GitHub Actions)

View the actual output from the Python script:

1. Go to: Repository → **Actions** tab
2. Click on the latest workflow run
3. Click on the **"Run Librarian"** step
4. **Review the output** - look for:
   - `🤖 Librarian Starting...`
   - `🔎 Found X notes to process.`
   - `📄 Processing: filename.md...`
   - `✅ Saved to: ...`
   - `📦 Committing: ...`
   - `🚀 Pushing to remote...`
   - `✅ Push complete.`

**What to look for**:
- ✅ If you see "Capture folder is empty" → No files to process
- ✅ If you see processing messages → Files are being processed
- ✅ If you see "⚠️ Warning: Failed to commit/push" → Git operation failed
- ❌ If logs are minimal or missing → Script may be failing early

**Copy the full log output** - this is critical evidence.

---

### Step 2: Check Container Logs

Check what the runner container logged:

```bash
# On Raspberry Pi
docker compose logs librarian-runner --tail=200 | grep -A 20 -B 5 "Run Librarian\|Starting Ingestion\|Librarian Starting"
```

**What to look for**:
- Python script output
- Error messages
- Git operation errors

---

### Step 3: Check Workspace State (Inside Container)

Check if files were actually processed in the workspace:

```bash
# SSH into Raspberry Pi, then:
docker compose exec librarian-runner bash

# Check Capture folder
ls -la _work/*/obsidian-notes/obsidian-notes/"00. Inbox/0. Capture/" 2>/dev/null || echo "Workspace not found"

# Check Review Queue
ls -la _work/*/obsidian-notes/obsidian-notes/"00. Inbox/1. Review Queue/" 2>/dev/null || echo "Review Queue not found"

# Check Git status (in workspace)
cd _work/*/obsidian-notes/obsidian-notes/ 2>/dev/null || exit
git status

# Check if there are uncommitted changes
git diff --name-only

# Check recent commits
git log --oneline -5
```

**What to look for**:
- ✅ Files in Capture folder → Not processed yet
- ✅ Files in Review Queue → Processing succeeded but commit failed
- ✅ `git status` shows changes → Files changed but not committed
- ✅ `git log` shows local commits → Committed but not pushed

---

### Step 4: Test Git Push Manually (Inside Container)

Test if Git push works manually:

```bash
# Inside container workspace (from Step 3)
cd _work/*/obsidian-notes/obsidian-notes/

# Try to push (if there are commits)
git push origin master 2>&1
```

**What to look for**:
- ✅ Push succeeds → Git works, but script didn't push
- ❌ Push fails with auth error → `GITHUB_TOKEN` issue
- ❌ Push fails with "nothing to push" → Already pushed or no commits

---

### Step 5: Verify Environment Variables

Check if required environment variables are set in workflow:

```bash
# In workflow logs (GitHub Actions UI), check:
# - GEMINI_API_KEY is set
# - OBSIDIAN_VAULT_ROOT is set to github.workspace
```

Or check in container after job runs:

```bash
docker compose exec librarian-runner env | grep -E "GEMINI|OBSIDIAN|GITHUB"
```

---

### Step 6: Run Manual Test (Inside Container)

Run the Python script manually to see full output:

```bash
# On Raspberry Pi
docker compose exec librarian-runner bash

# Navigate to workspace (from a recent job)
cd _work/obsidian-notes/obsidian-notes/

# Set environment variables (match workflow)
export GEMINI_API_KEY="your_key_here"
export OBSIDIAN_VAULT_ROOT=$(pwd)

# Run the script manually
python3 /home/runner/src/main.py

# Watch for errors or output
```

**What to look for**:
- Full output with all processing steps
- Any exception tracebacks
- Git operation errors

---

## Common Issues and Solutions

### Issue 1: "Capture folder is empty"

**Symptom**: Logs show "📭 Capture folder is empty. Exiting."

**Cause**: No `.md` files in Capture folder when script runs

**Solution**:
- Verify file is actually in `00. Inbox/0. Capture/` folder
- Check file extension is `.md` (case-sensitive)
- Ensure file was committed and pushed before workflow ran

**Debug**:
```bash
# In container workspace
ls -la "00. Inbox/0. Capture/"
file "00. Inbox/0. Capture/"*.md  # Check files exist
```

---

### Issue 2: "⚠️ Warning: Failed to commit/push changes"

**Symptom**: Logs show warning but job still succeeds

**Cause**: Git push failed (auth, network, or other error)

**Solution**: Check the error message after "Failed to commit/push"

**Common causes**:
- **Authentication failed**: `GITHUB_TOKEN` not set or insufficient permissions
- **Network error**: Push request failed
- **Nothing to commit**: Changes already committed in previous run

**Debug**:
```bash
# Check Git config
cd _work/*/obsidian-notes/obsidian-notes/
git remote -v
git log --oneline -5

# Test push manually
git push origin master
```

**Fix**: Ensure workflow has `token: ${{ secrets.GITHUB_TOKEN }}` in checkout action and `contents: write` permission.

---

### Issue 3: Processing Fails Silently

**Symptom**: Files found but no output after "Processing: filename.md..."

**Cause**: Exception in processing caught but script continues

**Solution**: Check for traceback in logs (may be truncated)

**Debug**: Look for:
- `❌ Failed to process filename.md: ...`
- `Traceback (most recent call last):`
- Any error messages

**Common causes**:
- Gemini API error (missing key, quota exceeded)
- File read/write permission issues
- YAML parsing errors

**Fix**: Address the specific error shown in traceback.

---

### Issue 4: Files Processed But Not Committed

**Symptom**: Files appear in Review Queue in workspace, but no Git commit

**Cause**: `git.commit_and_push()` not called or failed silently

**Debug**:
```bash
# In container workspace
cd _work/*/obsidian-notes/obsidian-notes/
git status  # Should show modified/new files

# Check if GitOps detected changes
# (This requires checking script logic - see main.py)
```

**Fix**: Check `main.py` - `processed_count` might be 0, preventing commit.

---

### Issue 5: Committed But Not Pushed

**Symptom**: Local commits exist but not on remote

**Cause**: Push operation failed but error was caught

**Debug**:
```bash
# In container workspace
cd _work/*/obsidian-notes/obsidian-notes/
git log --oneline -5  # Local commits
git log origin/master..HEAD --oneline  # Unpushed commits
git push origin master  # Try pushing
```

**Fix**: Check Git authentication and network connectivity.

---

## Systematic Diagnosis Workflow

Run these commands in order:

### 1. Check GitHub Actions Logs

```
Repository → Actions → Latest run → "Run Librarian" step
```

**Note**: What do the logs show? Copy key messages.

---

### 2. Check Workspace After Job

```bash
# On Raspberry Pi
docker compose exec librarian-runner bash

# Find workspace
cd _work/*/obsidian-notes/obsidian-notes/ 2>/dev/null || echo "No workspace"

# Check state
echo "=== Capture folder ==="
ls -la "00. Inbox/0. Capture/" 2>/dev/null || echo "Not found"

echo "=== Review Queue ==="
ls -la "00. Inbox/1. Review Queue/" 2>/dev/null || echo "Not found"

echo "=== Git Status ==="
git status 2>/dev/null || echo "Not a git repo"

echo "=== Recent Commits ==="
git log --oneline -5 2>/dev/null || echo "No commits"

exit
```

**Interpretation**:
- Files still in Capture → Not processed
- Files in Review Queue but `git status` shows changes → Processed but not committed
- Files in Review Queue and `git status` clean → Committed locally
- Recent commits but not on GitHub → Not pushed

---

### 3. Check Git Push Capability

```bash
# Still in container
cd _work/*/obsidian-notes/obsidian-notes/
git remote -v
git push origin master 2>&1
```

**What happens**:
- ✅ Push succeeds → Git works, script issue
- ❌ Auth error → `GITHUB_TOKEN` problem
- ❌ "Nothing to push" → Already pushed or no commits

---

## Adding Debug Logging (Temporary)

If standard diagnostics don't reveal the issue, add temporary debug logging to `main.py`:

```python
# Add after line ~96 in main.py (after files_to_process)
import sys
print(f"DEBUG: Found {len(files_to_process)} files: {[f.name for f in files_to_process]}", file=sys.stderr)

# Add before git.commit_and_push (around line 156)
print(f"DEBUG: processed_count = {processed_count}", file=sys.stderr)
print(f"DEBUG: About to commit/push", file=sys.stderr)
```

Then rebuild and rerun:
```bash
docker compose down
docker compose build
docker compose up -d
```

**Note**: Remove debug logging after diagnosis.

---

## Quick Fix Checklist

Run through this checklist:

- [ ] **Workflow logs show "Found X notes to process"** → If not, files not detected
- [ ] **Workflow logs show "Processing: filename.md"** → If not, loop not executing
- [ ] **Workflow logs show "✅ Saved to: ..."** → If not, file write failed
- [ ] **Workflow logs show "📦 Committing: ..."** → If not, `processed_count` is 0
- [ ] **Workflow logs show "🚀 Pushing to remote"** → If not, commit failed
- [ ] **Workflow logs show "✅ Push complete"** → If not, push failed
- [ ] **No "⚠️ Warning" messages** → If present, check the warning text
- [ ] **GitHub shows workflow as "success"** → If failed, check error messages

**Where the checklist stops** = where the failure occurs.

---

## Still Not Working?

If none of the above reveals the issue:

1. **Collect full diagnostic output**:
   ```bash
   {
       echo "=== Container Status ==="
       docker compose ps
       echo ""
       echo "=== Recent Container Logs ==="
       docker compose logs librarian-runner --tail=100
       echo ""
       echo "=== Workspace Check ==="
       docker compose exec librarian-runner bash -c 'cd _work/*/obsidian-notes/obsidian-notes/ 2>/dev/null && pwd && ls -la "00. Inbox/0. Capture/" 2>/dev/null && ls -la "00. Inbox/1. Review Queue/" 2>/dev/null && git status 2>/dev/null'
   } > /tmp/git-diagnostics.txt
   
   cat /tmp/git-diagnostics.txt
   ```

2. **Check GitHub Actions run details** - Screenshot or copy full "Run Librarian" step output

3. **Verify workflow file** - Ensure `.github/workflows/ingest.yml` in obsidian-notes repo is correct

---

## Related Documentation

- [Troubleshooting Guide](troubleshooting.md) - General troubleshooting
- [Workflow Documentation](workflows.md) - Workflow configuration
- [Component Documentation](components.md) - `main.py` and `git_ops.py` details
