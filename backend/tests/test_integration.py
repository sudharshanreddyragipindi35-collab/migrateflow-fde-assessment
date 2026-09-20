import json
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.tables import TargetWriteRow, TransformedRecordRow, WorkflowStateRow
from app.integration.models import PushRequest, PushStatus
from app.integration.service import payload_hash, push_record, retry_batch, rollback_batch
from app.main import app


def staged(db, batch: str, email: str, status: str = "VALID") -> tuple[TransformedRecordRow, dict]:
    payload = {
        "employee_id": str(uuid4()), "first_name": "Asha", "last_name": "Rao", "email": email,
        "hire_date": "2024-01-01", "department": "Engineering", "employment_status": "Active",
    }
    row = TransformedRecordRow(
        id=str(uuid4()), batch_id=batch, source_file="employees.csv", source_record_id=str(uuid4()),
        original_json="{}", transformed_json=json.dumps(payload), provenance_json="[]", status=status,
        errors_json="[]", attempt_count=1,
    )
    db.add(row)
    db.commit()
    return row, payload


def request_for(row: TransformedRecordRow, payload: dict, key: str) -> PushRequest:
    return PushRequest(
        batch_id=row.batch_id, record_id=row.id, source_record_id=row.source_record_id,
        idempotency_key=key, payload_hash=payload_hash(payload),
    )


def test_partial_success_retry_and_idempotency() -> None:
    with SessionLocal() as db:
        batch = str(uuid4())
        good, good_payload = staged(db, batch, "good@example.test")
        retry, retry_payload = staged(db, batch, "retry@example.test")
        first = push_record(db, request_for(good, good_payload, f"key-{uuid4()}"), demo_failures=True)
        retry_request = request_for(retry, retry_payload, f"key-{uuid4()}")
        second = push_record(db, retry_request, demo_failures=True)
        assert first.status == PushStatus.SUCCESS
        assert second.status == PushStatus.RETRYABLE_FAILURE
        replay = push_record(db, retry_request, demo_failures=True)
        assert replay.idempotent_replay
        results = retry_batch(db, batch)
        assert {item.status for item in results} == {PushStatus.SUCCESS}
        assert next(item for item in results if item.source_record_id == retry.source_record_id).retry_count == 1


def test_changed_payload_same_key_conflicts_and_invalid_record_cannot_push() -> None:
    with SessionLocal() as db:
        batch = str(uuid4())
        row, payload = staged(db, batch, "good@example.test")
        key = f"key-{uuid4()}"
        push_record(db, request_for(row, payload, key))
        changed = request_for(row, payload, key).model_copy(update={"payload_hash": "0" * 64})
        with pytest.raises(HTTPException) as conflict:
            push_record(db, changed)
        assert conflict.value.status_code == 409
        invalid, invalid_payload = staged(db, batch, "bad", status="ESCALATION")
        with pytest.raises(HTTPException):
            push_record(db, request_for(invalid, invalid_payload, f"key-{uuid4()}"))


def test_rollback_is_batch_scoped() -> None:
    with SessionLocal() as db:
        first_batch, other_batch = str(uuid4()), str(uuid4())
        first, first_payload = staged(db, first_batch, "first@example.test")
        other, other_payload = staged(db, other_batch, "other@example.test")
        first_result = push_record(db, request_for(first, first_payload, f"key-{uuid4()}"))
        other_result = push_record(db, request_for(other, other_payload, f"key-{uuid4()}"))
        assert rollback_batch(db, first_batch) == 1
        assert db.get(TargetWriteRow, first_result.target_write_id).status == PushStatus.ROLLED_BACK.value
        assert db.get(TargetWriteRow, other_result.target_write_id).status == PushStatus.SUCCESS.value


def test_bulk_push_endpoint_is_idempotent_and_skips_invalid_records() -> None:
    batch = str(uuid4())
    with SessionLocal() as db:
        db.add(WorkflowStateRow(batch_id=batch, thread_id=batch, status="COMPLETED", state_json="{}"))
        db.commit()
        valid, _ = staged(db, batch, "bulk@example.test")
        staged(db, batch, "invalid", status="ESCALATION")
        source_record_id = valid.source_record_id
    client = TestClient(app)
    first = client.post(f"/mock-target/migrations/{batch}/push-valid")
    second = client.post(f"/mock-target/migrations/{batch}/push-valid")
    assert first.status_code == 200
    assert len(first.json()) == 1
    assert first.json()[0]["source_record_id"] == source_record_id
    assert second.json()[0]["idempotent_replay"] is True
