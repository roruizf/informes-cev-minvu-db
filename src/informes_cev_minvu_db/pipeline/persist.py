"""Persist an extracted report into the detail tables (idempotent per eval_id).

Applies the transform layer: renames legacy extractor keys to schema columns,
resolves string dimensions to FK ids (tipo_vivienda, zona_termica, orientacion,
mes), and normalizes dates. Controlled redundancy (codigo/region_nombre/...) kept.
"""
import logging

from sqlmodel import Session, delete

from informes_cev_minvu_db.db import models as M
from informes_cev_minvu_db.transform import normalize as N

logger = logging.getLogger(__name__)


def _cols(model) -> set[str]:
    return set(model.__table__.columns.keys())


def _apply(model, data: dict) -> dict:
    cols = _cols(model)
    return {k: v for k, v in data.items() if k in cols}


def persist_report(session: Session, eval_id: str, report: dict) -> dict:
    counts: dict = {}

    # ── page 1 ──
    p1 = dict(report.get("pagina1") or {})
    if p1:
        for old, new in N.PAGINA1_RENAME.items():
            if old in p1:
                p1[new] = p1.pop(old)
        p1["tipo_vivienda_id"] = N.tipo_vivienda_id(session, p1.pop("tipo_vivienda", None))
        p1["emitida_el"] = N.parse_chilean_date(p1.get("emitida_el"))
        _replace_single(session, M.InformeV2Pagina1, eval_id, p1)
        counts["pagina1"] = 1

    # ── page 2 ──
    p2 = dict(report.get("pagina2") or {})
    if p2:
        for old, new in N.PAGINA2_RENAME.items():
            if old in p2:
                p2[new] = p2.pop(old)
        p2["tipo_vivienda_id"] = N.tipo_vivienda_id(session, p2.pop("tipo_vivienda", None))
        p2["zona_termica_id"] = N.zona_termica_id(session, p2.pop("zona_termica", None))
        _replace_single(session, M.InformeV2Pagina2, eval_id, p2)
        counts["pagina2"] = 1

    # ── page 3 consumos ──
    p3c = report.get("pagina3_consumos") or {}
    if p3c:
        _replace_single(session, M.InformeV2Pagina3Consumos, eval_id,
                        N.rename_pagina3_consumos(p3c))
        counts["pagina3_consumos"] = 1

    # ── page 7 ──
    p7 = report.get("pagina7") or {}
    if p7:
        _replace_single(session, M.InformeV2Pagina7, eval_id, p7)
        counts["pagina7"] = 1

    # ── page 3 envolvente (multi) ──
    rows = []
    for r in report.get("pagina3_envolvente") or []:
        r = dict(r)
        for old, new in N.PAGINA3E_RENAME.items():
            if old in r:
                r[new] = r.pop(old)
        r["orientacion_id"] = N.orientacion_id(session, r.pop("orientacion", None))
        rows.append(r)
    counts["pagina3_envolvente"] = _replace_multi(session, M.InformeV2Pagina3Envolvente, eval_id, rows)

    # ── page 4 (multi) ──
    rows = []
    for r in report.get("pagina4") or []:
        r = dict(r)
        for old, new in N.PAGINA4_RENAME.items():
            if old in r:
                r[new] = r.pop(old)
        r["mes_id"] = N.mes_id(r.pop("mes_id", r.pop("mes", None)))
        rows.append(r)
    counts["pagina4"] = _replace_multi(session, M.InformeV2Pagina4, eval_id, rows)

    # ── page 5 (multi) ──
    rows = []
    for r in report.get("pagina5") or []:
        r = dict(r)
        r["mes_id"] = N.mes_id(r.pop("mes", None) if "mes" in r else r.pop("mes_id", None))
        rows.append(r)
    counts["pagina5"] = _replace_multi(session, M.InformeV2Pagina5, eval_id, rows)

    # ── page 6 (multi) ──
    rows = []
    for r in report.get("pagina6") or []:
        r = dict(r)
        for old, new in N.PAGINA6_RENAME.items():
            if old in r:
                r[new] = r.pop(old)
        r["mes_id"] = N.mes_id(r.pop("mes", None))
        rows.append(r)
    counts["pagina6"] = _replace_multi(session, M.InformeV2Pagina6, eval_id, rows)

    session.commit()
    return counts


def _replace_single(session, model, eval_id, data):
    existing = session.get(model, eval_id)
    if existing:
        session.delete(existing)
        session.flush()
    session.add(model(**_apply(model, {**data, "eval_id": eval_id})))


def _replace_multi(session, model, eval_id, rows) -> int:
    session.exec(delete(model).where(model.eval_id == eval_id))
    session.flush()
    n = 0
    for r in rows:
        session.add(model(**_apply(model, {**r, "eval_id": eval_id})))
        n += 1
    return n
