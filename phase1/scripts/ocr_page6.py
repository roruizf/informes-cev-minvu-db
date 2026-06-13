"""Phase-1 page-6 OCR: cell-segmentation approach.

Legacy failure mode: OCR over a whole row-strip merges adjacent digits
(`25,124`, `322,922`). Fix: locate the table grid, crop each of the 24 hour
cells per row, and OCR each cell ALONE with a digit+comma whitelist.

Pipeline per month-band:
  1. Render the table region (header + 2 data rows) at high DPI.
  2. Find vertical grid lines -> 24 column boundaries; find the 2 data rows.
  3. For each cell: threshold, OCR with --psm 7/8/10 + tessedit_char_whitelist=0-9,.
  4. Parse to float; flag cells that fail / look suspect.

This module exposes extract_band(page, month) -> {"exterior":[...], "interior":[...], "conf":[...]}.
"""
import re

import cv2
import fitz
import numpy as np
import pytesseract

REPORT_W, REPORT_H = 215.9, 330.0
MONTHS = ["enero", "abril", "julio", "octubre"]

# Generous table regions (mm): x covers labels..col24, y covers header+exterior+interior.
# Derived from legacy month-strip coords, widened to include both data rows.
BAND_REGIONS = {
    "enero":   (38, 95.5, 206, 107.5),
    "abril":   (38, 150.3, 206, 162.3),
    "julio":   (38, 209.6, 206, 221.6),
    "octubre": (38, 268.8, 206, 280.8),
}

CELL_CFG = r"--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789,."


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


def _horizontal_lines(gray):
    """Return y positions of horizontal grid/border lines."""
    th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY_INV, 15, 10)
    w = th.shape[1]
    hor = cv2.erode(th, cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, w // 4), 1)))
    hor = cv2.dilate(hor, cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, w // 4), 1)))
    rowsum = hor.sum(axis=1)
    thr = rowsum.max() * 0.4
    ys, run = [], []
    for y, v in enumerate(rowsum):
        if v >= thr:
            run.append(y)
        elif run:
            ys.append(int(np.mean(run))); run = []
    if run:
        ys.append(int(np.mean(run)))
    return ys


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


def _crop_to_digits(g):
    """Crop a grayscale cell to its digit blobs, discarding grid-line fragments.

    Grid lines appear as full-height thin vertical strips or full-width thin
    horizontal strips touching the cell border; digits are mid-height blobs.
    """
    h, w = g.shape
    _, binv = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(binv, connectivity=8)
    keep = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < 8:
            continue
        # discard grid-line fragments: very tall+thin spanning the cell height,
        # or very wide+thin spanning the cell width
        if bh >= 0.85 * h and bw <= 0.12 * w:
            continue
        if bw >= 0.85 * w and bh <= 0.12 * h:
            continue
        # digit-like height
        if bh < 0.30 * h:
            continue
        keep.append((x, y, bw, bh))
    if not keep:
        return None
    x0 = min(k[0] for k in keep); y0 = min(k[1] for k in keep)
    x1 = max(k[0] + k[2] for k in keep); y1 = max(k[1] + k[3] for k in keep)
    pad = 4
    return g[max(0, y0 - pad):min(h, y1 + pad), max(0, x0 - pad):min(w, x1 + pad)]


def _ocr_cell(cell_img):
    g = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY) if cell_img.ndim == 3 else cell_img
    cropped = _crop_to_digits(g)
    if cropped is None or cropped.size == 0:
        return "", -1.0
    g = cv2.resize(cropped, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    _, th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = cv2.copyMakeBorder(th, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
    data = pytesseract.image_to_data(th, config=CELL_CFG, output_type=pytesseract.Output.DICT)
    toks, confs = [], []
    for t, c in zip(data["text"], data["conf"]):
        t = t.strip()
        if t:
            toks.append(t)
            try:
                confs.append(float(c))
            except ValueError:
                pass
    raw = "".join(toks)
    conf = min(confs) if confs else -1.0
    return raw, conf


def _to_float(raw):
    m = re.search(r"-?\d+(?:[.,]\d+)?", raw.replace(".", ","))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


def extract_band(page, month):
    """Extract one month-band's exterior+interior rows via cell OCR."""
    img = _render(page, BAND_REGIONS[month])
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    col_bounds, pitch = _column_bounds(gray)
    rows = _data_row_bands(gray, col_bounds)
    result = {"exterior": [], "interior": [], "conf_ext": [], "conf_int": [],
              "n_bounds": len(col_bounds), "pitch": round(pitch, 1)}
    for (y0, y1), key in [(rows[0], "exterior"), (rows[1], "interior")]:
        vals, confs = [], []
        for c in range(min(24, len(col_bounds) - 1)):
            cx0, cx1 = col_bounds[c], col_bounds[c + 1]
            # small symmetric inset; connected-component crop isolates digits
            w = cx1 - cx0
            ix0 = int(cx0 + 0.06 * w)
            ix1 = int(cx1 - 0.06 * w)
            cell = img[y0:y1, ix0:ix1]
            if cell.size == 0:
                vals.append(None); confs.append(-1); continue
            raw, conf = _ocr_cell(cell)
            vals.append(_to_float(raw)); confs.append(conf)
        result[key] = vals
        result["conf_" + ("ext" if key == "exterior" else "int")] = confs
    return result


if __name__ == "__main__":
    import sys
    pdf = sys.argv[1] if len(sys.argv) > 1 else "phase0/sample_pdfs/EX_2profile_10_6_1.pdf"
    d = fitz.open(pdf); page = d[5]
    for m in MONTHS:
        r = extract_band(page, m)
        print(f"{m}: bounds={r['n_bounds']} pitch={r['pitch']} ext({len(r['exterior'])})={r['exterior']}")
        print(f"{'':7s} int({len(r['interior'])})={r['interior']}")
    d.close()
