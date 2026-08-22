# 005화 패널 이미지

이 폴더에는 `../metadata.json`의 `panels[].file` 값과 같은 이름의 1024×1536 세로 래스터 패널(PNG 또는 WebP) 11장이 들어간다. 아트 지시는 `../ART_PROMPTS.md`를 따른다.

1. `01-door-crack.png`
2. `02-silent-morning.png`
3. `03-dry-roller.png`
4. `04-two-lunchboxes.png`
5. `05-faceless-photo.png`
6. `06-empty-ingot-shelf.png`
7. `07-inkless-seal.png`
8. `08-half-melted-stroke.png`
9. `09-shortened-name.png`
10. `10-turned-chopsticks.png`
11. `11-third-box.png`

11장이 모두 놓이기 전에는 `python3 scripts/publish_daily.py`가 자산 검사에서 중단된다.

- `01`은 004화 `11-returned-type.png` 상단 구석의 문틈 밝은 선을 반대편에서 잇는다. 선의 각도와 굵기를 바꾸지 않는다.
- `04`와 `11`은 같은 시야의 전후 컷이다. 광선 각도, 보자기 주름, 상판 흠집, 앞의 두 도시락 위치를 화소 단위로 동일하게 두고 세 번째만 추가한다.
- `07`의 눌린 도장 자국은 004화 `07-unseen-sheet.png`의 눌린 글자 자국과 같은 브러시·같은 광택으로 그린다.
- `05`에는 붉은색을 넣지 않는다. 이 부재가 이 회차의 핵심 정보다.
