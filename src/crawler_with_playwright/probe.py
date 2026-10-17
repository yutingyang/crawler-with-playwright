"""Look inside the live viewer: how a page is built, and which web fonts it renders with."""
import json
from collections import Counter

from .viewer import open_viewer, show_page

STRUCTURE_JS = """() => {
    const pg = document.querySelector('#page1');
    return {
        pageCount: document.querySelectorAll('.outer_page').length,
        textLayerTransform: getComputedStyle(pg.querySelector('.text_layer')).transform,
        page1Html: pg.outerHTML.slice(0, 1500),
    };
}"""

FONTS_JS = r"""() => ({
    webFonts: [...document.fonts].filter(f => /ff\d/.test(f.family)).map(f => `${f.family}:${f.status}`),
    fontStylesheet: [...document.styleSheets].map(s => s.href).filter(h => h && h.endsWith('ttfs.css')),
})"""


def structure() -> None:
    """Page count, the text-layer scale and page 1's HTML, plus which resources the viewer loads."""
    resources = []
    with open_viewer(on_response=lambda r: resources.append((r.request.resource_type, r.url))) as page:
        show_page(page, 2)
        info = page.evaluate(STRUCTURE_JS)
    print(json.dumps(info, indent=1, ensure_ascii=False))
    print("\nresource types:", dict(Counter(t for t, _ in resources)))
    print("document assets:")
    for t, url in resources:
        if "html.scribdassets.com" in url:
            print(f"  {t:7} {url.split('?')[0]}")


def fonts() -> None:
    """Which ffN web fonts are loaded (they come from ttfs.css as data URIs, so they never show up as requests)."""
    with open_viewer() as page:
        show_page(page, 2)
        print(json.dumps(page.evaluate(FONTS_JS), indent=1))
