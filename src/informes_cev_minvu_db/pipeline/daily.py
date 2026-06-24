"""Daily incremental job (stable phase).

Chains: discover NEW evaluaciones across the 16 regions (incremental: reverse
pagination + early-stop), then process any pending evaluaciones that have a PDF
source, sync the mirror, and clean orphan PDFs.

This is intentionally simple (Roberto: simplicity over services). The massive
initial backfill is a one-shot CLI run, not this job; the daily tick only picks up
what is newly published (last pages of the oldest-first portal).
"""
import logging

from sqlmodel import select

from informes_cev_minvu_db.db.models import Evaluaciones
from informes_cev_minvu_db.db.session import get_session
from informes_cev_minvu_db.discovery.run import discover
from informes_cev_minvu_db.mirror.sync import run_sync
from informes_cev_minvu_db.pipeline.cleanup import cleanup_orphans

logger = logging.getLogger(__name__)

ALL_REGIONS = list(range(1, 17))


def count_pending() -> int:
    with get_session() as s:
        return len(s.exec(
            select(Evaluaciones.eval_id).where(Evaluaciones.pdf_download_status == "pending")
        ).all())


def run_discovery(tipos=(1, 2)) -> dict:
    """Incremental discovery across all 16 regions (reverse pagination + early-stop).

    resume=True skips comuna/tipo units already marked 'done' in DiscoveryProgress so
    a crashed daily run picks up where it stopped. Returns per-region new-row counts.
    Each region is independent; a failure in one is logged and does not abort the rest.
    """
    out: dict = {"new_total": 0, "regions": {}}
    for rid in ALL_REGIONS:
        try:
            disc = discover(rid, tipos=tipos, incremental=True, resume=True)
            n_new = sum(d.get("rows_new", 0) for d in disc)
            n_err = sum(1 for d in disc if d.get("error"))
            out["regions"][rid] = {"new": n_new, "units": len(disc), "unit_errors": n_err}
            out["new_total"] += n_new
        except Exception as e:  # noqa: BLE001
            logger.exception("daily discovery region %s failed", rid)
            out["regions"][rid] = {"error": str(e)[:200]}
    return out


def run_daily(sync_limit: int | None = None, process_limit: int | None = None,
              discover: bool = True) -> dict:
    """Stable-phase daily tick: discover new → drain pending → mirror → housekeeping.

    Returns a summary dict (also used by /health/last-scrape style reporting).
    process_limit caps how many pending PDFs to extract per tick (None = all).
    discover=False skips the discovery step (e.g. to only drain a backlog).
    """
    from informes_cev_minvu_db.pipeline.queue import process_pending

    summary = {}
    # 0) discover newly published evals so the pending queue has fresh work
    if discover:
        summary["discovery"] = run_discovery()
    summary["pending_before"] = count_pending()
    # 1) drain the pending queue: download → extract → persist (B1)
    summary["process"] = process_pending(limit=process_limit)
    # 2) mirror anything extracted-but-not-synced (incremental)
    summary["mirror"] = run_sync(limit=sync_limit, full=False)
    # 3) housekeeping
    summary["cleanup"] = cleanup_orphans()
    logger.info("daily job: %s", summary)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run_daily())
