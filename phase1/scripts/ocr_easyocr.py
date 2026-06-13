"""Variant 7: EasyOCR on each full row image, then bin detections into the 24
columns by x-center using the detected grid bounds.

EasyOCR returns (bbox, text, conf) per detected token with precise positions,
which sidesteps the per-cell segmentation fragility of Tesseract.
"""
import re
import sys
from pathlib import Path

import cv2
import fitz
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from ocr_page6 import _column_bounds, _data_row_bands, _render, BAND_REGIONS, MONTHS

import easyocr  # noqa: E402

_READER = None


def reader():
    global _READER
    if _READER is None:
        _READER = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _READER


def _parse_num(t):
    t = t.replace(" ", "").replace("O", "0").replace("o", "0")
    m = re.search(r"-?\d+[.,]?\d*", t)
    if not m:
        return None
    s = m.group(0).replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return v


def extract_band_easyocr(page, month):
    img = _render(page, BAND_REGIONS[month])
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    col_bounds, pitch = _column_bounds(gray)
    rows = _data_row_bands(gray, col_bounds)
    if len(col_bounds) < 25:
        return {"exterior": [None] * 24, "interior": [None] * 24, "bad_grid": True}
    centers = [(col_bounds[c] + col_bounds[c + 1]) / 2 for c in range(24)]
    out = {}
    for (y0, y1), key in [(rows[0], "exterior"), (rows[1], "interior")]:
        strip = img[max(0, y0 - 4):y1 + 4, col_bounds[0]:col_bounds[-1]]
        x_off = col_bounds[0]
        # upscale for small digits
        strip2 = cv2.resize(strip, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        results = reader().readtext(strip2, allowlist="0123456789.,-",
                                    detail=1, paragraph=False)
        # map detections back to original x (divide by 3) + offset
        slots = [None] * 24
        slotconf = [-1.0] * 24
        for bbox, text, conf in results:
            xs = [p[0] for p in bbox]
            xc = (min(xs) + max(xs)) / 2 / 3.0 + x_off
            val = _parse_num(text)
            if val is None:
                continue
            # nearest column center
            ci = min(range(24), key=lambda i: abs(centers[i] - xc))
            if conf > slotconf[ci]:
                slots[ci] = val
                slotconf[ci] = conf
        out[key] = slots
        out["conf_" + ("ext" if key == "exterior" else "int")] = slotconf
    out["pitch"] = round(pitch, 1)
    return out


def extract_band_easyocr_percell(page, month):
    """Variant 8: EasyOCR on each cell individually (best recognition + forced split)."""
    img = _render(page, BAND_REGIONS[month])
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    col_bounds, pitch = _column_bounds(gray)
    rows = _data_row_bands(gray, col_bounds)
    out = {"pitch": round(pitch, 1)}
    if len(col_bounds) < 25:
        out["exterior"] = [None] * 24; out["interior"] = [None] * 24
        out["bad_grid"] = True
        return out
    rd = reader()
    for (y0, y1), key in [(rows[0], "exterior"), (rows[1], "interior")]:
        vals, confs = [], []
        for c in range(24):
            cx0, cx1 = col_bounds[c], col_bounds[c + 1]
            w = cx1 - cx0
            cell = img[max(0, y0 - 3):y1 + 3, int(cx0 + 0.04 * w):int(cx1 - 0.04 * w)]
            if cell.size == 0:
                vals.append(None); confs.append(-1); continue
            cell2 = cv2.resize(cell, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
            res = rd.readtext(cell2, allowlist="0123456789.,-", detail=1, paragraph=False)
            best, bestc = None, -1.0
            for _bbox, text, conf in res:
                v = _parse_num(text)
                if v is not None and conf > bestc:
                    best, bestc = v, conf
            vals.append(best); confs.append(bestc)
        out[key] = vals
        out["conf_" + ("ext" if key == "exterior" else "int")] = confs
    return out


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "phase0/sample_pdfs/EX_2profile_10_6_1.pdf"
    mode = sys.argv[2] if len(sys.argv) > 2 else "percell"
    GT_ext = [11.9, 10.9, 10.4, 10.0, 10.0, 11.0, 12.6, 14.6, 16.6, 18.3, 19.9, 20.9,
              21.8, 22.3, 22.5, 22.3, 21.7, 20.8, 19.5, 18.2, 16.9, 15.6, 14.3, 13.0]
    GT_int = [23.0, 22.3, 21.5, 20.9, 20.2, 19.8, 19.4, 19.6, 20.1, 21.0, 21.9, 23.1,
              24.1, 25.0, 25.8, 26.4, 26.5, 27.0, 26.9, 26.5, 26.0, 25.3, 24.5, 23.8]
    d = fitz.open(pdf); page = d[5]
    r = extract_band_easyocr_percell(page, "enero") if mode == "percell" else extract_band_easyocr(page, "enero")

    def acc(got, gt):
        return sum(1 for g, t in zip(got, gt) if g is not None and abs(g - t) < 0.05), len(gt)
    print("ext:", r["exterior"]); print("   acc:", acc(r["exterior"], GT_ext))
    print("int:", r["interior"]); print("   acc:", acc(r["interior"], GT_int))
    d.close()
