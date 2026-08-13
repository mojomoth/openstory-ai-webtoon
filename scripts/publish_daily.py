#!/usr/bin/env python3
"""오식 정적 사이트 결정론적 퍼블리셔. Python 표준 라이브러리만 사용한다."""

from __future__ import annotations

import html
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
EPISODES = ROOT / "episodes"
SITE_URL = "https://misprint-euljiro.example"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def load_episodes() -> list[dict]:
    found: list[dict] = []
    for meta_path in sorted(EPISODES.glob("*/metadata.json")):
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        required = {"episode", "title", "date", "description", "panels"}
        missing = required - data.keys()
        if missing:
            raise ValueError(f"{meta_path}: 필수 키 누락 {sorted(missing)}")
        folder = meta_path.parent
        if folder.name != data["date"]:
            raise ValueError(f"{meta_path}: 폴더 날짜와 metadata 날짜 불일치")
        if not 8 <= len(data["panels"]) <= 14:
            raise ValueError(f"{meta_path}: 패널은 8–14개여야 함")
        for panel in data["panels"]:
            if not panel.get("alt") or not panel.get("dialogue"):
                raise ValueError(f"{meta_path}: 모든 패널에 alt와 dialogue 필요")
            asset = folder / panel["file"]
            if not asset.is_file():
                raise FileNotFoundError(asset)
        data["_folder"] = folder
        data["_url"] = f"episodes/{data['date']}/index.html"
        found.append(data)
    if not found:
        raise RuntimeError("발행할 에피소드가 없습니다.")
    return sorted(found, key=lambda item: (item["date"], item["episode"]))


def shell(title: str, body: str, *, prefix: str = "") -> str:
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#111315">
<meta name="description" content="서울 인쇄 골목의 오컬트 미스터리 웹툰, 오식 — 을지로 교정소.">
<title>{esc(title)} · 오식(誤植)</title>
<link rel="alternate" type="application/rss+xml" title="오식 RSS" href="{prefix}rss.xml">
<link rel="stylesheet" href="{prefix}assets/style.css">
</head><body>
<a class="skip-link" href="#main">본문으로 건너뛰기</a><div class="progress" aria-hidden="true"><span></span></div>
<header class="site-head"><a class="brand" href="{prefix}index.html">오식(誤植) <small>— 을지로 교정소</small></a><nav class="site-nav" aria-label="주요 메뉴"><a href="{prefix}index.html">최신화</a><a href="{prefix}archive.html">기록 보관소</a></nav></header>
{body}
<footer class="site-foot"><p>글·그림 © 2026 오식 프로젝트. 모든 패널은 이 작품을 위해 직접 제작한 오리지널 SVG 아트입니다.</p><p>외부 이미지와 추적 스크립트를 사용하지 않습니다. <a href="{prefix}rss.xml">RSS</a></p></footer>
<script src="{prefix}assets/site.js" defer></script></body></html>
"""


def panel_html(panel: dict, number: int) -> str:
    dialogue = "".join(f"<p>{esc(line)}</p>" for line in panel["dialogue"])
    return f"""<figure class="panel">
<img src="{esc(panel['file'])}" alt="{esc(panel['alt'])}" width="720" height="1080" loading="{'eager' if number == 1 else 'lazy'}" decoding="async">
<figcaption><span class="panel-no">PANEL {number:02d}</span>{dialogue}</figcaption></figure>"""


def render_episode(ep: dict, previous: dict | None, following: dict | None) -> str:
    panels = "\n".join(panel_html(panel, i) for i, panel in enumerate(ep["panels"], 1))
    if following:
        next_markup = f'<a class="next-card" href="../../{following["_url"]}"><small>다음 화</small><strong>{following["episode"]:03d}화 〈{esc(following["title"]) }〉</strong></a>'
    else:
        announced = ep.get("next_episode", {})
        label = f'{announced.get("number", ep["episode"] + 1):03d}화 〈{esc(announced.get("title", "계속"))}〉 · {esc(announced.get("date", "준비 중"))}'
        next_markup = f'<div class="next-card" aria-disabled="true"><small>다음 화 예고</small><strong>{label}</strong></div>'
    previous_markup = ""
    if previous:
        previous_markup = f'<p><a href="../../{previous["_url"]}">← {previous["episode"]:03d}화로</a></p>'
    body = f"""<main id="main">
<header class="episode-head"><p class="episode-number">EPISODE {ep['episode']:03d}</p><h1>{esc(ep['title'])}</h1>
<div class="episode-meta"><time datetime="{esc(ep['date'])}">{esc(ep['date'])}</time><span>{esc(ep.get('content_rating', '15세 이상'))}</span><span>약 {esc(ep.get('reading_minutes', 6))}분</span></div>
<p class="episode-summary">{esc(ep['description'])}</p>{previous_markup}</header>
<article class="comic" aria-label="{esc(ep['episode'])}화 세로 웹툰">{panels}</article>
<section class="afterword" aria-labelledby="credit"><h2 id="credit">제작 기록</h2><p class="credit-stamp">글: {esc(ep['credits']['story'])}<br>그림: {esc(ep['credits']['art'])}<br>본 회차의 그림은 외부 이미지를 사용하지 않은 프로젝트 오리지널 작품입니다.</p>{next_markup}</section>
</main>"""
    return shell(f"{ep['episode']:03d}화 {ep['title']}", body, prefix="../../")


def render_home(latest: dict) -> str:
    body = f"""<main id="main"><section class="hero"><div class="hero-copy"><p class="eyebrow">매일 00:13 · 연속 일일 웹툰</p>
<h1>서울의 이름에<br><em>붉은 선</em>이 그어졌다.</h1><p class="dek">서울은 보이지 않는 인쇄판에서 매일 다시 찍힌다. 붉은 교정선을 보는 한서리는 지워진 오빠의 이름을 되찾기 위해 기억을 활자로 내놓는다.</p>
<a class="read-cta" href="{latest['_url']}">{latest['episode']:03d}화 〈{esc(latest['title'])}〉 읽기 →</a></div></section>
<section class="archive" aria-labelledby="latest"><p class="eyebrow">LATEST IMPRESSION</p><h2 id="latest">오늘 찍힌 이야기</h2><ul class="archive-list"><li class="archive-item"><a href="{latest['_url']}"><span class="num">{latest['episode']:03d}</span><strong>{esc(latest['title'])}</strong><time datetime="{latest['date']}">{latest['date']}</time></a></li></ul></section></main>"""
    return shell("최신화", body)


def render_archive(episodes: list[dict]) -> str:
    items = "".join(f'<li class="archive-item"><a href="{ep["_url"]}"><span class="num">{ep["episode"]:03d}</span><strong>{esc(ep["title"])}</strong><time datetime="{ep["date"]}">{ep["date"]}</time></a></li>' for ep in reversed(episodes))
    body = f'<main id="main" class="archive"><p class="eyebrow">CORRECTION REGISTER</p><h1>기록 보관소</h1><p>지워지기 전에, 모든 이름을 기록한다.</p><ol class="archive-list">{items}</ol></main>'
    return shell("기록 보관소", body)


def render_rss(episodes: list[dict]) -> str:
    items = []
    for ep in reversed(episodes[-20:]):
        url = f"{SITE_URL}/{ep['_url']}"
        item_title = f"{ep['episode']:03d}화 {ep['title']}"
        items.append(f"<item><title>{esc(item_title)}</title><link>{url}</link><guid>{url}</guid><pubDate>{ep['date']}T00:13:00+09:00</pubDate><description>{esc(ep['description'])}</description></item>")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>오식(誤植) — 을지로 교정소</title><link>{SITE_URL}/</link><description>서울 인쇄 골목의 연속 일일 웹툰</description>{"".join(items)}</channel></rss>\n'


def render_sitemap(episodes: list[dict]) -> str:
    pages = [("", episodes[-1]["date"]), ("archive.html", episodes[-1]["date"])] + [(ep["_url"], ep["date"]) for ep in episodes]
    urls = "".join(f"<url><loc>{SITE_URL}/{quote(path)}</loc><lastmod>{date}</lastmod></url>" for path, date in pages)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n'


def write(path: Path, content: str) -> None:
    # str content is constructed with LF line endings; Path.write_text has no newline argument on Python 3.11.
    path.write_text(content, encoding="utf-8")


def main() -> None:
    episodes = load_episodes()
    for i, ep in enumerate(episodes):
        previous = episodes[i - 1] if i else None
        following = episodes[i + 1] if i + 1 < len(episodes) else None
        write(ep["_folder"] / "index.html", render_episode(ep, previous, following))
    write(ROOT / "index.html", render_home(episodes[-1]))
    write(ROOT / "archive.html", render_archive(episodes))
    write(ROOT / "rss.xml", render_rss(episodes))
    write(ROOT / "sitemap.xml", render_sitemap(episodes))
    print(f"발행 완료: {len(episodes)}화 / 최신 {episodes[-1]['date']} / 패널 {sum(len(e['panels']) for e in episodes)}개")


if __name__ == "__main__":
    main()
