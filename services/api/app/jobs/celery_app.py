from celery import Celery

from app.config import get_settings

_app: Celery | None = None


def get_celery() -> Celery:
    global _app
    if _app is None:
        settings = get_settings()
        _app = Celery("roadvision", broker=settings.celery_broker_url, backend=settings.celery_result_backend)
        _app.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json")
    return _app
