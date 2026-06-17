"""FastAPI app with health checks for Zeabur + embedded scheduler."""
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlmodel import func, select

from informes_cev_minvu_db.config import settings
from informes_cev_minvu_db.db.models import DiscoveryProgress, Evaluaciones
from informes_cev_minvu_db.db.session import get_session
from informes_cev_minvu_db import admin_tasks, scheduler


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


def _require_admin(x_admin_token: str | None) -> None:
    """Shared-secret gate for /admin/*. If settings.admin_token is set, the request
    must send a matching X-Admin-Token header; if unset, endpoints are open."""
    if settings.admin_token and x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="invalid or missing admin token")


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
def admin_run_daily(background_tasks: BackgroundTasks,
                    x_admin_token: str | None = Header(default=None)):
    """Trigger the daily incremental job in the background (returns immediately).

    The job can take minutes (live mirror sync over REST); poll /health/last-scrape
    for the result.
    """
    _require_admin(x_admin_token)
    background_tasks.add_task(scheduler._job)
    return {"status": "scheduled", "note": "running in background; see /health/last-scrape"}


@app.post("/admin/run-backfill")
def admin_run_backfill(background_tasks: BackgroundTasks,
                       region: int | None = None,
                       tipo: int | None = None,
                       discover_only: bool = False,
                       max_pages: int | None = None,
                       process_limit: int | None = None,
                       incremental: bool = False,
                       resume: bool = False,
                       x_admin_token: str | None = Header(default=None)):
    """Launch the full backfill (or a single region) as an in-process background
    task — no Zeabur terminal / nohup required. Returns immediately; poll
    /admin/backfill-status for progress.

    Query params:
      region          one region id (1-16); omit for all 16
      tipo            1 or 2; omit for both
      discover_only   discover but don't drain the download queue
      max_pages       cap pages per comuna (testing)
      process_limit   cap PDFs extracted per region
      incremental     early-stop discovery per comuna once a page has 0 new rows
      resume          skip discovery units already 'done' (crash recovery)
    """
    _require_admin(x_admin_token)
    if admin_tasks.is_running():
        raise HTTPException(status_code=409, detail="a backfill is already running; "
                            "see /admin/backfill-status")
    tipos = (tipo,) if tipo else (1, 2)
    background_tasks.add_task(
        admin_tasks.run_backfill_task, region_id=region, tipos=tipos,
        discover_only=discover_only, max_pages=max_pages,
        process_limit=process_limit, incremental=incremental, resume=resume)
    return {"status": "scheduled",
            "note": "running in background; see /admin/backfill-status",
            "params": {"region": region, "tipos": list(tipos),
                       "incremental": incremental, "resume": resume}}


@app.get("/admin/backfill-status")
def admin_backfill_status(x_admin_token: str | None = Header(default=None)):
    """Live backfill state + DB-derived progress (pending downloads, discovery
    units done/total/early-stopped)."""
    _require_admin(x_admin_token)
    out = {"run": admin_tasks.STATE}
    try:
        with get_session() as s:
            out["pending_downloads"] = s.exec(
                select(func.count()).select_from(Evaluaciones)
                .where(Evaluaciones.pdf_download_status == "pending")).one()
            out["failed_downloads"] = s.exec(
                select(func.count()).select_from(Evaluaciones)
                .where(Evaluaciones.pdf_download_status == "failed")).one()
            out["evaluaciones_total"] = s.exec(
                select(func.count()).select_from(Evaluaciones)).one()
            out["discovery_units_total"] = s.exec(
                select(func.count()).select_from(DiscoveryProgress)).one()
            out["discovery_units_done"] = s.exec(
                select(func.count()).select_from(DiscoveryProgress)
                .where(DiscoveryProgress.status == "done")).one()
            out["discovery_units_early_stopped"] = s.exec(
                select(func.count()).select_from(DiscoveryProgress)
                .where(DiscoveryProgress.early_stopped == True)).one()  # noqa: E712
    except Exception as e:  # noqa: BLE001
        out["db_error"] = str(e)[:200]
    return out
