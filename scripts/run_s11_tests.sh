#!/bin/bash
set -e
set -o pipefail

pytest \
  --timeout=540 \
  --timeout-method=thread \
  --no-cov \
  tests/e2e/test_filer_ingestion_workflow.py
