from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.errors import ErrorCodes
from app.database.session import get_session_factory
from app.repositories.core import JobRepository
from app.schemas.common import JobRead
from app.security.deps import authenticate_websocket

router = APIRouter()


@router.websocket("/ws/jobs/{job_id}")
async def job_progress(websocket: WebSocket, job_id: UUID) -> None:
    factory = get_session_factory()
    db: Session = factory()
    try:
        user = await authenticate_websocket(websocket, db)
        if user is None:
            await websocket.close(code=4401)
            return
    finally:
        db.close()

    await websocket.accept()
    try:
        while True:
            db = factory()
            try:
                job = JobRepository(db).get(job_id)
                if not job:
                    await websocket.send_json(
                        {"error_code": ErrorCodes.NOT_FOUND, "message": "Job not found"}
                    )
                    await websocket.close()
                    return
                payload = JobRead.model_validate(job).model_dump(mode="json")
                await websocket.send_json(payload)
                if job.status in {"completed", "failed", "cancelled"}:
                    await websocket.close()
                    return
            finally:
                db.close()
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
