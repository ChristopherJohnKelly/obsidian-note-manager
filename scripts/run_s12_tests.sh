#!/bin/bash
set -e
set -o pipefail

# Run S12 tests: C1 (pure parser) + C2 (activity + fake provider)
# Neutralize project-wide coverage settings to allow narrow-subset runs
python3 -m pytest \
  --timeout=540 \
  --timeout-method=thread \
  -o addopts= \
  tests/unit/test_react_parser.py \
  tests/e2e/test_copilot_session_workflow.py
