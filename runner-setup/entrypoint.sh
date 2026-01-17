#!/bin/bash
set -e

# #region agent log
LOG_FILE="/home/runner/.cursor/debug.log"
mkdir -p "$(dirname "$LOG_FILE")"
log_debug() {
  local log_entry="{\"timestamp\":$(date +%s000),\"location\":\"entrypoint.sh:$1\",\"message\":\"$2\",\"data\":$3,\"sessionId\":\"debug-session\",\"runId\":\"registration\",\"hypothesisId\":\"$4\"}"
  echo "$log_entry" >> "$LOG_FILE"
  echo "[DEBUG] $log_entry" >&2
}
# #endregion agent log

# Check required inputs
if [ -z "$GITHUB_TOKEN" ]; then
  log_debug "5" "GITHUB_TOKEN not set" "{}" "H2"
  echo "Error: GITHUB_TOKEN is not set."
  exit 1
fi

if [ -z "$REPO_URL" ]; then
  log_debug "10" "REPO_URL not set" "{}" "H3"
  echo "Error: REPO_URL is not set."
  exit 1
fi

# #region agent log
log_debug "14" "Environment variables check" "{\"token_length\":${#GITHUB_TOKEN},\"repo_url\":\"${REPO_URL}\",\"repo_url_prefix\":\"${REPO_URL:0:50}...\",\"runner_name\":\"${RUNNER_NAME:-pi-docker-runner}\",\"url_format_valid\":$([ "${REPO_URL#https://github.com/}" != "$REPO_URL" ] && echo true || echo false)}" "H1,H2,H3"
# #endregion agent log

# Validate URL format
if [[ ! "$REPO_URL" =~ ^https://github\.com/[^/]+(/[^/]+)?$ ]]; then
  log_debug "18" "Invalid REPO_URL format" "{\"repo_url\":\"${REPO_URL}\",\"expected_format\":\"https://github.com/OWNER/REPO\"}" "H3"
  echo "Error: REPO_URL must be in format: https://github.com/OWNER/REPO"
  exit 1
fi

# Configure the Runner
# --unattended: Don't ask for prompts
# --replace: Overwrite existing runner with same name
# #region agent log
log_debug "25" "About to run config.sh" "{\"url\":\"${REPO_URL}\",\"name\":\"${RUNNER_NAME:-pi-docker-runner}\",\"token_first_chars\":\"${GITHUB_TOKEN:0:10}...\"}" "H1,H2,H3,H4"
# #endregion agent log

# Capture config.sh output for debugging
# Temporarily disable set -e to capture exit code
set +e
CONFIG_OUTPUT=$(./config.sh \
    --url "${REPO_URL}" \
    --token "${GITHUB_TOKEN}" \
    --name "${RUNNER_NAME:-pi-docker-runner}" \
    --work "_work" \
    --labels "self-hosted,docker,pi" \
    --unattended \
    --replace 2>&1)
CONFIG_EXIT_CODE=$?
set -e

# #region agent log
log_debug "40" "config.sh completed" "{\"exit_code\":$CONFIG_EXIT_CODE,\"output_lines\":$(echo "$CONFIG_OUTPUT" | wc -l),\"has_404\":$(echo "$CONFIG_OUTPUT" | grep -q "404\|NotFound" && echo true || echo false),\"has_expired\":$(echo "$CONFIG_OUTPUT" | grep -qi "expired\|invalid" && echo true || echo false)}" "H1,H2,H3,H4,H5"
# #endregion agent log

if [ $CONFIG_EXIT_CODE -ne 0 ]; then
  echo "$CONFIG_OUTPUT" >&2
  log_debug "45" "config.sh failed with output" "{\"exit_code\":$CONFIG_EXIT_CODE,\"output\":\"$(echo "$CONFIG_OUTPUT" | head -5 | tr '\n' ';')\"}" "H1,H2,H3,H4,H5"
  
  # Provide helpful error messages
  if echo "$CONFIG_OUTPUT" | grep -q "404\|NotFound"; then
    echo "" >&2
    echo "❌ Registration failed with 404 Not Found error." >&2
    echo "   This usually means:" >&2
    echo "   1. Registration token has expired (tokens expire after 1 hour)" >&2
    echo "   2. Invalid or malformed token" >&2
    echo "   3. Repository URL is incorrect" >&2
    echo "" >&2
    echo "   To fix:" >&2
    echo "   1. Go to: https://github.com/$(echo "$REPO_URL" | sed 's|https://github.com/||')/settings/actions/runners" >&2
    echo "   2. Click 'New self-hosted runner'" >&2
    echo "   3. Copy the new registration token" >&2
    echo "   4. Update GITHUB_RUNNER_TOKEN in your .env file" >&2
  fi
  
  exit $CONFIG_EXIT_CODE
fi

# Run the Runner
echo "✅ Runner Configured. Listening for jobs..."
./run.sh
