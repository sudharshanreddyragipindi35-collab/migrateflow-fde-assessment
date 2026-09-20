from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "migrateflow"}


def test_api_health() -> None:
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_model_runtime_status_is_safe_and_explicit(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.system.get_settings",
        lambda: Settings(model_mode="fallback", anthropic_api_key="must-not-appear"),
    )
    response = TestClient(app).get("/api/system/model")
    assert response.status_code == 200
    assert response.json() == {
        "mode": "fallback",
        "provider": "Deterministic fallback",
        "model": None,
        "status": "ready",
        "parallel_workers": 1,
        "failover_provider": None,
        "failover_status": "disabled",
    }
    assert "must-not-appear" not in response.text


def test_ollama_runtime_reports_anthropic_failover_without_exposing_key(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.system.get_settings",
        lambda: Settings(
            model_mode="ollama",
            llm_failover_provider="anthropic",
            anthropic_api_key="must-not-appear",
        ),
    )
    monkeypatch.setattr("app.api.system._ollama_status", lambda *_: "ready")

    response = TestClient(app).get("/api/system/model")

    assert response.status_code == 200
    assert response.json()["failover_provider"] == "Anthropic"
    assert response.json()["failover_status"] == "configured"
    assert "must-not-appear" not in response.text
