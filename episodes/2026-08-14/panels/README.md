# 002화 패널 이미지

이 폴더에는 `../metadata.json`의 `panels[].file` 값과 같은 이름의 1024×1536 세로 래스터 패널(PNG 또는 WebP) 10장이 들어간다. 아트 지시는 `../ART_PROMPTS.md`를 따른다.

1. `01-hand-off-page.png`
2. `02-wet-receipt.png`
3. `03-empty-type-slot.png`
4. `04-four-strokes.png`
5. `05-palm-array.png`
6. `06-red-ink-thread.png`
7. `07-first-correction.png`
8. `08-doyun-returns.png`
9. `09-no-such-address.png`
10. `10-silent-laugh.png`

10장이 모두 놓이기 전에는 `python3 scripts/publish_daily.py`가 자산 검사에서 중단된다.
