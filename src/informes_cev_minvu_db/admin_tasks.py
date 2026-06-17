"""Background backfill runner for the FastAPI admin endpoints (Fase 13).

Lets the backfill run *inside* the app process (Zeabur) as a background task, so it
no longer depends on an open terminal with `nohup`. A module-level run-state dict
tracks the live run for the status endpoint, and a lock prevents two backfills
overlapping (which would double-hit the portal).
"""
import logging
import threading
from datetime import datetime, timezone

from informes_cev_minvu_db.pipeline.backfill import ALL_REGIONS, backfill

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# Live state for GET /admin/backfill-status. running=True between start and finish.
STATE: dict = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "params": None,
    "summary": None,
    "error": None,
}


def is_running() -> bool:
    return STATE["running"]


def run_backfill_task(region_id: int | None = None, tipos=(1, 2),
                      discover_only: bool = False, max_pages: int | None = None,
                      process_limit: int | None = None, incremental: bool = False,
                      resume: bool = False) -> None:
    """Run a backfill, recording progress in STATE. Intended as a background task.

    Guarded by a lock: a second call while one is running is a no-op (logged).
    """
    if not _lock.acquire(blocking=False):
        logger.warning("backfill requested but one is already running; ignoring")
        return
    try:
        STATE.update({
            "running": True,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "params": {"region_id": region_id, "tipos": list(tipos),
                       "discover_only": discover_only, "max_pages": max_pages,
                       "process_limit": process_limit, "incremental": incremental,
                       "resume": resume},
            "summary": None,
            "error": None,
        })
        regions = [region_id] if region_id is not None else ALL_REGIONS
        logger.info("admin backfill starting: regions=%s incremental=%s resume=%s",
                    regions, incremental, resume)
        summary = backfill(region_id=region_id, tipos=tipos,
                           discover_only=discover_only, max_pages=max_pages,
                           process_limit=process_limit, incremental=incremental,
                           resume=resume)
        STATE["summary"] = summary
        logger.info("admin backfill finished: %s", summary)
    except Exception as e:  # noqa: BLE001
        logger.exception("admin backfill failed")
        STATE["error"] = str(e)[:500]
    finally:
        STATE["running"] = False
        STATE["finished_at"] = datetime.now(timezone.utc).isoformat()
        _lock.release()
