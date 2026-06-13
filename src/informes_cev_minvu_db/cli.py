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
    args = p.parse_args()

    if args.cmd in ("init-db", "init"):
        create_all()
        print("tables created")
    if args.cmd in ("seed", "init"):
        print("seeded:", seed())


if __name__ == "__main__":
    main()
