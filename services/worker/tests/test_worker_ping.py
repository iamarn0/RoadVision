from packages.app_meta import read_app_version
from app.worker import celery_app, ping


def test_ping_task_payload() -> None:
    result = ping()
    assert result["status"] == "ok"
    assert result["service"] == "worker"
    assert result["version"] == read_app_version()


def test_celery_uses_solo_pool() -> None:
    assert celery_app.conf.worker_pool == "solo"
    assert celery_app.conf.worker_concurrency == 1
