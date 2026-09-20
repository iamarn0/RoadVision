from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AppError, ErrorCodes
from app.database import get_db
from app.schemas.common import ExportRead
from app.security.audit import write_audit
from app.security.deps import RequireOperator, RequireReader, client_ip
from app.services.exports import create_export
from packages.db.models import Export

router = APIRouter(tags=["exports"])


def _create(job_id: UUID, export_type: str, request: Request, user, db: Session) -> ExportRead:
    export = create_export(db, job_id, export_type)
    write_audit(
        db,
        action="export_create",
        user_id=None if get_settings().auth_disabled else user.id,
        resource_type="export",
        resource_id=str(export.id),
        ip=client_ip(request),
        details={"type": export_type, "job_id": str(job_id)},
    )
    db.commit()
    return ExportRead.model_validate(export)


@router.post("/api/jobs/{job_id}/exports/csv", response_model=ExportRead)
def export_csv(
    job_id: UUID, request: Request, user: RequireOperator, db: Session = Depends(get_db)
) -> ExportRead:
    return _create(job_id, "csv", request, user, db)


@router.post("/api/jobs/{job_id}/exports/xlsx", response_model=ExportRead)
def export_xlsx(
    job_id: UUID, request: Request, user: RequireOperator, db: Session = Depends(get_db)
) -> ExportRead:
    return _create(job_id, "xlsx", request, user, db)


@router.post("/api/jobs/{job_id}/exports/json", response_model=ExportRead)
def export_json(
    job_id: UUID, request: Request, user: RequireOperator, db: Session = Depends(get_db)
) -> ExportRead:
    return _create(job_id, "json", request, user, db)


@router.post("/api/jobs/{job_id}/exports/evidence-zip", response_model=ExportRead)
def export_zip(
    job_id: UUID, request: Request, user: RequireOperator, db: Session = Depends(get_db)
) -> ExportRead:
    return _create(job_id, "evidence-zip", request, user, db)


@router.get("/api/exports/{export_id}", response_model=ExportRead)
def get_export(export_id: UUID, _: RequireReader, db: Session = Depends(get_db)) -> ExportRead:
    export = db.get(Export, export_id)
    if not export:
        raise AppError(ErrorCodes.NOT_FOUND, "Export not found", status_code=404)
    return ExportRead.model_validate(export)
