#!/usr/bin/env bash
set -euo pipefail
cd deploy/cloudflare
# The Python module invocation avoids depending on the pip user scripts PATH.
python -m uv run --python 3.13 --locked pywrangler deploy
