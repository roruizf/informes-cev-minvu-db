"""CLI entrypoints. Phase 2: init-db + seed. Later phases add backfill/daily/sync."""
import argparse

from informes_cev_minvu_db.db.seed import seed
from informes_cev_minvu_db.db.session import create_all


def main() -> None:
    p = argparse.ArgumentParser(prog="informes-cev-minvu-db")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db", help="create all tables")
    sub.add_parser("seed", help="seed reference tables (regiones, tipos)")
    sub.add_parser("init", help="init-db + seed")
    d = sub.add_parser("discover", help="scrape MINVU directory into evaluaciones")
    d.add_argument("--region", type=int, required=True)
    d.add_argument("--comuna", type=int, default=None, help="single comuna id (optional)")
    d.add_argument("--tipo", type=int, choices=[1, 2], default=None, help="1, 2, or both")
    d.add_argument("--max-pages", type=int, default=None, help="cap result pages (testing)")
    d.add_argument("--incremental", action="store_true",
                   help="early-stop each comuna once a page yields 0 new rows")
    d.add_argument("--resume", action="store_true",
                   help="skip discovery units already 'done' (crash recovery)")
    pp = sub.add_parser("process-pdf", help="process one local PDF end-to-end")
    pp.add_argument("--eval-id", required=True)
    pp.add_argument("--path", required=True)
    pp.add_argument("--ensure-eval", action="store_true", help="insert a stub eval row if missing")
    sub.add_parser("mirror-init", help="create all NoCodeBackend tables via MCP (run once, where MCP works)")
    sm = sub.add_parser("sync-mirror", help="push data to NoCodeBackend (incremental)")
    sm.add_argument("--limit", type=int, default=None)
    sm.add_argument("--full", action="store_true", help="re-sync all (ignore synced flag)")
    sub.add_parser("cleanup", help="remove orphan local PDFs older than N days")
    sub.add_parser("daily", help="run the daily incremental job once")
    pq = sub.add_parser("process-pending", help="drain the pending queue (download+extract)")
    pq.add_argument("--region", type=int, default=None)
    pq.add_argument("--limit", type=int, default=None)
    rf = sub.add_parser("retry-failed", help="reactivate failed evals (retry_count<max) and drain")
    rf.add_argument("--region", type=int, default=None)
    rf.add_argument("--max-retries", type=int, default=None)
    rf.add_argument("--limit", type=int, default=None)
    bf = sub.add_parser("backfill", help="discover a region (or all) + drain pending")
    bf.add_argument("--region", type=int, default=None, help="region id; omit for all 16")
    bf.add_argument("--tipo", type=int, choices=[1, 2], default=None)
    bf.add_argument("--discover-only", action="store_true")
    bf.add_argument("--max-pages", type=int, default=None)
    bf.add_argument("--process-limit", type=int, default=None)
    bf.add_argument("--incremental", action="store_true",
                    help="early-stop each comuna once a page yields 0 new rows")
    bf.add_argument("--resume", action="store_true",
                    help="skip discovery units already 'done' (crash recovery)")
    args = p.parse_args()

    if args.cmd in ("init-db", "init"):
        create_all()
        print("tables created")
    if args.cmd in ("seed", "init"):
        print("seeded:", seed())
    if args.cmd == "discover":
        import logging
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        from informes_cev_minvu_db.discovery.run import discover
        tipos = (args.tipo,) if args.tipo else (1, 2)
        res = discover(args.region, comuna_id=args.comuna, tipos=tipos,
                       max_pages=args.max_pages, incremental=args.incremental,
                       resume=args.resume)
        print("discovery summary:", res)
    if args.cmd == "process-pdf":
        import logging
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        from informes_cev_minvu_db.pipeline.process import process_pdf, _ensure_eval
        if args.ensure_eval:
            from informes_cev_minvu_db.db.session import get_session
            with get_session() as s:
                _ensure_eval(s, args.eval_id)
        print("result:", process_pdf(args.eval_id, args.path))
    if args.cmd == "sync-mirror":
        import logging
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        from informes_cev_minvu_db.mirror.sync import run_sync
        print("sync result:", run_sync(limit=args.limit, full=args.full))
    if args.cmd == "mirror-init":
        import logging
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        from informes_cev_minvu_db.mirror.sync import mirror_init
        print("mirror-init:", mirror_init())
    if args.cmd == "cleanup":
        from informes_cev_minvu_db.pipeline.cleanup import cleanup_orphans
        print("cleanup:", cleanup_orphans())
    if args.cmd == "daily":
        import logging
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        from informes_cev_minvu_db.pipeline.daily import run_daily
        print("daily:", run_daily())
    if args.cmd == "process-pending":
        import logging
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        from informes_cev_minvu_db.pipeline.queue import process_pending
        print("process-pending:", process_pending(region_id=args.region, limit=args.limit))
    if args.cmd == "retry-failed":
        import logging
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        from informes_cev_minvu_db.pipeline.queue import retry_failed
        print("retry-failed:", retry_failed(region_id=args.region,
                                             max_retries=args.max_retries, limit=args.limit))
    if args.cmd == "backfill":
        import logging
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        from informes_cev_minvu_db.pipeline.backfill import backfill
        tipos = (args.tipo,) if args.tipo else (1, 2)
        print("backfill:", backfill(region_id=args.region, tipos=tipos,
                                     discover_only=args.discover_only,
                                     max_pages=args.max_pages, process_limit=args.process_limit,
                                     incremental=args.incremental, resume=args.resume))


if __name__ == "__main__":
    main()
