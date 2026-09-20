from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_live_health() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"


def test_gpu_endpoint_reports_runtime_probe_not_hardcoded_ready() -> None:
    response = client.get("/api/system/gpu")
    assert response.status_code == 200
    body = response.json()
    # Must never invent a healthy GPU when CUDA is absent.
    assert "cuda_available" in body
    assert "status" in body
    if not body["cuda_available"]:
        assert body["status"] in {"cpu_fallback", "cpu", "unavailable", "configuration_error"}
        # Do not claim a selected CUDA device when CUDA is false.
        assert body.get("device") in {None, "cpu"} or str(body.get("device", "")).startswith("cpu")


def test_settings_does_not_expose_secrets() -> None:
    response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert "secret_key" not in body
    assert "password" not in str(body).lower()
    assert body["authentication_enabled"] is False  # AUTH_DISABLED=true in tests
    assert body["app_version"] == "0.1.0"
