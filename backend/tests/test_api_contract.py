from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.events.service import emit_event
from app.main import app


def test_openapi_contains_complete_workflow_contract() -> None:
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    required = {
        "/api/batches", "/api/batches/{batch_id}/profiles",
        "/api/batches/{batch_id}/mapping-proposals",
        "/api/batches/{batch_id}/workflow/start",
        "/api/batches/{batch_id}/workflow/status",
        "/api/batches/{batch_id}/escalations", "/api/escalations/{escalation_id}/resolve",
        "/api/batches/{batch_id}/records", "/api/batches/{batch_id}/events",
        "/mock-target/employees", "/mock-target/migrations/{batch_id}/retry",
        "/mock-target/migrations/{batch_id}/push-valid",
        "/api/system/model",
    }
    assert required <= set(paths)


def test_consistent_error_envelope() -> None:
    response = TestClient(app).get("/api/batches/not-found/profiles")
    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "HTTP_404", "message": "Batch not found", "retryable": False, "details": None,
    }


def test_sse_is_ordered_safe_and_resumable() -> None:
    batch = str(uuid4())
    with SessionLocal() as db:
        first = emit_event(db, batch, "node_started", {"node": "profile"})
        emit_event(db, batch, "progress", {"completed": 1})
        db.commit()
        first_id = first.id
    client = TestClient(app)
    full = client.get(f"/api/batches/{batch}/events?snapshot=true")
    assert full.status_code == 200
    assert "node_started" in full.text and "progress" in full.text
    assert "@example" not in full.text
    resumed = client.get(f"/api/batches/{batch}/events?snapshot=true", headers={"Last-Event-ID": str(first_id)})
    assert "node_started" not in resumed.text
    assert "progress" in resumed.text
