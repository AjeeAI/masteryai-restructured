"""Database setup (SQLAlchemy).

Logic:
- Lazily creates the SQLAlchemy engine/session factory.
- Provides get_db() dependency for FastAPI endpoints and scripts.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool, NullPool

from .config import settings

_engine: Engine | None = None
_session_factory: sessionmaker | None = None


class _EngineProxy:
    def __getattr__(self, item):
        return getattr(get_engine(), item)

    def __repr__(self) -> str:
        if _engine is None:
            return "<LazyEngineProxy uninitialized>"
        return repr(_engine)


engine = _EngineProxy()


class Base(DeclarativeBase):
    pass


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        database_url = (settings.database_url or "").strip()
        if not database_url:
            if os.getenv("PYTEST_CURRENT_TEST"):
                _engine = create_engine(
                    "sqlite://",
                    connect_args={"check_same_thread": False},
                    poolclass=StaticPool,
                )
                return _engine
            raise RuntimeError("DATABASE_URL is not configured.")
        
        # SUPABASE FIX: Added poolclass=NullPool to prevent Double Pooling 
        # with Supabase's internal PgBouncer pooler.
        _engine = create_engine(
            database_url, 
            pool_pre_ping=True, 
            poolclass=NullPool
        )
    return _engine


def _get_session_factory() -> sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _session_factory


def SessionLocal():
    return _get_session_factory()()


def reset_engine_for_tests() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()