"""Extract a full v2 report into a structured dict, ready for persistence.

Pages 1-5,7 via coordinate extractor; page 6 via template-matching OCR.
Includes a validation summary used by the pipeline to decide persist vs flag.
"""
import logging

import fitz

from informes_cev_minvu_db.pdf import extractor as ex
from informes_cev_minvu_db.pdf.ocr_page6 import extract_page6

logger = logging.getLogger(__name__)
MES_NOMBRE = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
              7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}


def extract_report(pdf_path) -> dict:
    """Return {pagina1, pagina2, pagina3_consumos, pagina3_envolvente(list),
    pagina4(list), pagina5(list), pagina6(list), pagina7, _validation}."""
    doc = fitz.open(pdf_path)
    try:
        out = {
            "pagina1": ex.get_informe_cev_v2_pagina1_as_dict(doc),
            "pagina2": ex.get_informe_cev_v2_pagina2_as_dict(doc),
            "pagina3_consumos": ex.get_informe_cev_v2_pagina3_consumos_as_dict(doc),
            "pagina3_envolvente": _rows_from_listdict(ex.get_informe_cev_v2_pagina3_envolvente_as_dict(doc)),
            "pagina4": _pagina4_rows(ex.get_informe_cev_v2_pagina4_as_dict(doc)),
            "pagina5": _rows_from_listdict(ex.get_informe_cev_v2_pagina5_as_dict(doc)),
            "pagina7": ex.get_informe_cev_v2_pagina7_as_dict(doc),
        }
    finally:
        doc.close()
    out["pagina6"] = _pagina6_rows(extract_page6(pdf_path))
    out["_validation"] = _validate(out)
    return out


def _rows_from_listdict(d: dict) -> list[dict]:
    """Convert {col: [v0,v1,...]} into [{col: v0}, {col: v1}, ...]."""
    if not d:
        return []
    keys = [k for k in d if k != "codigo_evaluacion"]
    n = max((len(d[k]) for k in keys), default=0)
    rows = []
    for i in range(n):
        rows.append({k: (d[k][i] if i < len(d[k]) else None) for k in keys})
    return rows


def _pagina4_rows(d: dict) -> list[dict]:
    rows = _rows_from_listdict(d)
    return rows


def _pagina6_rows(months: dict) -> list[dict]:
    """months = {mes: {exterior:[24], interior:[24], conf_*}} -> 24-hour rows per month."""
    rows = []
    for mes, band in months.items():
        ext = band.get("exterior", [None] * 24)
        intr = band.get("interior", [None] * 24)
        ce = band.get("conf_ext", [-1] * 24)
        ci = band.get("conf_int", [-1] * 24)
        for h in range(24):
            low_conf = (ext[h] is None or intr[h] is None
                        or (ce[h] >= 0 and ce[h] < 0.45) or (ci[h] >= 0 and ci[h] < 0.45))
            rows.append({"mes": mes.capitalize(), "hora": h,
                         "temp_exterior": ext[h], "temp_interior": intr[h],
                         "ocr_low_confidence": bool(low_conf)})
    return rows


def _validate(out: dict) -> dict:
    """Lightweight checks used by the pipeline (correctness validated elsewhere)."""
    p1 = out.get("pagina1") or {}
    p6 = out.get("pagina6") or []
    p6_vals = sum(1 for r in p6 if r["temp_exterior"] is not None and r["temp_interior"] is not None)
    p6_lowconf = sum(1 for r in p6 if r["ocr_low_confidence"])
    return {
        "has_codigo": bool(p1.get("codigo_evaluacion")),
        "has_letra": bool(p1.get("letra_eficiencia_energetica_dem")),
        "p6_rows": len(p6),               # expect 96 (4 months x 24h)
        "p6_filled": p6_vals,             # expect 192 (2 series x 96)... here counts rows fully filled
        "p6_low_confidence": p6_lowconf,
        "ok": bool(p1.get("codigo_evaluacion")) and len(p6) == 96,
    }
