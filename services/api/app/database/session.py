from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        url = settings.resolved_database_url
        connect_args: dict = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            db_path = url.split("///", 1)[-1]
            if db_path and not db_path.startswith(":memory:"):
                Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            url,
            pool_pre_ping=not url.startswith("sqlite"),
            connect_args=connect_args,
        )
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
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
