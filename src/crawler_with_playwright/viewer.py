"""Driving the live Scribd viewer with Playwright."""
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, Response, sync_playwright

from .config import DOC_URL

# Viewer decorations that are not part of the document
HIGHLIGHT_CSS = """
.text_layer span.extracted_term_highlight::before { display: none !important; }
.highlighter_canvas { display: none !important; }
"""

HIDE_OVERLAYS_JS = """() => { for (const e of document.querySelectorAll('body *')) {
    if (e.closest('.outer_page')) continue;
    const pos = getComputedStyle(e).position;
    if (pos === 'fixed' || pos === 'sticky') e.style.setProperty('visibility', 'hidden', 'important');
} }"""


@contextmanager
def open_viewer(*, headless: bool = True, scale: float = 1,
                on_response: Callable[[Response], None] | None = None) -> Iterator[Page]:
    """Launch Chromium and open the document; `scale` is the device pixel ratio for screenshots."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1280, "height": 1400}, device_scale_factor=scale)
        if on_response:
            page.on("response", on_response)
        page.goto(DOC_URL, wait_until="domcontentloaded", timeout=60_000)
        try:
            yield page
        finally:
            browser.close()


def show_page(page: Page, n: int) -> None:
    """Scroll page n into view; the viewer then downloads its fragment and image."""
    page.locator(f"#outer_page_{n}").scroll_into_view_if_needed()
    page.wait_for_selector(f"#page{n} .image_layer img[src]", state="attached", timeout=30_000)
    page.wait_for_timeout(1000)


def screenshot_pages(pages: list[int], out_dir: Path, scale: float = 2) -> list[Image.Image]:
    """Grayscale screenshots of the document pages only (toolbar, cookie banner and highlights hidden)."""
    out_dir.mkdir(exist_ok=True)
    shots = []
    with open_viewer(scale=scale) as page:
        page.add_style_tag(content=HIGHLIGHT_CSS)
        for n in pages:
            show_page(page, n)
            page.evaluate(HIDE_OVERLAYS_JS)
            path = out_dir / f"live_p{n}.png"
            page.locator(f"#page{n}").screenshot(path=str(path))
            shots.append(Image.open(path).convert("L"))
    return shots
