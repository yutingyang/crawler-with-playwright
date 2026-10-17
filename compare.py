"""Render each page of both PDFs side by side (A | B) for a visual check."""
import fitz
from PIL import Image

from common import OUT


def main():
    a, b = fitz.open(OUT / "method_a_pymupdf.pdf"), fitz.open(OUT / "method_b_chromium.pdf")
    for i in range(min(len(a), len(b))):
        imgs = [Image.frombytes("RGB", (pm.width, pm.height), pm.samples)
                for pm in (d[i].get_pixmap(dpi=100) for d in (a, b))]
        w, h = sum(im.width for im in imgs) + 10, max(im.height for im in imgs)
        canvas = Image.new("RGB", (w, h), "red")
        canvas.paste(imgs[0], (0, 0))
        canvas.paste(imgs[1], (imgs[0].width + 10, 0))
        canvas.save(OUT / f"compare_p{i + 1}.png")
    print(f"A: {len(a)} pages {a[0].rect}, B: {len(b)} pages {b[0].rect}")


if __name__ == "__main__":
    main()
