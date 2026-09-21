from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.errors import AppError, ErrorCodes
from app.database.session import get_session_factory
from app.repositories.core import AssetRepository
from app.security.deps import RequireReader
from app.storage.service import get_storage

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
def get_media(asset_id: UUID, _: RequireReader) -> FileResponse:
    db = get_session_factory()()
    try:
        asset = AssetRepository(db).get(asset_id)
        if not asset:
            raise AppError(ErrorCodes.NOT_FOUND, "Media asset not found", status_code=404)
        path = get_storage().get_path(asset.storage_key)
        mime = media_content_type(path.name, asset.mime_type)
        name = path.name
    finally:
        db.close()
    return FileResponse(path, media_type=mime, filename=name, content_disposition_type="inline")
