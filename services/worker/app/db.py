from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine = None
_factory = None


def get_session() -> Session:
    global _engine, _factory
    if _factory is None:
        settings = get_settings()
        connect_args: dict = {}
        url = settings.resolved_database_url
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
        _factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _factory()
