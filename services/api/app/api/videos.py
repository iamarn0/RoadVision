from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AppError, ErrorCodes
from app.database import get_db
from app.repositories.core import AssetRepository, VideoRepository
from app.schemas.common import VideoRead
from app.security.audit import write_audit
from app.security.deps import RequireAdmin, RequireOperator, RequireReader, client_ip
from app.services.video_validation import probe_video_metadata, validate_upload
from app.storage.service import get_storage
from packages.db.enums import AssetType, VideoStatus
from packages.db.models import MediaAsset, Video

router = APIRouter(prefix="/api/videos", tags=["videos"])


def _video_read(db: Session, video: Video) -> VideoRead:
    asset = db.scalar(
        select(MediaAsset).where(
            MediaAsset.video_id == video.id,
            MediaAsset.asset_type == AssetType.ORIGINAL_VIDEO.value,
        )
    )
    data = VideoRead.model_validate(video)
    return data.model_copy(update={"original_asset_id": asset.id if asset else None})


@router.post("/upload", summary="Upload a roadside video file", response_model=VideoRead)
async def upload_video(
    request: Request,
    user: RequireOperator,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> VideoRead:
    settings = get_settings()
    filename = file.filename or "upload.bin"
    data = await file.read()
    validate_upload(filename, file.content_type, len(data), settings)

    storage = get_storage()
    storage_key = storage.save("uploads", filename, data)
    path = storage.get_path(storage_key)
    try:
        meta = probe_video_metadata(path)
    except AppError:
        storage.delete(storage_key)
        raise

    video = Video(
        original_filename=Path(filename).name,
        storage_key=storage_key,
        file_size=len(data),
        mime_type=file.content_type,
        duration=meta.get("duration"),
        width=meta.get("width"),
        height=meta.get("height"),
        fps=meta.get("fps"),
        frame_count=meta.get("frame_count"),
        codec=meta.get("codec"),
        status=VideoStatus.READY.value,
        source_type=settings.default_source_type,
        source_id=str(path.name),
        created_by_user_id=None if get_settings().auth_disabled else user.id,
    )
    VideoRepository(db).add(video)
    AssetRepository(db).add(
        MediaAsset(
            video_id=video.id,
            asset_type=AssetType.ORIGINAL_VIDEO.value,
            storage_key=storage_key,
            mime_type=file.content_type,
            file_size=len(data),
            checksum=storage.checksum(storage_key) if hasattr(storage, "checksum") else None,
        )
    )
    write_audit(
        db,
        action="video_upload",
        user_id=None if settings.auth_disabled else user.id,
        resource_type="video",
        resource_id=None,
        ip=client_ip(request),
        details={"filename": Path(filename).name},
    )
    db.commit()
    db.refresh(video)
    return _video_read(db, video)


@router.get("", summary="List uploaded videos", response_model=list[VideoRead])
def list_videos(_: RequireReader, db: Session = Depends(get_db)) -> list[VideoRead]:
    return [_video_read(db, v) for v in VideoRepository(db).list()]


@router.get("/{video_id}", summary="Get video metadata", response_model=VideoRead)
def get_video(video_id: UUID, _: RequireReader, db: Session = Depends(get_db)) -> VideoRead:
    video = VideoRepository(db).get(video_id)
    if not video:
        raise AppError(ErrorCodes.NOT_FOUND, "Video not found", status_code=404)
    return _video_read(db, video)


@router.delete("/{video_id}", summary="Delete a video and its files")
def delete_video(
    video_id: UUID,
    request: Request,
    admin: RequireAdmin,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    repo = VideoRepository(db)
    video = repo.get(video_id)
    if not video:
        raise AppError(ErrorCodes.NOT_FOUND, "Video not found", status_code=404)
    storage = get_storage()
    storage.delete(video.storage_key)
    write_audit(
        db,
        action="video_delete",
        user_id=None if get_settings().auth_disabled else admin.id,
        resource_type="video",
        resource_id=str(video.id),
        ip=client_ip(request),
    )
    repo.delete(video)
    db.commit()
    return {"status": "deleted"}
