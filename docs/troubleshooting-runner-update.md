# Troubleshooting: Runner Update Error 127

This guide addresses the issue where the GitHub Actions runner fails after attempting to auto-update, exiting with error code 127 on `run-helper.sh` line 36.

## Symptoms

- Runner successfully registers and starts initially
- Runner attempts to auto-update (e.g., from 2.311.0 to 2.331.0)
- Container exits with error code 127
- Error points to line 36 in `run-helper.sh`
- Container restart fails with the same error

## Root Cause

**Exit code 127** means "command not found" - the `run-helper.sh` script (generated during runner updates) is trying to execute a command or binary that doesn't exist in the container.

Common causes:
1. **Architecture mismatch**: Runner update downloaded wrong architecture (x64 instead of ARM64)
2. **Missing dependencies**: Required tools not available after update
3. **Path issues**: Updated runner structure has different paths
4. **Corrupted update**: Update download was incomplete or corrupted

## Solution

### Option 1: Update Dockerfile to Match Auto-Update Version (Recommended)

The runner auto-updates to the latest version, but your Dockerfile starts with an older version. Update the Dockerfile to start with the same version the runner wants to update to.

**Step 1**: Check what version the runner is trying to update to:
```bash
docker compose logs librarian-runner | grep -i "runner version\|downloading\|update"
```

**Step 2**: Update `Dockerfile` to use that version:
```dockerfile
ARG RUNNER_VERSION="2.331.0"  # Match the version runner wants
```

**Step 3**: Rebuild and restart:
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

**Why this works**: Starting with the target version prevents the auto-update from running, avoiding the update bug.

---

### Option 2: Clean Reinstall (If Option 1 Doesn't Work)

If updating the Dockerfile version doesn't work, do a clean reinstall.

**Step 1**: Remove runner from GitHub UI:
- Go to: Settings → Actions → Runners
- Remove the runner

**Step 2**: Clean up container and data:
```bash
docker compose down -v  # Removes volumes too
docker system prune -f    # Optional: clean up unused Docker resources
```

**Step 3**: Rebuild with updated version:
```bash
# Update Dockerfile RUNNER_VERSION first (see Option 1)
docker compose build --no-cache
docker compose up -d
```

**Step 4**: Verify:
```bash
docker compose logs -f librarian-runner
```

---

### Option 3: Disable Auto-Updates (Temporary Workaround)

If you need to keep using the old version temporarily, you can disable auto-updates.

**Note**: This is NOT recommended long-term. GitHub recommends keeping runners updated for security.

**How to disable**:
1. Check runner configuration for update settings
2. Set environment variable: `ACTIONS_RUNNER_DISABLE_UPDATE=1` (if supported)
3. Or manually patch the runner code (not recommended)

**Better solution**: Fix the root cause (Option 1 or 2) instead of disabling updates.

---

## Prevention

To avoid this issue in the future:

### 1. Keep Dockerfile Version Updated

Regularly check for new runner versions and update `Dockerfile`:
```dockerfile
ARG RUNNER_VERSION="2.331.0"  # Update when GitHub releases new version
```

### 2. Monitor Runner Version in Logs

Watch for update messages in logs:
```bash
docker compose logs librarian-runner | grep -i "update\|version"
```

### 3. Rebuild Periodically

When you see update messages, proactively rebuild:
```bash
# Update RUNNER_VERSION in Dockerfile
docker compose build --no-cache
docker compose restart librarian-runner
```

---

## Diagnostic Steps

If the issue persists, collect diagnostic information:

### Check Current Runner Version

```bash
# In container
docker compose exec librarian-runner cat .runner | grep -i version || echo "No version in .runner"

# Check what version is running
docker compose exec librarian-runner ls -la bin.* | head -10

# Check runner diagnostic logs
docker compose exec librarian-runner tail -100 _diag/Runner_*.log | grep -i "version\|update"
```

### Check Architecture Match

```bash
# Container architecture
docker compose exec librarian-runner uname -m
# Should show: aarch64 (ARM64)

# Check if runner binary matches
docker compose exec librarian-runner file bin/Runner.Listener
# Should show: ELF 64-bit LSB executable, ARM aarch64
```

### Check run-helper.sh Content

```bash
# View the problematic file
docker compose exec librarian-runner cat run-helper.sh | sed -n '30,45p'

# Check what command is failing at line 36
docker compose exec librarian-runner sed -n '36p' run-helper.sh
```

### Check Missing Dependencies

```bash
# Check if required tools are available
docker compose exec librarian-runner which bash
docker compose exec librarian-runner which curl
docker compose exec librarian-runner which tar
docker compose exec librarian-runner which unzip

# Check PATH
docker compose exec librarian-runner echo $PATH
```

---

## Common Error Patterns

### Error: "run-helper.sh: line 36: /path/to/binary: No such file or directory"

**Cause**: Binary path doesn't exist after update

**Solution**: Update Dockerfile to match target version (Option 1)

---

### Error: "run-helper.sh: line 36: command: command not found"

**Cause**: Missing system command (e.g., `bash`, `tar`, `curl`)

**Solution**: Ensure all dependencies are installed in Dockerfile:
```dockerfile
RUN apt-get update && apt-get install -y \
    curl jq git unzip \
    bash \
    tar \
    ...
```

---

### Error: Architecture mismatch after update

**Cause**: Runner downloaded x64 binaries on ARM64 Pi

**Solution**: Update Dockerfile with correct `RUNNER_ARCH` and version

---

## Still Not Working?

If none of the solutions work:

1. **Collect full diagnostics**:
   ```bash
   {
       echo "=== Container Status ==="
       docker compose ps
       echo ""
       echo "=== Runner Version Info ==="
       docker compose exec librarian-runner cat .runner 2>/dev/null || echo "No .runner file"
       echo ""
       echo "=== Architecture ==="
       docker compose exec librarian-runner uname -m
       docker compose exec librarian-runner file bin/Runner.Listener 2>/dev/null || echo "No Runner.Listener"
       echo ""
       echo "=== run-helper.sh Line 36 ==="
       docker compose exec librarian-runner sed -n '36p' run-helper.sh 2>/dev/null || echo "No run-helper.sh"
       echo ""
       echo "=== Container Logs (last 100 lines) ==="
       docker compose logs librarian-runner --tail=100
   } > /tmp/runner-update-diagnostics.txt
   
   cat /tmp/runner-update-diagnostics.txt
   ```

2. **Check GitHub Runner Releases**: Verify 2.331.0 ARM64 build exists at https://github.com/actions/runner/releases

3. **Try manual download**: Download runner manually and extract to verify files:
   ```bash
   curl -L -o runner.tar.gz https://github.com/actions/runner/releases/download/v2.331.0/actions-runner-linux-arm64-2.331.0.tar.gz
   tar -tzf runner.tar.gz | head -20
   ```

---

## Related Documentation

- [Troubleshooting Guide](troubleshooting.md) - General troubleshooting
- [Pi Offline Troubleshooting](troubleshooting-pi-offline.md) - Raspberry Pi specific issues
- [Setup Guide](setup.md) - Installation instructions
