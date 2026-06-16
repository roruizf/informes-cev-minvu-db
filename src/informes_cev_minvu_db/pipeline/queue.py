"""Drain the pending-evaluations queue: download → process_pdf → cleanup.

B1: this is the missing link so the system EXTRACTS, not just discovers. Selects
evaluaciones WHERE pdf_download_status='pending', downloads each PDF from MINVU to a
temp file, processes it (extract→validate→persist→status), then deletes the temp PDF.

Failures bump retry_count and set status 'failed' (dead-letter, re-queryable);
after max_retries they stay 'failed' and are skipped by default.
"""
import logging
import time
from pathlib import Path

from sqlalchemy import func
from sqlmodel import select

from informes_cev_minvu_db.config import settings
from informes_cev_minvu_db.db.models import Comunas, Evaluaciones
from informes_cev_minvu_db.db.session import get_session
from informes_cev_minvu_db.pdf.downloader import download_from_minvu
from informes_cev_minvu_db.pipeline.process import process_pdf

logger = logging.getLogger(__name__)


def _pending_eval_ids(region_id: int | None, limit: int | None) -> list[str]:
    """Pending eval_ids in RANDOM order — avoids region/comuna bias if a backfill
    is interrupted (no whole region left unprocessed) and spreads portal load."""
    with get_session() as s:
        q = select(Evaluaciones.eval_id).where(Evaluaciones.pdf_download_status == "pending")
        if region_id is not None:
            comuna_ids = [c.comuna_id for c in
                          s.exec(select(Comunas).where(Comunas.region_id == region_id)).all()]
            q = q.where(Evaluaciones.comuna_id.in_(comuna_ids))
        q = q.order_by(func.random())
        if limit:
            q = q.limit(limit)
        return list(s.exec(q).all())


def _eval_context(eval_id: str):
    """Return (eval_row_snapshot, region_id, comuna_id, tipo) detached from the session."""
    with get_session() as s:
        ev = s.get(Evaluaciones, eval_id)
        if ev is None:
            return None
        comuna = s.get(Comunas, ev.comuna_id)
        region_id = comuna.region_id if comuna else None
        # snapshot the fields the downloader needs (avoid detached-instance access)
        snap = type("EvalSnap", (), {"codigo_informe": ev.codigo_informe})()
        return snap, region_id, ev.comuna_id, ev.tipo_evaluacion_id


def process_one(eval_id: str) -> dict:
    """Download + process a single pending evaluation."""
    ctx = _eval_context(eval_id)
    if ctx is None:
        return {"eval_id": eval_id, "status": "error", "detail": "not found"}
    snap, region_id, comuna_id, tipo = ctx
    if region_id is None:
        return {"eval_id": eval_id, "status": "error", "detail": "no region for comuna"}

    pdf_dir = Path(settings.pdf_dir)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    dest = pdf_dir / f"{eval_id}.pdf"

    ok = download_from_minvu(snap, dest, region_id, comuna_id, tipo)
    if not ok:
        _mark_failed(eval_id, "download failed")
        if dest.exists():
            dest.unlink()
        return {"eval_id": eval_id, "status": "download_failed"}

    # process_pdf updates evaluaciones status; delete temp PDF after.
    result = process_pdf(eval_id, dest, delete_after=True)
    return result


def _mark_failed(eval_id: str, reason: str) -> None:
    with get_session() as s:
        ev = s.get(Evaluaciones, eval_id)
        if ev:
            ev.pdf_download_status = "failed"
            ev.last_error = reason[:300]
            ev.retry_count = (ev.retry_count or 0) + 1
            s.add(ev); s.commit()


def retry_failed(region_id: int | None = None, max_retries: int | None = None,
                 limit: int | None = None) -> dict:
    """Reactivate 'failed' evaluations with retry_count < max_retries → 'pending',
    then drain. Those at/over max_retries stay failed (no infinite loop).

    Some MINVU downloads fail portal-side (expected); this is the on-demand path to
    re-attempt transient failures (portal down, etc.).
    """
    cap = settings.max_retries if max_retries is None else max_retries
    with get_session() as s:
        q = select(Evaluaciones).where(
            Evaluaciones.pdf_download_status == "failed",
            Evaluaciones.retry_count < cap,
        )
        if region_id is not None:
            comuna_ids = [c.comuna_id for c in
                          s.exec(select(Comunas).where(Comunas.region_id == region_id)).all()]
            q = q.where(Evaluaciones.comuna_id.in_(comuna_ids))
        if limit:
            q = q.limit(limit)
        evs = s.exec(q).all()
        reactivated = len(evs)
        for ev in evs:
            ev.pdf_download_status = "pending"
            s.add(ev)
        s.commit()
    logger.info("retry_failed: reactivated %s (max_retries=%s)", reactivated, cap)
    drained = process_pending(region_id=region_id, limit=limit)
    return {"reactivated": reactivated, "max_retries": cap, "drain": drained}


def process_pending(region_id: int | None = None, limit: int | None = None,
                    delay: float | None = None) -> dict:
    """Drain pending evaluations (optionally scoped to a region), in random order.

    Sleeps `delay` seconds between downloads (default settings.download_delay) to be
    polite with the MINVU portal at scale.
    """
    delay = settings.download_delay if delay is None else delay
    ids = _pending_eval_ids(region_id, limit)
    summary = {"selected": len(ids), "extracted": 0, "skipped_v1": 0, "failed": 0}
    for i, eval_id in enumerate(ids):
        try:
            r = process_one(eval_id)
            st = r.get("status")
            if st == "extracted":
                summary["extracted"] += 1
            elif st == "skipped_v1":
                summary["skipped_v1"] += 1
            else:
                summary["failed"] += 1
        except Exception as e:  # noqa: BLE001
            logger.exception("process_pending: %s failed", eval_id)
            _mark_failed(eval_id, str(e))
            summary["failed"] += 1
        if delay and i < len(ids) - 1:
            time.sleep(delay)
    logger.info("process_pending %s", summary)
    return summary
