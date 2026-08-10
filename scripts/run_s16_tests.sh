#!/usr/bin/env bash
set -euo pipefail

python3 -m pytest \
  -o addopts= \
  --timeout=540 \
  --timeout-method=thread \
  tests/ci/test_docker_compose_prod.py
