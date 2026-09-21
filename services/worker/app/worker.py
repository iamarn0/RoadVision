from datetime import UTC, datetime

from celery import Celery
from sqlalchemy import select

from app.config import get_settings
from app.core_logging import setup_logging
from app.db import get_session
from packages.db.enums import JobStatus
from packages.db.models import ProcessingJob

settings = get_settings()
setup_logging(settings.log_level, service="worker")

celery_app = Celery(
    "roadvision",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    worker_prefetch_multiplier=1,
    # solo avoids Linux prefork after OpenCV/NumPy import (breaks production jobs).
    worker_pool="solo",
    worker_concurrency=1,
    task_acks_late=True,
    beat_schedule={
        "recover-stale-jobs": {
            "task": "worker.recover_stale_jobs",
            "schedule": 60.0,
        }
    },
)


@celery_app.task(name="worker.ping")
def ping() -> dict[str, str]:
    return {"status": "ok", "service": "worker", "version": settings.app_version}


@celery_app.task(name="worker.process_video")
def process_video(job_id: str) -> dict[str, str]:
    from uuid import UUID

    from app.pipeline.runner import process_job

    db = get_session()
    try:
        process_job(db, UUID(job_id))
        return {"status": "ok", "job_id": job_id}
    finally:
        db.close()


@celery_app.task(name="worker.recover_stale_jobs")
def recover_stale_jobs() -> int:
    db = get_session()
    recovered = 0
    try:
        timeout = settings.stale_job_timeout_seconds
        jobs = list(
            db.scalars(select(ProcessingJob).where(ProcessingJob.status.in_(["processing", "validating", "finalizing"])))
        )
        now = datetime.now(UTC)
        for job in jobs:
            started = job.started_at or job.updated_at
            if started is None:
                continue
            age = (now - started.replace(tzinfo=started.tzinfo or UTC)).total_seconds()
            if age > timeout:
                job.status = JobStatus.FAILED.value
                job.error_code = "WORKER_UNAVAILABLE"
                job.error_message = "Job was abandoned after a worker timeout and marked failed. Retry the job."
                job.completed_at = now
                recovered += 1
        db.commit()
        return recovered
    finally:
        db.close()
