"""Diff the rebuilt PDFs against each other and, optionally, against screenshots of the live viewer.

output/compare_p{n}.png panels:
    with live:    live | live vs A | live vs B | A vs B
    without live: A | B | A vs B
Overlay colours: black = both agree, red = only in the first image, cyan = only in the second.
"""
from pathlib import Path

import pymupdf
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .config import OUT, PAGES, PDF_A, PDF_B
from .viewer import screenshot_pages

WIDTH = 1200  # every image is compared at this pixel width


def render_pdf(path: Path) -> list[Image.Image]:
    images = []
    for page in pymupdf.open(path):
        zoom = WIDTH / page.rect.width
        pm = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY)
        images.append(Image.frombytes("L", (pm.width, pm.height), pm.samples))
    return images


def overlay(a: Image.Image, b: Image.Image) -> Image.Image:
    """Agreeing ink is black, ink only in a is red, ink only in b is cyan."""
    return Image.merge("RGB", (b, a, a))


def diff_ratio(a: Image.Image, b: Image.Image) -> float:
    """Share of ink pixels that differ, after a small blur so 1px anti-alias jitter is ignored."""
    a2, b2 = (im.filter(ImageFilter.GaussianBlur(1.5)) for im in (a, b))
    diff = ImageChops.difference(a2, b2).point(lambda v: 255 if v > 60 else 0)
    ink = ImageChops.darker(a, b).point(lambda v: 255 if v < 128 else 0)
    return diff.histogram()[255] / (ink.histogram()[255] or 1)


def save_sheet(panels: list[tuple[str, Image.Image]], path: Path) -> None:
    w, h = panels[0][1].size
    sheet = Image.new("RGB", ((w + 10) * len(panels), h + 40), "white")
    draw = ImageDraw.Draw(sheet)
    for j, (label, im) in enumerate(panels):
        sheet.paste(im.convert("RGB"), (j * (w + 10), 40))
        draw.text((j * (w + 10) + 10, 10), label, fill="black", font_size=24)
    sheet.save(path)


def compare(live: bool = True) -> None:
    pdf_a, pdf_b = render_pdf(PDF_A), render_pdf(PDF_B)
    shots = screenshot_pages(PAGES, OUT) if live else None
    for i, n in enumerate(PAGES):
        a = pdf_a[i]
        b = pdf_b[i].resize(a.size, Image.LANCZOS)
        if shots:
            lv = shots[i].resize(a.size, Image.LANCZOS)
            panels = [("live", lv),
                      (f"live(red) vs A(cyan)  diff {diff_ratio(lv, a):.1%}", overlay(lv, a)),
                      (f"live(red) vs B(cyan)  diff {diff_ratio(lv, b):.1%}", overlay(lv, b))]
        else:
            panels = [("A", a), ("B", b)]
        panels.append((f"A(red) vs B(cyan)  diff {diff_ratio(a, b):.1%}", overlay(a, b)))
        save_sheet(panels, OUT / f"compare_p{n}.png")
        print(f"page {n}: " + " | ".join(label for label, _ in panels if " vs " in label))
