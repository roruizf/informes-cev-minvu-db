"""Persist an extracted report into the detail tables (idempotent per eval_id)."""
import logging
import re
from datetime import date

from sqlmodel import Session, delete

from informes_cev_minvu_db.db import models as M

logger = logging.getLogger(__name__)

_MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
          "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
          "noviembre": 11, "diciembre": 12}


def _parse_chilean_date(value):
    """Normalize Chilean date strings to date. Accepts DD-MM-YYYY, DD/MM/YYYY,
    and 'DD de <mes> de YYYY'. Returns date or None."""
    if value is None or isinstance(value, date):
        return value
    s = str(value).strip().lower()
    if not s:
        return None
    m = re.match(r"(\d{1,2})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{4})", s)
    if m:
        d, mo, y = (int(g) for g in m.groups())
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    m = re.match(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", s)
    if m and m.group(2) in _MESES:
        try:
            return date(int(m.group(3)), _MESES[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
    return None


_DATE_FIELDS = {"emitida_el"}

_SINGLE = {
    "pagina1": M.InformeV2Pagina1,
    "pagina2": M.InformeV2Pagina2,
    "pagina3_consumos": M.InformeV2Pagina3Consumos,
    "pagina7": M.InformeV2Pagina7,
}
_MULTI = {
    "pagina3_envolvente": M.InformeV2Pagina3Envolvente,
    "pagina4": M.InformeV2Pagina4,
    "pagina5": M.InformeV2Pagina5,
    "pagina6": M.InformeV2Pagina6,
}


def _cols(model) -> set[str]:
    return set(model.__table__.columns.keys())


def _filter(model, data: dict) -> dict:
    cols = _cols(model)
    out = {}
    for k, v in data.items():
        if k not in cols:
            continue
        out[k] = _parse_chilean_date(v) if k in _DATE_FIELDS else v
    return out


def persist_report(session: Session, eval_id: str, report: dict) -> dict:
    """Write all detail rows for one evaluation. Replaces existing rows (idempotent)."""
    counts = {}
    # single-row tables: delete + insert
    for key, model in _SINGLE.items():
        data = report.get(key) or {}
        if not data:
            continue
        existing = session.get(model, eval_id)
        if existing:
            session.delete(existing)
            session.flush()
        row = model(**_filter(model, {**data, "eval_id": eval_id}))
        session.add(row)
        counts[key] = 1
    # multi-row tables: delete all for eval, then insert
    for key, model in _MULTI.items():
        rows = report.get(key) or []
        session.exec(delete(model).where(model.eval_id == eval_id))
        n = 0
        for r in rows:
            session.add(model(**_filter(model, {**r, "eval_id": eval_id})))
            n += 1
        counts[key] = n
    session.commit()
    return counts
