#!/usr/bin/env bash
# 오식 일일 발행기 — ChatGPT 구독 인증 Codex가 집필/정전/대사/패널을 맡는다.
# 실행 위치는 저장소 루트여야 한다. 비밀은 /Users/jy/.secrets에만 둔다.
# 모든 실행 출력은 .run-logs/daily/YYYY-MM-DD.log에 남긴다.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
TODAY="${1:-$(TZ=Asia/Seoul date +%F)}"
LOG_DIR="$ROOT/.run-logs/daily"
LOG_FILE="$LOG_DIR/$TODAY.log"
mkdir -p "$LOG_DIR"

# Cron의 요약 메시지가 잘려도, 각 하위 CLI의 stdout/stderr는 보존한다.
exec > >(tee -a "$LOG_FILE") 2>&1

STEP="preflight"
on_error() {
  local code=$?
  printf '\n[FAIL] time=%s step=%s exit=%s\n' "$(TZ=Asia/Seoul date '+%F %T %Z')" "$STEP" "$code"
  printf '[FAIL] full log: %s\n' "$LOG_FILE"
  exit "$code"
}
trap on_error ERR

printf '[START] time=%s date=%s repository=%s\n' "$(TZ=Asia/Seoul date '+%F %T %Z')" "$TODAY" "$ROOT"
git rev-parse --is-inside-work-tree >/dev/null
printf '[GIT] '; git status --short --branch

if [[ ! -f scripts/publish_daily.py || ! -f STORY_BIBLE.md || ! -f CLAUDE.md ]]; then
  echo '[FAIL] required project files are missing; refusing to generate or deploy.'
  exit 10
fi

validate_episode_source() {
  python3 - "$TODAY" <<'PY'
import json
import sys
from pathlib import Path

date = sys.argv[1]
root = Path('episodes') / date
required = ['SCENARIO.md', 'ART_PROMPTS.md', 'metadata.json', 'panels/README.md']
missing = [name for name in required if not (root / name).is_file()]
if missing:
    raise SystemExit(f'missing source artifacts: {missing}')
data = json.loads((root / 'metadata.json').read_text(encoding='utf-8'))
if data.get('date') != date:
    raise SystemExit('metadata date mismatch')
for key in ('episode', 'title', 'description', 'credits'):
    if not data.get(key):
        raise SystemExit(f'missing metadata field: {key}')
panels = data.get('panels', [])
if not isinstance(panels, list) or not 8 <= len(panels) <= 14:
    raise SystemExit('invalid panel count/type')
seen = set()
for index, panel in enumerate(panels, 1):
    if not all(panel.get(key) for key in ('file', 'alt', 'dialogue')):
        raise SystemExit(f'incomplete metadata panel {index}')
    path = Path(panel['file'])
    if (path.is_absolute() or '..' in path.parts or len(path.parts) != 2
            or path.parts[0] != 'panels' or path.suffix.lower() not in ('.png', '.webp')
            or str(path) in seen):
        raise SystemExit(f'invalid/duplicate panel path: {path}')
    seen.add(str(path))
    if not isinstance(panel['dialogue'], list) or not all(
            isinstance(line, str) and line.strip() for line in panel['dialogue']):
        raise SystemExit(f'invalid dialogue panel {index}')
print(f'[SOURCE] validated {date}: {len(panels)} panels')
PY
}

# Pin the official provider and subscription auth for EVERY CLI invocation.
# Ignore user provider overrides; never fall back to API-key billing.
run_codex() {
  local command="$1"
  shift
  local ignore_config=""
  if [[ "$command" == exec ]]; then ignore_config="--ignore-user-config"; fi
  env -u OPENAI_API_KEY -u OPENAI_BASE_URL -u CODEX_API_KEY codex "$command" \
    ${ignore_config:+"$ignore_config"} -c 'forced_login_method="chatgpt"' \
    -c 'model_provider="openai"' "$@"
}
STEP="codex-auth"
AUTH_STATUS="$(run_codex login status 2>&1)"
[[ "$AUTH_STATUS" == *"Logged in using ChatGPT"* ]] || {
  echo '[FAIL] ChatGPT subscription login is required; API-key fallback is forbidden.'
  exit 14
}

if [[ -d "episodes/$TODAY" ]] && validate_episode_source; then
  echo '[RESUME] valid episode source detected; skipping writing.'
else
  STEP="codex-writing"
  echo '[STEP] Codex (ChatGPT subscription): scenario, canon and final dialogue'
  run_codex exec --sandbox danger-full-access \
    "오늘은 $TODAY 입니다. 오식(誤植)의 다음 회차 집필·정전 변경·최종 대사를 담당하세요. STORY_BIBLE.md 전체, CLAUDE.md와 직전 3화의 SCENARIO.md·ART_PROMPTS.md·metadata.json을 읽으세요. episodes/$TODAY/에 기존 파일이 있으면 먼저 읽고 보존하며 누락 파일을 완성하세요. SCENARIO.md, ART_PROMPTS.md, metadata.json, panels/README.md 네 파일을 완성하세요. 8~12 패널의 연결된 한국어 회차를 쓰세요. 직전 화의 마지막 이미지에서 즉시 이어지고 열린 실마리 하나를 진전시키며 새 단서 하나를 심고, 기억 비용·인물 상태·날짜 연속성을 지키세요. metadata의 date는 $TODAY, 패널마다 고유 panels/NN.png 또는 .webp 경로와 한국어 alt, 비어 있지 않은 dialogue 배열을 넣으세요. 기존 metadata 스키마를 지키고 story credit는 Codex (ChatGPT subscription)로 기록하세요. STORY_BIBLE.md의 타임라인, 열린 실마리, 변경 기록에 이번 화의 정전만 반영하세요. 기존 회차·프로젝트 코드·설정·무관한 파일을 수정하지 마세요. 이미지 생성, 커밋, 배포를 하지 마세요. API 키, 유료 API, Claude를 사용하지 말고 현재 ChatGPT 인증만 사용하세요. 필요한 네 파일을 완성하면 종료하세요." \
    >"$LOG_DIR/codex-writing-$TODAY.log" 2>&1
fi

STEP="validate-source"
validate_episode_source

STEP="codex-raster-art"
echo '[STEP] Codex: generating full-image raster panels'
run_codex exec --sandbox danger-full-access \
  "Use only the existing ChatGPT subscription, never API keys or paid APIs. Do not invoke Claude. Do not modify project code, settings, or unrelated files. Read STORY_BIBLE.md, CLAUDE.md, episodes/$TODAY/SCENARIO.md, episodes/$TODAY/ART_PROMPTS.md and episodes/$TODAY/metadata.json. Generate every metadata-referenced panel as an ACTUAL full-image 1024x1536 PNG or WebP in episodes/$TODAY/panels/. Do not create SVG, placeholders, HTML drawings, or text-only illustrations. Each panel must be a finished, cohesive Korean vertical webtoon image with character continuity and room for dialogue overlay; preserve the ink/paper/letterpress visual grammar, use red only for correction danger, and do not imitate a living artist. Update metadata file extensions if necessary. Then run python3 scripts/publish_daily.py --through $TODAY and validate every referenced raster panel exists. Do not commit, deploy, or change prior episodes."

STEP="validate-publish"
echo '[STEP] publishing static outputs and validating Python'
python3 scripts/publish_daily.py --through "$TODAY"
python3 -m py_compile scripts/publish_daily.py

STEP="git-commit"
echo '[STEP] committing generated episode'
# Stage only the current episode and deterministic public outputs. Never sweep
# unrelated interrupted future episodes into the current publication commit.
git add -- STORY_BIBLE.md "episodes/$TODAY" episodes/*/index.html index.html archive.html rss.xml sitemap.xml
git diff --cached --quiet && { echo '[FAIL] no publishable changes after generation.'; exit 12; }
git commit -m "feat: publish episode for $TODAY"

STEP="github-push"
echo '[STEP] pushing GitHub commit'
source /Users/jy/.secrets
git push "https://x-access-token:${GITHUB_TOKEN}@github.com/mojomoth/openstory-ai-webtoon.git" main

STEP="vercel-deploy"
echo '[STEP] deploying Vercel production'
# `--yes` after vercel answers deployment prompts; `npx --yes` separately
# suppresses its first-run package-install prompt in non-interactive cron jobs.
npx --yes vercel --prod --yes --name openstory-ai-webtoon --token "$VERCEL_TOKEN"

STEP="verify-production"
echo '[STEP] verifying production HTTP responses'
for url in \
  "https://openstory-ai-webtoon.vercel.app/" \
  "https://openstory-ai-webtoon.vercel.app/episodes/$TODAY"; do
  status="$(curl --fail --silent --show-error --location --output /dev/null --write-out '%{http_code}' "$url")"
  [[ "$status" == "200" ]] || { echo "[FAIL] production verification status=$status url=$url"; exit 13; }
  echo "[HTTP] $status $url"
done

STEP="complete"
printf '[SUCCESS] published: https://openstory-ai-webtoon.vercel.app/episodes/%s\n' "$TODAY"
printf '[SUCCESS] log: %s\n' "$LOG_FILE"
