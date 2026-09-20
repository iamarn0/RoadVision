from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCodes
from app.database import get_db
from app.schemas.auth import (
    UserCreatedResponse,
    UserCreateRequest,
    UserRead,
    UserUpdateRequest,
)
from app.security.audit import write_audit
from app.security.deps import RequireAdmin, client_ip
from app.security.passwords import generate_temporary_password, hash_password
from app.security.sessions import revoke_user_sessions
from packages.db.models import User

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(_: RequireAdmin, db: Session = Depends(get_db)) -> list[UserRead]:
    rows = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return [UserRead.model_validate(u) for u in rows]


@router.post("", response_model=UserCreatedResponse, status_code=201)
def create_user(
    body: UserCreateRequest,
    request: Request,
    admin: RequireAdmin,
    db: Session = Depends(get_db),
) -> UserCreatedResponse:
    email = body.email.lower().strip()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise AppError(ErrorCodes.CONFLICT, "A user with this email already exists", status_code=409)

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
    write_audit(
        db,
        action="user_created",
        user_id=admin.id,
        resource_type="user",
        resource_id=str(user.id),
        ip=client_ip(request),
        details={"email": email, "role": body.role},
    )
    db.commit()
    db.refresh(user)
    return UserCreatedResponse(user=UserRead.model_validate(user), temporary_password=temp_password)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: UUID,
    body: UserUpdateRequest,
    request: Request,
    admin: RequireAdmin,
    db: Session = Depends(get_db),
) -> UserRead:
    user = db.get(User, user_id)
    if not user:
        raise AppError(ErrorCodes.NOT_FOUND, "User not found", status_code=404)

    changes: dict = {}
    if body.display_name is not None:
        user.display_name = body.display_name.strip()
        changes["display_name"] = user.display_name
    if body.role is not None:
        user.role = body.role
        changes["role"] = body.role
    if body.is_active is not None:
        if user.id == admin.id and body.is_active is False:
            raise AppError(ErrorCodes.VALIDATION_ERROR, "You cannot disable your own account", status_code=400)
        user.is_active = body.is_active
        changes["is_active"] = body.is_active
        if not body.is_active:
            revoke_user_sessions(db, user.id)

    write_audit(
        db,
        action="user_updated",
        user_id=admin.id,
        resource_type="user",
        resource_id=str(user.id),
        ip=client_ip(request),
        details=changes,
    )
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.post("/{user_id}/reset-password", response_model=UserCreatedResponse)
def reset_password(
    user_id: UUID,
    request: Request,
    admin: RequireAdmin,
    db: Session = Depends(get_db),
) -> UserCreatedResponse:
    user = db.get(User, user_id)
    if not user:
        raise AppError(ErrorCodes.NOT_FOUND, "User not found", status_code=404)
    temp = generate_temporary_password()
    user.password_hash = hash_password(temp)
    user.must_change_password = False
    revoke_user_sessions(db, user.id)
    write_audit(
        db,
        action="password_reset",
        user_id=admin.id,
        resource_type="user",
        resource_id=str(user.id),
        ip=client_ip(request),
    )
    db.commit()
    db.refresh(user)
    return UserCreatedResponse(user=UserRead.model_validate(user), temporary_password=temp)


@router.post("/{user_id}/revoke-sessions")
def revoke_sessions(
    user_id: UUID,
    request: Request,
    admin: RequireAdmin,
    db: Session = Depends(get_db),
) -> dict[str, int]:
    user = db.get(User, user_id)
    if not user:
        raise AppError(ErrorCodes.NOT_FOUND, "User not found", status_code=404)
    count = revoke_user_sessions(db, user.id)
    write_audit(
        db,
        action="sessions_revoked",
        user_id=admin.id,
        resource_type="user",
        resource_id=str(user.id),
        ip=client_ip(request),
        details={"revoked": count},
    )
    db.commit()
    return {"revoked": count}
