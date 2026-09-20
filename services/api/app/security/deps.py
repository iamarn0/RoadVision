"""FastAPI auth dependencies."""

from __future__ import annotations

from typing import Annotated, Callable, Optional
from uuid import UUID

from fastapi import Depends, Request, WebSocket
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AppError, ErrorCodes
from app.database import get_db
from app.security.sessions import get_user_for_token
from packages.db.enums import UserRole
from packages.db.models import User


def _cookie_name() -> str:
    return get_settings().session_cookie_name or "roadvision_session"


def _demo_operator() -> User:
    """Synthetic operator used only when AUTH_DISABLED=true (tests/local)."""
    return User(
        id=UUID("00000000-0000-4000-8000-000000000001"),
        email="dev@localhost",
        display_name="Development Operator",
        password_hash="",
        role=UserRole.ADMIN.value,
        is_active=True,
        must_change_password=False,
    )


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    settings = get_settings()
    if settings.auth_disabled:
        return _demo_operator()
    token = request.cookies.get(_cookie_name())
    return get_user_for_token(db, token)


def get_current_user(user: Optional[User] = Depends(get_optional_user)) -> User:
    if user is None:
        raise AppError(ErrorCodes.UNAUTHENTICATED, "Authentication required", status_code=401)
    return user


def require_roles(*roles: str) -> Callable:
    allowed = set(roles)

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise AppError(ErrorCodes.FORBIDDEN, "Insufficient permissions", status_code=403)
        return user

    return _dep


RequireAdmin = Annotated[User, Depends(require_roles(UserRole.ADMIN.value))]
RequireOperator = Annotated[
    User,
    Depends(require_roles(UserRole.ADMIN.value, UserRole.OPERATOR.value)),
]
RequireReader = Annotated[
    User,
    Depends(
        require_roles(UserRole.ADMIN.value, UserRole.OPERATOR.value, UserRole.AUDITOR.value)
    ),
]


async def authenticate_websocket(websocket: WebSocket, db: Session) -> Optional[User]:
    settings = get_settings()
    if settings.auth_disabled:
        return _demo_operator()
    token = websocket.cookies.get(_cookie_name())
    return get_user_for_token(db, token)


def client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
