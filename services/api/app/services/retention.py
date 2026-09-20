"""Optional retention cleanup for demo deployments.

Authentication is intentionally disabled. This module only removes aged
storage records when invoked by an operator or scheduled task.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.storage.service import get_storage
from packages.db.models import MediaAsset, Video


def cleanup_expired(db: Session) -> int:
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(days=settings.retention_days)
    storage = get_storage()
    deleted = 0
    videos = list(db.scalars(select(Video).where(Video.created_at < cutoff)))
    for video in videos:
        assets = list(db.scalars(select(MediaAsset).where(MediaAsset.video_id == video.id)))
        for asset in assets:
            try:
                storage.delete(asset.storage_key)
            except Exception:
                pass
            db.delete(asset)
        try:
            storage.delete(video.storage_key)
        except Exception:
            pass
        db.delete(video)
        deleted += 1
    db.commit()
    return deleted
