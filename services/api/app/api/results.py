from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError, ErrorCodes
from app.database import get_db
from app.repositories.core import JobRepository
from app.schemas.common import (
    DetectionDetail,
    DetectionRead,
    JobResults,
    ObservationRead,
    PaginatedDetections,
    PaginatedObservations,
)
from app.security.deps import RequireReader
from app.security.districts import require_job_scope, scoped_district_ids, video_scope_clause
from packages.db.models import Observation, PlateDetection, ProcessingJob, VehicleTrack, Video
from packages.overlay_clock import overlay_label

router = APIRouter(tags=["results"])


def _detection_query():
    return (
        select(PlateDetection, VehicleTrack)
        .join(VehicleTrack, PlateDetection.vehicle_track_id == VehicleTrack.id)
    )


def _to_read(
    det: PlateDetection,
    track: VehicleTrack,
    job_metrics: dict | None = None,
) -> DetectionRead:
    return DetectionRead(
        id=det.id,
        track_id=track.track_id,
        vehicle_type=track.vehicle_type,
        vehicle_track_id=track.id,
        raw_ocr_text=det.raw_ocr_text,
        normalized_plate_text=det.normalized_plate_text,
        ocr_confidence=det.ocr_confidence,
        plate_detection_confidence=det.plate_detection_confidence,
        vehicle_detection_confidence=track.detection_confidence,
        status=det.status,
        first_seen_seconds=det.first_seen_seconds,
        last_seen_seconds=det.last_seen_seconds,
        first_seen_overlay=overlay_label(job_metrics, det.first_seen_seconds),
        last_seen_overlay=overlay_label(job_metrics, det.last_seen_seconds),
        best_frame_number=det.best_frame_number,
        consistency_score=det.consistency_score,
        full_frame_asset_id=det.full_frame_asset_id,
        vehicle_crop_asset_id=det.vehicle_crop_asset_id,
        plate_crop_asset_id=det.plate_crop_asset_id,
    )


@router.get("/api/jobs/{job_id}/results", summary="Paginated unique detections", response_model=JobResults)
def job_results(
    job_id: UUID,
    user: RequireReader,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = None,
    vehicle_type: str | None = None,
    status: str | None = None,
    sort: str = Query("newest"),
    db: Session = Depends(get_db),
) -> JobResults:
    from app.api.jobs import _job_read

    job = require_job_scope(db, JobRepository(db).get(job_id), scoped_district_ids(db, user))

    stmt = _detection_query().where(VehicleTrack.processing_job_id == job_id)
    if search:
        like = f"%{search.upper()}%"
        stmt = stmt.where(func.upper(PlateDetection.normalized_plate_text).like(like))
    if vehicle_type:
        stmt = stmt.where(VehicleTrack.vehicle_type == vehicle_type)
    if status:
        stmt = stmt.where(PlateDetection.status == status)

    if sort == "oldest":
        stmt = stmt.order_by(PlateDetection.first_seen_seconds.asc())
    elif sort == "highest_confidence":
        stmt = stmt.order_by(PlateDetection.plate_detection_confidence.desc())
    elif sort == "lowest_confidence":
        stmt = stmt.order_by(PlateDetection.plate_detection_confidence.asc())
    else:
        stmt = stmt.order_by(PlateDetection.first_seen_seconds.desc())

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    items = [_to_read(det, track, job.metrics) for det, track in rows]
    unique_vehicles = db.scalar(
        select(func.count()).select_from(VehicleTrack).where(VehicleTrack.processing_job_id == job_id)
    ) or 0
    unique_plates = db.scalar(
        select(func.count()).select_from(PlateDetection)
        .join(VehicleTrack)
        .where(VehicleTrack.processing_job_id == job_id)
    ) or 0
    return JobResults(
        job=_job_read(db, job),
        unique_vehicles=int(unique_vehicles),
        unique_plates=int(unique_plates),
        detections=PaginatedDetections(items=items, total=int(total), page=page, page_size=page_size),
    )


@router.get("/api/jobs/{job_id}/observations", summary="Paginated raw OCR observations", response_model=PaginatedObservations)
def job_observations(
    job_id: UUID,
    user: RequireReader,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PaginatedObservations:
    require_job_scope(db, JobRepository(db).get(job_id), scoped_district_ids(db, user))
    stmt = (
        select(Observation)
        .join(PlateDetection)
        .join(VehicleTrack)
        .where(VehicleTrack.processing_job_id == job_id)
        .order_by(Observation.frame_number.asc())
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return PaginatedObservations(
        items=[ObservationRead.model_validate(o) for o in items],
        total=int(total),
        page=page,
        page_size=page_size,
    )


@router.get("/api/plate-detections/{detection_id}", summary="Detection detail with OCR history", response_model=DetectionDetail)
def detection_detail(detection_id: UUID, user: RequireReader, db: Session = Depends(get_db)) -> DetectionDetail:
    row = db.execute(
        _detection_query()
        .options(selectinload(PlateDetection.observations))
        .where(PlateDetection.id == detection_id)
    ).first()
    if not row:
        raise AppError(ErrorCodes.NOT_FOUND, "Detection not found", status_code=404)
    det, track = row
    job = db.get(ProcessingJob, track.processing_job_id)
    require_job_scope(db, job, scoped_district_ids(db, user))
    base = _to_read(det, track, job.metrics if job else None)
    observations = sorted(det.observations, key=lambda o: o.frame_number)
    return DetectionDetail(
        **base.model_dump(),
        observations=[ObservationRead.model_validate(o) for o in observations],
    )


@router.get("/api/detections", summary="Cross-job unique detections", response_model=PaginatedDetections)
def all_detections(
    user: RequireReader,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = None,
    db: Session = Depends(get_db),
) -> PaginatedDetections:
    stmt = (
        _detection_query()
        .join(ProcessingJob, VehicleTrack.processing_job_id == ProcessingJob.id)
        .join(Video, ProcessingJob.video_id == Video.id)
        .where(video_scope_clause(scoped_district_ids(db, user)))
        .order_by(PlateDetection.created_at.desc())
    )
    if search:
        stmt = stmt.where(func.upper(PlateDetection.normalized_plate_text).like(f"%{search.upper()}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    job_ids = {track.processing_job_id for _, track in rows}
    jobs = (
        {job.id: job for job in db.scalars(select(ProcessingJob).where(ProcessingJob.id.in_(job_ids))).all()}
        if job_ids
        else {}
    )
    return PaginatedDetections(
        items=[
            _to_read(d, t, jobs[t.processing_job_id].metrics if t.processing_job_id in jobs else None)
            for d, t in rows
        ],
        total=int(total),
        page=page,
        page_size=page_size,
    )
