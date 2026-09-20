"""SQLite-friendly schema patches for local development databases."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def ensure_sqlite_auth_schema(engine: Engine) -> None:
    """Create missing auth tables and add nullable attribution columns on existing DBs."""
    if not str(engine.url).startswith("sqlite"):
        return

    with engine.begin() as conn:
        tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "videos" in tables:
            video_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(videos)"))}
            if "created_by_user_id" not in video_cols:
                conn.execute(text("ALTER TABLE videos ADD COLUMN created_by_user_id CHAR(36)"))
        if "processing_jobs" in tables:
            job_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(processing_jobs)"))}
            if "created_by_user_id" not in job_cols:
                conn.execute(text("ALTER TABLE processing_jobs ADD COLUMN created_by_user_id CHAR(36)"))
