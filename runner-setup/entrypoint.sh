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

# Configure the Runner
# --unattended: Don't ask for prompts
# --replace: Overwrite existing runner with same name
./config.sh \
    --url "${REPO_URL}" \
    --token "${GITHUB_TOKEN}" \
    --name "${RUNNER_NAME:-pi-docker-runner}" \
    --work "_work" \
    --labels "self-hosted,docker,pi" \
    --unattended \
    --replace

# Run the Runner
echo "✅ Runner Configured. Listening for jobs..."
./run.sh
