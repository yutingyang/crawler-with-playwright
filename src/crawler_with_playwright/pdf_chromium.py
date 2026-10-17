"""Method B: put the page fragments back into an HTML page with the viewer's CSS and let Chromium print it.

The browser does the whole layout (scale(0.2), letter-spacing, clip...), we only:
  1. include ttfs.css (the real ffN web fonts) and the viewer's layout rules,
  2. point <img> at the local image files,
  3. wrap each .newpage in a Letter-sized sheet and scale 902px -> 816px (8.5in @ 96 css px/in),
  4. call page.pdf().
"""
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .assets import font_css, page_html, page_image, viewer_rules
from .config import PAGE_W_PX, PAGES, PDF_B

SHEET_W_PX = 816  # 8.5in in CSS px

SHEET_CSS = f"""
@page {{ size: 8.5in 11in; margin: 0; }}
html, body {{ margin: 0; }}
.sheet {{ width: 8.5in; height: 11in; overflow: hidden; break-after: page; }}
.sheet .newpage {{ transform: scale({SHEET_W_PX / PAGE_W_PX}); transform-origin: 0 0; }}
"""


def build(out: Path = PDF_B) -> Path:
    sheets = []
    for n in PAGES:
        soup = BeautifulSoup(page_html(n), "html.parser")
        for img in soup.select("img"):
            img["src"] = page_image(n).resolve().as_uri()  # local copy instead of html.scribdassets.com
        sheets.append(f'<div class="sheet">{soup}</div>')

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<style>{font_css()}</style>
<style>{chr(10).join(viewer_rules())}</style>
<style>{SHEET_CSS}</style></head><body>{''.join(sheets)}</body></html>"""
    out.parent.mkdir(exist_ok=True)
    source = out.with_suffix(".html")  # kept for inspection
    source.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(source.resolve().as_uri(), wait_until="load")
        page.pdf(path=str(out), prefer_css_page_size=True, print_background=True)
        browser.close()
    print("wrote", out)
    return out
