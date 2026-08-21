# 004화 패널 이미지

이 폴더에는 `../metadata.json`의 `panels[].file` 값과 같은 이름의 1024×1536 세로 래스터 패널(PNG 또는 WebP) 11장이 들어간다. 아트 지시는 `../ART_PROMPTS.md`를 따른다.

1. `01-sealed-gap.png`
2. `02-fourth-sound.png`
3. `03-do-not-tear.png`
4. `04-scratched-sign.png`
5. `05-composing-bench.png`
6. `06-three-sheets.png`
7. `07-unseen-sheet.png`
8. `08-never-twice.png`
9. `09-worn-fingertip.png`
10. `10-empty-slots.png`
11. `11-returned-type.png`

11장이 모두 놓이기 전에는 `python3 scripts/publish_daily.py`가 자산 검사에서 중단된다.

- `01`은 003화 `11-fingerless-hand.png`의 레이아웃을 상속한다. 담벼락 먹 면의 비율과 틈의 좌우 위치를 바꾸지 않는다.
- `10`의 빈 칸 열세 개는 003화 `06-missing-stroke.png`의 점 열세 개와 동일한 좌표계로 배치한다.
