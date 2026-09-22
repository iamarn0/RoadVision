"""District appointment scoping and district-master personnel tests."""

from __future__ import annotations

import os
from typing import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

os.environ["AUTH_DISABLED"] = "false"
os.environ["APP_ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@example.com"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "BootstrapAdmin1!"
os.environ["BOOTSTRAP_ADMIN_NAME"] = "Test Admin"


@pytest.fixture()
def district_client(tmp_path) -> Generator[TestClient, None, None]:
    os.environ["AUTH_DISABLED"] = "false"
    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / 'districts.db').as_posix()}"

    from app.config import get_settings

    get_settings.cache_clear()

    import app.database.session as db_session

    db_session._engine = None
    db_session._SessionLocal = None

    import app.models  # noqa: F401
    from app.database.session import get_engine, get_session_factory
    from app.main import app
    from app.security.bootstrap import bootstrap_admin
    from app.security.districts import seed_west_bengal_districts
    from app.security.passwords import hash_password
    from packages.db.base import Base
    from packages.db.enums import UserRole
    from packages.db.models import District, User, UserDistrict

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    factory = get_session_factory()
    db = factory()
    try:
        seed_west_bengal_districts(db)
        bootstrap_admin(db)
        kolkata = db.scalar(select(District).where(District.name == "Kolkata"))
        howrah = db.scalar(select(District).where(District.name == "Howrah"))
        assert kolkata is not None and howrah is not None

        master = User(
            email="master.kolkata@example.com",
            display_name="Kolkata Master",
            password_hash=hash_password("MasterPass1!"),
            role=UserRole.DISTRICT_MASTER.value,
            is_active=True,
        )
        db.add(master)
        db.flush()
        db.add(UserDistrict(user_id=master.id, district_id=kolkata.id))
        db.add(UserDistrict(user_id=master.id, district_id=howrah.id))

        howrah_master = User(
            email="master.howrah@example.com",
            display_name="Howrah Master",
            password_hash=hash_password("MasterPass1!"),
            role=UserRole.DISTRICT_MASTER.value,
            is_active=True,
        )
        db.add(howrah_master)
        db.flush()
        db.add(UserDistrict(user_id=howrah_master.id, district_id=howrah.id))

        op_both = User(
            email="op.both@example.com",
            display_name="Both Operator",
            password_hash=hash_password("OperatorPass1!"),
            role=UserRole.OPERATOR.value,
            is_active=True,
        )
        db.add(op_both)
        db.flush()
        db.add(UserDistrict(user_id=op_both.id, district_id=kolkata.id))
        db.add(UserDistrict(user_id=op_both.id, district_id=howrah.id))

        op_howrah = User(
            email="op.howrah@example.com",
            display_name="Howrah Operator",
            password_hash=hash_password("OperatorPass1!"),
            role=UserRole.OPERATOR.value,
            is_active=True,
        )
        db.add(op_howrah)
        db.flush()
        db.add(UserDistrict(user_id=op_howrah.id, district_id=howrah.id))
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


def _district_ids(client: TestClient) -> tuple[str, str]:
    from app.database.session import get_session_factory
    from packages.db.models import District

    db = get_session_factory()()
    try:
        kolkata = db.scalar(select(District).where(District.name == "Kolkata"))
        howrah = db.scalar(select(District).where(District.name == "Howrah"))
        assert kolkata is not None and howrah is not None
        return str(kolkata.id), str(howrah.id)
    finally:
        db.close()


def _seed_video(district_name: str, filename: str) -> str:
    from app.database.session import get_session_factory
    from packages.db.enums import VideoStatus
    from packages.db.models import District, Video

    db = get_session_factory()()
    try:
        district = db.scalar(select(District).where(District.name == district_name))
        assert district is not None
        video = Video(
            original_filename=filename,
            storage_key=f"uploads/{uuid4().hex}_{filename}",
            file_size=12,
            status=VideoStatus.READY.value,
            district_id=district.id,
        )
        db.add(video)
        db.commit()
        return str(video.id)
    finally:
        db.close()


def test_master_me_includes_appointed_districts(district_client: TestClient) -> None:
    response = _login(district_client, "master.kolkata@example.com", "MasterPass1!")
    assert response.status_code == 200
    names = {row["name"] for row in response.json()["districts"]}
    assert names == {"Kolkata", "Howrah"}


def test_operator_cannot_create_user(district_client: TestClient) -> None:
    kolkata_id, _ = _district_ids(district_client)
    assert _login(district_client, "op.both@example.com", "OperatorPass1!").status_code == 200
    response = district_client.post(
        "/api/users",
        json={
            "email": "staff@example.com",
            "display_name": "Staff",
            "role": "operator",
            "district_ids": [kolkata_id],
        },
    )
    assert response.status_code == 403


def test_admin_cannot_create_user(district_client: TestClient) -> None:
    kolkata_id, _ = _district_ids(district_client)
    assert _login(district_client, "admin@example.com", "BootstrapAdmin1!").status_code == 200
    response = district_client.post(
        "/api/users",
        json={
            "email": "staff@example.com",
            "display_name": "Staff",
            "role": "operator",
            "district_ids": [kolkata_id],
        },
    )
    assert response.status_code == 403


def test_master_creates_operator_in_own_districts(district_client: TestClient) -> None:
    kolkata_id, howrah_id = _district_ids(district_client)
    assert _login(district_client, "master.kolkata@example.com", "MasterPass1!").status_code == 200
    response = district_client.post(
        "/api/users",
        json={
            "email": "new.op@example.com",
            "display_name": "New Op",
            "role": "operator",
            "district_ids": [kolkata_id, howrah_id],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["email"] == "new.op@example.com"
    assert body["user"]["role"] == "operator"
    assert {row["name"] for row in body["user"]["districts"]} == {"Kolkata", "Howrah"}
    assert body["temporary_password"]


def test_master_cannot_create_admin_or_master(district_client: TestClient) -> None:
    kolkata_id, _ = _district_ids(district_client)
    assert _login(district_client, "master.kolkata@example.com", "MasterPass1!").status_code == 200
    for role in ("admin", "district_master"):
        response = district_client.post(
            "/api/users",
            json={
                "email": f"{role}@example.com",
                "display_name": role,
                "role": role,
                "district_ids": [kolkata_id],
            },
        )
        assert response.status_code == 422


def test_master_can_appoint_any_west_bengal_district(district_client: TestClient) -> None:
    from app.database.session import get_session_factory
    from packages.db.models import District

    db = get_session_factory()()
    try:
        nadia = db.scalar(select(District).where(District.name == "Nadia"))
        assert nadia is not None
        nadia_id = str(nadia.id)
    finally:
        db.close()

    assert _login(district_client, "master.howrah@example.com", "MasterPass1!").status_code == 200
    catalog = district_client.get("/api/districts")
    assert catalog.status_code == 200
    names = {row["name"] for row in catalog.json()}
    assert "Kolkata" in names
    assert "Nadia" in names
    assert "Howrah" in names
    assert len(catalog.json()) == 23
    response = district_client.post(
        "/api/users",
        json={
            "email": "outsider@example.com",
            "display_name": "Outsider",
            "role": "operator",
            "district_ids": [nadia_id],
        },
    )
    assert response.status_code == 201, response.text
    assert {row["name"] for row in response.json()["user"]["districts"]} == {"Nadia"}


def test_master_list_hides_masters_and_admins(district_client: TestClient) -> None:
    assert _login(district_client, "master.howrah@example.com", "MasterPass1!").status_code == 200
    response = district_client.get("/api/users")
    assert response.status_code == 200
    emails = {row["email"] for row in response.json()}
    assert "op.howrah@example.com" in emails
    assert "op.both@example.com" in emails
    assert "master.kolkata@example.com" not in emails
    assert "admin@example.com" not in emails


def test_cross_district_video_is_hidden(district_client: TestClient) -> None:
    kolkata_video = _seed_video("Kolkata", "kolkata.mp4")
    howrah_video = _seed_video("Howrah", "howrah.mp4")

    assert _login(district_client, "op.howrah@example.com", "OperatorPass1!").status_code == 200
    listed = district_client.get("/api/videos")
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()}
    assert howrah_video in ids
    assert kolkata_video not in ids
    assert district_client.get(f"/api/videos/{kolkata_video}").status_code == 404
    assert district_client.get(f"/api/videos/{howrah_video}").status_code == 200

    dash = district_client.get("/api/dashboard")
    assert dash.status_code == 200
    recent = {row["id"] for row in dash.json()["recent_videos"]}
    assert howrah_video in recent
    assert kolkata_video not in recent


def test_multi_district_operator_sees_both(district_client: TestClient) -> None:
    kolkata_video = _seed_video("Kolkata", "kolkata.mp4")
    howrah_video = _seed_video("Howrah", "howrah.mp4")
    assert _login(district_client, "op.both@example.com", "OperatorPass1!").status_code == 200
    ids = {row["id"] for row in district_client.get("/api/videos").json()}
    assert kolkata_video in ids
    assert howrah_video in ids


def test_admin_without_districts_sees_no_case_data(district_client: TestClient) -> None:
    _seed_video("Kolkata", "kolkata.mp4")
    assert _login(district_client, "admin@example.com", "BootstrapAdmin1!").status_code == 200
    assert district_client.get("/api/videos").json() == []
    assert district_client.get("/api/dashboard").json()["videos_processed"] == 0
