#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/daily_python.sh"
export WEBTOON_TOTAL_TIMEOUT="${WEBTOON_TOTAL_TIMEOUT:-2400}"
export WEBTOON_STEP_TIMEOUT="${WEBTOON_STEP_TIMEOUT:-900}"
export WEBTOON_ART_TIMEOUT="${WEBTOON_ART_TIMEOUT:-600}"
# Classify only a fresh, intentional pending yield. Bare exit 75 (including
# lock contention), crashes, authentication failures and forced kills still fail.
OUTPUT="$(mktemp)"
trap 'rm -f "$OUTPUT"' EXIT
set +e
"$WEBTOON_RUNTIME" "$ROOT/scripts/daily_pipeline.py" --mode produce "$@" | tee "$OUTPUT"
RESULTS=("${PIPESTATUS[@]}")
set -e
if [[ "${RESULTS[1]}" != 0 ]]; then
  exit "${RESULTS[1]}"
fi
if [[ "${RESULTS[0]}" == 75 ]] &&
   grep -q '^\[YIELD\] pending; next producer run resumes: ' "$OUTPUT" &&
   ! grep -q '^\[FAIL\]' "$OUTPUT"; then
  echo '[DEFERRED] Production remains pending; not ready or published. Next scheduled run resumes.'
  exit 0
fi
exit "${RESULTS[0]}"
