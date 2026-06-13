"""Embedded APScheduler — runs the daily incremental job inside the app process.

Simplest orchestration that satisfies 24/7 on Zeabur (no native cron). The
scheduler is started/stopped via the FastAPI lifespan. Last-run state is kept in
memory for the /health/last-scrape endpoint.
"""
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from informes_cev_minvu_db.config import settings
from informes_cev_minvu_db.pipeline.daily import run_daily

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
LAST_RUN: dict = {"at": None, "summary": None, "error": None}


def _job():
    global LAST_RUN
    try:
        summary = run_daily()
        LAST_RUN = {"at": datetime.now(timezone.utc).isoformat(), "summary": summary, "error": None}
    except Exception as e:  # noqa: BLE001
        logger.exception("daily job failed")
        LAST_RUN = {"at": datetime.now(timezone.utc).isoformat(), "summary": None, "error": str(e)[:300]}


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(_job, "cron", hour=settings.daily_scrape_hour, minute=0,
                       id="daily_incremental", replace_existing=True)
    _scheduler.start()
    logger.info("scheduler started: daily job at %02d:00 UTC", settings.daily_scrape_hour)


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
