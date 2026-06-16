"""One-shot backfill: discover a region (or all 16) then drain the pending queue.

B3: orchestrates discovery + extraction for the initial mass load (~156K). For the
stable phase use the daily scheduler instead. Reuses discovery.run.discover (B1's
process_pending drains what discovery enqueues).
"""
import logging

from informes_cev_minvu_db.discovery.run import discover
from informes_cev_minvu_db.pipeline.queue import process_pending

logger = logging.getLogger(__name__)

ALL_REGIONS = list(range(1, 17))


def backfill(region_id: int | None = None, tipos=(1, 2),
             discover_only: bool = False, max_pages: int | None = None,
             process_limit: int | None = None) -> dict:
    """Backfill one region (region_id) or all 16 (region_id=None).

    Per region: discover (populate comunas + evaluaciones) then process pending.
    """
    regions = [region_id] if region_id is not None else ALL_REGIONS
    summary = {"regions": {}}
    for rid in regions:
        disc = discover(rid, tipos=tipos, max_pages=max_pages)
        n_new = sum(d.get("rows_new", 0) for d in disc)
        entry = {"discovered_new": n_new}
        if not discover_only:
            entry["process"] = process_pending(region_id=rid, limit=process_limit)
        summary["regions"][rid] = entry
        logger.info("backfill region %s: %s", rid, entry)
    return summary
