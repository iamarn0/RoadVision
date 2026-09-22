from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.repositories.core import JobRepository
from app.schemas.common import ExportRead
from app.security.audit import write_audit
from app.security.deps import RequireOperator, RequireReader, client_ip
from app.security.districts import require_export_scope, require_job_scope, scoped_district_ids
from app.services.exports import create_export
from packages.db.models import Export

router = APIRouter(tags=["exports"])


def _create(job_id: UUID, export_type: str, request: Request, user, db: Session) -> ExportRead:
    require_job_scope(db, JobRepository(db).get(job_id), scoped_district_ids(db, user))
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
def get_export(export_id: UUID, user: RequireReader, db: Session = Depends(get_db)) -> ExportRead:
    export = require_export_scope(db, db.get(Export, export_id), scoped_district_ids(db, user))
    return ExportRead.model_validate(export)
