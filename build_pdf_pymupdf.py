"""Method A: parse the HTML ourselves and redraw it with PyMuPDF (image layer + text layer).

Coordinate pipeline
    text_layer units --x0.2--> page px --x(612/902)--> PDF pt
    image_layer units ---------> page px --x(612/902)--> PDF pt
Both the browser and PDF use a top-left origin in PyMuPDF, so y needs no flipping.
"""
import io
import re

import fitz  # PyMuPDF
from bs4 import BeautifulSoup, NavigableString, Tag
from PIL import Image

from common import (OUT, PAGE_H_PX, PAGE_W_PX, PAGES, PX_TO_PT, TEXT_SCALE,
                    page_html, page_image, parse_style, px, viewer_rules)

# The ffN web fonts are never downloaded, so the browser falls back to Arial / Times New Roman.
# PDF Base-14 Helvetica / Times have the same metrics.
BASE14 = {  # (serif, bold, italic) -> Base-14 name
    (False, False, False): "helv", (False, True, False): "hebo", (False, False, True): "heit", (False, True, True): "hebi",
    (True, False, False): "tiro", (True, True, False): "tibo", (True, False, True): "tiit", (True, True, True): "tibi",
}
# span.a has line-height:1, so baseline = top + (ascent - half of (ascent+descent-1)) * font-size
BASELINE = {False: 0.905 - (0.905 + 0.212 - 1) / 2,   # Arial
            True: 0.891 - (0.891 + 0.216 - 1) / 2}    # Times New Roman


def font_table():
    """div.ffN -> (fitz.Font, serif) from rules like `div.ff11 span { font-family: ff11, Arial...; font-weight: bold; ... }`."""
    table = {}
    for r in viewer_rules():
        m = re.match(r"div\.(ff\d+) span \{ font-family: [^,]+, (.+?); font-weight: (\w+); font-style: (\w+);", r)
        if m:
            serif = "Times" in m.group(2)
            name = BASE14[(serif, m.group(3) == "bold", m.group(4) == "italic")]
            table[m.group(1)] = (fitz.Font(name), serif)
    return table


def draw_images(page: fitz.Page, soup: BeautifulSoup, n: int):
    src = Image.open(page_image(n)).convert("RGBA")  # sprite png is transparent; RGB would turn it black
    for img in soup.select(".image_layer img"):
        st = parse_style(img.get("style"))
        left, top, w, h = (px(st[k]) for k in ("left", "top", "width", "height"))
        # CSS clip: rect(top right bottom left), relative to the <img> box
        clip = [float(v) for v in re.findall(r"-?[\d.]+", st.get("clip", ""))] or [0, w, h, 0]
        ct, cr, cb, cl = clip
        sx, sy = src.width / w, src.height / h  # displayed box -> source pixels
        crop = src.crop((round(cl * sx), round(ct * sy), round(cr * sx), round(cb * sy)))
        rect = fitz.Rect((left + cl) * PX_TO_PT, (top + ct) * PX_TO_PT,
                         (left + cr) * PX_TO_PT, (top + cb) * PX_TO_PT)
        buf = io.BytesIO()
        crop.save(buf, "PNG")
        page.insert_image(rect, stream=buf.getvalue())


def layout_span(span: Tag, font: fitz.Font, serif: bool, fs: float, tw: fitz.TextWriter):
    """Replay the browser's inline layout of one span.a, glyph by glyph, in text_layer units."""
    st = parse_style(span.get("style"))
    letter_sp, word_sp = px(st.get("letter-spacing")), px(st.get("word-spacing"))
    x = px(st.get("left"))
    baseline = px(st.get("top")) + fs * BASELINE[serif]
    k = TEXT_SCALE * PX_TO_PT  # text_layer unit -> pt

    def walk(node: Tag):
        nonlocal x
        for child in node.children:
            if isinstance(child, NavigableString):
                for ch in str(child).replace("\n", ""):
                    if not ch.isspace():
                        tw.append((x * k, baseline * k), ch, font=font, fontsize=fs * k)
                    x += font.text_length(ch, fs) + letter_sp + (word_sp if ch == " " else 0)
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


def build():
    fonts = font_table()
    doc = fitz.open()
    for n in PAGES:
        soup = BeautifulSoup(page_html(n), "html.parser")
        page = doc.new_page(width=PAGE_W_PX * PX_TO_PT, height=PAGE_H_PX * PX_TO_PT)
        draw_images(page, soup, n)  # z-index 1
        tw = fitz.TextWriter(page.rect)
        for div in soup.select(".text_layer div[class^=ff]"):  # z-index 2
            font, serif = fonts.get(div["class"][0], (fitz.Font("helv"), False))
            fs = px(parse_style(div.get("style")).get("font-size"))
            for span in div.find_all("span", class_="a", recursive=False):
                layout_span(span, font, serif, fs, tw)
        tw.write_text(page)
    OUT.mkdir(exist_ok=True)
    out = OUT / "method_a_pymupdf.pdf"
    doc.save(out, garbage=3, deflate=True, subset_fonts=True)
    print("wrote", out)


if __name__ == "__main__":
    build()
