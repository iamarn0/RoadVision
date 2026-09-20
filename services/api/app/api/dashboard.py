from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.core import JobRepository, VideoRepository
from app.schemas.common import DashboardMetrics
from app.security.deps import RequireReader
from packages.db.models import PlateDetection, ProcessingJob, VehicleTrack, Video

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardMetrics)
def dashboard(_: RequireReader, db: Session = Depends(get_db)) -> DashboardMetrics:
    videos_processed = db.scalar(select(func.count()).select_from(Video)) or 0
    processing_jobs = db.scalar(select(func.count()).select_from(ProcessingJob)) or 0
    vehicles_detected = db.scalar(select(func.count()).select_from(VehicleTrack)) or 0
    unique_plates = db.scalar(
        select(func.count(func.distinct(PlateDetection.normalized_plate_text))).where(
            PlateDetection.normalized_plate_text.is_not(None)
        )
    ) or 0

    from app.api.jobs import _job_read
    from app.api.results import _to_read
    from app.api.videos import _video_read

    active = [_job_read(db, j) for j in JobRepository(db).active()]
    recent_videos = [_video_read(db, v) for v in VideoRepository(db).list(limit=8)]
    recent_rows = db.execute(
        select(PlateDetection, VehicleTrack)
        .join(VehicleTrack)
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
