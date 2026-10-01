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


## 일일 실행 제한 및 재시도

두 셸 진입점은 표준 라이브러리 Python supervisor를 사용합니다. macOS에서는
`/usr/bin/python3`, 다른 시스템에서는 PATH의 `python3`를 선택하며 시작할 때
`pyexpat`와 `xml.etree.ElementTree`의 XML 파싱을 검사합니다.

| 환경 변수 | 기본값 | 의미 |
| --- | --- | --- |
| `WEBTOON_PYTHON` | 위 플랫폼별 선택 | 사용할 Python 3 실행 파일의 명시적 경로 |
| `WEBTOON_TOTAL_TIMEOUT` | `3240` | 대상 선택부터 HTTP 검증까지 전체 제한(초) |
| `WEBTOON_STEP_TIMEOUT` | `600` | 개별 CLI 실행 제한(초), 남은 전체 시간 이내 |
| `WEBTOON_ART_TIMEOUT` | `300` | 패널 한 장의 Codex 실행 제한(초), 남은 전체 시간 이내 |

제한값은 0보다 크고 3240 이하인 유한한 숫자여야 합니다. 전체 watchdog의
종료 유예는 최대 2초이며 별도 Python 시작 검사도 5초로 제한되어 3300초보다 짧습니다. 시간 초과는 종료 코드 124로
보고하며 실행한 CLI의 자식 프로세스 그룹도 종료합니다. 동시 실행은 잠금으로 거부합니다.
GitHub/Vercel 비밀은 기존 `/Users/jy/.secrets`에서만 가져오며 CLI 인수와 오류 출력을
로그에 노출하지 않습니다.

`.run-logs/daily/pending-target`은 생성 전에 기록되고 전체 HTTP 검증 성공 후에만
삭제됩니다. 커밋 또는 push가 끝난 뒤 실패해도 다음 `run_daily.sh`가 같은 날짜를
재시도합니다. 다른 날짜를 명시하려면 먼저 보류된 회차를 완료해야 합니다. 커밋할 변경이
없어도 push와 배포는 계속합니다. 별도 Git index와 명시적인 발행 파일 목록을 사용하여
무관한 staged 파일을 커밋하지 않습니다.

내용이 있는 소스 파일과 모든 PNG/WebP가 유효하면 Codex 인증도 호출하지 않습니다.
PNG는 전체 청크 CRC, zlib 스트림, 스캔라인과 팔레트를 검사합니다. WebP는 실제
디코더(`sips`, 또는 `dwebp`)로 PNG로 변환해 검사하며 디코더가 없으면 거부합니다.
누락/손상 패널은 임시 작업 공간에서 한 장씩 생성하고 검증된 결과만 반영합니다.
중단된 아트 작업은 `.run-logs/daily/art/`에 남겨 다음 실행에서 소스 일치와 그림 유효성을
확인한 뒤 복구합니다. 유효한 기존 그림은 교체하지 않습니다. 소스 생성도 임시 공간에서 실행하며 기존 소스는
보존합니다. 불완전한 작업은 다음 실행에서 이어집니다.

배포 후 루트, 해당 회차, archive, RSS, sitemap 및 해당 회차의 모든 패널에 대해
HTTP 200, MIME, 로컬 파일과의 SHA-256 일치를 확인합니다. 검증 실패 시 보류 상태를
유지합니다. 회귀 테스트는 임시 실제 Git 저장소와 모의 Codex/push/Vercel/HTTP를 사용하며
실제 비밀 파일이나 외부 발행 서비스에 접근하지 않습니다.
