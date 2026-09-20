from fastapi.testclient import TestClient

from app.main import app


VALID_CSV = b"""employee_id,first_name,last_name,email,hire_date,department,employment_status
E100,Ada,Lovelace,ada@example.com,2024-01-15,Engineering,Active
"""


def _upload(client: TestClient, mode: str) -> str:
    response = client.post(
        "/api/batches",
        data={"execution_mode": mode},
        files=[("files", ("employees.csv", VALID_CSV, "text/csv"))],
    )
    assert response.status_code == 201
    return response.json()["batch_id"]


def test_autopilot_runs_safe_agents_until_final_push_decision() -> None:
    client = TestClient(app)
    batch_id = _upload(client, "AUTOPILOT")

    initial = client.get(f"/api/batches/{batch_id}/pipeline").json()
    assert initial["execution_mode"] == "AUTOPILOT"
    assert initial["current_stage"] == "analyze"
    assert initial["stages"][0]["status"] == "COMPLETED"

    advanced = client.post(
        f"/api/batches/{batch_id}/pipeline/advance?fallback=true"
    )
    assert advanced.status_code == 200
    result = advanced.json()
    assert result["status"] == "AWAITING_PUSH_DECISION"
    assert result["current_stage"] == "push"
    assert [item["status"] for item in result["stages"]] == [
        "COMPLETED", "COMPLETED", "COMPLETED", "COMPLETED", "READY_TO_PUSH"
    ]

    declined = client.post(
        f"/api/batches/{batch_id}/pipeline/push-decision",
        json={"decision": "DO_NOT_PUSH"},
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "COMPLETED_WITHOUT_PUSH"
    assert declined.json()["stages"][-1]["status"] == "SKIPPED"
    assert client.get(f"/mock-target/migrations/{batch_id}").json() == []


def test_human_in_loop_mode_is_available_for_existing_supervised_flow() -> None:
    client = TestClient(app)
    batch_id = _upload(client, "HUMAN_IN_LOOP")

    initial = client.get(f"/api/batches/{batch_id}/pipeline").json()
    assert initial["execution_mode"] == "HUMAN_IN_LOOP"
    assert initial["stages"][1]["status"] == "WAITING_APPROVAL"


def test_autopilot_still_pauses_for_genuine_ambiguity() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/batches",
        data={"execution_mode": "AUTOPILOT"},
        files=[("files", ("ambiguous.csv", b"person_value\nmasked\n", "text/csv"))],
    )
    batch_id = response.json()["batch_id"]

    result = client.post(
        f"/api/batches/{batch_id}/pipeline/advance?fallback=true"
    ).json()

    assert result["status"] == "PAUSED"
    assert result["current_stage"] == "review"
    assert result["stages"][2]["status"] == "NEEDS_REVIEW"
    assert result["requires_action"] is True
