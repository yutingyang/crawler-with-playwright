"""Method A: parse the HTML ourselves and redraw it with PyMuPDF (image layer + text layer).

Coordinate pipeline
    text_layer units --x0.2--> page px --x(612/902)--> PDF pt
    image_layer units ---------> page px --x(612/902)--> PDF pt
PyMuPDF uses a top-left origin like the browser, so y needs no flipping.
"""
import io
import re
from pathlib import Path

import pymupdf
from bs4 import BeautifulSoup, NavigableString, Tag
from PIL import Image

from .assets import font_files, page_html, page_image, parse_style, px, viewer_rules
from .config import PAGE_H_PX, PAGE_W_PX, PAGES, PDF_A, PX_TO_PT, TEXT_SCALE

# Fallback when an ffN web font is missing: the CSS falls back to Arial / Times New Roman,
# whose metrics match PDF Base-14 Helvetica / Times.
BASE14 = {  # (serif, bold, italic) -> Base-14 name
    (False, False, False): "helv", (False, True, False): "hebo", (False, False, True): "heit", (False, True, True): "hebi",
    (True, False, False): "tiro", (True, True, False): "tibo", (True, False, True): "tiit", (True, True, True): "tibi",
}
ARIAL_TIMES_METRICS = {False: (0.905, -0.212), True: (0.891, -0.216)}  # (ascender, descender) in em


def baseline_factor(ascender: float, descender: float) -> float:
    """span.a has line-height:1 -> half-leading = (1 - (asc - desc)) / 2, baseline = top + half-leading + asc."""
    return (1 + ascender + descender) / 2


def font_table() -> dict[str, tuple[pymupdf.Font, float]]:
    """div.ffN -> (font, baseline factor).

    Prefer the real web font embedded in ttfs.css (what the viewer actually renders with);
    glyph widths must match, otherwise long spans drift away from the next absolutely-positioned span.
    """
    embedded = font_files()
    table = {}
    for r in viewer_rules():
        m = re.match(r"div\.(ff\d+) span \{ font-family: [^,]+, (.+?); font-weight: (\w+); font-style: (\w+);", r)
        if not m:
            continue
        ff = m.group(1)
        if ff in embedded:
            font = pymupdf.Font(fontbuffer=embedded[ff])
            table[ff] = (font, baseline_factor(font.ascender, font.descender))
        else:
            serif = "Times" in m.group(2)
            font = pymupdf.Font(BASE14[(serif, m.group(3) == "bold", m.group(4) == "italic")])
            table[ff] = (font, baseline_factor(*ARIAL_TIMES_METRICS[serif]))
    return table


def draw_images(page: pymupdf.Page, soup: BeautifulSoup, n: int) -> None:
    src = Image.open(page_image(n)).convert("RGBA")  # sprite png is transparent; RGB would turn it black
    for img in soup.select(".image_layer img"):
        st = parse_style(img.get("style"))
        left, top, w, h = (px(st[k]) for k in ("left", "top", "width", "height"))
        # CSS clip: rect(top right bottom left), relative to the <img> box
        clip = [float(v) for v in re.findall(r"-?[\d.]+", st.get("clip", ""))] or [0, w, h, 0]
        ct, cr, cb, cl = clip
        sx, sy = src.width / w, src.height / h  # displayed box -> source pixels
        crop = src.crop((round(cl * sx), round(ct * sy), round(cr * sx), round(cb * sy)))
        rect = pymupdf.Rect((left + cl) * PX_TO_PT, (top + ct) * PX_TO_PT,
                            (left + cr) * PX_TO_PT, (top + cb) * PX_TO_PT)
        buf = io.BytesIO()
        crop.save(buf, "PNG")
        page.insert_image(rect, stream=buf.getvalue())


def layout_span(span: Tag, font: pymupdf.Font, base: float, fs: float, tw: pymupdf.TextWriter) -> None:
    """Replay the browser's inline layout of one span.a, glyph by glyph, in text_layer units."""
    st = parse_style(span.get("style"))
    letter_sp, word_sp = px(st.get("letter-spacing")), px(st.get("word-spacing"))
    x = px(st.get("left"))
    baseline = px(st.get("top")) + fs * base
    k = TEXT_SCALE * PX_TO_PT  # text_layer unit -> pt

    def walk(node: Tag):
        nonlocal x
        for child in node.children:
            if isinstance(child, NavigableString):
                for ch in str(child).replace("\n", ""):
                    if not ch.isspace():
                        tw.append((x * k, baseline * k), ch, font=font, fontsize=fs * k)
                    # CSS word-spacing applies to U+0020 and U+00A0 (spans after a heading start with &nbsp;)
                    x += font.text_length(ch, fs) + letter_sp + (word_sp if ch in " \xa0" else 0)
            elif isinstance(child, Tag):
                cst, classes = parse_style(child.get("style")), child.get("class", [])
                for c in classes:  # span.l3 = margin-left:-3px, span.w8 = width:8px
                    if m := re.fullmatch(r"l(\d+)", c):
                        x -= int(m.group(1))
                    elif m := re.fullmatch(r"w(\d+)", c):
                        x += int(m.group(1))
                x += px(cst.get("margin-left"))
                if "w" in classes:
                    x += px(cst.get("width"))
                walk(child)

    walk(span)


def build(out: Path = PDF_A) -> Path:
    fonts = font_table()
    fallback = (pymupdf.Font("helv"), baseline_factor(*ARIAL_TIMES_METRICS[False]))
    doc = pymupdf.open()
    for n in PAGES:
        soup = BeautifulSoup(page_html(n), "html.parser")
        page = doc.new_page(width=PAGE_W_PX * PX_TO_PT, height=PAGE_H_PX * PX_TO_PT)
        draw_images(page, soup, n)  # z-index 1
        tw = pymupdf.TextWriter(page.rect)
        for div in soup.select(".text_layer div[class^=ff]"):  # z-index 2
            font, base = fonts.get(div["class"][0], fallback)
            fs = px(parse_style(div.get("style")).get("font-size"))
            for span in div.find_all("span", class_="a", recursive=False):
                layout_span(span, font, base, fs, tw)
        tw.write_text(page)
    out.parent.mkdir(exist_ok=True)
    doc.save(out, garbage=3, deflate=True)
    print("wrote", out)
    return out
