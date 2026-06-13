"""Generate side-by-side evidence images for human verification.

For a stratified subset of PDFs/months, render the printed table strip and
overlay the extracted values beneath each column, marking flagged cells in red.
Roberto compares the printed digits (top) against the extracted values (bottom).
"""
import pickle
import sys
from pathlib import Path

import cv2
import fitz
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import ocr_templates as ot
from run_scale import analyze_band

WORK = Path(__file__).resolve().parents[1] / "work_pdfs"
EVID = Path(__file__).resolve().parents[1] / "evidence"
EVID.mkdir(parents=True, exist_ok=True)


def make_for(pdf_path, month, templates):
    d = fitz.open(pdf_path); page = d[5]
    img = ot._render(page, ot.BAND_REGIONS[month])
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cb, _ = ot._column_bounds(gray)
    r = ot.extract_band(page, month, templates)
    d.close()
    if r.get("bad_grid") or len(cb) < 25:
        return None
    h, w = img.shape[:2]
    canvas = np.full((h + 120, w, 3), 255, np.uint8)
    canvas[:h] = img
    for key, yrow, color in [("exterior", h + 35, (0, 0, 0)), ("interior", h + 90, (0, 0, 0))]:
        vals = r[key]
        flags = dict(analyze_band(vals))
        for c in range(min(24, len(cb) - 1)):
            cx = int((cb[c] + cb[c + 1]) / 2)
            v = vals[c]
            txt = "X" if v is None else f"{v:.1f}"
            col = (0, 0, 220) if c in flags else color
            cv2.putText(canvas, txt, (cx - 28, yrow), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, col, 2, cv2.LINE_AA)
    cv2.putText(canvas, f"{Path(pdf_path).name[:30]} / {month} (rojo=flag)",
                (10, h + 115), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 120, 120), 1)
    out = EVID / f"EVID_{Path(pdf_path).stem[:24]}_{month}.png"
    cv2.imwrite(str(out), canvas)
    return out


def main(n_pdfs=8):
    templates = pickle.loads(ot.TEMPLATES_PATH.read_bytes())
    pdfs = sorted(WORK.glob("*.pdf"))
    rng = np.random.default_rng(5)
    pick = rng.choice(len(pdfs), size=min(n_pdfs, len(pdfs)), replace=False)
    made = []
    for i in pick:
        for m in ["enero", "julio"]:
            o = make_for(pdfs[i], m, templates)
            if o:
                made.append(o.name)
    print(f"evidence images written: {len(made)} in {EVID}")
    for m in made:
        print("  ", m)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
