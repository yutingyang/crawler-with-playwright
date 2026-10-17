"""Shared helpers: read the captured pages and the viewer's CSS."""
import base64
import json
import re
from pathlib import Path

DATA = Path("data")
OUT = Path("output")
PAGES = [1, 2, 3]

PAGE_W_PX, PAGE_H_PX = 902, 1167  # .newpage size in the jsonp
TEXT_SCALE = 0.2                  # .text_layer { transform: scale(0.2) }
LETTER_W_PT = 612                 # 8.5in; 902px / 8.5in ≈ 106 dpi, 1167px / 11in ≈ 106 dpi -> US Letter
PX_TO_PT = LETTER_W_PT / PAGE_W_PX


def page_html(n: int) -> str:
    return (DATA / f"page{n}.html").read_text(encoding="utf-8")


def page_image(n: int) -> Path:
    return next(DATA.glob(f"page{n}.*[!l]"))  # page{n}.webp / .jpg / .png (not .html)


def viewer_rules() -> list[str]:
    """CSS rules captured from the live viewer, minus the ones that only matter there."""
    rules = json.loads((DATA / "css_info.json").read_text(encoding="utf-8"))["rules"]
    skip = ("blurred_page", "extracted_term", "display: none")
    return [r for r in rules if not any(s in r for s in skip)]


def font_css() -> str:
    """The viewer's ttfs.css: one @font-face per ffN, each a base64 TTF data URI."""
    return (DATA / "ttfs.css").read_text(encoding="utf-8")


def font_files() -> dict[str, bytes]:
    """ffN -> TTF bytes decoded from ttfs.css."""
    faces = re.findall(r"@font-face\s*\{(.*?)\}", font_css(), re.S)
    out = {}
    for face in faces:
        fam = re.search(r"font-family:\s*['\"]?(ff\d+)", face)
        data = re.search(r"base64,([A-Za-z0-9+/=]+)", face)
        if fam and data:
            out[fam.group(1)] = base64.b64decode(data.group(1))
    return out


def parse_style(style: str) -> dict[str, str]:
    out = {}
    for decl in (style or "").split(";"):
        if ":" in decl:
            k, v = decl.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def px(v: str | None) -> float:
    return float(re.sub(r"px$", "", v.strip())) if v else 0.0
