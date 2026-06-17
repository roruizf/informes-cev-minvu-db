"""Database engine + session helpers.

Resilience (Fase 13): a transient Postgres outage (e.g. Zeabur restart →
"the database system is in recovery mode") must NOT kill a long-running backfill.
get_session retries the *connect* with bounded backoff before giving up, mirroring
the portal client's network retry. pool_pre_ping already recycles stale pooled
connections; this adds recovery from a server that is briefly unreachable/recovering.
"""
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import DBAPIError, OperationalError
from sqlmodel import Session, SQLModel, create_engine

from informes_cev_minvu_db.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(settings.database_url, pool_pre_ping=True)

# Transient DB errors worth retrying: connection refused, server in recovery mode,
# admin shutdown, etc. We retry the connection, not application logic.
_RETRYABLE = (OperationalError, DBAPIError)


def _connect_with_retry() -> Session:
    """Open a Session, retrying the connection on transient DB errors."""
    retries = settings.db_connect_retries
    backoff = settings.db_connect_backoff
    last: Exception | None = None
    for attempt in range(retries):
        try:
            s = Session(engine)
            # Force an actual connection now so we retry HERE, not on first query.
            s.connection()
            return s
        except _RETRYABLE as e:
            last = e
            wait = backoff * (2 ** attempt)
            logger.warning(
                "DB connect transient error (try %d/%d): %s; sleep %.1fs",
                attempt + 1, retries, str(e)[:120], wait,
            )
            time.sleep(wait)
    raise RuntimeError(
        f"DB connect failed after {retries} retries: {last}"
    ) from last


def create_all() -> None:
    """Create all tables. Models must be imported so they register on metadata."""
    import informes_cev_minvu_db.db.models  # noqa: F401
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    session = _connect_with_retry()
    try:
        yield session
    finally:
        session.close()
