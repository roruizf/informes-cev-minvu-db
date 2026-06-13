"""Pipeline: acquire → detect version → extract → validate → persist → cleanup.

Policy (Phase-4): extract → validate → persist → THEN delete the PDF. For the
irreplaceable Drive backfill, the Drive copy is not deleted until persisted;
the local temp file is always removed after processing.
"""
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session

from informes_cev_minvu_db.db.models import Evaluaciones
from informes_cev_minvu_db.db.session import get_session
from informes_cev_minvu_db.pdf.extract_all import extract_report
from informes_cev_minvu_db.pdf.version_detect import detect_version
from informes_cev_minvu_db.pipeline.persist import persist_report

logger = logging.getLogger(__name__)


def process_pdf(eval_id: str, pdf_path: str | Path, *, delete_after: bool = False) -> dict:
    """Process a single local PDF for a known eval_id. Updates evaluaciones state.

    Returns a summary dict. Does not delete the source unless delete_after=True.
    """
    pdf_path = Path(pdf_path)
    version = detect_version(pdf_path)
    now = datetime.now(timezone.utc)

    with get_session() as s:
        ev = s.get(Evaluaciones, eval_id)
        if ev is None:
            return {"eval_id": eval_id, "error": "eval_id not found in evaluaciones"}

        if version == 1:
            ev.report_version = 1
            ev.pdf_download_status = "skipped_v1"
            ev.last_processed_at = now
            s.add(ev); s.commit()
            return {"eval_id": eval_id, "version": 1, "status": "skipped_v1"}
        if version != 2:
            ev.pdf_download_status = "failed"
            ev.last_error = f"unrecognized version (pages={version})"
            ev.retry_count += 1
            s.add(ev); s.commit()
            return {"eval_id": eval_id, "version": version, "status": "failed"}

        try:
            report = extract_report(pdf_path)
        except Exception as e:  # noqa: BLE001
            ev.pdf_download_status = "failed"
            ev.last_error = str(e)[:300]
            ev.retry_count += 1
            s.add(ev); s.commit()
            return {"eval_id": eval_id, "status": "failed", "error": str(e)[:200]}

        val = report.get("_validation", {})
        if not val.get("ok"):
            ev.pdf_download_status = "failed"
            ev.last_error = f"validation failed: {val}"
            ev.retry_count += 1
            s.add(ev); s.commit()
            return {"eval_id": eval_id, "status": "failed", "validation": val}

        counts = persist_report(s, eval_id, report)
        ev.report_version = 2
        ev.pdf_download_status = "extracted"
        ev.last_processed_at = now
        ev.last_error = None
        s.add(ev); s.commit()

    if delete_after and pdf_path.exists():
        pdf_path.unlink()

    return {"eval_id": eval_id, "version": 2, "status": "extracted",
            "rows": counts, "validation": val}


def _ensure_eval(session: Session, eval_id: str, comuna_id: int = 12,
                 tipo: int = 2, ident: str = "TEST") -> None:
    """Insert a minimal eval row if missing (used for local pipeline tests)."""
    if session.get(Evaluaciones, eval_id) is None:
        session.add(Evaluaciones(eval_id=eval_id, comuna_id=comuna_id,
                                 tipo_evaluacion_id=tipo, identificacion_vivienda=ident,
                                 pdf_download_status="pending"))
        session.commit()
