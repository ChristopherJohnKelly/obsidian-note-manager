# Troubleshooting: Runner Shows Offline on Raspberry Pi

This guide specifically addresses the issue where the runner shows as "Offline" in GitHub even though container logs show success.

## Symptoms

- ✅ Container logs show: "Listening for Jobs" and "Connected to GitHub"
- ✅ Container is running: `docker compose ps` shows container up
- ❌ GitHub shows runner as "Offline" (gray) instead of "Idle" (green)
- ❌ Workflows are queued but not executing

## Root Causes

### 1. Network Connectivity Issues (Most Common)

The runner may connect initially but lose connection due to network issues.

**Diagnostics**:

```bash
# Check if container can reach GitHub API
docker compose exec librarian-runner curl -v https://api.github.com 2>&1 | head -20

# Check DNS resolution
docker compose exec librarian-runner nslookup api.github.com

# Test runner service endpoint (from runner diagnostic logs)
docker compose exec librarian-runner curl -v https://pipelinesghubeus6.actions.githubusercontent.com 2>&1 | head -20
```

**What to look for**:
- Connection timeout errors
- DNS resolution failures
- SSL/TLS certificate errors
- Firewall blocking outbound HTTPS (443)

---

### 2. Runner Process Not Running

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

---

### 3. Runner Diagnostic Logs

Check the runner's internal diagnostic logs for connection issues.

**Diagnostics**:

```bash
# List diagnostic log files
docker compose exec librarian-runner ls -lt _diag/ | head -10

# View most recent runner log
docker compose exec librarian-runner tail -100 _diag/Runner_*.log | tail -50

# Look for these patterns:
# - "MessageListener: Session created"
# - "MessageListener: Listening for Jobs"
# - "RunnerServer: EstablishVssConnection"
# - Any "error", "failed", "timeout", "disconnect" messages
```

**What to look for**:
- Connection errors after initial connection
- Heartbeat failures
- Session timeout errors
- SSL/TLS handshake failures

---

### 4. Firewall or Proxy Issues

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

**Common issues**:
- `ufw` firewall blocking outbound HTTPS
- Router firewall blocking connections
- Corporate network/proxy requiring configuration

---

### 5. Time Synchronization Issues

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

---

### 6. DNS Resolution Issues

Container may not be able to resolve GitHub hostnames.

**Diagnostics**:

```bash
# Test DNS from container
docker compose exec librarian-runner nslookup api.github.com
docker compose exec librarian-runner nslookup pipelinesghubeus6.actions.githubusercontent.com

# Check container's DNS servers
docker compose exec librarian-runner cat /etc/resolv.conf
```

**Solution**: If DNS fails, check host DNS:
```bash
# On Raspberry Pi host
cat /etc/resolv.conf
systemctl status systemd-resolved
```

---

### 7. Runner Session State

The runner may have a stale session that GitHub hasn't cleared.

**Diagnostics**:

```bash
# Check .runner config file
docker compose exec librarian-runner cat .runner

# Look for serverUrl - this should match GitHub's runner service
```

**Solution**: Remove runner and force fresh registration:

```bash
# 1. Remove runner from GitHub UI
#    Settings → Actions → Runners → Remove runner

# 2. Stop and remove container (deletes .runner file)
docker compose down

# 3. Start fresh
docker compose up -d

# 4. Wait 30-60 seconds for registration
docker compose logs -f librarian-runner
```

---

### 8. GitHub Actions Service Endpoint

The runner may be trying to connect to a regional endpoint that's blocked or unreachable.

**Diagnostics**:

```bash
# Check what endpoint the runner is using
docker compose exec librarian-runner cat .runner | grep serverUrl

# Try to reach that endpoint
docker compose exec librarian-runner curl -v $(docker compose exec librarian-runner cat .runner | grep -oP '"serverUrl":\s*"\K[^"]+')
```

**Note**: GitHub Actions uses regional endpoints. If one is blocked, the runner may fail.

---

## Systematic Debugging Steps

Follow these steps in order:

### Step 1: Verify Container and Process

```bash
# Check container status
docker compose ps

# Check runner process
docker compose exec librarian-runner ps aux | grep Runner

# Expected output should include:
# /bin/bash ./run.sh
# /home/runner/bin/Runner.Listener run
```

**If process missing**: Container logs may show why it exited. Check `docker compose logs`.

---

### Step 2: Check Network Connectivity

```bash
# Test basic connectivity
docker compose exec librarian-runner ping -c 3 8.8.8.8

# Test DNS
docker compose exec librarian-runner nslookup api.github.com

# Test HTTPS to GitHub
docker compose exec librarian-runner curl -I https://api.github.com

# Test runner service endpoint
docker compose exec librarian-runner curl -I https://pipelinesghubeus6.actions.githubusercontent.com
```

**If any fail**: Network/firewall issue. Check host firewall and network settings.

---

### Step 3: Check Runner Diagnostic Logs

```bash
# Find most recent log
docker compose exec librarian-runner ls -lt _diag/Runner_*.log | head -1

# View last 100 lines
docker compose exec librarian-runner tail -100 $(docker compose exec librarian-runner ls -t _diag/Runner_*.log | head -1)
```

**Look for**:
- ✅ "Session created" - Good, runner connected
- ✅ "Listening for Jobs" - Good, waiting for work
- ❌ "error", "timeout", "failed" - Problem identified
- ❌ No recent entries after initial connection - Runner stopped logging

---

### Step 4: Check Container Logs for Errors

```bash
# View all logs
docker compose logs librarian-runner --tail=200

# Filter for errors
docker compose logs librarian-runner 2>&1 | grep -i "error\|failed\|timeout\|disconnect"
```

**Common issues**:
- "Connection refused" - Network/firewall
- "Name resolution failed" - DNS
- "SSL/TLS handshake failed" - Time sync or certificate issues

---

### Step 5: Verify Time Synchronization

```bash
# Check container time vs actual time
docker compose exec librarian-runner date
date -u  # Compare

# Check time drift
docker compose exec librarian-runner date +%s
date +%s  # Should be within a few seconds
```

**If time is off**: Sync system time (see Solution 5 above).

---

### Step 6: Test Runner Re-registration

```bash
# Remove runner from GitHub UI first!

# Stop container
docker compose down

# Remove .runner file to force re-registration
# (This happens automatically when container is removed)

# Start fresh
docker compose up -d

# Watch logs
docker compose logs -f librarian-runner
```

**Expected**:
- `🔑 Fetching registration token using PAT...`
- `✅ Runner Configured. Listening for jobs...`
- `√ Connected to GitHub`
- `Listening for Jobs`

**Then check GitHub UI**: Runner should appear as "Idle" (green) within 60 seconds.

---

## Specific Solutions by Error Type

### Error: "Connection timed out" or "Connection refused"

**Cause**: Firewall or network blocking outbound HTTPS

**Solution**:
```bash
# On Raspberry Pi host
# Allow outbound HTTPS (if using ufw)
sudo ufw allow out 443/tcp

# Or check router/firewall settings
# Ensure outbound HTTPS (port 443) is allowed
```

---

### Error: "Name resolution failed" or "Could not resolve host"

**Cause**: DNS not working in container

**Solution**:
```bash
# Check host DNS
cat /etc/resolv.conf

# Ensure docker-compose.yml uses host DNS (if needed, add to docker-compose.yml):
# dns:
#   - 8.8.8.8
#   - 8.8.4.4
```

Or restart Docker network:
```bash
docker compose down
docker network prune
docker compose up -d
```

---

### Error: "SSL handshake failed" or "Certificate verify failed"

**Cause**: System time incorrect or CA certificates outdated

**Solution**:
```bash
# Sync time
sudo timedatectl set-ntp true

# Update CA certificates (on host)
sudo apt update
sudo apt install ca-certificates

# Restart container
docker compose restart librarian-runner
```

---

### No Errors, But Runner Still Offline

**Cause**: Runner connected but GitHub hasn't detected it yet, or heartbeat is failing

**Solution**:

1. **Wait longer**: GitHub may take 60-90 seconds to detect runner after connection
2. **Check runner logs**: Look for heartbeat messages in `_diag/Runner_*.log`
3. **Remove and re-add**: Remove from GitHub UI, wait 30 seconds, restart container

---

## Advanced Debugging

### Enable Verbose Logging

Edit `entrypoint.sh` to add debug output (temporary):

```bash
# Add after ./run.sh line in entrypoint.sh
# DEBUG: Check runner status every 30 seconds
while true; do
    sleep 30
    ps aux | grep Runner.Listener | grep -v grep || echo "WARNING: Runner.Listener not running"
    docker compose exec librarian-runner tail -1 _diag/Runner_*.log 2>/dev/null || echo "No recent log entries"
done &
```

### Monitor Network Traffic

On Raspberry Pi host:
```bash
# Install tcpdump (if not installed)
sudo apt install tcpdump

# Monitor outbound connections to GitHub
sudo tcpdump -i any -n host api.github.com or host pipelinesghubeus6.actions.githubusercontent.com
```

Look for:
- Connection attempts
- SSL handshakes
- Data packets (heartbeats)
- Connection resets or timeouts

---

## Prevention

To avoid this issue in the future:

1. **Ensure stable network**: Use wired Ethernet if possible (more stable than WiFi)
2. **Check firewall rules**: Don't block outbound HTTPS
3. **Keep time synced**: Enable NTP on Raspberry Pi
4. **Monitor logs**: Regularly check `docker compose logs`
5. **Restart strategy**: Use `restart: unless-stopped` in docker-compose.yml (already configured)

---

## Still Not Working?

If none of these solutions work:

1. **Collect diagnostics**:
   ```bash
   # Create diagnostics file
   {
       echo "=== Container Status ==="
       docker compose ps
       echo ""
       echo "=== Runner Process ==="
       docker compose exec librarian-runner ps aux | grep -E "Runner|run"
       echo ""
       echo "=== Container Logs (last 100 lines) ==="
       docker compose logs librarian-runner --tail=100
       echo ""
       echo "=== Runner Diagnostic Log (last 50 lines) ==="
       docker compose exec librarian-runner tail -50 _diag/Runner_*.log 2>/dev/null || echo "No log found"
       echo ""
       echo "=== Network Test ==="
       docker compose exec librarian-runner curl -I https://api.github.com 2>&1 | head -10
       echo ""
       echo "=== Time Check ==="
       echo "Container: $(docker compose exec librarian-runner date)"
       echo "Host: $(date)"
   } > /tmp/runner-diagnostics.txt
   
   cat /tmp/runner-diagnostics.txt
   ```

2. **Share the diagnostics** for further help (remove any sensitive tokens/IPs first)

3. **Check GitHub Status**: Sometimes GitHub Actions has outages - check https://www.githubstatus.com/
