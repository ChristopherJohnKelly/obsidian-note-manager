#!/bin/bash
set -e
set -o pipefail

# Run S12 cycle tests (react_parser unit tests)
# Neutralize project-wide pytest addopts (coverage flags) for narrow subset
python -m pytest \
  tests/unit/test_react_parser.py \
  --timeout=540 \
  --timeout-method=thread \
  -o addopts=
