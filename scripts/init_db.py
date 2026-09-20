"""Initialize the database schema for local development.

PostgreSQL:
  Prefer: alembic upgrade head

SQLite (no Postgres user required):
  Set DATABASE_URL=sqlite:///./storage/roadvision.db
  Then run this script.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "services" / "api"
for path in (str(REPO_ROOT), str(API_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.config import get_settings  # noqa: E402
from app.database.session import get_engine  # noqa: E402
from app.models import Base  # noqa: E402


def main() -> None:
    settings = get_settings()
    engine = get_engine()
    if settings.database_url.startswith("sqlite"):
        Path(settings.storage_root).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    print(f"Schema ready: {settings.database_url}")


if __name__ == "__main__":
    main()
