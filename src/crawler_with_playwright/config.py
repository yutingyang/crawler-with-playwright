"""Settings shared by every step."""
from pathlib import Path

DOC_URL = "https://www.scribd.com/document/4026761/Intelligent-Platform-Management-Interface-Specification-v1-0"
PAGES = list(range(1, 4))

DATA = Path("data")    # captured from the viewer (fetch)
OUT = Path("output")   # PDFs, screenshots, comparison images

# Coordinate system of a Scribd page (see NOTES.md)
PAGE_W_PX, PAGE_H_PX = 902, 1167  # .newpage size in the page fragment
TEXT_SCALE = 0.2                  # .text_layer { transform: scale(0.2) }
LETTER_W_PT = 612                 # 902px / 8.5in ≈ 1167px / 11in ≈ 106 dpi -> US Letter
PX_TO_PT = LETTER_W_PT / PAGE_W_PX

PDF_A = OUT / "method_a_pymupdf.pdf"
PDF_B = OUT / "method_b_chromium.pdf"
