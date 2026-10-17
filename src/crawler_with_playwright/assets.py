"""Reading the captured data in DATA (written by fetch)."""
import base64
import json
import re
from pathlib import Path

from .config import DATA

IMAGE_SUFFIXES = {".webp", ".jpg", ".png"}


def page_html(n: int) -> str:
    return (DATA / f"page{n}.html").read_text(encoding="utf-8")


def page_image(n: int) -> Path:
    return next(p for p in DATA.glob(f"page{n}.*") if p.suffix in IMAGE_SUFFIXES)


def viewer_rules() -> list[str]:
    """Layout CSS captured from the viewer, minus the rules that only matter inside the viewer."""
    rules = json.loads((DATA / "viewer_rules.json").read_text(encoding="utf-8"))
    skip = ("blurred_page", "extracted_term", "display: none")
    return [r for r in rules if not any(s in r for s in skip)]


def font_css() -> str:
    """The viewer's ttfs.css: one @font-face per ffN, each a base64 TTF data URI."""
    return (DATA / "ttfs.css").read_text(encoding="utf-8")


def font_files() -> dict[str, bytes]:
    """ffN -> TTF bytes decoded from ttfs.css."""
    out = {}
    for face in re.findall(r"@font-face\s*\{(.*?)\}", font_css(), re.S):
        fam = re.search(r"font-family:\s*['\"]?(ff\d+)", face)
        data = re.search(r"base64,([A-Za-z0-9+/=]+)", face)
        if fam and data:
            out[fam.group(1)] = base64.b64decode(data.group(1))
    return out


def parse_style(style: str | None) -> dict[str, str]:
    out = {}
    for decl in (style or "").split(";"):
        if ":" in decl:
            k, v = decl.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def px(v: str | None) -> float:
    return float(re.sub(r"px$", "", v.strip())) if v else 0.0
