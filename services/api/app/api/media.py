from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from packages.video_normalize import playable_copy

from app.database import get_db
from app.repositories.core import AssetRepository
from app.security.deps import RequireReader
from app.security.districts import require_asset_scope, scoped_district_ids
from app.storage.service import get_storage
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/media", tags=["media"])

_VIDEO_MIME = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
}


def media_content_type(path_name: str, stored: str | None) -> str:
    """Browsers will not start playback when a video is served as octet-stream."""
    suffix = path_name.rsplit(".", 1)[-1].lower() if "." in path_name else ""
    ext = f".{suffix}" if suffix else ""
    mime = (stored or "").split(";")[0].strip().lower()
    if ext in {".mp4", ".m4v"}:
        return "video/mp4"
    if mime.startswith("video/"):
        return mime
    return _VIDEO_MIME.get(ext, mime or "application/octet-stream")


@router.get("/{asset_id}", summary="Stream a stored media asset by opaque ID")
def get_media(asset_id: UUID, user: RequireReader, db: Session = Depends(get_db)) -> FileResponse:
    asset = require_asset_scope(db, AssetRepository(db).get(asset_id), scoped_district_ids(db, user))
    path = get_storage().get_path(asset.storage_key)
    mime = media_content_type(path.name, asset.mime_type)
    if mime.startswith("video/"):
        path = playable_copy(path)
        mime = media_content_type(path.name, "video/mp4")
    return FileResponse(
        path,
        media_type=mime,
        filename=path.name,
        content_disposition_type="inline",
        headers={"Cache-Control": "no-cache"},
    )
