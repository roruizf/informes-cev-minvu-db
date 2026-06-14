"""Sync job: push CEV data from Postgres to the NoCodeBackend mirror.

Incremental: selects evaluaciones with synced_to_mirror_at IS NULL (or all with
--full), mirrors their directory row + all detail rows + the dimensional tables,
then stamps synced_to_mirror_at. EXCLUDES busquedas/paginas_html (scraping mechanics).

Detail rows are pushed with their own business keys so the mirror is self-contained.
For multi-row detail tables we use a composite text key column `mirror_key`
(eval_id + discriminator) so incremental upsert can find the exact row.
"""
import logging
from datetime import date, datetime, timezone

from sqlmodel import select

from informes_cev_minvu_db.db import models as M
from informes_cev_minvu_db.db.session import get_session
from informes_cev_minvu_db.mirror.nocode import NocodeMirror

logger = logging.getLogger(__name__)

# dimensional tables: small, full upsert by their natural key.
# (orientaciones/tipos_vivienda/zonas_termicas removed — now raw text in pages.)
_DIMS = [
    ("regiones", M.Regiones, "region_id"),
    ("comunas", M.Comunas, "comuna_id"),
    ("tipos_evaluacion", M.TiposEvaluacion, "tipo_evaluacion_id"),
    ("meses", M.Meses, "mes_id"),
]
_SINGLE = [
    ("informe_v2_pagina1", M.InformeV2Pagina1),
    ("informe_v2_pagina2", M.InformeV2Pagina2),
    ("informe_v2_pagina3_consumos", M.InformeV2Pagina3Consumos),
    ("informe_v2_pagina7", M.InformeV2Pagina7),
]
_MULTI = [
    ("informe_v2_pagina3_envolvente", M.InformeV2Pagina3Envolvente,
     lambda r: f"{r.eval_id}:{r.orientacion_nombre}"),
    ("informe_v2_pagina4", M.InformeV2Pagina4, lambda r: f"{r.eval_id}:{r.mes_id}"),
    ("informe_v2_pagina5", M.InformeV2Pagina5, lambda r: f"{r.eval_id}:{r.mes_id}"),
    ("informe_v2_pagina6", M.InformeV2Pagina6, lambda r: f"{r.eval_id}:{r.mes_id}:{r.hora}"),
]


def _dump(obj) -> dict:
    # SQLModel public API; serialize dates below.
    return obj.model_dump()


def _serialize(d: dict) -> dict:
    """JSON-safe: dates/datetimes → iso strings."""
    out = {}
    for k, v in d.items():
        if isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def sync_dimensions(mirror: NocodeMirror) -> dict:
    summary = {}
    with get_session() as s:
        for table, model, key in _DIMS:
            rows = [_serialize(_dump(o)) for o in s.exec(select(model)).all()]
            if not rows:
                summary[table] = "no rows"
                continue
            mirror.ensure_table(table, rows)
            summary[table] = mirror.upsert(table, rows, key=key)
    return summary


def sync_evaluations(mirror: NocodeMirror, limit: int | None = None, full: bool = False) -> dict:
    """Mirror evaluaciones (directory) + detail rows for pending evals."""
    with get_session() as s:
        q = select(M.Evaluaciones)
        if not full:
            q = q.where(M.Evaluaciones.synced_to_mirror_at.is_(None))
        if limit:
            q = q.limit(limit)
        evals = s.exec(q).all()
        eval_ids = [e.eval_id for e in evals]
        if not eval_ids:
            return {"evaluaciones": 0, "note": "nothing to sync"}

        # directory rows
        dir_rows = [_serialize(_dump(e)) for e in evals]
        mirror.ensure_table("evaluaciones", dir_rows)
        summary = {"evaluaciones": mirror.upsert("evaluaciones", dir_rows, key="eval_id")}

        # single-row detail tables
        for table, model in _SINGLE:
            rows = [_serialize(_dump(o)) for o in
                    s.exec(select(model).where(model.eval_id.in_(eval_ids))).all()]
            if rows:
                mirror.ensure_table(table, rows)
                summary[table] = mirror.upsert(table, rows, key="eval_id")

        # multi-row detail tables (composite mirror_key)
        for table, model, keyfn in _MULTI:
            objs = s.exec(select(model).where(model.eval_id.in_(eval_ids))).all()
            rows = []
            for o in objs:
                d = _serialize(_dump(o))
                d["mirror_key"] = keyfn(o)
                rows.append(d)
            if rows:
                mirror.ensure_table(table, rows)
                summary[table] = mirror.upsert(table, rows, key="mirror_key")

        # stamp synced
        now = datetime.now(timezone.utc)
        for e in evals:
            e.synced_to_mirror_at = now
            s.add(e)
        s.commit()
    return summary


def run_sync(limit: int | None = None, full: bool = False) -> dict:
    mirror = NocodeMirror()
    if not mirror.enabled:
        return {"error": "mirror not configured (NOCODEBACKEND_INSTANCE/SECRET_KEY missing)"}
    dims = sync_dimensions(mirror)
    evals = sync_evaluations(mirror, limit=limit, full=full)
    return {"dimensions": dims, "evaluations": evals}
