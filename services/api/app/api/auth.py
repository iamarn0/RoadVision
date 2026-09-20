from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AppError, ErrorCodes
from app.database import get_db
from app.schemas.auth import ChangePasswordRequest, LoginRequest, MeResponse
from app.security.audit import write_audit
from app.security.deps import client_ip, get_current_user
from app.security.passwords import hash_password, verify_password
from app.security.rate_limit import check_login_allowed, clear_login_failures, record_login_failure
from app.security.sessions import create_session, delete_session_by_token
from packages.db.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_ttl_seconds,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
    )


@router.post("/login", response_model=MeResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> MeResponse:
    email = body.email.lower().strip()
    ip = client_ip(request)
    check_login_allowed(ip=ip, email=email)

    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(body.password, user.password_hash):
        record_login_failure(ip=ip, email=email)
        write_audit(
            db,
            action="login_failed",
            user_id=user.id if user else None,
            ip=ip,
            details={"email": email},
        )
        db.commit()
        raise AppError(ErrorCodes.INVALID_CREDENTIALS, "Invalid email or password", status_code=401)

    if not user.is_active:
        write_audit(db, action="login_disabled", user_id=user.id, ip=ip)
        db.commit()
        raise AppError(ErrorCodes.ACCOUNT_DISABLED, "Account is disabled", status_code=403)

    clear_login_failures(ip=ip, email=email)
    token, _ = create_session(
        db,
        user,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )
    user.last_login_at = datetime.now(UTC)
    if user.must_change_password:
        user.must_change_password = False
    write_audit(db, action="login_success", user_id=user.id, ip=ip)
    db.commit()
    db.refresh(user)
    _set_session_cookie(response, token)
    return MeResponse.model_validate(user)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    delete_session_by_token(db, token)
    write_audit(db, action="logout", user_id=user.id, ip=client_ip(request))
    db.commit()
    _clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse.model_validate(user)


@router.post("/change-password", response_model=MeResponse)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MeResponse:
    if get_settings().auth_disabled:
        raise AppError(ErrorCodes.FORBIDDEN, "Password changes are disabled in AUTH_DISABLED mode", status_code=403)
    if not verify_password(body.current_password, user.password_hash):
        raise AppError(ErrorCodes.INVALID_CREDENTIALS, "Current password is incorrect", status_code=401)
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    write_audit(db, action="password_changed", user_id=user.id, ip=client_ip(request))
    db.commit()
    db.refresh(user)
    return MeResponse.model_validate(user)
