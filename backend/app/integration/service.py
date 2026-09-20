import hashlib
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.tables import AuditEventRow, TargetWriteRow, TransformedRecordRow
from app.integration.models import PushRequest, PushResult, PushStatus

MAX_RETRIES = 3


def payload_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _result(row: TargetWriteRow, replay: bool = False) -> PushResult:
    return PushResult(
        target_write_id=row.id, batch_id=row.batch_id, source_record_id=row.source_record_id,
        idempotency_key=row.idempotency_key, payload_hash=row.payload_hash,
        status=PushStatus(row.status), retry_count=row.retry_count, idempotent_replay=replay,
    )


def _audit(db: Session, row: TargetWriteRow, action: str) -> None:
    db.add(
        AuditEventRow(
            batch_id=row.batch_id, actor_type="SYSTEM", actor_id="mock_target",
            action=action, entity_type="target_write", entity_id=row.id,
            details_json=json.dumps({"status": row.status, "retry_count": row.retry_count}),
        )
    )


def push_record(db: Session, request: PushRequest, demo_failures: bool = False) -> PushResult:
    existing = db.scalar(select(TargetWriteRow).where(TargetWriteRow.idempotency_key == request.idempotency_key))
    if existing:
        if existing.batch_id != request.batch_id or existing.source_record_id != request.source_record_id:
            raise HTTPException(409, "Idempotency key belongs to a different record")
        if existing.payload_hash != request.payload_hash:
            raise HTTPException(409, "Idempotency key was already used with a different payload hash")
        return _result(existing, True)
    staged = db.get(TransformedRecordRow, request.record_id)
    if staged is None or staged.batch_id != request.batch_id or staged.source_record_id != request.source_record_id:
        raise HTTPException(404, "Approved staged record not found")
    if staged.status != "VALID":
        raise HTTPException(409, "Only valid approved records can be pushed")
    payload = json.loads(staged.transformed_json)
    actual_hash = payload_hash(payload)
    if actual_hash != request.payload_hash:
        raise HTTPException(409, "Payload hash does not match the approved staged record")
    email = str(payload.get("email", ""))
    if demo_failures and "permanent" in email:
        status = PushStatus.PERMANENT_FAILURE
    elif demo_failures and "retry" in email:
        status = PushStatus.RETRYABLE_FAILURE
    else:
        status = PushStatus.SUCCESS
    row = TargetWriteRow(
        id=str(uuid4()), batch_id=request.batch_id, source_record_id=request.source_record_id,
        idempotency_key=request.idempotency_key, payload_hash=actual_hash,
        payload_json=json.dumps(payload, separators=(",", ":")), status=status.value, retry_count=0,
    )
    db.add(row)
    _audit(db, row, "target.push")
    db.commit()
    db.refresh(row)
    return _result(row)


def retry_batch(db: Session, batch_id: str) -> list[PushResult]:
    rows = db.scalars(select(TargetWriteRow).where(TargetWriteRow.batch_id == batch_id)).all()
    results: list[PushResult] = []
    for row in rows:
        if row.status != PushStatus.RETRYABLE_FAILURE.value or row.retry_count >= MAX_RETRIES:
            results.append(_result(row))
            continue
        row.retry_count += 1
        row.status = PushStatus.SUCCESS.value
        _audit(db, row, "target.retry_succeeded")
        results.append(_result(row))
    db.commit()
    return results


def rollback_batch(db: Session, batch_id: str) -> int:
    rows = db.scalars(select(TargetWriteRow).where(TargetWriteRow.batch_id == batch_id)).all()
    count = 0
    for row in rows:
        if row.status == PushStatus.SUCCESS.value:
            row.status = PushStatus.ROLLED_BACK.value
            _audit(db, row, "target.rollback")
            count += 1
    db.commit()
    return count
