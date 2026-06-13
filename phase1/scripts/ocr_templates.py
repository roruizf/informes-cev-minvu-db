"""Variant 10: glyph segmentation + template matching for page-6 digits.

The report font is constant, so each digit is the same glyph everywhere. We:
  1. use the detected column grid to crop each cell
  2. segment glyphs by connected components, discarding grid-line remnants
     (blobs taller than the digit band) and merging split sub-blobs
  3. classify each glyph against per-digit templates by normalized correlation
  4. detect the comma (tiny low blob) for the decimal point

Templates are BUILT from cells whose values we know (enero ground truth of the
2-profile example), then reused for all PDFs (same font).
"""
import pickle
import sys
from pathlib import Path

import cv2
import fitz
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from ocr_page6 import _column_bounds, _data_row_bands, _render, BAND_REGIONS, MONTHS

GLYPH_SIZE = (32, 24)  # h, w normalized
TEMPLATES_PATH = Path(__file__).parent / "digit_templates.pkl"

GT_ENERO_EXT = [11.9, 10.9, 10.4, 10.0, 10.0, 11.0, 12.6, 14.6, 16.6, 18.3, 19.9, 20.9,
                21.8, 22.3, 22.5, 22.3, 21.7, 20.8, 19.5, 18.2, 16.9, 15.6, 14.3, 13.0]
GT_ENERO_INT = [23.0, 22.3, 21.5, 20.9, 20.2, 19.8, 19.4, 19.6, 20.1, 21.0, 21.9, 23.1,
                24.1, 25.0, 25.8, 26.4, 26.5, 27.0, 26.9, 26.5, 26.0, 25.3, 24.5, 23.8]


def _cell_glyphs(cell_gray):
    """Return ordered list of (x, glyph_img, is_comma) for digit/comma glyphs."""
    _, binv = cv2.threshold(cell_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(binv, connectivity=8)
    H = cell_gray.shape[0]
    # digit height ~ the modal blob height; estimate from blobs
    heights = [stats[i][3] for i in range(1, n) if stats[i][4] >= 6]
    if not heights:
        return []
    digit_h = np.median([h for h in heights if h > 8]) if any(h > 8 for h in heights) else max(heights)
    raw = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < 5:
            continue
        # grid-line remnant: taller than digits and thin
        if bh > digit_h * 1.18 and bw <= 6:
            continue
        is_comma = bh <= digit_h * 0.45 and y > H * 0.45
        raw.append([x, y, bw, bh, is_comma, binv[y:y + bh, x:x + bw]])
    raw.sort(key=lambda r: r[0])
    # merge horizontally-overlapping/adjacent sub-blobs of the same digit
    merged = []
    for g in raw:
        if merged and not g[4] and not merged[-1][4]:
            px, py, pw, ph, *_ = merged[-1]
            if g[0] <= px + pw + 2 and abs(g[3] - ph) < ph * 0.6 and not g[4]:
                # merge bounding boxes
                nx0 = min(px, g[0]); ny0 = min(py, g[1])
                nx1 = max(px + pw, g[0] + g[2]); ny1 = max(py + ph, g[1] + g[3])
                merged[-1] = [nx0, ny0, nx1 - nx0, ny1 - ny0, False, None]
                continue
        merged.append(g)
    return merged


def _norm_glyph(cell_gray, box):
    x, y, w, h = box[0], box[1], box[2], box[3]
    crop = cell_gray[y:y + h, x:x + w]
    _, th = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.resize(th, (GLYPH_SIZE[1], GLYPH_SIZE[0]), interpolation=cv2.INTER_AREA)


def _iter_cells(page, month):
    img = _render(page, BAND_REGIONS[month])
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cb, pitch = _column_bounds(gray)
    rows = _data_row_bands(gray, cb)
    if len(cb) < 25:
        return None
    cells = {"exterior": [], "interior": []}
    for (y0, y1), key in [(rows[0], "exterior"), (rows[1], "interior")]:
        for c in range(24):
            cx0, cx1 = cb[c], cb[c + 1]
            w = cx1 - cx0
            cell = gray[max(0, y0 - 2):y1 + 2, int(cx0 + 0.06 * w):int(cx1 - 0.06 * w)]
            cells[key].append(cell)
    return cells


def build_templates(pdf):
    """Build digit templates from the enero ground-truth cells."""
    d = fitz.open(pdf); page = d[5]
    cells = _iter_cells(page, "enero"); d.close()
    samples = {str(k): [] for k in range(10)}
    for key, gt in [("exterior", GT_ENERO_EXT), ("interior", GT_ENERO_INT)]:
        for cell, val in zip(cells[key], gt):
            digits = f"{val:.1f}".replace(".", ",")  # e.g. "11,9"
            glyphs = _cell_glyphs(cell)
            dig_glyphs = [g for g in glyphs if not g[4]]
            digit_chars = [ch for ch in digits if ch.isdigit()]
            if len(dig_glyphs) != len(digit_chars):
                continue  # skip ambiguous cells for clean templates
            for g, ch in zip(dig_glyphs, digit_chars):
                samples[ch].append(_norm_glyph(cell, g).astype(np.float32))
    templates = {}
    for ch, imgs in samples.items():
        if imgs:
            templates[ch] = np.mean(imgs, axis=0)
    TEMPLATES_PATH.write_bytes(pickle.dumps(templates))
    return {ch: len(v) for ch, v in samples.items()}


def _classify(glyph_img, templates):
    """templates[ch] is either a single mean image or a list of exemplar images.
    Classify by best normalized correlation across all exemplars of each digit."""
    g = glyph_img.astype(np.float32)
    best, bestscore = "?", -1
    for ch, tmpl in templates.items():
        exemplars = tmpl if isinstance(tmpl, list) else [tmpl]
        for ex in exemplars:
            score = cv2.matchTemplate(g, ex.astype(np.float32), cv2.TM_CCOEFF_NORMED)[0][0]
            if score > bestscore:
                bestscore, best = score, ch
    return best, bestscore


def read_cell(cell_gray, templates):
    glyphs = _cell_glyphs(cell_gray)
    if not glyphs:
        return None, -1
    chars, scores = [], []
    for g in glyphs:
        if g[4]:
            chars.append(",")
        else:
            ch, sc = _classify(_norm_glyph(cell_gray, g), templates)
            chars.append(ch); scores.append(sc)
    s = "".join(chars)
    try:
        return float(s.replace(",", ".")), (min(scores) if scores else -1)
    except ValueError:
        return None, (min(scores) if scores else -1)


def extract_band(page, month, templates):
    cells = _iter_cells(page, month)
    out = {"exterior": [None] * 24, "interior": [None] * 24}
    if cells is None:
        out["bad_grid"] = True
        return out
    for key in ("exterior", "interior"):
        vals = []
        for cell in cells[key]:
            v, _ = read_cell(cell, templates)
            vals.append(v)
        out[key] = vals
    return out


if __name__ == "__main__":
    ex = "phase0/sample_pdfs/EX_2profile_10_6_1.pdf"
    counts = build_templates(ex)
    print("template samples per digit:", counts)
    templates = pickle.loads(TEMPLATES_PATH.read_bytes())
    d = fitz.open(ex); page = d[5]
    r = extract_band(page, "enero", templates)

    def acc(got, gt):
        return sum(1 for g, t in zip(got, gt) if g is not None and abs(g - t) < 0.05), len(gt)
    print("ext:", r["exterior"]); print("   acc:", acc(r["exterior"], GT_ENERO_EXT))
    print("int:", r["interior"]); print("   acc:", acc(r["interior"], GT_ENERO_INT))
    d.close()
