"""Pytest defaults: auth bypass for legacy tests; schema ready for TestClient."""

from __future__ import annotations

import os

# Must run before app.config / app.main imports in test modules.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("AUTH_DISABLED", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _prepare_database() -> None:
    from app.config import get_settings

    get_settings.cache_clear()
    import app.models  # noqa: F401 — register metadata
    from app.database.session import get_engine
    from packages.db.base import Base

    engine = get_engine()
    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def client() -> TestClient:
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
