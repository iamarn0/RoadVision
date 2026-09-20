from __future__ import annotations

import sys
from pathlib import Path

# Make packages.* importable. In Docker this is /app; locally it is the repo root.
_HERE = Path(__file__).resolve()
API_ROOT = _HERE.parents[1]
REPO_ROOT = next((p for p in [API_ROOT, *_HERE.parents] if (p / "packages").is_dir()), API_ROOT)
for path in (str(REPO_ROOT), str(API_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from app.config import get_settings
from app.models import Base

config = context.config
settings = get_settings()
db_url = settings.resolved_database_url
# Escape percent signs for ConfigParser interpolation used by Alembic.
config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))

target_metadata = Base.metadata


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = db_url
    if _is_sqlite(url):
        # Initial migration uses PostgreSQL-specific types; for local SQLite demos
        # create the portable ORM schema directly.
        db_path = url.split("///", 1)[-1]
        if db_path and not db_path.startswith(":memory:"):
            Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            connect_args={"check_same_thread": False},
        )
        with connectable.begin() as connection:
            Base.metadata.create_all(bind=connection)
            connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS alembic_version ("
                    "version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
                )
            )
            current = connection.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            if current is None:
                connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('002_auth')"))
            elif current[0] == "001_initial":
                # Fresh create_all already includes auth tables; advance stamp.
                connection.execute(text("UPDATE alembic_version SET version_num = '002_auth'"))
        print(f"SQLite schema ready at {url}")
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
