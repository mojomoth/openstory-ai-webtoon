# 019화 패널 이미지

이 폴더에는 `../metadata.json`의 `panels[].file` 값과 같은 이름의 1024×1536 세로 래스터 패널(PNG 또는 WebP) 12장이 들어간다. 아트 지시는 `../ART_PROMPTS.md`를 따른다.

1. `01-the-door-without-an-answer.png`
2. `02-the-hand-that-opens.png`
3. `03-the-shutter-at-shoulder-height.png`
4. `04-cast-in-the-night.png`
5. `05-forty-years-no-people.png`
6. `06-setting-around-the-gap.png`
7. `07-the-price-goes-first.png`
8. `08-three-times-and-one-more.png`
9. `09-two-spans.png`
10. `10-the-breath-that-laughed.png`
11. `11-the-place-that-did-not-stay.png`
12. `12-the-stroke-i-cannot-set.png`

12장이 모두 놓이기 전에는 `python3 scripts/publish_daily.py`가 자산 검사에서 중단된다.

## 검수 노트

- 01은 018화 `12-friday-and-four-thirteen.png`의 수평 중경을 그대로 상속하며, 달라지는 것은 서리가 방문증 줄을 벗어 결재인 옆에 내려놓는 것 하나뿐이다.
- 붉은 픽셀은 04의 식어 가는 도가니 안쪽 붉은 기 한 점뿐이며, 12에는 붉은 픽셀이 하나도 없다.
- 황동 치환(서리의 시점 컷)은 03·06·09·12에 적용한다.
- 09의 벌어진 자리 안쪽에는 사람·손·활자·풍경·글자를 그리지 않는다. 진입은 이 회차의 사건이 아니다.
- 06·12에서 왼손바닥 흉터 배열의 002화에 빠진 획 자리를 채우지 않는다.
