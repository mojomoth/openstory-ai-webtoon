#!/usr/bin/env bash
# 오식 일일 발행기 — Claude Opus는 정전/각본, Codex는 SVG 패널/검증을 맡는다.
# 실행 위치는 저장소 루트여야 한다. 비밀은 /Users/jy/.secrets에만 둔다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
TODAY="${1:-$(TZ=Asia/Seoul date +%F)}"
YESTERDAY="$(TZ=Asia/Seoul date -v-1d +%F)"

if [[ -d "episodes/$TODAY" ]]; then
  echo "이미 $TODAY 회차가 존재합니다. 중복 발행하지 않습니다." >&2
  exit 2
fi

# 1. Claude Opus: 정전과 직전 회차를 읽고 다음의 연결된 이야기를 작성한다.
claude -p --model opus --effort high --max-turns 18 --max-budget-usd 5 \
  "오늘은 $TODAY 입니다. 오식(誤植) 연속 웹툰의 다음 회차를 실제 파일로 발행하세요. 먼저 STORY_BIBLE.md 전체, CLAUDE.md, 그리고 episodes/ 아래 가장 최근 회차의 SCENARIO.md·ART_PROMPTS.md·metadata.json을 읽으세요. 새 episodes/$TODAY/{SCENARIO.md,ART_PROMPTS.md,metadata.json,panels/}을 만들고 8~12 패널의 연결된 한국어 회차를 작성하세요. 직전 화의 마지막 이미지에서 즉시 이어지고, 열린 실마리 하나를 진전시키며 새 단서 하나를 심고, 기억 비용·인물 상태·날짜 연속성을 지키세요. metadata의 패널마다 고유 file/alt/dialogue를 넣으세요. STORY_BIBLE.md의 현재 타임라인, 열린 실마리, 변경 기록을 업데이트하세요. 절대 기존 화를 수정하거나 이미지 파일을 만들지 마세요." \
  --allowedTools "Read,Write,Edit,Bash" \
  --output-format json >/tmp/osik-claude-$TODAY.json

# 2. Codex: Claude의 패널 지시를 읽고, 같은 시각 언어의 실제 SVG 벡터 패널을 만든다.
codex exec --sandbox danger-full-access \
  "Read STORY_BIBLE.md, CLAUDE.md, episodes/$TODAY/SCENARIO.md, ART_PROMPTS.md and metadata.json. Create every metadata-referenced SVG file in episodes/$TODAY/panels/. Make 8–12 cohesive original 720x1080 vertical SVG illustrations, with Korean accessibility title/desc. Preserve the established ink/paper/letterpress visual grammar, use red only for correction danger, and do not use external images or imitate a living artist. Then run python3 scripts/publish_daily.py and validate every listed panel exists. Do not commit, deploy, or change prior episodes." 

# 3. Deterministic public outputs, GitHub grass, production Vercel deployment.
python3 scripts/publish_daily.py
python3 -m py_compile scripts/publish_daily.py
git add -A
git diff --cached --quiet && { echo "발행할 변경 사항이 없습니다." >&2; exit 3; }
git commit -m "feat: publish episode for $TODAY"
source /Users/jy/.secrets
git push "https://x-access-token:${GITHUB_TOKEN}@github.com/mojomoth/openstory-ai-webtoon.git" main
npx vercel --prod --yes --token "$VERCEL_TOKEN"
echo "발행 완료: https://openstory-ai-webtoon.vercel.app/episodes/$TODAY"
