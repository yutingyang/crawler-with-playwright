"""Screenshot pages 1-3 in the live Scribd viewer and diff them against both rebuilt PDFs.

For each page writes output/live_vs_pdf_p{n}.png with four panels:
    live screenshot | overlay live vs A | overlay live vs B | overlay A vs B
Overlay colours: black = both agree, red = only in the first image, cyan = only in the second.
"""
import pymupdf as fitz
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps
from playwright.sync_api import sync_playwright

from common import OUT, PAGES

URL = "https://www.scribd.com/document/4026761/Intelligent-Platform-Management-Interface-Specification-v1-0"
WIDTH = 1200  # compare everything at this pixel width

# Live-viewer decorations that are not part of the document
HIDE_CSS = """
.text_layer span.extracted_term_highlight::before { display: none !important; }
.highlighter_canvas { display: none !important; }
"""


def screenshot_live() -> list[Image.Image]:
    shots = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1400}, device_scale_factor=2)
        page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        page.add_style_tag(content=HIDE_CSS)
        for n in PAGES:
            loc = page.locator(f"#page{n}")
            page.locator(f"#outer_page_{n}").scroll_into_view_if_needed()
            page.wait_for_selector(f"#page{n} .image_layer img[src]", timeout=30_000)
            page.wait_for_timeout(1500)
            # hide every fixed/sticky element outside the document (toolbar, cookie banner, ads)
            page.evaluate("""() => { for (const e of document.querySelectorAll('body *')) {
                if (e.closest('.outer_page')) continue;
                const pos = getComputedStyle(e).position;
                if (pos === 'fixed' || pos === 'sticky') e.style.setProperty('visibility', 'hidden', 'important');
            } }""")
            path = OUT / f"live_p{n}.png"
            loc.screenshot(path=str(path))
            shots.append(Image.open(path).convert("L"))
        browser.close()
    return shots


def render_pdf(name: str) -> list[Image.Image]:
    doc = fitz.open(OUT / name)
    imgs = []
    for pg in doc:
        pm = pg.get_pixmap(matrix=fitz.Matrix(WIDTH / pg.rect.width, WIDTH / pg.rect.width), colorspace=fitz.csGRAY)
        imgs.append(Image.frombytes("L", (pm.width, pm.height), pm.samples))
    return imgs


def fit(img: Image.Image, size) -> Image.Image:
    return img.resize(size, Image.LANCZOS)


def overlay(a: Image.Image, b: Image.Image) -> Image.Image:
    """a in red channel, b in green+blue: agreeing ink is black, a-only is red, b-only is cyan."""
    return Image.merge("RGB", (b, a, a))


def diff_ratio(a: Image.Image, b: Image.Image) -> float:
    """Share of 'ink' pixels that differ, after a small blur so 1px anti-alias jitter is ignored."""
    a2, b2 = (im.filter(ImageFilter.GaussianBlur(1.5)) for im in (a, b))
    d = ImageChops.difference(a2, b2).point(lambda v: 255 if v > 60 else 0)
    ink = ImageChops.darker(a, b).point(lambda v: 255 if v < 128 else 0)
    n_ink = sum(ink.histogram()[255:]) or 1
    return sum(d.histogram()[255:]) / n_ink


def main():
    live = screenshot_live()
    pdf_a, pdf_b = render_pdf("method_a_pymupdf.pdf"), render_pdf("method_b_chromium.pdf")
    for i, n in enumerate(PAGES):
        size = pdf_a[i].size
        L, A, B = fit(live[i], size), pdf_a[i], fit(pdf_b[i], size)
        panels = [("live", ImageOps.grayscale(L).convert("RGB")),
                  (f"live(red) vs A(cyan)  diff {diff_ratio(L, A):.1%}", overlay(L, A)),
                  (f"live(red) vs B(cyan)  diff {diff_ratio(L, B):.1%}", overlay(L, B)),
                  (f"A(red) vs B(cyan)  diff {diff_ratio(A, B):.1%}", overlay(A, B))]
        w, h = size
        sheet = Image.new("RGB", (w * 4 + 30, h + 40), "white")
        draw = ImageDraw.Draw(sheet)
        for j, (label, im) in enumerate(panels):
            sheet.paste(im, (j * (w + 10), 40))
            draw.text((j * (w + 10) + 10, 10), label, fill="black", font_size=24)
        sheet.save(OUT / f"live_vs_pdf_p{n}.png")
        print(f"page {n}: live {live[i].size} -> {size}; " + " | ".join(lbl for lbl, _ in panels[1:]))


if __name__ == "__main__":
    main()
