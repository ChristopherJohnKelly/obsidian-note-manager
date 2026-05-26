#!/bin/bash
set -e
set -o pipefail

python3 -m pytest tests/s15/test_readme_images.py \
  --timeout=540 \
  --timeout-method=thread \
  -o addopts=
