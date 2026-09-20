"""Bootstrap the first admin account when the database has no users."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.security.passwords import hash_password
from packages.db.enums import UserRole
from packages.db.models import User

logger = logging.getLogger(__name__)


def bootstrap_admin(db: Session) -> None:
    settings = get_settings()
    count = db.scalar(select(func.count()).select_from(User)) or 0
    if count > 0:
        return

    email = (settings.bootstrap_admin_email or "").strip().lower()
    password = settings.bootstrap_admin_password or ""
    if not email or not password:
        logger.warning(
            "No users exist and BOOTSTRAP_ADMIN_EMAIL/PASSWORD are unset; "
            "create an admin before enabling production traffic."
        )
        return

    user = User(
        email=email,
        display_name=settings.bootstrap_admin_name or "Administrator",
        password_hash=hash_password(password),
        role=UserRole.ADMIN.value,
        is_active=True,
        must_change_password=False,
    )
    db.add(user)
    db.commit()
    logger.info("Bootstrapped first admin user: %s", email)
