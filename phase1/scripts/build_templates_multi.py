"""Enrich digit templates using multiple PDFs.

Seed templates come from the enero ground-truth of the 2-profile example.
We then scan cells across many work PDFs and, for cells that classify with
HIGH confidence (every glyph's correlation >= THRESH and value in physical
range), add their glyphs to the template sample pool. This robustifies
under-sampled digits (5/6/7) without needing more hand-labelled GT.
"""
import pickle
import sys
from pathlib import Path

import cv2
import fitz
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import ocr_templates as ot

WORK = Path(__file__).resolve().parents[1] / "work_pdfs"
HIGH_CONF = 0.55
OUT = Path(__file__).parent / "digit_templates.pkl"


def _glyph_samples_from_cell(cell, templates, pool):
    glyphs = ot._cell_glyphs(cell)
    if not glyphs:
        return
    chars, norms, scores = [], [], []
    for g in glyphs:
        if g[4]:
            chars.append(","); norms.append(None); continue
        ng = ot._norm_glyph(cell, g)
        ch, sc = ot._classify(ng, templates)
        chars.append(ch); norms.append(ng); scores.append(sc)
    s = "".join(chars)
    try:
        val = float(s.replace(",", "."))
    except ValueError:
        return
    if not (-20 <= val <= 50):
        return
    if scores and min(scores) >= HIGH_CONF:
        for ch, ng in zip(chars, norms):
            if ng is not None:
                pool.setdefault(ch, []).append(ng.astype(np.float32))


def main(limit=40):
    # seed
    counts = ot.build_templates("phase0/sample_pdfs/EX_2profile_10_6_1.pdf")
    templates = pickle.loads(OUT.read_bytes())
    print("seed samples/digit:", counts)
    pool = {k: [] for k in "0123456789"}
    pdfs = sorted(WORK.glob("*.pdf"))[:limit]
    for i, pdf in enumerate(pdfs):
        try:
            d = fitz.open(pdf); page = d[5]
            for m in ot.MONTHS:
                cells = ot._iter_cells(page, m)
                if cells is None:
                    continue
                for key in ("exterior", "interior"):
                    for cell in cells[key]:
                        _glyph_samples_from_cell(cell, templates, pool)
            d.close()
        except Exception:
            continue
    # Multi-exemplar: keep the seed mean + K diverse enriched exemplars per digit.
    # Diversity via simple stride sampling over the high-confidence pool.
    K = 12
    exemplars = {}
    for ch in "0123456789":
        ex = []
        if ch in templates:
            ex.append(np.asarray(templates[ch], dtype=np.float32))  # seed mean
        samples = pool.get(ch, [])
        if samples:
            step = max(1, len(samples) // K)
            ex.extend(samples[::step][:K])
        if ex:
            exemplars[ch] = ex
    OUT.write_bytes(pickle.dumps(exemplars))
    print("enriched samples/digit:", {k: len(pool.get(k, [])) for k in "0123456789"})
    print("exemplars/digit:", {k: len(v) for k, v in exemplars.items()})


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
