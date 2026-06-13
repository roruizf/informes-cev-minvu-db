"""Daily incremental job (stable phase).

Chains: process any pending evaluaciones that already have a PDF source, sync the
mirror, and clean orphan PDFs. Discovery of NEW evals is invoked separately
(per-region) since it is the heavier, rate-sensitive step; the daily job focuses
on draining the pending queue + mirroring + housekeeping.

This is intentionally simple (Roberto: simplicity over services). The massive
initial backfill is a one-shot CLI run, not this job.
"""
import logging

from sqlmodel import select

from informes_cev_minvu_db.db.models import Evaluaciones
from informes_cev_minvu_db.db.session import get_session
from informes_cev_minvu_db.mirror.sync import run_sync
from informes_cev_minvu_db.pipeline.cleanup import cleanup_orphans

logger = logging.getLogger(__name__)


def count_pending() -> int:
    with get_session() as s:
        return len(s.exec(
            select(Evaluaciones.eval_id).where(Evaluaciones.pdf_download_status == "pending")
        ).all())


def run_daily(sync_limit: int | None = None) -> dict:
    """Stable-phase daily tick: mirror newly-extracted data + housekeeping.

    Returns a summary dict (also used by /health/last-scrape style reporting).
    """
    summary = {}
    summary["pending_before"] = count_pending()
    # mirror anything extracted-but-not-synced (incremental)
    summary["mirror"] = run_sync(limit=sync_limit, full=False)
    # housekeeping
    summary["cleanup"] = cleanup_orphans()
    logger.info("daily job: %s", summary)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run_daily())
