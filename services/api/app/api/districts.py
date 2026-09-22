from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import DistrictRead
from app.security.deps import RequireDistrictMaster
from app.security.districts import list_districts

router = APIRouter(prefix="/api/districts", tags=["districts"])


@router.get("", response_model=list[DistrictRead])
def get_districts(_: RequireDistrictMaster, db: Session = Depends(get_db)) -> list[DistrictRead]:
    return [DistrictRead(id=row.id, name=row.name) for row in list_districts(db)]
