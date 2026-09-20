import sqlite3

from fastapi.testclient import TestClient

from app.agent.graph import build_graph
from app.main import app


def test_langgraph_uses_sqlite_checkpointer() -> None:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    graph = build_graph(connection)
    state = graph.invoke(
        {"batch_id": "batch-graph", "proposal": {"source_column": "Email"}, "policy": "AUTO_APPLY", "decision": None},
        config={"configurable": {"thread_id": "batch-graph"}},
    )
    assert state["batch_id"] == "batch-graph"
    assert graph.get_state({"configurable": {"thread_id": "batch-graph"}}).values["policy"] == "AUTO_APPLY"


def test_pause_correct_resume_and_reject_double_resolution() -> None:
    client = TestClient(app)
    upload = client.post(
        "/api/batches",
        files=[("files", ("ambiguous.csv", b"person_value\nmasked\n", "text/csv"))],
    )
    batch_id = upload.json()["batch_id"]
    mapped = client.post(f"/api/batches/{batch_id}/mapping-proposals?fallback=true")
    assert mapped.status_code == 200
    started = client.post(f"/api/batches/{batch_id}/workflow/start")
    assert started.json()["status"] == "PAUSED"
    assert started.json()["thread_id"] == batch_id
    items = client.get(f"/api/batches/{batch_id}/escalations").json()
    resolved = client.post(
        f"/api/escalations/{items[0]['escalation_id']}/resolve",
        json={"action": "CORRECT", "corrected_value": "email", "actor": "consultant@example.test"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "COMPLETED"
    assert list(resolved.json()["applied_mappings"].values()) == ["email"]
    repeated = client.post(
        f"/api/escalations/{items[0]['escalation_id']}/resolve",
        json={"action": "REJECT", "actor": "consultant@example.test"},
    )
    assert repeated.status_code == 409
