#!/usr/bin/env bash
set -e
set -o pipefail

python3 -m pytest \
    -o addopts= \
    --timeout=540 \
    --timeout-method=thread \
    tests/e2e/test_night_watchman_write_back.py
