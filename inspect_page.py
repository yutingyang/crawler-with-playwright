"""Inspect how Scribd renders a document page (DOM structure + network resources)."""
import json
from collections import Counter

from playwright.sync_api import sync_playwright

URL = "https://www.scribd.com/document/4026761/Intelligent-Platform-Management-Interface-Specification-v1-0"


def main():
    requests = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 1000})
        page.on("response", lambda r: requests.append((r.request.resource_type, r.url, r.headers.get("content-type", ""))))
        page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(5000)
        for _ in range(6):
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(1000)

        # Find the first rendered document page and summarise its structure
        info = page.evaluate("""() => {
            const pg = document.querySelector('[id^="page"] .newpage, .outer_page, [class*="page_container"], [data-page]');
            const pages = document.querySelectorAll('.outer_page, [id^="outer_page"]');
            const root = pages[0] || pg;
            if (!root) return {error: 'no page container found', classes: [...new Set([...document.querySelectorAll('div')].map(d => d.className).filter(Boolean))].slice(0, 80)};
            const walk = (el, depth) => {
                if (depth > 4) return null;
                const kids = [...el.children].slice(0, 6).map(c => walk(c, depth + 1)).filter(Boolean);
                return {tag: el.tagName, cls: el.className && el.className.baseVal === undefined ? el.className : '', style: (el.getAttribute('style') || '').slice(0, 120),
                        src: el.getAttribute('src') || el.getAttribute('orig') || '', text: el.childElementCount ? '' : (el.textContent || '').slice(0, 60), n: el.children.length, kids};
            };
            return {pageCount: pages.length, tree: walk(root, 0), sampleHtml: root.outerHTML.slice(0, 3000)};
        }""")
        print(json.dumps(info, indent=1, ensure_ascii=False)[:8000])

        print("\n=== Resource types ===")
        print(Counter(t for t, _, _ in requests))
        print("\n=== Interesting resources (images / json / js page data) ===")
        for t, u, ct in requests:
            if any(k in u for k in ("pages", "jsonp", "page", ".jpg", ".png", ".svg", ".woff", "font")) and "google" not in u:
                print(t, ct[:30], u[:160])
        browser.close()


if __name__ == "__main__":
    main()
