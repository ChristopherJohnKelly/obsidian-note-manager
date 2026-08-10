#!/usr/bin/env bash
set -e
set -o pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

python3 -m pytest \
  -o addopts= \
  --timeout=540 \
  --timeout-method=thread \
  tests/ci/
