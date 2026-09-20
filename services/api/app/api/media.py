from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCodes
from app.database import get_db
from app.repositories.core import AssetRepository
from app.security.deps import RequireReader
from app.storage.service import get_storage

router = APIRouter(prefix="/api/media", tags=["media"])


@router.get("/{asset_id}", summary="Stream a stored media asset by opaque ID")
def get_media(asset_id: UUID, _: RequireReader, db: Session = Depends(get_db)) -> FileResponse:
    asset = AssetRepository(db).get(asset_id)
    if not asset:
        raise AppError(ErrorCodes.NOT_FOUND, "Media asset not found", status_code=404)
    path = get_storage().get_path(asset.storage_key)
    return FileResponse(path, media_type=asset.mime_type or "application/octet-stream", filename=path.name)
