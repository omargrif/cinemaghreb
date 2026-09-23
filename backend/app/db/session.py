"""Engine/session setup.

SQLite is the default for local dev (no Postgres/Docker install required — see
`.env.example`). Swapping to Postgres later is a `DATABASE_URL` change only,
which is why every query in this codebase goes through plain SQLAlchemy Core/ORM
rather than anything SQLite-specific.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.settings import settings

# SQLite's default driver rejects a connection used across threads; FastAPI's
# request-scoped sessions are short-lived so sharing the connection is safe.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create any tables that don't exist yet. No migrations — see plan notes:
    the schema isn't stable enough yet to justify Alembic.
    """
    from app.db.base import Base
    from app.models import (
        movie,  # noqa: F401 — import registers the table on Base.metadata
    )

    Base.metadata.create_all(bind=engine)
