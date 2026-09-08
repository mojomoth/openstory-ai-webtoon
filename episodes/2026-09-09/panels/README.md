# 020화 패널 이미지

이 폴더에는 `../metadata.json`의 `panels[].file` 값과 같은 이름의 1024×1536 세로 래스터 패널(PNG 또는 WebP) 12장이 들어간다. 아트 지시는 `../ART_PROMPTS.md`를 따른다.

1. `01-the-hand-that-lifts-the-paper.png`
2. `02-no-impression-on-the-back.png`
3. `03-half-a-step-behind.png`
4. `04-the-shallow-letter.png`
5. `05-then-it-is-todays.png`
6. `06-the-question-she-never-asked.png`
7. `07-the-first-page.png`
8. `08-three-sounds-one-line.png`
9. `09-three-different-spacings.png`
10. `10-the-ledger-closes.png`
11. `11-both-ears.png`
12. `12-a-line-i-cannot-date.png`

12장이 모두 놓이기 전에는 `python3 scripts/publish_daily.py`가 자산 검사에서 중단된다.

## 검수 노트

- 01은 019화 `12-the-stroke-i-cannot-set.png`의 서리 시점 근경을 그대로 상속하며, 달라지는 것은 프레임 왼쪽에서 태오의 손이 들어와 종이의 한쪽 귀를 드는 것 하나뿐이다.
- 붉은 픽셀은 08의 이중선 한 줄과 12의 이중선 한 줄, 모두 두 점뿐이다.
- **12의 이중선은 낡은 선의 농도와 마른 가장자리로 그린다.** 젖은 선의 진한 농도와 젖은 가장자리를 쓰지 않는 것이 019화 획값의 결과이며, 언제 그어진 것인지 그림에서 알 수 없어야 한다.
- 황동 치환(서리의 시점 컷)은 01·08·12에 적용한다.
- 07에서 펴지는 것은 대장의 첫 장뿐이며 47쪽은 이 회차에 나오지 않는다. 대장이 스스로 움직이는 표현을 쓰지 않는다.
- 08에서 세 벌·세 음을 도해하지 않는다. 격자·치수선·화살표·음파·숫자를 넣지 않으며 이름은 판독되지 않는다.
- 01에서 왼손바닥 흉터 배열의 002화에 빠진 획 자리를 채우지 않는다.
- 11의 양쪽 이어폰은 시리즈에서 단 한 번의 예외다. 각성의 연출을 쓰지 않는다.
