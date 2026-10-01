#!/usr/bin/env bash
# Selection and publication share one deadline and durable pending target.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/daily_python.sh"
exec "$WEBTOON_RUNTIME" "$ROOT/scripts/daily_pipeline.py"
