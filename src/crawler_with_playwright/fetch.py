"""Capture what the viewer downloads for PAGES: HTML fragments, background images, web fonts and CSS rules."""
import json
import re

from playwright.sync_api import Response

from .config import DATA, PAGES
from .viewer import open_viewer, show_page

IMAGE_EXT = {"image/webp": ".webp", "image/jpeg": ".jpg", "image/png": ".png"}
ASSET_RE = re.compile(r"/(pages|images)/(\d+)-[0-9a-f]+\.(?:jsonp|jpg|png)")

# Same-origin rules that define the page layout (ttfs.css is cross-origin, so it is taken from the response instead)
RULES_JS = r"""() => { const rules = [];
    for (const sheet of document.styleSheets) {
        let list; try { list = sheet.cssRules } catch (e) { continue }
        for (const r of list)
            if (/text_layer|ie_fix|\.ff\d|newpage|absimg|image_layer|span\.a|\.a\b/.test(r.cssText) && r.cssText.length < 600)
                rules.push(r.cssText);
    }
    return rules; }"""


def save_response(resp: Response) -> str | None:
    """Store a page fragment / page image / font stylesheet; returns a key for what was saved."""
    if resp.url.endswith("/ttfs.css"):
        (DATA / "ttfs.css").write_bytes(resp.body())
        return "fonts"
    m = ASSET_RE.search(resp.url)
    if not m or int(m.group(2)) not in PAGES:
        return None
    kind, n = m.group(1), int(m.group(2))
    body = resp.body()
    if kind == "pages":
        # window.pageN_callback(["<div class=\"newpage\" ...>"]) -> the HTML string
        payload = body.decode("utf-8")
        html = json.loads(payload[payload.index("(") + 1: payload.rindex(")")])[0]
        (DATA / f"page{n}.html").write_text(html, encoding="utf-8")
    else:
        ext = IMAGE_EXT.get(resp.headers.get("content-type", "").split(";")[0], ".bin")
        (DATA / f"page{n}{ext}").write_bytes(body)
    return f"{kind}{n}"


def fetch() -> None:
    DATA.mkdir(exist_ok=True)
    wanted = {"fonts"} | {f"{k}{n}" for k in ("pages", "images") for n in PAGES}
    got: set[str] = set()

    with open_viewer(on_response=lambda r: got.add(save_response(r) or "")) as page:
        for n in PAGES:
            show_page(page, n)
        for _ in range(20):
            if wanted <= got:
                break
            page.wait_for_timeout(500)
        rules = page.evaluate(RULES_JS)
    (DATA / "viewer_rules.json").write_text(json.dumps(rules, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"captured {sorted(wanted & got)} and {len(rules)} CSS rules into {DATA}/")
    if missing := wanted - got:
        print("missing:", sorted(missing))
