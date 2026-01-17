#!/bin/bash
set -e

# Check required inputs
if [ -z "$REPO_URL" ]; then
  echo "Error: REPO_URL is not set."
  exit 1
fi

# Validate URL format
if [[ ! "$REPO_URL" =~ ^https://github\.com/[^/]+(/[^/]+)?$ ]]; then
  echo "Error: REPO_URL must be in format: https://github.com/OWNER/REPO"
  exit 1
fi

# Check if runner is already configured
if [ -f ".runner" ]; then
  echo "✅ Runner already configured. Starting runner..."
  ./run.sh
  exit 0
fi

# Need to register runner - check for token source
REGISTRATION_TOKEN=""

if [ -n "$GITHUB_PAT" ]; then
  # Use PAT to fetch registration token dynamically
  echo "🔑 Fetching registration token using PAT..."
  set +e
  REGISTRATION_TOKEN=$(python3 src/token_fetcher.py "$REPO_URL" "$GITHUB_PAT" 2>&1)
  TOKEN_EXIT_CODE=$?
  set -e
  
  if [ $TOKEN_EXIT_CODE -ne 0 ]; then
    echo "❌ Failed to fetch registration token using PAT:" >&2
    echo "$REGISTRATION_TOKEN" >&2
    echo "" >&2
    echo "   This usually means:" >&2
    echo "   1. PAT is invalid or expired" >&2
    echo "   2. PAT doesn't have required permissions (needs 'repo' scope or 'Actions: Read and write')" >&2
    echo "   3. Repository URL is incorrect or no access" >&2
    exit 1
  fi
  
elif [ -n "$GITHUB_TOKEN" ]; then
  # Fallback to direct registration token (backward compatibility)
  echo "⚠️  Using GITHUB_TOKEN (legacy method). Consider using GITHUB_PAT for automatic token management."
  REGISTRATION_TOKEN="$GITHUB_TOKEN"
  
else
  echo "Error: Neither GITHUB_PAT nor GITHUB_TOKEN is set." >&2
  echo "   Please set one of:" >&2
  echo "   - GITHUB_PAT (recommended): Personal Access Token for automatic token fetching" >&2
  echo "   - GITHUB_TOKEN (legacy): Direct registration token (expires after 1 hour)" >&2
  exit 1
fi

# Configure the Runner
# --unattended: Don't ask for prompts
# --replace: Overwrite existing runner with same name
# Temporarily disable set -e to capture exit code and provide helpful errors
set +e
CONFIG_OUTPUT=$(./config.sh \
    --url "${REPO_URL}" \
    --token "${REGISTRATION_TOKEN}" \
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
    if [ -n "$GITHUB_PAT" ]; then
      echo "   Since using PAT, the token should have been fetched fresh. Check PAT permissions." >&2
    else
      echo "   To fix:" >&2
      echo "   1. Go to: https://github.com/$(echo "$REPO_URL" | sed 's|https://github.com/||')/settings/actions/runners" >&2
      echo "   2. Click 'New self-hosted runner'" >&2
      echo "   3. Copy the new registration token" >&2
      echo "   4. Update GITHUB_RUNNER_TOKEN in your .env file" >&2
    fi
  fi
  
  exit $CONFIG_EXIT_CODE
fi

# Run the Runner
echo "✅ Runner Configured. Listening for jobs..."
./run.sh
