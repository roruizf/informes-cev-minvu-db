"""Discovery orchestrator: scrape the MINVU directory into comunas + evaluaciones.

Flow per (region, comuna, tipo):
  search() -> parse total count -> for each result page: parse rows -> upsert
Idempotent: eval_id is deterministic, so re-runs update rather than duplicate.

Fase 13 (resilience refactor):
  * PARALLEL discovery — units of work are (comuna, tipo), each scraped by its OWN
    PortalClient in a thread pool (settings.discovery_concurrency). Pages WITHIN a
    unit stay sequential because the portal is VIEWSTATE-stateful.
  * CHECKPOINT — DiscoveryProgress holds one row per (comuna, tipo). A crashed run
    resumes skipping units already 'done'; a partially-paginated unit resumes from
    pages_done+1.
  * EARLY-STOP (incremental) — the portal lists OLDEST-first (txtCampo=0/txtOrden=0,
    verified by the product owner), so new evaluations land on the LAST pages. In
    incremental mode we therefore paginate in REVERSE (last page first); once we hit
    `early_stop_grace` consecutive all-known pages we stop, because everything older
    (lower page numbers) is already in the DB. This is what makes "search only what's
    new" fast instead of re-paginating ~90% of pages. NOTE: early-stop assumes the
    unit was fully scraped in a prior run; a unit that never completed can have gaps
    in its middle pages, which a periodic FULL run (incremental=False) heals.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from sqlmodel import select

from informes_cev_minvu_db.config import settings
from informes_cev_minvu_db.db.models import Comunas, DiscoveryProgress, Evaluaciones
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


def _get_progress(comuna_id: int, tipo: int) -> DiscoveryProgress | None:
    with get_session() as s:
        return s.get(DiscoveryProgress, (comuna_id, tipo))


def _save_progress(region_id: int, comuna_id: int, tipo: int, **fields) -> None:
    """Upsert the DiscoveryProgress row for a (comuna, tipo) unit."""
    with get_session() as s:
        row = s.get(DiscoveryProgress, (comuna_id, tipo))
        if row is None:
            row = DiscoveryProgress(comuna_id=comuna_id, tipo_evaluacion_id=tipo,
                                    region_id=region_id)
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_at = datetime.now(timezone.utc)
        s.add(row)
        s.commit()


def discover_comuna(client: PortalClient, region_id: int, comuna_id: int, tipo: int,
                    max_pages: int | None = None, delay: float = 1.0,
                    incremental: bool = False, resume_from_page: int = 1,
                    early_stop_grace: int = 2) -> dict:
    """Discover all evaluations for one (region, comuna, tipo). Returns summary.

    incremental: paginate in REVERSE (last page first) and stop after
        `early_stop_grace` CONSECUTIVE pages yield 0 new rows. The portal lists
        OLDEST-first, so new evaluations are on the LAST pages; once we hit a run of
        all-known rows the remaining (lower-numbered) pages are older/known. The grace
        window (default 2 pages) tolerates an isolated all-known page interleaved with
        new ones. The default sort params are txtCampo=0 / txtOrden=0 in PortalClient.
    resume_from_page: skip pages already scraped in a prior (crashed) FULL run. Only
        applies to forward (non-incremental) pagination; in incremental reverse mode it
        is ignored — a reverse run always restarts from the last page (cheap, early-stop
        kicks in fast) and a crashed incremental run simply re-runs.
    Updates DiscoveryProgress as it goes so a crash mid-unit can resume.
    """
    page = client.search(region_id, comuna_id, tipo)
    total = hp.parse_total_count(page, tipo)
    pages = hp.total_pages(total)
    if max_pages:
        pages = min(pages, max_pages)
    new_rows = 0
    seen = 0
    early_stopped = False
    zero_streak = 0
    start = max(1, resume_from_page)

    # Incremental: walk last→first so new evals (oldest-first portal) come first and
    # early-stop can short-circuit. Full: walk first→last, honouring resume_from_page.
    page_range = reversed(range(1, pages + 1)) if incremental else range(1, pages + 1)
    pages_done = 0

    for p in page_range:
        if not incremental and p < start:
            continue  # already done in a prior (crashed) full run
        if p > 1:
            page = client.goto_page(region_id, comuna_id, tipo, p)
            time.sleep(delay)
        rows = hp.parse_rows(page, region_id, comuna_id, tipo)
        seen += len(rows)
        page_new = _upsert_rows(rows)
        new_rows += page_new
        pages_done += 1
        # In forward mode pages_done == p (contiguous from 1), so resume picks up at
        # p+1. In reverse (incremental) mode it is just a count of pages processed.
        progress_page = p if not incremental else pages_done
        _save_progress(region_id, comuna_id, tipo, status="pending",
                       pages_done=progress_page, total_pages=pages, rows_new=new_rows,
                       rows_seen=seen, early_stopped=False, last_error=None)
        if incremental and rows:
            zero_streak = zero_streak + 1 if page_new == 0 else 0
            if zero_streak >= early_stop_grace:
                early_stopped = True
                logger.info("comuna %s tipo %s: early-stop at page %s "
                            "(%d consecutive pages with 0 new)",
                            comuna_id, tipo, p, zero_streak)
                break

    _save_progress(region_id, comuna_id, tipo, status="done", total_pages=pages,
                   rows_new=new_rows, rows_seen=seen, early_stopped=early_stopped)
    return {"region": region_id, "comuna": comuna_id, "tipo": tipo,
            "total_reported": total, "pages": pages, "rows_seen": seen,
            "rows_new": new_rows, "early_stopped": early_stopped}


def _discover_unit(region_id: int, comuna_id: int, tipo: int,
                   max_pages: int | None, incremental: bool,
                   resume_from_page: int) -> dict:
    """Scrape one (comuna, tipo) unit with its own PortalClient (thread-safe).

    Each unit gets an independent httpx session + VIEWSTATE, so units run in
    parallel; pages inside a unit stay sequential.
    """
    try:
        with PortalClient() as client:
            return discover_comuna(client, region_id, comuna_id, tipo,
                                   max_pages=max_pages, incremental=incremental,
                                   resume_from_page=resume_from_page)
    except Exception as e:  # noqa: BLE001
        logger.exception("discover unit comuna=%s tipo=%s failed", comuna_id, tipo)
        _save_progress(region_id, comuna_id, tipo, last_error=str(e)[:300])
        return {"region": region_id, "comuna": comuna_id, "tipo": tipo,
                "error": str(e)[:200]}


def discover(region_id: int, comuna_id: int | None = None, tipos=(1, 2),
             max_pages: int | None = None, incremental: bool = False,
             resume: bool = False, concurrency: int | None = None) -> list[dict]:
    """Discover a region (all comunas) or a single comuna, for the given tipos.

    Parallelizes across (comuna, tipo) units (settings.discovery_concurrency).

    incremental: early-stop each unit once a page has 0 new rows (fast re-runs).
    resume: skip units already marked 'done' in DiscoveryProgress, and resume
        partially-done units from where they stopped (crash recovery).
    """
    conc = concurrency or settings.discovery_concurrency

    # sync_comunas primes the comuna list; run it once, serially.
    with PortalClient() as client:
        n = sync_comunas(client, region_id)
    logger.info("region %s: %s comunas synced", region_id, n)

    if comuna_id is not None:
        comuna_ids = [comuna_id]
    else:
        with get_session() as s:
            comuna_ids = [c.comuna_id for c in
                          s.exec(select(Comunas).where(Comunas.region_id == region_id)).all()]

    # Build the unit list, applying resume policy.
    units: list[tuple[int, int, int]] = []  # (comuna_id, tipo, resume_from_page)
    for cid in comuna_ids:
        for tipo in tipos:
            resume_from = 1
            if resume:
                prog = _get_progress(cid, tipo)
                if prog is not None:
                    if prog.status == "done":
                        logger.info("skip comuna %s tipo %s (already done)", cid, tipo)
                        continue
                    resume_from = (prog.pages_done or 0) + 1
            units.append((cid, tipo, resume_from))

    out: list[dict] = []
    if not units:
        return out
    with ThreadPoolExecutor(max_workers=conc) as pool:
        futures = {
            pool.submit(_discover_unit, region_id, cid, tipo, max_pages,
                        incremental, rfp): (cid, tipo)
            for cid, tipo, rfp in units
        }
        for fut in as_completed(futures):
            summary = fut.result()
            logger.info("discovered %s", summary)
            out.append(summary)
    return out
