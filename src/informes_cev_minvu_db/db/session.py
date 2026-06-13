"""Database engine + session helpers."""
from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from informes_cev_minvu_db.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)


def create_all() -> None:
    """Create all tables. Models must be imported so they register on metadata."""
    import informes_cev_minvu_db.db.models  # noqa: F401
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
