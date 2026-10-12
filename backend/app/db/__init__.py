"""Couche de persistance (SQLAlchemy) : PostgreSQL en production, SQLite en développement."""

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _pragmas(conn, _record):  # clés étrangères et accès concurrents (calculs en tâche de fond)
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=10000")
            cur.close()

        return engine
    return create_engine(url, pool_pre_ping=True)


@lru_cache
def _fabrique() -> sessionmaker:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def session() -> Iterator[Session]:
    """Session transactionnelle : commit en sortie normale, rollback sur exception."""
    s = _fabrique()()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
