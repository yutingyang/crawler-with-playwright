"""Shared helpers: read the captured pages and the viewer's CSS."""
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


def parse_style(style: str) -> dict[str, str]:
    out = {}
    for decl in (style or "").split(";"):
        if ":" in decl:
            k, v = decl.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def px(v: str | None) -> float:
    return float(re.sub(r"px$", "", v.strip())) if v else 0.0
