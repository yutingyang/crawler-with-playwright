"""Check the I2C gap on page 2 in the live viewer: which fonts load, and where the trailing 'I' really ends."""
import json

from playwright.sync_api import sync_playwright

URL = "https://www.scribd.com/document/4026761/Intelligent-Platform-Management-Interface-Specification-v1-0"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1000})
        page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_selector("#page2 .text_layer", state="attached", timeout=30_000)
        page.locator("#outer_page_2").scroll_into_view_if_needed()
        page.wait_for_timeout(3000)

        info = page.evaluate("""() => {
            const fonts = [...document.fonts].map(f => `${f.family}:${f.status}`).filter(s => /ff\\d/.test(s));
            const spans = [...document.querySelectorAll('#page2 span.a')];
            const line = spans.find(s => s.textContent.includes('subset of the'));
            const sup = spans.find(s => s.style.left === '3289px');
            // Measure the last character ('I') of the long span with a Range
            const walker = document.createTreeWalker(line, NodeFilter.SHOW_TEXT);
            let last; while (walker.nextNode()) last = walker.currentNode;
            const r = document.createRange();
            r.setStart(last, last.length - 1); r.setEnd(last, last.length);
            const pg = document.querySelector('#page2').getBoundingClientRect();
            const scale = pg.width / 902;  // viewer zoom
            const toLayer = x => (x - pg.left) / scale / 0.2;  // screen px -> text_layer units
            return {
                ff_fonts_loaded: fonts,
                computed_font: getComputedStyle(line).fontFamily,
                I_right_edge: toLayer(r.getBoundingClientRect().right),
                sup2_left: toLayer(sup.getBoundingClientRect().left),
            };
        }""")
        print(json.dumps(info, indent=1))
        box = page.locator("#page2").bounding_box()
        page.screenshot(path="output/live_p2_i2c.png", clip={
            "x": box["x"], "y": box["y"] + box["height"] * 0.76, "width": box["width"], "height": box["height"] * 0.08})
        browser.close()


if __name__ == "__main__":
    main()
