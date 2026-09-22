from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCodes
from app.database import get_db
from app.schemas.auth import (
    DistrictRead,
    UserCreatedResponse,
    UserCreateRequest,
    UserRead,
    UserUpdateRequest,
)
from app.security.audit import write_audit
from app.security.deps import RequireDistrictMaster, client_ip
from app.security.districts import districts_for_user
from app.security.passwords import generate_temporary_password, hash_password
from app.security.sessions import revoke_user_sessions
from packages.db.enums import UserRole
from packages.db.models import District, User, UserDistrict

router = APIRouter(prefix="/api/users", tags=["users"])

_STAFF_ROLES = {UserRole.OPERATOR.value, UserRole.AUDITOR.value}


def to_user_read(db: Session, user: User) -> UserRead:
    assigned = districts_for_user(db, user)
    return UserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        created_at=user.created_at or datetime.now(UTC),
        last_login_at=user.last_login_at,
        districts=[DistrictRead(id=row.id, name=row.name) for row in assigned],
    )


def _catalog_ids(db: Session) -> set[UUID]:
    return set(db.scalars(select(District.id)).all())


def _require_known_districts(db: Session, district_ids: list[UUID]) -> list[UUID]:
    requested = list(dict.fromkeys(district_ids))
    if not requested:
        raise AppError(ErrorCodes.VALIDATION_ERROR, "Appoint at least one district", status_code=400)
    catalog = _catalog_ids(db)
    unknown = [str(item) for item in requested if item not in catalog]
    if unknown:
        raise AppError(ErrorCodes.VALIDATION_ERROR, "Unknown district", status_code=400, details={"district_ids": unknown})
    return requested


def _visible_staff(db: Session, _master: User) -> list[User]:
    return list(
        db.scalars(
            select(User).where(User.role.in_(_STAFF_ROLES)).order_by(User.created_at.desc())
        ).all()
    )


def _managed_staff(db: Session, _master: User, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if not user or user.role not in _STAFF_ROLES:
        raise AppError(ErrorCodes.NOT_FOUND, "User not found", status_code=404)
    return user


def _appoint(db: Session, user: User, district_ids: list[UUID]) -> None:
    for district_id in district_ids:
        exists = db.scalar(
            select(UserDistrict).where(
                UserDistrict.user_id == user.id,
                UserDistrict.district_id == district_id,
            )
        )
        if exists:
            continue
        db.add(UserDistrict(user_id=user.id, district_id=district_id))


@router.get("", response_model=list[UserRead])
def list_users(master: RequireDistrictMaster, db: Session = Depends(get_db)) -> list[UserRead]:
    return [to_user_read(db, user) for user in _visible_staff(db, master)]


@router.post("", response_model=UserCreatedResponse, status_code=201)
def create_user(
    body: UserCreateRequest,
    request: Request,
    master: RequireDistrictMaster,
    db: Session = Depends(get_db),
) -> UserCreatedResponse:
    email = body.email.lower().strip()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise AppError(ErrorCodes.CONFLICT, "A user with this email already exists", status_code=409)

    requested = _require_known_districts(db, body.district_ids)

    temp_password = body.password or generate_temporary_password()
    user = User(
        email=email,
        display_name=body.display_name.strip(),
        password_hash=hash_password(temp_password),
        role=body.role,
        is_active=True,
        must_change_password=False,
    )
    db.add(user)
    db.flush()
    _appoint(db, user, requested)
    write_audit(
        db,
        action="user_created",
        user_id=master.id,
        resource_type="user",
        resource_id=str(user.id),
        ip=client_ip(request),
        details={"email": email, "role": body.role, "district_ids": [str(item) for item in requested]},
    )
    db.commit()
    db.refresh(user)
    return UserCreatedResponse(user=to_user_read(db, user), temporary_password=temp_password)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: UUID,
    body: UserUpdateRequest,
    request: Request,
    master: RequireDistrictMaster,
    db: Session = Depends(get_db),
) -> UserRead:
    user = _managed_staff(db, master, user_id)
    changes: dict = {}
    if body.display_name is not None:
        user.display_name = body.display_name.strip()
        changes["display_name"] = user.display_name
    if body.role is not None:
        user.role = body.role
        changes["role"] = body.role
    if body.is_active is not None:
        if user.id == master.id and body.is_active is False:
            raise AppError(ErrorCodes.VALIDATION_ERROR, "You cannot disable your own account", status_code=400)
        user.is_active = body.is_active
        changes["is_active"] = body.is_active
        if not body.is_active:
            revoke_user_sessions(db, user.id)
    if body.district_ids is not None:
        requested = set(_require_known_districts(db, body.district_ids))
        current = set(db.scalars(select(UserDistrict.district_id).where(UserDistrict.user_id == user.id)).all())
        to_add = requested - current
        to_remove = current - requested
        for district_id in to_add:
            db.add(UserDistrict(user_id=user.id, district_id=district_id))
        if to_remove:
            rows = db.scalars(
                select(UserDistrict).where(
                    UserDistrict.user_id == user.id,
                    UserDistrict.district_id.in_(to_remove),
                )
            ).all()
            for row in rows:
                db.delete(row)
        changes["district_ids"] = [str(item) for item in sorted(requested, key=str)]

    write_audit(
        db,
        action="user_updated",
        user_id=master.id,
        resource_type="user",
        resource_id=str(user.id),
        ip=client_ip(request),
        details=changes,
    )
    db.commit()
    db.refresh(user)
    return to_user_read(db, user)


@router.post("/{user_id}/reset-password", response_model=UserCreatedResponse)
def reset_password(
    user_id: UUID,
    request: Request,
    master: RequireDistrictMaster,
    db: Session = Depends(get_db),
) -> UserCreatedResponse:
    user = _managed_staff(db, master, user_id)
    temp = generate_temporary_password()
    user.password_hash = hash_password(temp)
    user.must_change_password = False
    revoke_user_sessions(db, user.id)
    write_audit(
        db,
        action="password_reset",
        user_id=master.id,
        resource_type="user",
        resource_id=str(user.id),
        ip=client_ip(request),
    )
    db.commit()
    db.refresh(user)
    return UserCreatedResponse(user=to_user_read(db, user), temporary_password=temp)


@router.post("/{user_id}/revoke-sessions")
def revoke_sessions(
    user_id: UUID,
    request: Request,
    master: RequireDistrictMaster,
    db: Session = Depends(get_db),
) -> dict[str, int]:
    user = _managed_staff(db, master, user_id)
    count = revoke_user_sessions(db, user.id)
    write_audit(
        db,
        action="sessions_revoked",
        user_id=master.id,
        resource_type="user",
        resource_id=str(user.id),
        ip=client_ip(request),
        details={"revoked": count},
    )
    db.commit()
    return {"revoked": count}
