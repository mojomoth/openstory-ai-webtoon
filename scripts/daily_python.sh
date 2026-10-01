# Shared bootstrap. macOS system Python avoids broken package-manager expat builds.
if [[ -n "${WEBTOON_PYTHON:-}" ]]; then
  WEBTOON_RUNTIME="$WEBTOON_PYTHON"
elif [[ "$OSTYPE" == darwin* ]]; then
  WEBTOON_RUNTIME=/usr/bin/python3
else
  WEBTOON_RUNTIME="$(command -v python3)"
fi
# Bound the bootstrap probe too, before the Python supervisor is available.
# Job control gives each background job its own process group on macOS/Linux.
set -m
"$WEBTOON_RUNTIME" -c 'import pyexpat; import xml.etree.ElementTree as ET; ET.fromstring("<probe/>")' >/dev/null 2>&1 &
WEBTOON_PROBE_PID=$!
(sleep 5; kill -KILL -- "-$WEBTOON_PROBE_PID" 2>/dev/null || true) >/dev/null 2>&1 &
WEBTOON_PROBE_WATCHDOG=$!
WEBTOON_PROBE_RESULT=0
wait "$WEBTOON_PROBE_PID" 2>/dev/null || WEBTOON_PROBE_RESULT=$?
kill -KILL -- "-$WEBTOON_PROBE_WATCHDOG" 2>/dev/null || true
wait "$WEBTOON_PROBE_WATCHDOG" 2>/dev/null || true
set +m
if [[ "$WEBTOON_PROBE_RESULT" != 0 ]]; then
  echo '[FAIL] Python XML runtime probe failed; set WEBTOON_PYTHON to a working Python 3.' >&2
  exit 10
fi
