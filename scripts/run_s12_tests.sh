#!/bin/bash
set -e
set -o pipefail

# Run S12 C1 tests: pure parser unit tests
# Neutralize project-wide coverage settings to allow narrow-subset runs
python3 -m pytest \
  --timeout=540 \
  --timeout-method=thread \
  -o addopts= \
  tests/unit/test_react_parser.py
