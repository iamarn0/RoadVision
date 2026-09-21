from packages.app_meta import read_app_version
from app.worker import ping


def test_ping_task_payload() -> None:
    result = ping()
    assert result["status"] == "ok"
    assert result["service"] == "worker"
    assert result["version"] == read_app_version()
