#!/usr/bin/env bash
set -e
set -o pipefail

python3 -m pytest \
    -o addopts= \
    --timeout=540 \
    --timeout-method=thread \
    tests/unit/test_client_wiring.py
