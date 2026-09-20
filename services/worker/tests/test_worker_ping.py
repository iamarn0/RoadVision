from app.worker import ping


def test_ping_task_payload() -> None:
    result = ping()
    assert result["status"] == "ok"
    assert result["service"] == "worker"
    assert result["version"] == "0.1.0"
