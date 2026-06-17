"""One-shot backfill: discover a region (or all 16) then drain the pending queue.

B3: orchestrates discovery + extraction for the initial mass load (~156K). For the
stable phase use the daily scheduler instead. Reuses discovery.run.discover (B1's
process_pending drains what discovery enqueues).

Fase 13: discovery is now parallel + checkpointed (DiscoveryProgress). Pass
incremental=True for fast "only what's new" runs (early-stop per comuna), and
resume=True to skip units already completed after a crash/outage.
"""
import logging

from informes_cev_minvu_db.discovery.run import discover
from informes_cev_minvu_db.pipeline.queue import process_pending

logger = logging.getLogger(__name__)

ALL_REGIONS = list(range(1, 17))


def backfill(region_id: int | None = None, tipos=(1, 2),
             discover_only: bool = False, max_pages: int | None = None,
             process_limit: int | None = None, incremental: bool = False,
             resume: bool = False) -> dict:
    """Backfill one region (region_id) or all 16 (region_id=None).

    Per region: discover (populate comunas + evaluaciones) then process pending.
    incremental: early-stop discovery per comuna once a page yields 0 new rows.
    resume: skip discovery units already 'done' (crash/outage recovery).
    """
    regions = [region_id] if region_id is not None else ALL_REGIONS
    summary = {"regions": {}}
    for rid in regions:
        disc = discover(rid, tipos=tipos, max_pages=max_pages,
                        incremental=incremental, resume=resume)
        n_new = sum(d.get("rows_new", 0) for d in disc)
        n_err = sum(1 for d in disc if d.get("error"))
        entry = {"discovered_new": n_new, "units": len(disc), "unit_errors": n_err}
        if not discover_only:
            entry["process"] = process_pending(region_id=rid, limit=process_limit)
        summary["regions"][rid] = entry
        logger.info("backfill region %s: %s", rid, entry)
    return summary
