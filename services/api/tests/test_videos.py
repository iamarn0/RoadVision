from uuid import uuid4

from fastapi.testclient import TestClient

from app.database.session import get_session_factory
from packages.db.enums import AssetType, JobStatus, VideoStatus
from packages.db.models import MediaAsset, ProcessingJob, VehicleTrack, Video


def _seed_video_with_job() -> str:
    db = get_session_factory()()
    try:
        video = Video(
            original_filename="clip.mp4",
            storage_key=f"uploads/{uuid4().hex}_clip.mp4",
            file_size=12,
            status=VideoStatus.READY.value,
        )
        db.add(video)
        db.flush()
        job = ProcessingJob(video_id=video.id, status=JobStatus.COMPLETED.value)
        db.add(job)
        db.flush()
        db.add(
            MediaAsset(
                video_id=video.id,
                asset_type=AssetType.ORIGINAL_VIDEO.value,
                storage_key=video.storage_key,
                file_size=12,
            )
        )
        db.add(
            VehicleTrack(
                processing_job_id=job.id,
                track_id=1,
                vehicle_type="car",
            )
        )
        db.commit()
        return str(video.id)
    finally:
        db.close()


def test_delete_video_removes_jobs_and_assets(client: TestClient) -> None:
    video_id = _seed_video_with_job()
    response = client.delete(f"/api/videos/{video_id}")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "deleted"
    missing = client.get(f"/api/videos/{video_id}")
    assert missing.status_code == 404
    remaining = client.get("/api/videos")
    assert remaining.status_code == 200
    assert all(item["id"] != video_id for item in remaining.json())
