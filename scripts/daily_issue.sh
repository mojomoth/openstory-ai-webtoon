#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/daily_python.sh"
exec "$WEBTOON_RUNTIME" "$ROOT/scripts/daily_pipeline.py" "${1:-}"
