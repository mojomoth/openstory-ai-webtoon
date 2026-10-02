#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/daily_python.sh"
export WEBTOON_TOTAL_TIMEOUT="${WEBTOON_TOTAL_TIMEOUT:-2400}"
export WEBTOON_STEP_TIMEOUT="${WEBTOON_STEP_TIMEOUT:-900}"
export WEBTOON_ART_TIMEOUT="${WEBTOON_ART_TIMEOUT:-600}"
exec "$WEBTOON_RUNTIME" "$ROOT/scripts/daily_pipeline.py" --mode produce "$@"
