"""Page-6 hourly-temperature extractor: grid detection + glyph template matching.

Self-contained production version of the Phase-1 winner (94.8% vs ground truth).
Templates live in digit_templates.pkl (multi-exemplar, built once from known data).
"""
import pickle
import re
from pathlib import Path

import cv2
import fitz
import numpy as np

REPORT_W, REPORT_H = 215.9, 330.0
MONTHS = ["enero", "abril", "julio", "octubre"]
GLYPH_SIZE = (32, 24)
BAND_REGIONS = {
    "enero":   (38, 95.5, 206, 107.5),
    "abril":   (38, 150.3, 206, 162.3),
    "julio":   (38, 209.6, 206, 221.6),
    "octubre": (38, 268.8, 206, 280.8),
}
_TEMPLATES_PATH = Path(__file__).parent / "digit_templates.pkl"
_TEMPLATES = None


def _templates():
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = pickle.loads(_TEMPLATES_PATH.read_bytes())
    return _TEMPLATES



def _render(page, region, dpi=600):
    x1, y1, x2, y2 = region
    pr = page.rect
    clip = fitz.Rect(x1 / REPORT_W * pr.width, y1 / REPORT_H * pr.height,
                     x2 / REPORT_W * pr.width, y2 / REPORT_H * pr.height)
    pix = page.get_pixmap(dpi=dpi, clip=clip)
    arr = np.frombuffer(pix.tobytes("png"), np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)



def _raw_vertical_lines(gray):
    th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY_INV, 15, 10)
    h = th.shape[0]
    vert = cv2.erode(th, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(5, h // 3))))
    vert = cv2.dilate(vert, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(5, h // 3))))
    colsum = vert.sum(axis=0)
    thresh = colsum.max() * 0.4
    xs, run = [], []
    for x, v in enumerate(colsum):
        if v >= thresh:
            run.append(x)
        elif run:
            xs.append(int(np.mean(run))); run = []
    if run:
        xs.append(int(np.mean(run)))
    return xs



def _column_bounds(gray):
    """Reconstruct the 25 boundaries of the 24 hour columns robustly.

    The grid has a regular pitch; detect it from the most common spacing and
    rebuild a uniform 24-column grid anchored on the detected lines. This is
    robust to missing lines and to noise lines in the label block / margins.
    """
    xs = _raw_vertical_lines(gray)
    if len(xs) < 5:
        return [], 0
    diffs = np.diff(xs)
    # the column pitch = median of diffs that are "large" (ignore tiny noise gaps)
    big = diffs[diffs > 0.5 * np.median(diffs)]
    pitch = float(np.median(big)) if len(big) else float(np.median(diffs))
    # keep only lines that participate in the regular grid (neighbor ~ pitch)
    grid = [xs[i] for i in range(len(xs))
            if (i > 0 and abs(diffs[i - 1] - pitch) < 0.3 * pitch)
            or (i < len(diffs) and abs(diffs[i] - pitch) < 0.3 * pitch)]
    if len(grid) < 2:
        return [], pitch
    # rightmost grid line = right edge of column 24; build 25 bounds going left
    right = grid[-1]
    bounds = [right - k * pitch for k in range(25)][::-1]
    return [int(round(b)) for b in bounds], pitch



def _ink_row_bands(gray, x_lo, x_hi):
    """Find contiguous bands of dark ink (text) in the data-column x-range.

    Returns list of (y0,y1). The 3 expected bands are header, exterior, interior.
    """
    sub = gray[:, x_lo:x_hi]
    ink = (sub < 128).sum(axis=1).astype(float)
    thr = max(ink.max() * 0.12, 20)
    bands, run = [], []
    for y, v in enumerate(ink):
        if v >= thr:
            run.append(y)
        elif run:
            bands.append((run[0], run[-1])); run = []
    if run:
        bands.append((run[0], run[-1]))
    # merge bands separated by tiny gaps, drop too-thin noise
    merged = []
    for a, b in bands:
        if merged and a - merged[-1][1] < 6:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    merged = [(max(0, a - 3), min(gray.shape[0], b + 3)) for a, b in merged if b - a >= 6]
    return merged



def _data_row_bands(gray, col_bounds):
    """exterior & interior row y-ranges via ink projection in the data columns."""
    if len(col_bounds) >= 2:
        x_lo, x_hi = col_bounds[0], col_bounds[-1]
    else:
        x_lo, x_hi = gray.shape[1] // 4, gray.shape[1]
    bands = _ink_row_bands(gray, x_lo, x_hi)
    # expect 3 text bands (header, exterior, interior) -> take last two
    if len(bands) >= 3:
        return bands[-2:]
    if len(bands) == 2:
        return bands
    h = gray.shape[0]
    return [(h // 3, 2 * h // 3), (2 * h // 3, h)]



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



def extract_band(page, month):
    """Extract one month-band: {'exterior':[24], 'interior':[24]} + low-confidence flag list."""
    templates = _templates()
    cells = _iter_cells(page, month)
    out = {"exterior": [None] * 24, "interior": [None] * 24,
           "conf_ext": [-1.0] * 24, "conf_int": [-1.0] * 24}
    if cells is None:
        out["bad_grid"] = True
        return out
    for key, ck in (("exterior", "conf_ext"), ("interior", "conf_int")):
        vals, confs = [], []
        for cell in cells[key]:
            v, c = read_cell(cell, templates)
            vals.append(v); confs.append(c)
        out[key] = vals; out[ck] = confs
    return out


def extract_page6(pdf_path) -> dict:
    """Extract all 4 months from a PDF. Returns {month: {exterior, interior, conf_*}}."""
    doc = fitz.open(pdf_path)
    if doc.page_count < 6:
        doc.close(); return {}
    page = doc[5]
    result = {m: extract_band(page, m) for m in MONTHS}
    doc.close()
    return result
