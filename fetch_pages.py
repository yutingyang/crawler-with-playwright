"""Load the Scribd viewer, capture the page fragments (jsonp) and background images of the first N pages."""
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://www.scribd.com/document/4026761/Intelligent-Platform-Management-Interface-Specification-v1-0"
N_PAGES = 3
OUT = Path("data")
EXT = {"image/webp": ".webp", "image/jpeg": ".jpg", "image/png": ".png"}


def main():
    OUT.mkdir(exist_ok=True)
    got = {}

    def on_response(resp):
        if resp.url.endswith("/ttfs.css"):  # @font-face for ff0..ffN (cross-origin, so read the response itself)
            (OUT / "ttfs.css").write_bytes(resp.body())
            return
        m = re.search(r"/(pages|images)/(\d+)-[0-9a-f]+\.(jsonp|jpg|png)", resp.url)
        if not m or int(m.group(2)) > N_PAGES:
            return
        kind, n = m.group(1), int(m.group(2))
        body = resp.body()
        if kind == "pages":
            # window.pageN_callback(["<div ...>"]) -> the HTML string
            payload = body.decode("utf-8")
            html = json.loads(payload[payload.index("(") + 1 : payload.rindex(")")])[0]
            (OUT / f"page{n}.html").write_text(html, encoding="utf-8")
        else:
            ext = EXT.get(resp.headers.get("content-type", "").split(";")[0], ".bin")
            (OUT / f"page{n}{ext}").write_bytes(body)
        got[(kind, n)] = True

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 1000})
        page.on("response", on_response)
        page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        for _ in range(15):
            if len(got) >= 2 * N_PAGES:
                break
            page.mouse.wheel(0, 800)
            page.wait_for_timeout(800)

        # Record the CSS the viewer applies, so the coordinate system can be reproduced offline
        css = page.evaluate("""() => {
            const q = s => document.querySelector(s);
            const cs = (el, props) => el ? Object.fromEntries(props.map(k => [k, getComputedStyle(el)[k]])) : null;
            const span = q('#page1 .text_layer span.a');
            const font = q('#page1 .text_layer div[class^="ff"]');
            const rules = [];
            for (const sheet of document.styleSheets) {
                try { for (const r of sheet.cssRules) if (/text_layer|ie_fix|\\.ff\\d|newpage|absimg|image_layer|span\\.a|\\.a\\b/.test(r.cssText) && r.cssText.length < 600) rules.push(r.cssText.slice(0, 300)); } catch (e) {}
            }
            return {
                text_layer: cs(q('#page1 .text_layer'), ['position', 'transform', 'transformOrigin', 'width', 'height']),
                ie_fix: cs(q('#page1 .ie_fix'), ['position', 'transform', 'transformOrigin']),
                span: cs(span, ['position', 'fontFamily', 'fontSize', 'lineHeight', 'whiteSpace', 'color']),
                span_rect: span && span.getBoundingClientRect().toJSON(),
                page_rect: q('#page1').getBoundingClientRect().toJSON(),
                font_div: cs(font, ['fontFamily']),
                rules,
            };
        }""")
        (OUT / "css_info.json").write_text(json.dumps(css, indent=1, ensure_ascii=False), encoding="utf-8")
        browser.close()

    print("captured:", sorted(got))


if __name__ == "__main__":
    main()
