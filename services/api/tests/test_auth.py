"""Authentication and RBAC tests (AUTH_DISABLED=false)."""

from __future__ import annotations

import os
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

# Force auth on for this module before importing app pieces.
os.environ["AUTH_DISABLED"] = "false"
os.environ["APP_ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@example.com"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "BootstrapAdmin1!"
os.environ["BOOTSTRAP_ADMIN_NAME"] = "Test Admin"


@pytest.fixture()
def auth_client(tmp_path) -> Generator[TestClient, None, None]:
    os.environ["AUTH_DISABLED"] = "false"
    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / 'auth.db').as_posix()}"

    from app.config import get_settings

    get_settings.cache_clear()

    import app.database.session as db_session

    db_session._engine = None
    db_session._SessionLocal = None

    import app.models  # noqa: F401
    from app.database.session import get_engine, get_session_factory
    from app.main import app
    from app.security.bootstrap import bootstrap_admin
    from app.security.passwords import hash_password
    from packages.db.base import Base
    from packages.db.enums import UserRole
    from packages.db.models import User

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    factory = get_session_factory()
    db = factory()
    try:
        bootstrap_admin(db)
        existing = set(db.scalars(select(User.email)).all())
        if "operator@example.com" not in existing:
            db.add(
                User(
                    email="operator@example.com",
                    display_name="Operator",
                    password_hash=hash_password("OperatorPass1!"),
                    role=UserRole.OPERATOR.value,
                    is_active=True,
                )
            )
        if "auditor@example.com" not in existing:
            db.add(
                User(
                    email="auditor@example.com",
                    display_name="Auditor",
                    password_hash=hash_password("AuditorPass1!"),
                    role=UserRole.AUDITOR.value,
                    is_active=True,
                )
            )
        if "disabled@example.com" not in existing:
            db.add(
                User(
                    email="disabled@example.com",
                    display_name="Disabled",
                    password_hash=hash_password("DisabledPass1!"),
                    role=UserRole.OPERATOR.value,
                    is_active=False,
                )
            )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        yield client

    get_settings.cache_clear()
    db_session._engine = None
    db_session._SessionLocal = None
    os.environ["AUTH_DISABLED"] = "true"


def _login(client: TestClient, email: str, password: str):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_success(auth_client: TestClient) -> None:
    response = _login(auth_client, "admin@example.com", "BootstrapAdmin1!")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "admin@example.com"
    assert body["role"] == "admin"
    assert body["districts"] == []
    assert "roadvision_session" in response.cookies


def test_login_bad_password(auth_client: TestClient) -> None:
    response = _login(auth_client, "admin@example.com", "wrong-password")
    assert response.status_code == 401
    assert response.json()["error_code"] == "INVALID_CREDENTIALS"


def test_login_disabled_user(auth_client: TestClient) -> None:
    response = _login(auth_client, "disabled@example.com", "DisabledPass1!")
    assert response.status_code == 403
    assert response.json()["error_code"] == "ACCOUNT_DISABLED"


def test_protected_route_requires_cookie(auth_client: TestClient) -> None:
    response = auth_client.get("/api/videos")
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHENTICATED"


def test_operator_can_list_videos(auth_client: TestClient) -> None:
    assert _login(auth_client, "operator@example.com", "OperatorPass1!").status_code == 200
    response = auth_client.get("/api/videos")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_auditor_forbidden_from_upload(auth_client: TestClient) -> None:
    assert _login(auth_client, "auditor@example.com", "AuditorPass1!").status_code == 200
    response = auth_client.post(
        "/api/videos/upload",
        files={"file": ("clip.mp4", b"not-a-real-video", "video/mp4")},
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN"


def test_auditor_can_read_settings(auth_client: TestClient) -> None:
    assert _login(auth_client, "auditor@example.com", "AuditorPass1!").status_code == 200
    response = auth_client.get("/api/settings")
    assert response.status_code == 200
    assert response.json()["authentication_enabled"] is True


def test_non_admin_cannot_list_users(auth_client: TestClient) -> None:
    assert _login(auth_client, "operator@example.com", "OperatorPass1!").status_code == 200
    response = auth_client.get("/api/users")
    assert response.status_code == 403


def test_admin_cannot_create_user(auth_client: TestClient) -> None:
    assert _login(auth_client, "admin@example.com", "BootstrapAdmin1!").status_code == 200
    response = auth_client.post(
        "/api/users",
        json={"email": "new.op@example.com", "display_name": "New Op", "role": "operator", "district_ids": []},
    )
    assert response.status_code == 403


def test_websocket_rejects_without_cookie(auth_client: TestClient) -> None:
    with pytest.raises(Exception):
        with auth_client.websocket_connect("/ws/jobs/00000000-0000-4000-8000-000000000099"):
            pass


def test_production_refuses_auth_disabled() -> None:
    from app.config import Settings

    with pytest.raises(RuntimeError, match="AUTH_DISABLED"):
        Settings(app_env="production", auth_disabled=True, secret_key="not-placeholder-value").validate_runtime()


def test_production_refuses_placeholder_secret() -> None:
    from app.config import Settings

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Settings(
            app_env="production",
            auth_disabled=False,
            secret_key="change-me-in-development",
        ).validate_runtime()
