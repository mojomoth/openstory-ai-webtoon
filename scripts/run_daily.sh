#!/usr/bin/env bash
# Durable, no-agent daily runner: avoids consuming the Hermes orchestration model.
set -Eeuo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT"

TARGET="$(TZ=Asia/Seoul python3 - <<'PY'
import datetime as dt
import json
import subprocess
from pathlib import Path

root = Path.cwd()
today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
episodes = root / 'episodes'
entries = []
for folder in sorted(episodes.iterdir()):
    if not folder.is_dir():
        continue
    try:
        date = dt.date.fromisoformat(folder.name)
    except ValueError:
        continue
    if date > today:
        continue
    meta = folder / 'metadata.json'
    tracked = False
    if meta.is_file():
        tracked = subprocess.run(
            ['git', 'ls-files', '--error-unmatch', str(meta)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
    # Prioritize any interrupted or generated-but-unpublished episode.
    if not meta.is_file() or not tracked:
        print(folder.name)
        raise SystemExit
    data = json.loads(meta.read_text(encoding='utf-8'))
    if any(not (folder / panel['file']).is_file() for panel in data.get('panels', [])):
        print(folder.name)
        raise SystemExit
    entries.append(date)

base = max(entries) if entries else today - dt.timedelta(days=1)
target = min(base + dt.timedelta(days=1), today)
print(target.isoformat())
PY
)"

printf '[RUNNER] target=%s repository=%s\n' "$TARGET" "$PROJECT"
if ./scripts/daily_issue.sh "$TARGET"; then
  :
else
  code=$?
  echo "[RUNNER] failed target=$TARGET exit=$code"
  echo "[RUNNER] log tail:"
  tail -80 ".run-logs/daily/$TARGET.log" 2>/dev/null || true
  exit "$code"
fi

git fetch origin >/dev/null 2>&1 || true
printf '[RUNNER] commit='; git log -1 --format='%h %s'
printf '[RUNNER] episode=https://openstory-ai-webtoon.vercel.app/episodes/%s\n' "$TARGET"
