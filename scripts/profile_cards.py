"""Generate self-contained profile SVGs with Python's standard library.

Only public, owned repositories are counted. Language bytes exclude forks.
An API failure stops generation before any existing cards are overwritten.
"""

import base64
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


USERNAME = "MUSESTAR-Official"
ASSETS = Path(__file__).resolve().parents[1] / "assets"
OUTPUT = ASSETS / "profile"
THEMES = {
    "dark": {"bg": "#17151e", "surface": "#211e2a", "raised": "#2a2634",
             "text": "#f2eff9", "muted": "#a09aad", "accent": "#a78bfa",
             "line": "#453956", "soft": "#332a46"},
    "light": {"bg": "#f3f1f8", "surface": "#ffffff", "raised": "#eae6f3",
              "text": "#292330", "muted": "#766e84", "accent": "#7651d8",
              "line": "#dcd3ed", "soft": "#eae3f7"},
}
COLORS = ["#a78bfa", "#c993ed", "#e0a0c8", "#8da8ef", "#79c7bf", "#c9b785"]


def api(path):
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "MUSESTAR-profile-cards",
               "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(3):
        try:
            request = Request("https://api.github.com" + path, headers=headers)
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def collect():
    profile = api(f"/users/{USERNAME}")
    repos = []
    page = 1
    while True:
        batch = api(f"/users/{USERNAME}/repos?type=owner&per_page=100&page={page}")
        repos.extend(repo for repo in batch if not repo["private"]
                     and repo["owner"]["login"].casefold() == USERNAME.casefold())
        if len(batch) < 100:
            break
        page += 1
    languages = Counter()
    unavailable = 0
    for repo in repos:
        if not repo["fork"]:
            try:
                languages.update(api(f"/repos/{USERNAME}/{quote(repo['name'], safe='')}/languages"))
            except HTTPError as error:
                # Listed repositories can be blocked by GitHub; disclose omissions.
                if error.code != 451:
                    raise
                unavailable += 1
    return {
        "repos": len(repos),
        "stars": sum(repo["stargazers_count"] for repo in repos),
        "forks": sum(repo["forks_count"] for repo in repos),
        "followers": profile["followers"],
        "languages": dict(languages.most_common()),
        "unavailable": unavailable,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def text(x, y, value, size=14, fill="text", weight=400, extra=""):
    return (f'<text x="{x}" y="{y}" font-size="{size}" class="{fill}" '
            f'font-weight="{weight}" {extra}>{escape(str(value))}</text>')


def star(x, y, size=24, color="accent", opacity=1):
    return (f'<g transform="translate({x} {y}) scale({size / 24})" '
            f'class="{color}" opacity="{opacity}"><path '
            'd="M12 2 21 18H3ZM12 22 3 6h18Z" fill="none" '
            'stroke="currentColor" stroke-width="1"/></g>')


def svg(width, height, title, description, body, theme):
    palette = THEMES[theme]
    classes = "".join(f'.{name}{{fill:{color};color:{color}}}'
                      for name, color in palette.items())
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>
<defs>
  <linearGradient id="wash" x1="0" y1="1" x2="1" y2="0"><stop stop-color="{palette['surface']}"/><stop offset="1" stop-color="{palette['soft']}"/></linearGradient>
  <linearGradient id="brand"><stop stop-color="{palette['accent']}"/><stop offset="1" stop-color="#d69ded"/></linearGradient>
  <clipPath id="card"><rect x="1" y="1" width="{width-2}" height="{height-2}" rx="24"/></clipPath>
</defs>
<style>text{{font-family:'Segoe UI','Microsoft YaHei','Noto Sans CJK SC',sans-serif}}{classes}</style>
<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="24" fill="{palette['surface']}" stroke="{palette['line']}"/>
{body}
</svg>
'''


def brand_image(name, x, y, width, height):
    # Inline the original PNG so the SVG works as a GitHub README image.
    encoded = base64.b64encode((ASSETS / "brand" / name).read_bytes()).decode("ascii")
    return (f'<image x="{x}" y="{y}" width="{width}" height="{height}" '
            f'href="data:image/png;base64,{encoded}"/>')


def hero(theme):
    body = '''<g clip-path="url(#card)">
<rect x="1" y="1" width="958" height="262" fill="url(#wash)"/>
<g fill="none" stroke="currentColor" class="accent" opacity=".13">
<circle cx="800" cy="128" r="100" fill="none"/><circle cx="800" cy="128" r="154" fill="none"/><circle cx="800" cy="128" r="210" fill="none"/>
</g>
<g transform="translate(546 123) scale(.35)" class="accent" opacity=".2">
<path d="M120 12 214 174H26ZM120 228 26 66h188Z" fill="none" stroke="currentColor" stroke-width="2"/>
</g></g>'''
    body += '<rect x="56" y="32" width="177" height="28" rx="14" class="soft"/>'
    body += '<circle cx="71" cy="46" r="3" class="accent"/>'
    body += text(83, 50, "WELCOME TO MY ORBIT", 10, "accent", 600, 'letter-spacing="1.1"')
    body += brand_image("musestar-wordmark.png", 44, 77, 460, 92)
    body += text(56, 207, "缪斯星 / 始于一份热爱", 23, "accent", 500)
    body += brand_image("musestar-symbol.png", 736, 64, 128, 128)
    # This point sits on the outer orbit, clear of the central brand symbol.
    body += '<circle cx="938" cy="196" r="4" class="accent"/>'
    body += text(916, 236, "MUSESTAR.CC  ↗", 11, "muted", 500, 'text-anchor="end" letter-spacing="1"')
    return svg(960, 264, "MUSESTAR · 缪斯星", "MUSESTAR 原版 Logo · 缪斯星 / 始于一份热爱", body, theme)


def stats(data, theme):
    body = star(26, 25, 21) + text(58, 42, "GitHub Stats", 20, weight=600)
    body += text(28, 65, "A LITTLE PROGRESS, EVERY DAY", 9, "muted", extra='letter-spacing="1.2"')
    for x, y, key, label in [(28, 113, "repos", "Public repos"), (246, 113, "stars", "Stars received"),
                              (28, 191, "forks", "Forks received"), (246, 191, "followers", "Followers")]:
        body += text(x, y, f"{data[key]:,}", 32, "accent", 600)
        body += text(x, y + 22, label, 12, "muted")
    body += '<path d="M218 87V214" stroke="currentColor" class="line"/>'
    body += text(28, 246, data["updated"], 10, "muted")
    return svg(440, 264, "MUSESTAR GitHub Stats", "Public owned repositories; stars and forks received; followers. " + data["updated"], body, theme)


def languages(data, theme):
    body = star(26, 25, 21) + text(58, 42, "Code Palette", 20, weight=600)
    body += text(28, 65, "LANGUAGES / PUBLIC NON-FORK REPOS", 9, "muted", extra='letter-spacing="1"')
    ranked = sorted(((name, size) for name, size in data["languages"].items() if size > 0),
                    key=lambda item: (-item[1], item[0]))
    total = sum(size for _, size in ranked)
    shown = ranked[:6] if len(ranked) <= 6 else ranked[:5] + [("Other", sum(size for _, size in ranked[5:]))]
    if not total:
        body += text(28, 140, "No language data yet", 16, "muted")
    else:
        body += '<defs><clipPath id="bar"><rect x="28" y="87" width="384" height="12" rx="6"/></clipPath></defs><g clip-path="url(#bar)">'
        offset = 28
        for index, (_, size) in enumerate(shown):
            width = 384 * size / total
            body += f'<rect x="{offset:.3f}" y="87" width="{width:.3f}" height="12" fill="{COLORS[index]}"/>'
            offset += width
        body += '</g>'
        for index, (name, size) in enumerate(shown):
            x, y = 28 + (index % 2) * 202, 132 + (index // 2) * 34
            body += f'<circle cx="{x+4}" cy="{y-4}" r="4" fill="{COLORS[index]}"/>'
            body += text(x + 16, y, name, 12)
            body += text(x + 180, y, f"{size / total:.1%}", 11, "muted", extra='text-anchor="end"')
    note = "By code bytes · forks excluded"
    if data.get("unavailable"):
        note += f" · {data['unavailable']} repos unavailable"
    body += text(28, 225, note, 10, "muted")
    body += text(28, 246, data["updated"], 10, "muted")
    return svg(440, 264, "MUSESTAR Code Palette", "Language distribution by bytes in accessible public non-fork repositories. " + note + ". " + data["updated"], body, theme)


def footer(theme):
    body = star(467, 23, 26)
    body += text(480, 80, "谢谢你，来过我的小宇宙。", 22, extra='text-anchor="middle"')
    body += text(480, 112, "MUSESTAR  /  KEEP A LITTLE STARDUST", 10, "muted",
                 extra='text-anchor="middle" letter-spacing="2"')
    return svg(960, 144, "谢谢你，来过我的小宇宙。", "MUSESTAR · 始于一份热爱", body, theme)


def section_heading(label, kind, theme, compact=False):
    width = 366 if compact else 846
    accent = "#b18aff" if theme == "dark" else THEMES[theme]["accent"]
    icons = {
        "stats": '<path d="M4 20h16M7 16v-4m5 4V5m5 11V9"/>',
        "visitors": ('<circle cx="9" cy="8" r="3"/>'
                     '<path d="M3 21v-2a6 6 0 0 1 12 0v2M16 5a3 3 0 0 1 0 6m3 10v-2a6 6 0 0 0-3-5"/>'),
    }
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="32" viewBox="0 0 {width} 32" role="img" aria-labelledby="title">
<title id="title">{escape(label)}</title>
<defs><linearGradient id="divider"><stop stop-color="{accent}" stop-opacity=".4"/><stop offset=".7" stop-color="{accent}" stop-opacity=".08"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></linearGradient></defs>
<g transform="translate(1 5) scale(.833333)" fill="none" stroke="currentColor" color="{accent}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{icons[kind]}</g>
<text x="31" y="24" fill="{accent}" font-family="'Microsoft YaHei','Noto Sans CJK SC','PingFang SC',sans-serif" font-size="21" font-weight="700">{escape(label)}</text>
<rect x="185" y="16" width="{width - 185}" height="1" fill="url(#divider)"/>
</svg>
'''


def render(data):
    cards = {}
    for theme in THEMES:
        cards[f"hero-{theme}.svg"] = hero(theme)
        cards[f"stats-{theme}.svg"] = stats(data, theme)
        cards[f"languages-{theme}.svg"] = languages(data, theme)
        cards[f"footer-{theme}.svg"] = footer(theme)
        for kind, label in [("stats", "GitHub Stats"), ("visitors", "来过的小伙伴")]:
            cards[f"heading-{kind}-{theme}.svg"] = section_heading(label, kind, theme)
            cards[f"heading-{kind}-{theme}-mobile.svg"] = section_heading(label, kind, theme, compact=True)
    return cards


def main():
    # Fetch and render everything first: an API outage keeps the last good cards.
    cards = render(collect())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, content in cards.items():
        path = OUTPUT / name
        temporary = path.with_suffix(".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    print(f"Updated {len(cards)} profile cards.")


if __name__ == "__main__":
    main()
