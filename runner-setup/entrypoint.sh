#!/bin/bash
set -e

# #region agent log
LOG_FILE="/home/runner/.cursor/debug.log"
mkdir -p "$(dirname "$LOG_FILE")"
log_debug() {
  echo "{\"timestamp\":$(date +%s000),\"location\":\"entrypoint.sh:$1\",\"message\":\"$2\",\"data\":$3,\"sessionId\":\"debug-session\",\"runId\":\"registration\",\"hypothesisId\":\"$4\"}" >> "$LOG_FILE"
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
log_debug "14" "Environment variables check" "{\"token_length\":${#GITHUB_TOKEN},\"repo_url_prefix\":\"${REPO_URL:0:30}...\",\"runner_name\":\"${RUNNER_NAME:-pi-docker-runner}\"}" "H1,H2,H3"
# #endregion agent log

# Configure the Runner
# --unattended: Don't ask for prompts
# --replace: Overwrite existing runner with same name
# #region agent log
log_debug "22" "About to run config.sh" "{\"url\":\"${REPO_URL}\",\"name\":\"${RUNNER_NAME:-pi-docker-runner}\"}" "H1,H2,H3,H4"
# #endregion agent log

./config.sh \
    --url "${REPO_URL}" \
    --token "${GITHUB_TOKEN}" \
    --name "${RUNNER_NAME:-pi-docker-runner}" \
    --work "_work" \
    --labels "self-hosted,docker,pi" \
    --unattended \
    --replace

CONFIG_EXIT_CODE=$?

# #region agent log
log_debug "35" "config.sh completed" "{\"exit_code\":$CONFIG_EXIT_CODE}" "H1,H2,H3,H4,H5"
# #endregion agent log

if [ $CONFIG_EXIT_CODE -ne 0 ]; then
  log_debug "38" "config.sh failed" "{\"exit_code\":$CONFIG_EXIT_CODE}" "H1,H2,H3,H4,H5"
  exit $CONFIG_EXIT_CODE
fi

# Run the Runner
echo "✅ Runner Configured. Listening for jobs..."
./run.sh
