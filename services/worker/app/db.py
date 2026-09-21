from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings

_engine = None
_factory = None


def _enable_sqlite_wal(dbapi_conn, _connection_record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def get_session() -> Session:
    global _engine, _factory
    if _factory is None:
        settings = get_settings()
        connect_args: dict = {}
        url = settings.resolved_database_url
        kwargs: dict = {"pool_pre_ping": not url.startswith("sqlite")}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            connect_args["timeout"] = 30
            kwargs["poolclass"] = NullPool
            db_path = url.split("///", 1)[-1]
            if db_path and not db_path.startswith(":memory:"):
                Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        else:
            kwargs["pool_size"] = 5
            kwargs["max_overflow"] = 5
            kwargs["pool_recycle"] = 1800
        _engine = create_engine(url, connect_args=connect_args, **kwargs)
        if url.startswith("sqlite"):
            event.listen(_engine, "connect", _enable_sqlite_wal)
            with _engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL"))
                conn.commit()
        _factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _factory()
