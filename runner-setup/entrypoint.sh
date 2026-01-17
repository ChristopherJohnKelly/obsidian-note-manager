#!/bin/bash
set -e

# Check required inputs
if [ -z "$GITHUB_TOKEN" ]; then
  echo "Error: GITHUB_TOKEN is not set."
  exit 1
fi

if [ -z "$REPO_URL" ]; then
  echo "Error: REPO_URL is not set."
  exit 1
fi

# Validate URL format
if [[ ! "$REPO_URL" =~ ^https://github\.com/[^/]+(/[^/]+)?$ ]]; then
  echo "Error: REPO_URL must be in format: https://github.com/OWNER/REPO"
  exit 1
fi

# Configure the Runner
# --unattended: Don't ask for prompts
# --replace: Overwrite existing runner with same name
# Temporarily disable set -e to capture exit code and provide helpful errors
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

if [ $CONFIG_EXIT_CODE -ne 0 ]; then
  echo "$CONFIG_OUTPUT" >&2
  
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
