from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.errors import AppError, ErrorCodes
from app.database.session import get_session_factory
from app.repositories.core import AssetRepository
from app.security.deps import RequireReader
from app.storage.service import get_storage

router = APIRouter(prefix="/api/media", tags=["media"])


@router.get("/{asset_id}", summary="Stream a stored media asset by opaque ID")
def get_media(asset_id: UUID, _: RequireReader) -> FileResponse:
    db = get_session_factory()()
    try:
        asset = AssetRepository(db).get(asset_id)
        if not asset:
            raise AppError(ErrorCodes.NOT_FOUND, "Media asset not found", status_code=404)
        path = get_storage().get_path(asset.storage_key)
        mime = asset.mime_type or "application/octet-stream"
        name = path.name
    finally:
        db.close()
    return FileResponse(path, media_type=mime, filename=name)
