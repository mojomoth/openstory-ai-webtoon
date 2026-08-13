# 오식(誤植) — 을지로 교정소

서울 인쇄 골목을 무대로 한 오리지널 한국어 연속 일일 웹툰의 정적 저장소입니다. 모든 그림은 이 프로젝트를 위해 직접 제작한 SVG 작품이며 외부 이미지나 런타임 의존성을 쓰지 않습니다.

## 로컬 실행

```bash
python3 scripts/publish_daily.py
python3 -m http.server 8000
```

브라우저에서 `http://localhost:8000/`을 엽니다. 퍼블리셔는 `episodes/*/metadata.json`을 정렬해 루트 최신화, 회차 리더, `archive.html`, `rss.xml`, `sitemap.xml`을 결정론적으로 생성합니다.

## 구조

- `STORY_BIBLE.md` — 정전, 규칙, 인물, 60화 시즌 계획
- `CLAUDE.md` — Claude Opus 일일 연속성 워크플로
- `episodes/YYYY-MM-DD/` — 대본, 프롬프트, 메타데이터, 패널
- `assets/` — 공통 CSS/JS
- `scripts/publish_daily.py` — Python 표준 라이브러리 전용 퍼블리셔

## 새 회차 발행

이전 회차 폴더를 스키마 참고용으로 보고 새 날짜 폴더를 만듭니다. `metadata.json`과 패널 SVG를 작성한 뒤 퍼블리셔를 실행합니다. 생성 파일은 다시 실행해도 같은 바이트를 내야 합니다.

## 저작권/표시

글·설정·SVG 아트: **오식 프로젝트 오리지널 창작물**. 저장소의 그림은 외부 작품을 복제하지 않은 프로젝트 전용 벡터 일러스트입니다.

