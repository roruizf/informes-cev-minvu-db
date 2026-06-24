"""Read-only DB diagnostic: fixed queries that summarize pipeline health.

Single source of truth for the diagnostic SQL, shared by the CLI (`cev diagnostic`)
and the HTTP endpoint (GET /admin/db-diagnostic). No arbitrary SQL — every query is
hardcoded here — and no DATABASE_URL/credentials are ever returned.

Output is a stable JSON-able dict so external agents (Claude Code, OpenCode) can
diff it over time:

    {
      "ok": true,
      "ts": "2026-06-24T...Z",
      "evaluaciones": {"total": N, "by_status": {...}, "by_report_version": {...},
                       "unsynced": N},
      "detail_tables": {"informe_v2_pagina1": N, ...},
      "discovery_progress": {"by_status": {...}, "by_early_stopped": {...}},
      "pagina1_nulls": {"superficie_interior_util_m2": N, "emitida_el": N,
                        "demanda_calefaccion_kwh_m2_ano": N},
    }
"""
from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import select

from informes_cev_minvu_db.db import models as M
from informes_cev_minvu_db.db.session import get_session

# Detail tables counted generically (name comes from the model, not a literal).
_DETAIL_MODELS = (
    M.InformeV2Pagina1, M.InformeV2Pagina2, M.InformeV2Pagina3Consumos,
    M.InformeV2Pagina3Envolvente, M.InformeV2Pagina4, M.InformeV2Pagina5,
    M.InformeV2Pagina6, M.InformeV2Pagina7,
)

# Página-1 critical columns to null-check (model attrs → stable JSON keys).
_PAGINA1_NULL_CHECKS = (
    "superficie_interior_util_m2",
    "emitida_el",
    "demanda_calefaccion_kwh_m2_ano",
)


def _count(s, model) -> int:
    return s.exec(select(func.count()).select_from(model)).one()


def _group_counts(s, model, column) -> dict:
    """{column_value (as str): count} for a GROUP BY column."""
    rows = s.exec(select(column, func.count()).group_by(column)).all()
    return {("null" if k is None else str(k)): n for k, n in rows}


def diagnostic() -> dict:
    """Run all diagnostic queries in one session. Raises on DB error (callers wrap)."""
    with get_session() as s:
        total = _count(s, M.Evaluaciones)
        by_status = _group_counts(s, M.Evaluaciones, M.Evaluaciones.pdf_download_status)
        by_version = _group_counts(s, M.Evaluaciones, M.Evaluaciones.report_version)
        # drop the NULL bucket from versions (un-extracted evals have no version)
        by_version.pop("null", None)
        unsynced = s.exec(
            select(func.count()).select_from(M.Evaluaciones)
            .where(M.Evaluaciones.synced_to_mirror_at.is_(None))
        ).one()

        detail = {m.__tablename__: _count(s, m) for m in _DETAIL_MODELS}

        dp_status = _group_counts(s, M.DiscoveryProgress, M.DiscoveryProgress.status)
        dp_early = _group_counts(s, M.DiscoveryProgress, M.DiscoveryProgress.early_stopped)

        p1_nulls = {}
        for attr in _PAGINA1_NULL_CHECKS:
            col = getattr(M.InformeV2Pagina1, attr)
            p1_nulls[attr] = s.exec(
                select(func.count()).select_from(M.InformeV2Pagina1)
                .where(col.is_(None))
            ).one()

    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        "evaluaciones": {
            "total": total,
            "by_status": by_status,
            "by_report_version": by_version,
            "unsynced": unsynced,
        },
        "detail_tables": detail,
        "discovery_progress": {
            "by_status": dp_status,
            "by_early_stopped": dp_early,
        },
        "pagina1_nulls": p1_nulls,
    }
