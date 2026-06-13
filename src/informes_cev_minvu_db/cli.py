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
    pp = sub.add_parser("process-pdf", help="process one local PDF end-to-end")
    pp.add_argument("--eval-id", required=True)
    pp.add_argument("--path", required=True)
    pp.add_argument("--ensure-eval", action="store_true", help="insert a stub eval row if missing")
    sm = sub.add_parser("sync-mirror", help="push data to NoCodeBackend (incremental)")
    sm.add_argument("--limit", type=int, default=None)
    sm.add_argument("--full", action="store_true", help="re-sync all (ignore synced flag)")
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
        res = discover(args.region, comuna_id=args.comuna, tipos=tipos, max_pages=args.max_pages)
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


if __name__ == "__main__":
    main()
