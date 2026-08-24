# 006화 패널 이미지

이 폴더에는 `../metadata.json`의 `panels[].file` 값과 같은 이름의 1024×1536 세로 래스터 패널(PNG 또는 WebP) 11장이 들어간다. 아트 지시는 `../ART_PROMPTS.md`를 따른다.

1. `01-third-on-the-sill.png`
2. `02-out-under-the-shutter.png`
3. `03-girl-who-listens.png`
4. `04-not-a-la-today.png`
5. `05-nothing-left-at-the-end.png`
6. `06-name-in-sound.png`
7. `07-alley-of-pitches.png`
8. `08-no-sound-here.png`
9. `09-reversed-knot.png`
10. `10-pressed-nameplate.png`
11. `11-last-syllable.png`

11장이 모두 놓이기 전에는 `python3 scripts/publish_daily.py`가 자산 검사에서 중단된다.

- `01`은 005화 `11-third-box.png`의 작업대 탑숏을 그대로 상속한다. 광선 각도, 보자기 주름, 상판 흠집, 도시락 세 개의 크기·색·재질을 바꾸지 않고 손의 동작만 이어 붙인다.
- `05`와 `10`의 눌린 자국은 004화 `07-unseen-sheet.png`, 005화 `07-inkless-seal.png`와 같은 브러시·같은 광택으로 그린다. 네 자국이 같은 계열이어야 한다.
- `08`에는 붉은색을 넣지 않는다. 이 부재가 이 회차의 핵심 정보이며, 이 집의 정체가 밝혀지는 회차까지 유지한다.
- `09`의 보자기 천은 `01`과 같은 패턴이어야 하고 접힌 방향과 매듭 방향만 반대다.
- `11`의 셔터 밑 틈 안쪽에는 형상도 빛도 넣지 않는다. 003화의 폭 이 미터짜리 틈과 시각적으로 구별되게 낮고 좁게, 황동빛 없이 그린다.
