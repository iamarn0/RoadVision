"""Opaque session token helpers."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from packages.db.models import User, UserSession


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(
    db: Session,
    user: User,
    *,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> tuple[str, UserSession]:
    settings = get_settings()
    raw = secrets.token_urlsafe(32)
    row = UserSession(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds),
        ip=ip,
        user_agent=(user_agent or "")[:512] or None,
    )
    db.add(row)
    db.flush()
    return raw, row


def get_user_for_token(db: Session, token: Optional[str]) -> Optional[User]:
    if not token:
        return None
    now = datetime.now(UTC)
    row = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == hash_token(token),
            UserSession.expires_at > now,
        )
    )
    if not row:
        return None
    user = db.get(User, row.user_id)
    if not user or not user.is_active:
        return None
    return user


def delete_session_by_token(db: Session, token: Optional[str]) -> None:
    if not token:
        return
    db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))


def revoke_user_sessions(db: Session, user_id: UUID) -> int:
    result = db.execute(delete(UserSession).where(UserSession.user_id == user_id))
    return result.rowcount or 0
