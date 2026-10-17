"""Command line entry point: uv run crawler-with-playwright <command>"""
import argparse

from . import compare, fetch, pdf_chromium, pdf_pymupdf, probe
from .config import OUT
from .viewer import open_viewer


def open_document() -> None:
    """Open the document in a visible browser window and save a screenshot."""
    OUT.mkdir(exist_ok=True)
    with open_viewer(headless=False) as page:
        print("Title:", page.title())
        page.screenshot(path=str(OUT / "screenshot.png"))
        input("Browser is open. Press Enter to close...")


def build(method: str) -> None:
    if method in ("a", "all"):
        pdf_pymupdf.build()
    if method in ("b", "all"):
        pdf_chromium.build()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="crawler-with-playwright",
                                     description="Rebuild Scribd viewer pages (image layer + text layer) as PDF.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("open", help="open the document in a visible browser")
    sub.add_parser("fetch", help="capture page fragments, images, fonts and CSS into data/")
    p_build = sub.add_parser("build", help="build the PDFs from data/")
    p_build.add_argument("method", nargs="?", choices=["a", "b", "all"], default="all",
                         help="a = PyMuPDF, b = Chromium page.pdf()")
    p_cmp = sub.add_parser("compare", help="diff the PDFs (and live screenshots) into output/compare_p*.png")
    p_cmp.add_argument("--no-live", action="store_true", help="only compare A vs B, skip the live screenshots")
    p_probe = sub.add_parser("probe", help="inspect the live viewer")
    p_probe.add_argument("what", choices=["structure", "fonts"])
    sub.add_parser("all", help="fetch + build + compare")
    args = parser.parse_args(argv)

    match args.cmd:
        case "open":
            open_document()
        case "fetch":
            fetch.fetch()
        case "build":
            build(args.method)
        case "compare":
            compare.compare(live=not args.no_live)
        case "probe":
            {"structure": probe.structure, "fonts": probe.fonts}[args.what]()
        case "all":
            fetch.fetch()
            build("all")
            compare.compare()
