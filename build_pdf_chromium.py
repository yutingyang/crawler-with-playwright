"""Method B: put the page fragments back into an HTML page with the viewer's CSS and let Chromium print it.

The browser does the whole layout (scale(0.2), letter-spacing, clip...), we only:
  1. point <img> at the local image files,
  2. wrap each .newpage in a Letter-sized sheet and scale 902px -> 816px (8.5in @ 96 css px/in),
  3. call page.pdf().
"""
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from common import DATA, OUT, PAGE_W_PX, PAGES, page_html, page_image, viewer_rules

SHEET_W_PX = 816  # 8.5in in CSS px

CSS = f"""
@page {{ size: 8.5in 11in; margin: 0; }}
html, body {{ margin: 0; }}
.sheet {{ width: 8.5in; height: 11in; overflow: hidden; break-after: page; }}
.sheet .newpage {{ transform: scale({SHEET_W_PX / PAGE_W_PX}); transform-origin: 0 0; }}
"""


def build():
    sheets = []
    for n in PAGES:
        soup = BeautifulSoup(page_html(n), "html.parser")
        for img in soup.select("img"):
            img["src"] = page_image(n).name  # local copy instead of html.scribdassets.com
        sheets.append(f'<div class="sheet">{soup}</div>')

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<style>{chr(10).join(viewer_rules())}</style>
<style>{CSS}</style></head><body>{''.join(sheets)}</body></html>"""
    combined = DATA / "combined.html"
    combined.write_text(html, encoding="utf-8")

    OUT.mkdir(exist_ok=True)
    out = OUT / "method_b_chromium.pdf"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(combined.resolve().as_uri(), wait_until="load")
        page.pdf(path=str(out), prefer_css_page_size=True, print_background=True)
        browser.close()
    print("wrote", out)


if __name__ == "__main__":
    build()
