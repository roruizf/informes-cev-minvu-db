"""FastAPI app with health checks for Zeabur."""
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlmodel import func, select

from informes_cev_minvu_db.db.models import Evaluaciones
from informes_cev_minvu_db.db.session import get_session

app = FastAPI(title="informes-cev-minvu-db", version="0.1.0")


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
        return {"status": "ok", "last_processed_at": last.isoformat() if last else None,
                "pending": pending}
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "error", "detail": str(e)[:200]})
