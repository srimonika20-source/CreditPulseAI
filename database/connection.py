"""
Database connection management (SQLAlchemy + SQLite).

Provides an engine and session factory. No tables are created in Phase 1;
ORM models arrive in Phase 2 (portfolio data) and Phase 7 (actions).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from config.settings import APP


def create_db_engine(database_url: str | None = None, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine.

    Args:
        database_url: Connection URL. Defaults to the configured SQLite file.
        echo: If True, log emitted SQL (useful when debugging).

    Returns:
        A SQLAlchemy ``Engine``.
    """
    url = database_url or APP.database_url
    if url.startswith("sqlite:///") and url != "sqlite:///:memory:":
        APP.database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, echo=echo, future=True)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the shared application engine (created once per process)."""
    return create_db_engine()


@contextmanager
def get_session(engine: Engine | None = None) -> Iterator[Session]:
    """Provide a transactional session scope.

    Commits on success, rolls back on error, and always closes the session.

    Args:
        engine: Engine to bind to. Defaults to the shared application engine.

    Yields:
        An active SQLAlchemy ``Session``.
    """
    factory = sessionmaker(bind=engine or get_engine(), expire_on_commit=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_connection(engine: Engine | None = None) -> bool:
    """Check that the database is reachable.

    Args:
        engine: Engine to test. Defaults to the shared application engine.

    Returns:
        True if a trivial query succeeds, otherwise False.
    """
    try:
        with (engine or get_engine()).connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - any failure means "not reachable"
        return False
