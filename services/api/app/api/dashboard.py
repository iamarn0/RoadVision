from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.core import JobRepository, VideoRepository
from app.schemas.common import DashboardMetrics
from app.security.deps import RequireReader
from app.security.districts import scoped_district_ids, video_scope_clause
from packages.db.models import PlateDetection, ProcessingJob, VehicleTrack, Video

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardMetrics)
def dashboard(user: RequireReader, db: Session = Depends(get_db)) -> DashboardMetrics:
    scope = scoped_district_ids(db, user)
    video_clause = video_scope_clause(scope)
    videos_processed = db.scalar(select(func.count()).select_from(Video).where(video_clause)) or 0
    processing_jobs = (
        db.scalar(
            select(func.count())
            .select_from(ProcessingJob)
            .join(Video, ProcessingJob.video_id == Video.id)
            .where(video_clause)
        )
        or 0
    )
    vehicles_detected = (
        db.scalar(
            select(func.count())
            .select_from(VehicleTrack)
            .join(ProcessingJob, VehicleTrack.processing_job_id == ProcessingJob.id)
            .join(Video, ProcessingJob.video_id == Video.id)
            .where(video_clause)
        )
        or 0
    )
    unique_plates = (
        db.scalar(
            select(func.count(func.distinct(PlateDetection.normalized_plate_text)))
            .select_from(PlateDetection)
            .join(VehicleTrack, PlateDetection.vehicle_track_id == VehicleTrack.id)
            .join(ProcessingJob, VehicleTrack.processing_job_id == ProcessingJob.id)
            .join(Video, ProcessingJob.video_id == Video.id)
            .where(PlateDetection.normalized_plate_text.is_not(None), video_clause)
        )
        or 0
    )

    from app.api.jobs import _job_read
    from app.api.results import _to_read
    from app.api.videos import _video_read

    active = [_job_read(db, j) for j in JobRepository(db).active(district_ids=scope)]
    recent_videos = [_video_read(db, v) for v in VideoRepository(db).list(limit=8, district_ids=scope)]
    recent_rows = db.execute(
        select(PlateDetection, VehicleTrack)
        .join(VehicleTrack)
        .join(ProcessingJob, VehicleTrack.processing_job_id == ProcessingJob.id)
        .join(Video, ProcessingJob.video_id == Video.id)
        .where(video_clause)
        .order_by(PlateDetection.created_at.desc())
        .limit(8)
    ).all()
    recent_detections = [_to_read(d, t) for d, t in recent_rows]
    return DashboardMetrics(
        videos_processed=int(videos_processed),
        processing_jobs=int(processing_jobs),
        vehicles_detected=int(vehicles_detected),
        unique_plates=int(unique_plates),
        active_jobs=active,
        recent_videos=recent_videos,
        recent_detections=recent_detections,
    )
