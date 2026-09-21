from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _enable_sqlite_wal(dbapi_conn, _connection_record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        url = settings.resolved_database_url
        connect_args: dict = {}
        kwargs: dict = {"pool_pre_ping": not _is_sqlite(url)}
        if _is_sqlite(url):
            connect_args["check_same_thread"] = False
            connect_args["timeout"] = 30
            memory = ":memory:" in url
            kwargs["poolclass"] = StaticPool if memory else NullPool
            db_path = url.split("///", 1)[-1]
            if db_path and not db_path.startswith(":memory:"):
                Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        else:
            kwargs["pool_size"] = 10
            kwargs["max_overflow"] = 20
            kwargs["pool_timeout"] = 30
            kwargs["pool_recycle"] = 1800
        _engine = create_engine(url, connect_args=connect_args, **kwargs)
        if _is_sqlite(url):
            event.listen(_engine, "connect", _enable_sqlite_wal)
            with _engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL"))
                conn.commit()
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False, expire_on_commit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


@lru_cache
def reset_engine_cache() -> None:
    """Test helper placeholder."""
    return None
