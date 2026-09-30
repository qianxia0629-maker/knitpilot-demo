#!/usr/bin/env bash
set -euo pipefail
export NEXT_TELEMETRY_DISABLED=1
npm --prefix apps/web ci
npm --prefix apps/web run build
python scripts/prepare_cloudflare.py
# Workers Builds includes pip, but does not promise a preinstalled uv executable.
python -m pip install --user 'uv>=0.9.8,<1'
