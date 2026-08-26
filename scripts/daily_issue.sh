#!/usr/bin/env bash
# 오식 일일 발행기 — Claude Opus는 정전/각본, Codex는 래스터 패널/검증을 맡는다.
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

if [[ -d "episodes/$TODAY" ]]; then
  # A prior job may have been interrupted after Claude created only part of a
  # source episode. Preserve every existing file and ask Claude to finish only
  # the missing source artifacts before moving on to Codex.
  if [[ -f "episodes/$TODAY/SCENARIO.md" && -f "episodes/$TODAY/ART_PROMPTS.md" && -f "episodes/$TODAY/metadata.json" ]]; then
    echo "[RESUME] complete episode source detected; skipping Claude writing step."
  else
    STEP="claude-resume-source"
    echo '[STEP] Claude Opus: completing interrupted episode source'
    claude -p --model opus --effort high --max-turns 30 --max-budget-usd 5 \
      "episodes/$TODAY/ is an interrupted, partially written next episode of the continuous webtoon 오식(誤植). Read STORY_BIBLE.md, CLAUDE.md, every existing file inside episodes/$TODAY/, and the most recent complete earlier episode. Preserve existing source files unless a correction is essential for metadata consistency. Complete the missing required source artifacts: SCENARIO.md, ART_PROMPTS.md, metadata.json, and panels/README.md. metadata.json must contain 8~12 unique Korean panels with file/alt/dialogue and must match the scenario. Update STORY_BIBLE.md only with canon actually established by this episode. Do not create image panels, commit, deploy, or modify prior episodes. Finish the files within this single run and then stop." \
      --allowedTools "Read,Write,Edit,Bash" \
      --output-format json >"$LOG_DIR/claude-$TODAY.json"
  fi
else
  STEP="claude-writing"
  echo '[STEP] Claude Opus: writing scenario and canon update'
  claude -p --model opus --effort high --max-turns 30 --max-budget-usd 5 \
    "오늘은 $TODAY 입니다. 오식(誤植) 연속 웹툰의 다음 회차를 실제 파일로 발행하세요. 먼저 STORY_BIBLE.md 전체, CLAUDE.md, 그리고 episodes/ 아래 가장 최근 회차의 SCENARIO.md·ART_PROMPTS.md·metadata.json을 읽으세요. 새 episodes/$TODAY/{SCENARIO.md,ART_PROMPTS.md,metadata.json,panels/}을 만들고 8~12 패널의 연결된 한국어 회차를 작성하세요. 직전 화의 마지막 이미지에서 즉시 이어지고, 열린 실마리 하나를 진전시키며 새 단서 하나를 심고, 기억 비용·인물 상태·날짜 연속성을 지키세요. metadata의 패널마다 고유 file/alt/dialogue를 넣으세요. STORY_BIBLE.md의 현재 타임라인, 열린 실마리, 변경 기록을 업데이트하세요. 절대 기존 화를 수정하거나 이미지 파일을 만들지 마세요. 필요한 네 파일을 모두 만든 즉시 종료하세요; 불필요한 반복 검토는 하지 마세요." \
    --allowedTools "Read,Write,Edit,Bash" \
    --output-format json >"$LOG_DIR/claude-$TODAY.json"
fi

STEP="codex-raster-art"
echo '[STEP] Codex: generating full-image raster panels'
codex exec --sandbox danger-full-access \
  "Read STORY_BIBLE.md, CLAUDE.md, episodes/$TODAY/SCENARIO.md, episodes/$TODAY/ART_PROMPTS.md and episodes/$TODAY/metadata.json. Generate every metadata-referenced panel as an ACTUAL full-image 1024x1536 PNG or WebP in episodes/$TODAY/panels/. Do not create SVG, placeholders, HTML drawings, or text-only illustrations. Each panel must be a finished, cohesive Korean vertical webtoon image with character continuity and room for dialogue overlay; preserve the ink/paper/letterpress visual grammar, use red only for correction danger, and do not imitate a living artist. Update metadata file extensions if necessary. Then run python3 scripts/publish_daily.py and validate every referenced raster panel exists. Do not commit, deploy, or change prior episodes."

STEP="validate-publish"
echo '[STEP] publishing static outputs and validating Python'
python3 scripts/publish_daily.py
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

STEP="complete"
printf '[SUCCESS] published: https://openstory-ai-webtoon.vercel.app/episodes/%s\n' "$TODAY"
printf '[SUCCESS] log: %s\n' "$LOG_FILE"
