#!/usr/bin/env bash
set -e
set -o pipefail

# Test runner for S10 C2: NightWatchmanWorkflow happy-path E2E
# Ensures coverage addopts don't interfere with narrow-subset runs
# Includes pytest-timeout with thread method for diagnostic stack traces on deadlock

pytest \
  --timeout=540 \
  --timeout-method=thread \
  -o addopts= \
  tests/e2e/test_night_watchman_workflow.py
