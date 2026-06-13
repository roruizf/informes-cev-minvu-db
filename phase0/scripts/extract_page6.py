"""Phase 0 finding: page-6 hourly temperatures come from the PDF TEXT LAYER,
not OCR. This extractor groups numeric words by row (y) and column (x).

Per v2 report, page 6 has 4 month-bands (Enero, Abril, Julio, Octubre); each
band's data TABLE has exactly 2 numeric rows (T° exterior, T interior) plus an
hour-header row (0..23). The visible "3rd profile" (Temperatura media de
confort) is only a CHART LINE — it has no tabular text row.

Returns: {band_index: {"hours":[..], "exterior":[24], "interior":[24]}}
"""
import re
from pathlib import Path

import fitz

NUM = re.compile(r"^-?\d+(?:,\d+)?$")


def _to_float(tok: str) -> float:
    return float(tok.replace(",", "."))


def extract_page6(pdf_path) -> dict:
    doc = fitz.open(pdf_path)
    if doc.page_count < 6:
        doc.close()
        return {}
    page = doc[5]
    words = page.get_text("words")  # (x0,y0,x1,y1,text,block,line,word)
    doc.close()

    # numeric tokens with their position
    nums = [(w[0], round(w[1], 1), w[4]) for w in words if NUM.match(w[4])]
    by_row: dict[float, list] = {}
    for x, y, t in nums:
        by_row.setdefault(y, []).append((x, t))

    # data rows = rows with >= 20 numeric tokens (24 hourly columns)
    data_rows = {y: sorted(v) for y, v in by_row.items() if len(v) >= 20}

    # group the 12 rows into 4 bands of 3 (header, exterior, interior) by y order
    ys = sorted(data_rows)
    bands = {}
    for band_idx in range(len(ys) // 3):
        hdr, ext, intr = ys[band_idx * 3: band_idx * 3 + 3]
        bands[band_idx] = {
            "hours": [int(t) for _, t in data_rows[hdr]],
            "exterior": [_to_float(t) for _, t in data_rows[ext]],
            "interior": [_to_float(t) for _, t in data_rows[intr]],
        }
    return bands


def validate(bands: dict) -> dict:
    """Return per-band validation: 24/24 counts and physical-range check."""
    out = {}
    for i, b in bands.items():
        ext, intr = b["exterior"], b["interior"]
        out[i] = {
            "exterior_count": len(ext),
            "interior_count": len(intr),
            "ext_24": len(ext) == 24,
            "int_24": len(intr) == 24,
            "in_range": all(-20 <= v <= 50 for v in ext + intr),
        }
    return out


if __name__ == "__main__":
    samples = Path(__file__).resolve().parents[1] / "sample_pdfs"
    for pdf in sorted(samples.glob("*.pdf")):
        bands = extract_page6(pdf)
        if not bands:
            print(f"{pdf.name[:38]:38s}  v1/no-p6")
            continue
        v = validate(bands)
        ok = sum(1 for r in v.values() if r["ext_24"] and r["int_24"] and r["in_range"])
        print(f"{pdf.name[:38]:38s}  bands={len(bands)}  fully-valid={ok}/{len(bands)}")
