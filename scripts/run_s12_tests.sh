#!/bin/bash
set -e
set -o pipefail

# Run S12 cycle C2 tests (copilot_session E2E test)
# Neutralize project-wide pytest addopts (coverage flags) for narrow subset
python3 -m pytest \
  tests/e2e/test_copilot_session_workflow.py \
  --timeout=540 \
  --timeout-method=thread \
  -o addopts=
