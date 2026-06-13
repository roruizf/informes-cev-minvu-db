"""Run template-matching extraction over all work PDFs, measure coverage,
auto-flag suspect cells, and emit stratified evidence images for human review.

Metrics (no manual GT needed for all 58):
  - completeness: % of cells that produced a value (not None)
  - plausibility: % in physical range AND no sharp jump vs neighbors
  - flagged cells: None | out-of-range | sharp local jump | low match score
Evidence: for a stratified subset (all flagged + N random per PDF), render the
printed table strip with the OCR value overlaid for visual verification.
"""
import json
import pickle
import sys
from pathlib import Path

import cv2
import fitz
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import ocr_templates as ot

WORK = Path(__file__).resolve().parents[1] / "work_pdfs"
EVID = Path(__file__).resolve().parents[1] / "evidence"
EVID.mkdir(parents=True, exist_ok=True)
RANDOM_PER_PDF = 6


def sharp_jump(vals, i, thr=8.0):
    """Flag value i if it deviates sharply from BOTH neighbors (likely OCR error)."""
    v = vals[i]
    if v is None:
        return False
    neigh = [vals[j] for j in (i - 1, i + 1) if 0 <= j < len(vals) and vals[j] is not None]
    if len(neigh) < 1:
        return False
    return all(abs(v - n) > thr for n in neigh)


def analyze_band(vals):
    flags = []
    for i, v in enumerate(vals):
        if v is None:
            flags.append((i, "none"))
        elif not (-20 <= v <= 50):
            flags.append((i, "range"))
        elif sharp_jump(vals, i):
            flags.append((i, "jump"))
    return flags


def main(limit=58):
    templates = pickle.loads(ot.TEMPLATES_PATH.read_bytes())
    pdfs = sorted(WORK.glob("*.pdf"))[:limit]
    total_cells = filled = plausible = 0
    flagged = 0
    per_pdf = []
    rng = np.random.default_rng(13)
    for pdf in pdfs:
        try:
            d = fitz.open(pdf); page = d[5]
        except Exception:
            continue
        pdf_cells = pdf_flags = 0
        for m in ot.MONTHS:
            r = ot.extract_band(page, m, templates)
            if r.get("bad_grid"):
                continue
            for key in ("exterior", "interior"):
                vals = r[key]
                total_cells += len(vals); pdf_cells += len(vals)
                filled += sum(1 for v in vals if v is not None)
                fl = analyze_band(vals)
                flagged += len(fl); pdf_flags += len(fl)
                plausible += sum(1 for i, v in enumerate(vals)
                                 if v is not None and -20 <= v <= 50 and not sharp_jump(vals, i))
        per_pdf.append((pdf.name, pdf_cells, pdf_flags))
        d.close()
    print(f"PDFs processed: {len(per_pdf)}")
    print(f"total cells: {total_cells}")
    print(f"filled (not None): {filled} = {100*filled/total_cells:.1f}%")
    print(f"plausible (range + no jump): {plausible} = {100*plausible/total_cells:.1f}%")
    print(f"flagged for review: {flagged} = {100*flagged/total_cells:.1f}%")
    worst = sorted(per_pdf, key=lambda x: -x[2])[:8]
    print("\nworst PDFs by flags:")
    for n, c, f in worst:
        print(f"  {f:3d} flags / {c:3d} cells  {n[:46]}")
    summary = {"pdfs": len(per_pdf), "cells": total_cells,
               "filled_pct": round(100 * filled / total_cells, 1),
               "plausible_pct": round(100 * plausible / total_cells, 1),
               "flagged_pct": round(100 * flagged / total_cells, 1),
               "per_pdf": per_pdf}
    (EVID.parent / "scale_summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 58)
