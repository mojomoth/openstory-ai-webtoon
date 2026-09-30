# 오식(誤植) — 을지로 교정소

서울 인쇄 골목을 무대로 한 오리지널 한국어 연속 일일 웹툰의 정적 저장소입니다. 모든 그림은 이 프로젝트를 위해 생성한 풀컬러 PNG 웹툰 패널이며 외부 이미지나 런타임 의존성을 쓰지 않습니다.

## 로컬 실행

```bash
python3 scripts/publish_daily.py
python3 -m http.server 8000
```

브라우저에서 `http://localhost:8000/`을 엽니다. 퍼블리셔는 `episodes/*/metadata.json`을 정렬해 루트 최신화, 회차 리더, `archive.html`, `rss.xml`, `sitemap.xml`을 결정론적으로 생성합니다.

## 구조

- `STORY_BIBLE.md` — 정전, 규칙, 인물, 60화 시즌 계획
- `CLAUDE.md` — Codex CLI 일일 연속성 워크플로 (파일명은 기존 호환 유지)
- `scripts/run_daily.sh` — 중단 회차 또는 다음 날짜를 선택하는 일일 실행기
- `scripts/daily_issue.sh` — Codex 집필·정전·대사·래스터 아트 생성, 검증, 커밋·배포
- `episodes/YYYY-MM-DD/` — 대본, 프롬프트, 메타데이터, 패널
- `assets/` — 공통 CSS/JS
- `scripts/publish_daily.py` — Python 표준 라이브러리 전용 퍼블리셔

## 새 회차 발행

```bash
./scripts/run_daily.sh
# 특정 회차 복구: ./scripts/daily_issue.sh YYYY-MM-DD
```

집필·정전 변경·최종 대사·이미지 생성은 모두 **Codex CLI + ChatGPT 구독 OAuth 로그인**을 사용합니다. `codex login status`가 `Logged in using ChatGPT`여야 하며 API 키 인증은 거부합니다. Claude는 호출하지 않습니다. GitHub/Vercel 배포에는 기존 인증을 사용합니다.

실행기는 중단된 회차를 우선 복구하고, 없으면 마지막 회차의 다음 날짜를 발행합니다 (서울 날짜 상한). 한 번 실행할 때 한 회차만 발행하므로 밀린 날짜를 건너뛰지 않습니다. 로그는 `.run-logs/daily/`에 보관합니다. 기존 cron 래퍼도 이 실행기에 위임합니다.

이전 회차 폴더를 스키마 참고용으로 보고 `metadata.json`과 풀컬러 PNG/WebP 패널을 완성한 뒤 퍼블리셔를 실행합니다. 생성 HTML은 다시 실행해도 같은 바이트를 내야 합니다. 회귀 검사는 `python3 -m unittest discover -s tests -v`로 실행합니다.

## 저작권/표시

글·설정·래스터 웹툰 아트: **오식 프로젝트 오리지널 창작물**. 저장소의 그림은 외부 작품을 복제하지 않은 프로젝트 전용 풀컬러 웹툰 이미지입니다.

