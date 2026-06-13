"""Orphan PDF cleanup: remove local working PDFs older than N days.

Preventive only — the pipeline already deletes each PDF after extract+persist
(delete_after). This sweeps anything left behind by crashes/retries. The system
NEVER touches Google Drive (Roberto deletes Drive manually).
"""
import logging
import time
from pathlib import Path

from informes_cev_minvu_db.config import settings

logger = logging.getLogger(__name__)


def cleanup_orphans(pdf_dir: str | None = None, older_than_days: int | None = None) -> dict:
    pdf_dir = Path(pdf_dir or settings.pdf_dir)
    days = older_than_days if older_than_days is not None else settings.pdf_cleanup_days
    if not pdf_dir.exists():
        return {"dir": str(pdf_dir), "removed": 0, "note": "dir does not exist"}
    cutoff = time.time() - days * 86400
    removed = 0
    freed = 0
    for pdf in pdf_dir.glob("*.pdf"):
        try:
            st = pdf.stat()
            if st.st_mtime < cutoff:
                freed += st.st_size
                pdf.unlink()
                removed += 1
        except OSError as e:  # noqa: PERF203
            logger.warning("cleanup: could not remove %s: %s", pdf, e)
    return {"dir": str(pdf_dir), "older_than_days": days, "removed": removed,
            "freed_mb": round(freed / 1_048_576, 1)}


if __name__ == "__main__":
    print(cleanup_orphans())
