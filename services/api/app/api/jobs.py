import json
from datetime import UTC, datetime
from pathlib import Path
from shutil import copy2
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AppError, ErrorCodes
from app.database import get_db
from app.jobs.celery_app import get_celery
from app.jobs.control import (
    clear_capture,
    clear_job_flags,
    clear_pause,
    is_paused,
    request_cancel,
    request_capture,
    request_pause,
    wait_capture_result,
)
from app.repositories.core import AssetRepository, JobRepository, VideoRepository
from app.schemas.common import CaptureJobResponse, JobRead, LiveCapturesResponse, ProcessJobRequest
from app.security.audit import write_audit
from app.security.deps import RequireOperator, RequireReader, client_ip
from app.security.districts import require_job_scope, require_video_scope, scoped_district_ids
from packages.capture_index import item_by_key, load_index, snapshot_index_item, upsert_index_item
from packages.overlay_clock import overlay_label
from packages.db.enums import AssetType, JobStatus
from packages.db.models import MediaAsset, ProcessingJob

router = APIRouter(tags=["jobs"])


def _storage_root() -> Path:
    return get_settings().storage_root_path


def _live_frame_path(job_id: UUID) -> Path:
    return (_storage_root() / "processed" / str(job_id) / "live.jpg").resolve()


def _live_raw_path(job_id: UUID) -> Path:
    return (_storage_root() / "processed" / str(job_id) / "live_raw.jpg").resolve()


def _captures_dir(job_id: UUID) -> Path:
    return (_storage_root() / "processed" / str(job_id) / "captures").resolve()


def _next_snapshot_index(captures_dir: Path) -> int:
    nums: list[int] = []
    if captures_dir.exists():
        for path in captures_dir.glob("snapshot_*.jpg"):
            try:
                nums.append(int(path.stem.split("_", 1)[1]))
            except (IndexError, ValueError):
                continue
    return (max(nums) + 1) if nums else 1


def _clock_label(overlay: str | None) -> str | None:
    text = (overlay or "").strip()
    return text or None


def _load_sidecar(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _merge_meta(*parts: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for part in parts:
        if part:
            merged.update(part)
    return merged


def _snapshot_item(job_id: UUID, path: Path, meta: dict[str, Any] | None = None, job_metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    snapshot_id = int(path.stem.split("_", 1)[1])
    first_seen = float((meta or {}).get("first_seen_seconds") or 0.0)
    overlay = _clock_label((meta or {}).get("captured_at") or overlay_label(job_metrics, first_seen))
    return {
        "track_id": snapshot_id,
        "kind": "snapshot",
        "label": f"Snapshot #{snapshot_id}",
        "plate_url": f"/api/jobs/{job_id}/live-captures/snapshots/{snapshot_id}",
        "vehicle_url": f"/api/jobs/{job_id}/live-captures/snapshots/{snapshot_id}",
        "full_url": f"/api/jobs/{job_id}/live-captures/snapshots/{snapshot_id}",
        "updated_at": path.stat().st_mtime,
        "vehicle_type": (meta or {}).get("vehicle_type") or None,
        "first_seen_seconds": first_seen,
        "last_seen_seconds": first_seen,
        "timestamp": first_seen,
        "timestamp_overlay": overlay,
        "last_seen_overlay": overlay,
    }


def _plate_item(job_id: UUID, path: Path, track_id: int, meta: dict[str, Any] | None = None, job_metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    first_seen = float((meta or {}).get("first_seen_seconds") if (meta or {}).get("first_seen_seconds") is not None else 0.0)
    last_seen = float((meta or {}).get("last_seen_seconds") if (meta or {}).get("last_seen_seconds") is not None else first_seen)
    overlay = _clock_label((meta or {}).get("captured_at") or overlay_label(job_metrics, first_seen))
    last_overlay = _clock_label((meta or {}).get("last_seen_overlay") or overlay_label(job_metrics, last_seen))
    return {
        "track_id": track_id,
        "kind": "plate",
        "label": f"Track #{track_id}",
        "plate_url": f"/api/jobs/{job_id}/live-captures/{track_id}/plate",
        "vehicle_url": f"/api/jobs/{job_id}/live-captures/{track_id}/vehicle",
        "full_url": f"/api/jobs/{job_id}/live-captures/{track_id}/full",
        "updated_at": path.stat().st_mtime,
        "vehicle_type": (meta or {}).get("vehicle_type") or None,
        "first_seen_seconds": first_seen,
        "last_seen_seconds": last_seen,
        "timestamp": first_seen,
        "timestamp_overlay": overlay,
        "last_seen_overlay": last_overlay,
        "plate_confidence": (meta or {}).get("plate_confidence"),
        "vehicle_confidence": (meta or {}).get("vehicle_confidence"),
    }


def _job_overlay_clock(job: ProcessingJob, captures_dir: Path) -> dict[str, Any] | None:
    index = load_index(captures_dir) if captures_dir.exists() else {"overlay_clock": None}
    if index.get("overlay_clock"):
        return index["overlay_clock"]
    metrics = job.metrics if isinstance(job.metrics, dict) else {}
    clock = metrics.get("overlay_clock")
    return clock if isinstance(clock, dict) else None


def _save_live_snapshot(job: ProcessingJob, db: Session | None = None) -> Path:
    raw = _live_raw_path(job.id)
    live = _live_frame_path(job.id)
    src = raw if raw.exists() else live
    if not src.exists():
        raise AppError(ErrorCodes.NOT_FOUND, "Live frame is not available yet", status_code=404)
    captures_dir = _captures_dir(job.id)
    captures_dir.mkdir(parents=True, exist_ok=True)
    dest = captures_dir / f"snapshot_{_next_snapshot_index(captures_dir)}.jpg"
    copy2(src, dest)
    video = VideoRepository(db).get(job.video_id) if db is not None else None
    fps = float(getattr(video, "fps", 0) or 25.0) or 25.0
    seconds = float(job.current_frame or 0) / fps
    clock = _job_overlay_clock(job, captures_dir)
    upsert_index_item(captures_dir, snapshot_index_item(int(dest.stem.split("_", 1)[1]), seconds, clock), clock)
    return dest


def _job_read(db: Session, job: ProcessingJob) -> JobRead:
    video = VideoRepository(db).get(job.video_id)
    assets = AssetRepository(db).for_job(job.id, AssetType.ANNOTATED_VIDEO.value)
    original = None
    if video:
        original = db.scalar(
            select(MediaAsset).where(
                MediaAsset.video_id == video.id,
                MediaAsset.asset_type == AssetType.ORIGINAL_VIDEO.value,
            )
        )
    live_path = _live_frame_path(job.id)
    district = video.district if video else None
    payload = JobRead.model_validate(job).model_copy(
        update={
            "source_filename": video.original_filename if video else None,
            "annotated_asset_id": assets[0].id if assets else None,
            "original_asset_id": original.id if original else None,
            "source_fps": video.fps if video else None,
            "live_frame_available": live_path.exists(),
            "paused": is_paused(job.id),
            "district_id": video.district_id if video else None,
            "district_name": district.name if district else None,
        }
    )
    return payload


@router.post("/api/videos/{video_id}/process", summary="Create an ANPR processing job", response_model=JobRead)
def create_job(
    video_id: UUID,
    request: Request,
    user: RequireOperator,
    body: ProcessJobRequest | None = None,
    db: Session = Depends(get_db),
) -> JobRead:
    body = body or ProcessJobRequest()
    video = require_video_scope(VideoRepository(db).get(video_id), scoped_district_ids(db, user))
    settings = get_settings()
    job = ProcessingJob(
        video_id=video.id,
        processing_run_id=uuid4(),
        status=JobStatus.QUEUED.value,
        total_frames=video.frame_count or 0,
        requested_device=settings.processing_device,
        processing_profile=body.processing_profile,
        ocr_engine=settings.ocr_engine,
        model_versions={
            "vehicle": settings.vehicle_model_version,
            "plate": settings.plate_model_version,
            "overrides": body.model_dump(),
        },
        created_by_user_id=None if settings.auth_disabled else user.id,
    )
    JobRepository(db).add(job)
    write_audit(
        db,
        action="job_start",
        user_id=None if settings.auth_disabled else user.id,
        resource_type="job",
        resource_id=None,
        ip=client_ip(request),
        details={"video_id": str(video_id)},
    )
    db.commit()
    db.refresh(job)
    try:
        async_result = get_celery().send_task("worker.process_video", args=[str(job.id)])
        job.celery_task_id = async_result.id
        db.commit()
    except Exception:
        job.status = JobStatus.FAILED.value
        job.error_code = ErrorCodes.WORKER_UNAVAILABLE
        job.error_message = "The processing worker could not be reached. Start Redis and the Celery worker."
        db.commit()
    return _job_read(db, job)


@router.get("/api/jobs", summary="List processing jobs", response_model=list[JobRead])
def list_jobs(user: RequireReader, db: Session = Depends(get_db)) -> list[JobRead]:
    return [_job_read(db, job) for job in JobRepository(db).list(district_ids=scoped_district_ids(db, user))]


@router.get("/api/jobs/{job_id}", summary="Get job status", response_model=JobRead)
def get_job(job_id: UUID, user: RequireReader, db: Session = Depends(get_db)) -> JobRead:
    job = require_job_scope(db, JobRepository(db).get(job_id), scoped_district_ids(db, user))
    return _job_read(db, job)


@router.get("/api/jobs/{job_id}/live-frame", summary="Latest annotated live frame JPEG")
def get_live_frame(job_id: UUID, user: RequireReader, db: Session = Depends(get_db)) -> FileResponse:
    require_job_scope(db, JobRepository(db).get(job_id), scoped_district_ids(db, user))
    path = _live_frame_path(job_id)
    if not path.exists():
        raise AppError(ErrorCodes.NOT_FOUND, "Live frame is not available yet", status_code=404)
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/api/jobs/{job_id}/live-captures", summary="Plate crops captured so far", response_model=LiveCapturesResponse)
def get_live_captures(job_id: UUID, user: RequireReader, db: Session = Depends(get_db)) -> dict[str, Any]:
    job = require_job_scope(db, JobRepository(db).get(job_id), scoped_district_ids(db, user))
    captures_dir = _captures_dir(job_id)
    items: list[dict[str, Any]] = []
    if captures_dir.exists():
        index = load_index(captures_dir)
        clock = index.get("overlay_clock")
        if not clock and isinstance(job.metrics, dict):
            clock = job.metrics.get("overlay_clock")
        job_metrics = {"overlay_clock": clock} if clock else (job.metrics if isinstance(job.metrics, dict) else None)
        for path in captures_dir.glob("snapshot_*.jpg"):
            try:
                snapshot_id = int(path.stem.split("_", 1)[1])
            except (IndexError, ValueError):
                continue
            meta = _merge_meta(item_by_key(index, f"snapshot-{snapshot_id}"), _load_sidecar(captures_dir / f"snapshot_{snapshot_id}.json"))
            items.append(_snapshot_item(job_id, path, meta, job_metrics))
        for path in captures_dir.glob("track_*.jpg"):
            try:
                track_id = int(path.stem.split("_", 1)[1])
            except (IndexError, ValueError):
                continue
            meta = _merge_meta(item_by_key(index, f"plate-{track_id}"), _load_sidecar(captures_dir / f"track_{track_id}.json"))
            items.append(_plate_item(job_id, path, track_id, meta, job_metrics))
    items.sort(
        key=lambda item: (
            float(item.get("first_seen_seconds") or 0) or float(item["updated_at"]),
            float(item["updated_at"]),
        ),
        reverse=True,
    )
    return {"job_id": str(job_id), "plates_captured": len([i for i in items if i.get("kind") != "snapshot"]), "items": items}


@router.get("/api/jobs/{job_id}/live-captures/snapshots/{snapshot_id}", summary="Serve a manual frame snapshot")
def get_live_snapshot(
    job_id: UUID,
    snapshot_id: int,
    user: RequireReader,
    db: Session = Depends(get_db),
) -> FileResponse:
    require_job_scope(db, JobRepository(db).get(job_id), scoped_district_ids(db, user))
    path = _captures_dir(job_id) / f"snapshot_{snapshot_id}.jpg"
    if not path.exists():
        raise AppError(ErrorCodes.NOT_FOUND, "Capture not found", status_code=404)
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/api/jobs/{job_id}/live-captures/{track_id}/{kind}", summary="Serve a live plate/vehicle crop")
def get_live_capture_image(
    job_id: UUID,
    track_id: int,
    kind: str,
    user: RequireReader,
    db: Session = Depends(get_db),
) -> FileResponse:
    require_job_scope(db, JobRepository(db).get(job_id), scoped_district_ids(db, user))
    if kind not in {"plate", "vehicle", "full"}:
        raise AppError(ErrorCodes.VALIDATION_ERROR, "kind must be plate, vehicle, or full", status_code=400)
    filename = {"plate": f"track_{track_id}.jpg", "vehicle": f"vehicle_{track_id}.jpg", "full": f"full_{track_id}.jpg"}[kind]
    path = _captures_dir(job_id) / filename
    if not path.exists():
        raise AppError(ErrorCodes.NOT_FOUND, "Capture not found", status_code=404)
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


def _require_processing_job(job: ProcessingJob | None) -> ProcessingJob:
    if not job:
        raise AppError(ErrorCodes.NOT_FOUND, "Job not found", status_code=404)
    if job.status != JobStatus.PROCESSING.value:
        raise AppError(
            ErrorCodes.CONFLICT,
            f"Job cannot be controlled from status {job.status}",
            status_code=409,
        )
    return job


@router.post("/api/jobs/{job_id}/pause", summary="Pause a running job", response_model=JobRead)
def pause_job(job_id: UUID, user: RequireOperator, db: Session = Depends(get_db)) -> JobRead:
    job = _require_processing_job(require_job_scope(db, JobRepository(db).get(job_id), scoped_district_ids(db, user)))
    request_pause(job.id)
    return _job_read(db, job)


@router.post("/api/jobs/{job_id}/resume", summary="Resume a paused job", response_model=JobRead)
def resume_job(job_id: UUID, user: RequireOperator, db: Session = Depends(get_db)) -> JobRead:
    job = _require_processing_job(require_job_scope(db, JobRepository(db).get(job_id), scoped_district_ids(db, user)))
    clear_pause(job.id)
    return _job_read(db, job)


@router.post("/api/jobs/{job_id}/capture", summary="Capture the current live frame", response_model=CaptureJobResponse)
def capture_job(job_id: UUID, user: RequireOperator, db: Session = Depends(get_db)) -> CaptureJobResponse:
    job = _require_processing_job(require_job_scope(db, JobRepository(db).get(job_id), scoped_district_ids(db, user)))
    dest = _save_live_snapshot(job, db)
    request_capture(job.id)
    wait_capture_result(job.id)
    payload = _job_read(db, job).model_dump()
    snapshot_id = int(dest.stem.split("_", 1)[1])
    meta = item_by_key(load_index(_captures_dir(job.id)), f"snapshot-{snapshot_id}")
    clock = _job_overlay_clock(job, _captures_dir(job.id))
    payload["snapshot"] = _snapshot_item(job.id, dest, meta, {"overlay_clock": clock} if clock else None)
    return CaptureJobResponse.model_validate(payload)


@router.post("/api/jobs/{job_id}/cancel", summary="Cancel a running job", response_model=JobRead)
def cancel_job(job_id: UUID, user: RequireOperator, db: Session = Depends(get_db)) -> JobRead:
    job = require_job_scope(db, JobRepository(db).get(job_id), scoped_district_ids(db, user))
    if job.status in {JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value}:
        raise AppError(ErrorCodes.CONFLICT, f"Job cannot be cancelled from status {job.status}", status_code=409)
    request_cancel(job.id)
    clear_pause(job.id)
    clear_capture(job.id)
    job.status = JobStatus.CANCELLED.value
    job.completed_at = datetime.now(UTC)
    job.error_code = None
    job.error_message = "Cancelled by operator"
    db.commit()
    db.refresh(job)
    return _job_read(db, job)


def _wipe_run_results(db: Session, job: ProcessingJob) -> None:
    for track in list(job.tracks):
        db.delete(track)
    for asset in list(job.assets):
        if asset.asset_type != AssetType.ORIGINAL_VIDEO.value:
            db.delete(asset)
    db.flush()


@router.post("/api/jobs/{job_id}/retry", summary="Retry a failed or cancelled job", response_model=JobRead)
def retry_job(job_id: UUID, user: RequireOperator, db: Session = Depends(get_db)) -> JobRead:
    job = require_job_scope(db, JobRepository(db).get(job_id), scoped_district_ids(db, user))
    _wipe_run_results(db, job)
    clear_job_flags(job.id)
    job.processing_run_id = uuid4()
    job.status = JobStatus.QUEUED.value
    job.progress = 0
    job.current_frame = 0
    job.processed_frames = 0
    job.skipped_frames = 0
    job.processing_fps = None
    job.estimated_remaining_seconds = None
    job.error_code = None
    job.error_message = None
    job.fallback_reason = None
    job.started_at = None
    job.completed_at = None
    job.vehicles_detected = 0
    job.plates_detected = 0
    db.commit()
    try:
        async_result = get_celery().send_task("worker.process_video", args=[str(job.id)])
        job.celery_task_id = async_result.id
        db.commit()
    except Exception:
        job.status = JobStatus.FAILED.value
        job.error_code = ErrorCodes.WORKER_UNAVAILABLE
        job.error_message = "The processing worker could not be reached."
        db.commit()
    db.refresh(job)
    return _job_read(db, job)
