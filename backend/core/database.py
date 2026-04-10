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


# core/database.py

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
        
        # SUPABASE FIX (For Port 5432 - Session Pooling):
        # 1. Remove NullPool so SQLAlchemy can maintain a stable queue.
        # 2. pool_pre_ping: Checks if the connection is alive before using it.
        # 3. pool_size & max_overflow: Gives you enough concurrent connections for the dashboard prewarm.
        # 4. pool_recycle: Forces connections to refresh every 30 minutes.
        _engine = create_engine(
            database_url, 
            pool_pre_ping=True,
            pool_size=15,
            max_overflow=20,
            pool_recycle=1800,
            connect_args={
                "sslmode": "require",
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5
            }
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