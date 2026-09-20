import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db
from app.db.tables import EscalationRow, PipelineRunRow, TargetWriteRow, TransformedRecordRow, WorkflowStateRow
from app.agent.pipeline import update_stage
from app.integration.models import PushRequest, PushResult
from app.integration.service import payload_hash, push_record, retry_batch, rollback_batch
from app.events.service import emit_event

router = APIRouter(prefix="/mock-target", tags=["mock-target"])


def require_push_ready(db: Session, batch_id: str) -> None:
    workflow = db.get(WorkflowStateRow, batch_id)
    pending = db.scalar(select(EscalationRow.id).where(EscalationRow.batch_id == batch_id, EscalationRow.status == "OPEN").limit(1))
    pipeline = db.get(PipelineRunRow, batch_id)
    if pipeline:
        db.refresh(pipeline)
    if pipeline and pipeline.status in {"CANCELLED", "COMPLETED_WITHOUT_PUSH", "ROLLED_BACK"}:
        raise HTTPException(409, "This migration is stopped. Start a new migration to send records.")
    if workflow is None or workflow.status != "COMPLETED" or pending:
        raise HTTPException(409, "Resolve all review items before pushing records")


def sync_target_status(db: Session, batch_id: str) -> None:
    pipeline = db.get(PipelineRunRow, batch_id)
    if pipeline is None:
        return
    results = db.scalars(select(TargetWriteRow).where(TargetWriteRow.batch_id == batch_id)).all()
    if not results:
        return
    statuses = {item.status for item in results}
    failed = statuses & {"RETRYABLE_FAILURE", "PERMANENT_FAILURE"}
    status = "PARTIAL_FAILURE" if failed else "ROLLED_BACK" if "ROLLED_BACK" in statuses else "COMPLETED"
    pipeline.status = status
    pipeline.current_stage = "push"
    update_stage(pipeline, "push", "FAILED" if failed else status,
                 "Some records were not sent. Open results to retry temporary failures." if failed
                 else "Sent records have been undone; failed records will not be retried." if status == "ROLLED_BACK"
                 else "All approved records were sent successfully.")
    emit_event(db, batch_id, "agent_completed" if not failed else "agent_failed", {"agent": "push", "status": status})
    db.commit()


@router.post("/migrations/{batch_id}/push-valid", response_model=list[PushResult])
def push_valid(batch_id: str, db: Session = Depends(get_db)) -> list[PushResult]:
    require_push_ready(db, batch_id)
    rows = db.scalars(
        select(TransformedRecordRow).where(
            TransformedRecordRow.batch_id == batch_id,
            TransformedRecordRow.status == "VALID",
        )
    ).all()
    results: list[PushResult] = []
    for row in rows:
        require_push_ready(db, batch_id)
        result = push_record(
            db,
            PushRequest(
                batch_id=batch_id,
                record_id=row.id,
                source_record_id=row.source_record_id,
                idempotency_key=f"{batch_id}:{row.source_file}:{row.source_record_id}",
                payload_hash=payload_hash(json.loads(row.transformed_json)),
            ),
            demo_failures=get_settings().demo_failures,
        )
        emit_event(
            db,
            batch_id,
            "push_result",
            {"source_record_id": result.source_record_id, "status": result.status.value},
        )
        results.append(result)
    db.commit()
    sync_target_status(db, batch_id)
    return results


@router.post("/employees", response_model=PushResult)
def push(request: PushRequest, db: Session = Depends(get_db)) -> PushResult:
    require_push_ready(db, request.batch_id)
    result = push_record(db, request, demo_failures=get_settings().demo_failures)
    emit_event(db, request.batch_id, "push_result", {"source_record_id": result.source_record_id, "status": result.status.value})
    db.commit()
    return result


@router.get("/migrations/{batch_id}", response_model=list[PushResult])
def migration(batch_id: str, db: Session = Depends(get_db)) -> list[PushResult]:
    rows = db.scalars(select(TargetWriteRow).where(TargetWriteRow.batch_id == batch_id)).all()
    return [
        PushResult(
            target_write_id=row.id, batch_id=row.batch_id, source_record_id=row.source_record_id,
            idempotency_key=row.idempotency_key, payload_hash=row.payload_hash,
            status=row.status, retry_count=row.retry_count,
        )
        for row in rows
    ]


@router.post("/migrations/{batch_id}/retry", response_model=list[PushResult])
def retry(batch_id: str, db: Session = Depends(get_db)) -> list[PushResult]:
    require_push_ready(db, batch_id)
    results = retry_batch(db, batch_id)
    for item in results:
        emit_event(db, batch_id, "push_result", {"source_record_id": item.source_record_id, "status": item.status.value, "retry_count": item.retry_count})
    db.commit()
    sync_target_status(db, batch_id)
    return results


@router.delete("/migrations/{batch_id}")
def rollback(batch_id: str, db: Session = Depends(get_db)) -> dict[str, int | str]:
    count = rollback_batch(db, batch_id)
    emit_event(db, batch_id, "rollback", {"rolled_back": count})
    db.commit()
    pipeline = db.get(PipelineRunRow, batch_id)
    if pipeline:
        pipeline.status = "ROLLED_BACK"
        update_stage(pipeline, "push", "ROLLED_BACK", "Sent records were undone. Start a new migration to send again.")
        db.commit()
    return {"batch_id": batch_id, "rolled_back": count}
