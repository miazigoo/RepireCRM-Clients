"""Database engine and session factory.

The engine is created lazily on first call to ``get_engine()`` so tests can
override ``CLIENT_PORTAL_DATABASE_URL`` before any import triggers a
connection attempt.  ``dispose_engine()`` is called from the FastAPI lifespan
on clean shutdown to release the connection pool.
"""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None  # type: ignore[type-arg]


class Base(DeclarativeBase):
    pass


def _connect_args(database_url: str) -> dict[str, bool]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def get_engine() -> Engine:
    """Return the singleton engine, creating it on first call."""
    global _engine
    if _engine is None:
        url = get_settings().database_url
        _engine = create_engine(url, connect_args=_connect_args(url), future=True)
    return _engine


def get_session_factory() -> sessionmaker:  # type: ignore[type-arg]
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False, future=True
        )
    return _SessionLocal


def dispose_engine() -> None:
    """Release all pooled connections — call on application shutdown."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionLocal = None


# ---------------------------------------------------------------------------
# Convenience shims so existing code that imports ``SessionLocal`` or
# ``engine`` directly continues to work without modification.
# ---------------------------------------------------------------------------


class _EngineProxy:
    """Proxy that lazily forwards attribute access to the real engine."""

    def __getattr__(self, name: str):
        return getattr(get_engine(), name)

    def __call__(self, *args, **kwargs):
        return get_engine()(*args, **kwargs)


class _SessionLocalProxy:
    """Proxy that acts like ``sessionmaker``: callable and context-manager."""

    def __call__(self, *args, **kwargs):
        return get_session_factory()(*args, **kwargs)

    def __enter__(self):
        session = get_session_factory()()
        self._session = session
        return session

    def __exit__(self, *exc_info):
        self._session.close()


engine = _EngineProxy()  # type: ignore[assignment]
SessionLocal = _SessionLocalProxy()  # type: ignore[assignment]


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
