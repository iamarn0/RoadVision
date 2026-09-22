from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from packages.db.models import Export, MediaAsset, Observation, PlateDetection, ProcessingJob, VehicleTrack, Video


class VideoRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, video: Video) -> Video:
        self.db.add(video)
        self.db.flush()
        return video

    def get(self, video_id: UUID) -> Video | None:
        return self.db.scalar(
            select(Video).options(selectinload(Video.district)).where(Video.id == video_id)
        )

    def list(self, limit: int = 50, district_ids: set[UUID] | None = None) -> list[Video]:
        from app.security.districts import video_scope_clause

        stmt = (
            select(Video)
            .options(selectinload(Video.district))
            .where(video_scope_clause(district_ids))
            .order_by(Video.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def delete(self, video: Video) -> None:
        self.db.delete(video)


class JobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, job: ProcessingJob) -> ProcessingJob:
        self.db.add(job)
        self.db.flush()
        return job

    def get(self, job_id: UUID) -> ProcessingJob | None:
        return self.db.get(ProcessingJob, job_id)

    def list(self, limit: int = 50, district_ids: set[UUID] | None = None) -> list[ProcessingJob]:
        from app.security.districts import video_scope_clause

        stmt = (
            select(ProcessingJob)
            .join(Video, ProcessingJob.video_id == Video.id)
            .where(video_scope_clause(district_ids))
            .order_by(ProcessingJob.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def active(self, district_ids: set[UUID] | None = None) -> list[ProcessingJob]:
        from app.security.districts import video_scope_clause

        stmt = (
            select(ProcessingJob)
            .join(Video, ProcessingJob.video_id == Video.id)
            .where(
                ProcessingJob.status.in_(["queued", "validating", "processing", "finalizing"]),
                video_scope_clause(district_ids),
            )
            .order_by(ProcessingJob.created_at.desc())
        )
        return list(self.db.scalars(stmt))


class AssetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, asset: MediaAsset) -> MediaAsset:
        self.db.add(asset)
        self.db.flush()
        return asset

    def get(self, asset_id: UUID) -> MediaAsset | None:
        return self.db.get(MediaAsset, asset_id)

    def for_job(self, job_id: UUID, asset_type: str | None = None) -> list[MediaAsset]:
        stmt = select(MediaAsset).where(MediaAsset.processing_job_id == job_id)
        if asset_type:
            stmt = stmt.where(MediaAsset.asset_type == asset_type)
        return list(self.db.scalars(stmt))
