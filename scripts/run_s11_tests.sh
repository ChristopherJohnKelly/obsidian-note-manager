#!/bin/bash
set -e
set -o pipefail

python3 -m pytest \
  tests/e2e/test_filer_ingestion_workflow.py \
  --timeout=540 \
  --timeout-method=thread \
  -o addopts= \
  "$@"
