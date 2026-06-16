"""Discovery orchestrator: scrape the MINVU directory into comunas + evaluaciones.

Flow per (region, comuna, tipo):
  search() -> parse total count -> for each result page: parse rows -> upsert
Idempotent: eval_id is deterministic, so re-runs update rather than duplicate.
"""
import logging
import time
from datetime import datetime, timezone

from sqlmodel import select

from informes_cev_minvu_db.db.models import Comunas, Evaluaciones
from informes_cev_minvu_db.db.session import get_session
from informes_cev_minvu_db.discovery import html_parser as hp
from informes_cev_minvu_db.discovery.portal_client import PortalClient

logger = logging.getLogger(__name__)


def sync_comunas(client: PortalClient, region_id: int) -> int:
    """Populate comunas for a region from the portal dropdown."""
    page = client.select_region(region_id)
    comunas = hp.parse_comunas(page)
    with get_session() as s:
        for cid, name in comunas:
            existing = s.get(Comunas, cid)
            if existing is None:
                s.add(Comunas(comuna_id=cid, comuna_nombre=name, region_id=region_id))
            elif existing.region_id != region_id or existing.comuna_nombre != name:
                existing.region_id = region_id
                existing.comuna_nombre = name
                s.add(existing)
        s.commit()
    return len(comunas)


def _upsert_rows(rows: list[dict]) -> int:
    n = 0
    now = datetime.now(timezone.utc)
    with get_session() as s:
        for row in rows:
            existing = s.get(Evaluaciones, row["eval_id"])
            if existing is None:
                s.add(Evaluaciones(**row, pdf_download_status="pending", last_seen_at=now))
                n += 1
            else:
                # refresh the directory summary fields (keep pipeline state)
                for k, v in row.items():
                    if k != "eval_id":
                        setattr(existing, k, v)
                existing.last_seen_at = now  # stamp every time it appears in discovery
                s.add(existing)
        s.commit()
    return n


def discover_comuna(client: PortalClient, region_id: int, comuna_id: int, tipo: int,
                    max_pages: int | None = None, delay: float = 1.0) -> dict:
    """Discover all evaluations for one (region, comuna, tipo). Returns summary."""
    page = client.search(region_id, comuna_id, tipo)
    total = hp.parse_total_count(page, tipo)
    pages = hp.total_pages(total)
    if max_pages:
        pages = min(pages, max_pages)
    new_rows = 0
    seen = 0
    for p in range(1, pages + 1):
        if p > 1:
            page = client.goto_page(region_id, comuna_id, tipo, p)
            time.sleep(delay)
        rows = hp.parse_rows(page, region_id, comuna_id, tipo)
        seen += len(rows)
        new_rows += _upsert_rows(rows)
    return {"region": region_id, "comuna": comuna_id, "tipo": tipo,
            "total_reported": total, "pages": pages, "rows_seen": seen, "rows_new": new_rows}


def discover(region_id: int, comuna_id: int | None = None, tipos=(1, 2),
             max_pages: int | None = None) -> list[dict]:
    """Discover a region (all comunas) or a single comuna, for the given tipos."""
    out = []
    with PortalClient() as client:
        n = sync_comunas(client, region_id)
        logger.info("region %s: %s comunas synced", region_id, n)
        if comuna_id is not None:
            comuna_ids = [comuna_id]
        else:
            with get_session() as s:
                comuna_ids = [c.comuna_id for c in
                              s.exec(select(Comunas).where(Comunas.region_id == region_id)).all()]
        for cid in comuna_ids:
            for tipo in tipos:
                summary = discover_comuna(client, region_id, cid, tipo, max_pages=max_pages)
                logger.info("discovered %s", summary)
                out.append(summary)
    return out
