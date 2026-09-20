"""Audit log helpers."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from packages.db.models import AuditLog


def write_audit(
    db: Session,
    *,
    action: str,
    user_id: Optional[UUID] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip=ip,
            details=details,
        )
    )
