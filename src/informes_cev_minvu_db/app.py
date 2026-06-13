"""FastAPI app with health checks for Zeabur + embedded scheduler."""
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlmodel import func, select

from informes_cev_minvu_db.db.models import Evaluaciones
from informes_cev_minvu_db.db.session import get_session
from informes_cev_minvu_db import scheduler


import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Allow disabling the scheduler (e.g. CLI containers, tests) via env.
    if os.environ.get("CEV_ENABLE_SCHEDULER", "1") == "1":
        scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="informes-cev-minvu-db", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@app.get("/health/db")
def health_db():
    try:
        with get_session() as s:
            s.exec(text("SELECT 1"))
        return {"status": "ok", "db": "reachable"}
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "error", "db": str(e)[:200]})


@app.get("/health/last-scrape")
def health_last_scrape():
    try:
        with get_session() as s:
            last = s.exec(select(func.max(Evaluaciones.last_processed_at))).one()
            pending = s.exec(
                select(func.count()).select_from(Evaluaciones)
                .where(Evaluaciones.pdf_download_status == "pending")
            ).one()
        return {"status": "ok",
                "last_processed_at": last.isoformat() if last else None,
                "pending": pending,
                "scheduler_last_run": scheduler.LAST_RUN}
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "error", "detail": str(e)[:200]})


@app.post("/admin/run-daily")
def admin_run_daily(background_tasks: BackgroundTasks):
    """Trigger the daily incremental job in the background (returns immediately).

    The job can take minutes (live mirror sync over REST); poll /health/last-scrape
    for the result.
    """
    background_tasks.add_task(scheduler._job)
    return {"status": "scheduled", "note": "running in background; see /health/last-scrape"}
