"""Phase 0 — Test A: visual verification of extraction coordinates.

For each sample PDF:
  - report page count (v2 = 7 pages; v1 = 4 pages -> would be skipped)
  - draw extraction rectangles on all pages -> phase0/outputs/<name>_rects.pdf
  - render page 6 (hourly temps) at 300 DPI -> phase0/outputs/<name>_p6.png
  - extract a few page-1 fields as a sanity check (codigo, region, comuna)

Run: ./venv/bin/python phase0/scripts/test_a_coordinates.py
"""
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).parent))
from cev_coords import draw_all_pages_rectangles, get_page_coordinates, normalize_coordinates

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "phase0" / "sample_pdfs"
OUT = ROOT / "phase0" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

REPORT_W, REPORT_H = 215.9, 330.0


def extract_area(page, area):
    pr = page.rect
    x1, y1, x2, y2 = area
    rx1, ry1 = normalize_coordinates(x1, y1, REPORT_W, REPORT_H, pr.width, pr.height)
    rx2, ry2 = normalize_coordinates(x2, y2, REPORT_W, REPORT_H, pr.width, pr.height)
    txt = page.get_textbox(fitz.Rect(rx1, ry1, rx2, ry2))
    return (txt or "").strip()


def render_page6(doc, out_png):
    if doc.page_count < 6:
        return False
    page = doc[5]
    pix = page.get_pixmap(dpi=300)
    pix.save(str(out_png))
    return True


def main():
    pdfs = sorted(SAMPLES.glob("*.pdf"))
    print(f"Found {len(pdfs)} sample PDFs\n")
    print(f"{'file':40s} {'pages':>5} {'codigo':>14} {'region':>10} {'p6_png':>7}")
    print("-" * 90)
    summary = []
    for pdf in pdfs:
        doc = fitz.open(pdf)
        n = doc.page_count
        codigo = region = ""
        if n >= 1:
            c0 = get_page_coordinates(0)
            codigo = extract_area(doc[0], c0["codigo_evaluacion"])
            region = extract_area(doc[0], c0["region"])[:10]
        # draw rectangles on a fresh copy
        rects_doc = fitz.open(pdf)
        draw_all_pages_rectangles(rects_doc, str(OUT / f"{pdf.stem}_rects.pdf"))
        rects_doc.close()
        # render page 6
        has_p6 = render_page6(doc, OUT / f"{pdf.stem}_p6.png")
        doc.close()
        print(f"{pdf.name[:40]:40s} {n:>5} {codigo[:14]:>14} {region:>10} {'yes' if has_p6 else 'no':>7}")
        summary.append((pdf.name, n, codigo, region, has_p6))
    print()
    v2 = sum(1 for s in summary if s[1] == 7)
    print(f"v2 (7-page): {v2}/{len(summary)}  |  outputs in phase0/outputs/")


if __name__ == "__main__":
    main()
