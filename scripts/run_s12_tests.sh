#!/bin/bash
set -e
set -o pipefail

# Run S12 tests: C3 (CopilotSessionWorkflow single-turn)
# Neutralize project-wide coverage settings to allow narrow-subset runs
python3 -m pytest \
  --timeout=540 \
  --timeout-method=thread \
  -o addopts= \
  tests/e2e/test_copilot_session_workflow.py
