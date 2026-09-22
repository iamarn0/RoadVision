"""District catalog, appointments, and case-data scoping."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import false, select, true
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from app.config import get_settings
from app.core.errors import AppError, ErrorCodes
from packages.db.districts import WEST_BENGAL_DISTRICTS, district_slug
from packages.db.models import District, Export, MediaAsset, ProcessingJob, User, UserDistrict, Video


def seed_west_bengal_districts(db: Session) -> None:
    existing = set(db.scalars(select(District.name)).all())
    for name in WEST_BENGAL_DISTRICTS:
        if name in existing:
            continue
        db.add(District(name=name, slug=district_slug(name)))
    db.commit()


def list_districts(db: Session) -> list[District]:
    return list(db.scalars(select(District).order_by(District.name)))


def districts_for_user(db: Session, user: User) -> list[District]:
    if get_settings().auth_disabled:
        return list_districts(db)
    return list(
        db.scalars(
            select(District)
            .join(UserDistrict, UserDistrict.district_id == District.id)
            .where(UserDistrict.user_id == user.id)
            .order_by(District.name)
        )
    )


def scoped_district_ids(db: Session, user: User) -> set[UUID] | None:
    """Return appointed district ids, or None when access is unrestricted."""
    if get_settings().auth_disabled:
        return None
    return set(db.scalars(select(UserDistrict.district_id).where(UserDistrict.user_id == user.id)).all())


def video_scope_clause(district_ids: set[UUID] | None) -> ColumnElement[bool]:
    if district_ids is None:
        return true()
    if not district_ids:
        return false()
    return Video.district_id.in_(district_ids)


def video_in_scope(video: Video | None, district_ids: set[UUID] | None) -> bool:
    if video is None:
        return False
    if district_ids is None:
        return True
    return video.district_id is not None and video.district_id in district_ids


def require_video_scope(video: Video | None, district_ids: set[UUID] | None, message: str = "Video not found") -> Video:
    if not video_in_scope(video, district_ids):
        raise AppError(ErrorCodes.NOT_FOUND, message, status_code=404)
    assert video is not None
    return video


def require_job_scope(db: Session, job: ProcessingJob | None, district_ids: set[UUID] | None) -> ProcessingJob:
    if not job:
        raise AppError(ErrorCodes.NOT_FOUND, "Job not found", status_code=404)
    video = db.get(Video, job.video_id)
    require_video_scope(video, district_ids, "Job not found")
    return job


def require_asset_scope(db: Session, asset: MediaAsset | None, district_ids: set[UUID] | None) -> MediaAsset:
    if not asset:
        raise AppError(ErrorCodes.NOT_FOUND, "Media asset not found", status_code=404)
    video: Video | None = None
    if asset.video_id:
        video = db.get(Video, asset.video_id)
    elif asset.processing_job_id:
        job = db.get(ProcessingJob, asset.processing_job_id)
        if job:
            video = db.get(Video, job.video_id)
    require_video_scope(video, district_ids, "Media asset not found")
    return asset


def require_export_scope(db: Session, export: Export | None, district_ids: set[UUID] | None) -> Export:
    if not export:
        raise AppError(ErrorCodes.NOT_FOUND, "Export not found", status_code=404)
    job = db.get(ProcessingJob, export.processing_job_id)
    require_job_scope(db, job, district_ids)
    return export


def require_appointed_district(db: Session, user: User, district_id: UUID) -> District:
    district = db.get(District, district_id)
    if not district:
        raise AppError(ErrorCodes.VALIDATION_ERROR, "Unknown district", status_code=400)
    allowed = scoped_district_ids(db, user)
    if allowed is not None and district.id not in allowed:
        raise AppError(ErrorCodes.FORBIDDEN, "You are not appointed to that district", status_code=403)
    return district
