from enum import StrEnum

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent.pipeline import (
    ExecutionMode,
    PipelineStatus,
    initial_stages,
    pipeline_model,
    stages_from_row,
    update_stage,
)
from app.agent.service import start_workflow
from app.api.mappings import create_mapping_proposals
from app.api.mock_target import sync_target_status
from app.integration.client import push_batch
from app.api.records import transform
from app.db.database import get_db
from app.db.tables import IngestionBatchRow, PipelineRunRow, WorkflowStateRow
from app.events.service import emit_event

router = APIRouter(prefix="/api/batches", tags=["agent-pipeline"])


@router.post("/{batch_id}/pipeline/run", response_model=PipelineStatus, status_code=202)
def queue_pipeline(batch_id: str, db: Session = Depends(get_db)) -> PipelineStatus:
    from app.agent.jobs import enqueue
    row = _pipeline(db, batch_id)
    if row.status in {"CANCELLED", "COMPLETED", "COMPLETED_WITHOUT_PUSH", "ROLLED_BACK", "PARTIAL_FAILURE"}:
        return pipeline_model(row)
    enqueue(db, batch_id)
    return pipeline_model(row)


class PushDecision(StrEnum):
    PUSH = "PUSH"
    DO_NOT_PUSH = "DO_NOT_PUSH"


class PushDecisionRequest(BaseModel):
    decision: PushDecision


def _pipeline(db: Session, batch_id: str) -> PipelineRunRow:
    row = db.get(PipelineRunRow, batch_id)
    if row is not None:
        return row
    if db.get(IngestionBatchRow, batch_id) is None:
        raise HTTPException(404, "Batch not found")
    mode = ExecutionMode.HUMAN_IN_LOOP
    row = PipelineRunRow(
        batch_id=batch_id,
        execution_mode=mode.value,
        status="ACTIVE",
        current_stage="analyze",
        stages_json=__import__("json").dumps(initial_stages(mode), separators=(",", ":")),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _stage_status(row: PipelineRunRow, stage_id: str) -> str:
    return next(item["status"] for item in stages_from_row(row) if item["stage_id"] == stage_id)


def _begin(db: Session, row: PipelineRunRow, stage: str, agent: str) -> None:
    db.refresh(row)
    if row.status == "CANCELLED":
        raise HTTPException(409, "Migration stopped by the reviewer")
    row.status = "ACTIVE"
    update_stage(row, stage, "RUNNING", f"{agent} is working now.")
    emit_event(db, row.batch_id, "agent_started", {"agent": stage, "mode": row.execution_mode})
    db.commit()


def _complete(db: Session, row: PipelineRunRow, stage: str, detail: str) -> None:
    db.refresh(row)
    if row.status == "CANCELLED":
        raise HTTPException(409, "Migration stopped by the reviewer")
    update_stage(row, stage, "COMPLETED", detail)
    emit_event(db, row.batch_id, "agent_completed", {"agent": stage, "message": detail})
    db.commit()


def _next(row: PipelineRunRow, stage: str, mode: ExecutionMode, detail: str) -> None:
    row.current_stage = stage
    status = "QUEUED" if mode == ExecutionMode.AUTOPILOT else "WAITING_APPROVAL"
    update_stage(row, stage, status, detail)


def _pause_for_review(db: Session, row: PipelineRunRow, stage: str, count: int) -> PipelineStatus:
    db.refresh(row)
    if row.status in {"CANCELLED", "ROLLED_BACK"}:
        return pipeline_model(row)
    row.status = "PAUSED"
    update_stage(
        row,
        stage,
        "NEEDS_REVIEW",
        f"{count} genuinely uncertain item(s) need a human decision.",
    )
    emit_event(
        db,
        row.batch_id,
        "agent_waiting",
        {"agent": stage, "reason": "human_review", "open_items": count},
    )
    db.commit()
    return pipeline_model(row)


def _sync_resolved_review(db: Session, row: PipelineRunRow) -> None:
    if row.status in {"CANCELLED", "COMPLETED", "COMPLETED_WITHOUT_PUSH", "ROLLED_BACK", "PARTIAL_FAILURE"}:
        return
    workflow = db.get(WorkflowStateRow, row.batch_id)
    if workflow is None or workflow.status != "COMPLETED":
        return
    mode = ExecutionMode(row.execution_mode)
    if row.current_stage == "review" and _stage_status(row, "review") == "NEEDS_REVIEW":
        _complete(db, row, "review", "All mapping decisions are resolved.")
        _next(row, "preview", mode, "Mapping review is complete; validation can continue.")
        row.status = "ACTIVE"
        db.commit()
    elif row.current_stage == "preview" and _stage_status(row, "preview") == "NEEDS_REVIEW":
        _complete(db, row, "preview", "All record validation decisions are resolved.")
        row.current_stage = "push"
        row.status = "AWAITING_PUSH_DECISION"
        update_stage(
            row,
            "push",
            "READY_TO_PUSH",
            "Validated records are ready. Choose Push or Do not push.",
        )
        db.commit()


@router.get("/{batch_id}/pipeline", response_model=PipelineStatus)
def get_pipeline(batch_id: str, db: Session = Depends(get_db)) -> PipelineStatus:
    row = _pipeline(db, batch_id)
    _sync_resolved_review(db, row)
    return pipeline_model(row)


@router.post("/{batch_id}/pipeline/advance", response_model=PipelineStatus)
def advance_pipeline(
    batch_id: str,
    fallback: bool = Query(False),
    db: Session = Depends(get_db),
) -> PipelineStatus:
    from app.agent.jobs import worker_batch
    from app.db.tables import PipelineJobRow
    job = db.get(PipelineJobRow, batch_id)
    if job and job.status == "RUNNING" and worker_batch.get() != batch_id:
        return pipeline_model(_pipeline(db, batch_id))
    row = _pipeline(db, batch_id)
    _sync_resolved_review(db, row)
    mode = ExecutionMode(row.execution_mode)
    if row.status in {"CANCELLED", "COMPLETED", "COMPLETED_WITHOUT_PUSH", "ROLLED_BACK", "PARTIAL_FAILURE"}:
        return pipeline_model(row)
    if _stage_status(row, row.current_stage) == "NEEDS_REVIEW":
        return pipeline_model(row)
    if row.current_stage == "push":
        return pipeline_model(row)

    try:
        while True:
            if row.current_stage == "analyze":
                _begin(db, row, "analyze", "Analyze agent")
                proposals = create_mapping_proposals(batch_id, fallback, db)
                _complete(
                    db,
                    row,
                    "analyze",
                    f"Generated {len(proposals)} explainable mapping proposal(s).",
                )
                _next(row, "review", mode, "Mapping proposals are ready for policy review.")
                db.commit()
                if mode == ExecutionMode.HUMAN_IN_LOOP:
                    return pipeline_model(row)

            if row.current_stage == "review":
                _begin(db, row, "review", "Review agent")
                workflow = start_workflow(db, batch_id)
                if workflow.status == "PAUSED":
                    return _pause_for_review(db, row, "review", workflow.open_escalations)
                _complete(db, row, "review", "Safe mappings were applied with no unresolved ambiguity.")
                _next(row, "preview", mode, "Mappings are approved; records can now be validated.")
                db.commit()
                if mode == ExecutionMode.HUMAN_IN_LOOP:
                    return pipeline_model(row)

            if row.current_stage == "preview":
                _begin(db, row, "preview", "Validation agent")
                records = transform(batch_id, db)
                workflow_row = db.get(WorkflowStateRow, batch_id)
                if workflow_row is not None and workflow_row.status == "PAUSED":
                    open_count = sum(1 for record in records if record.status == "ESCALATION")
                    return _pause_for_review(db, row, "preview", open_count)
                _complete(
                    db,
                    row,
                    "preview",
                    f"Cleaned, reconciled, and validated {len(records)} record(s).",
                )
                row.current_stage = "push"
                row.status = "AWAITING_PUSH_DECISION"
                update_stage(
                    row,
                    "push",
                    "READY_TO_PUSH",
                    "Review the preview, then choose Push or Do not push.",
                )
                emit_event(db, batch_id, "agent_waiting", {"agent": "push", "reason": "final_decision"})
                db.commit()
                return pipeline_model(row)
    except Exception:
        db.rollback()
        db.refresh(row)
        if row.status == "CANCELLED":
            return pipeline_model(row)
        row.status = "FAILED"
        update_stage(
            row,
            row.current_stage,
            "FAILED",
            "This agent stopped safely without pushing data. Retry when ready.",
        )
        emit_event(db, batch_id, "agent_failed", {"agent": row.current_stage})
        db.commit()
        raise


@router.post("/{batch_id}/pipeline/push-decision", response_model=PipelineStatus)
def decide_push(
    batch_id: str,
    request: PushDecisionRequest,
    db: Session = Depends(get_db),
) -> PipelineStatus:
    from app.agent.jobs import worker_batch
    from app.db.tables import PipelineJobRow
    job = db.get(PipelineJobRow, batch_id)
    if job and job.status == "RUNNING" and worker_batch.get() != batch_id:
        raise HTTPException(409, "This migration is already being processed. Watch the live progress.")
    row = _pipeline(db, batch_id)
    _sync_resolved_review(db, row)
    if row.status in {"CANCELLED", "COMPLETED_WITHOUT_PUSH", "ROLLED_BACK"}:
        raise HTTPException(409, "This migration has stopped. Start a new migration to send records.")
    if row.current_stage != "push" or _stage_status(row, "push") not in {"READY_TO_PUSH", "FAILED"}:
        raise HTTPException(409, "Complete validation before making the final push decision")
    if request.decision == PushDecision.DO_NOT_PUSH:
        update_stage(row, "push", "SKIPPED", "You chose not to push any records.")
        row.status = "COMPLETED_WITHOUT_PUSH"
        emit_event(db, batch_id, "agent_completed", {"agent": "push", "decision": "not_pushed"})
        db.commit()
        return pipeline_model(row)

    _begin(db, row, "push", "Integration agent")
    try:
        results = push_batch(batch_id)
        db.expire_all()
        success_count = sum(1 for result in results if result.status.value == "SUCCESS")
        _complete(
            db,
            row,
            "push",
            f"Pushed {success_count} of {len(results)} approved record(s). Check audit for details.",
        )
        row.status = "COMPLETED"
        db.commit()
        sync_target_status(db, batch_id)
        db.refresh(row)
        return pipeline_model(row)
    except Exception:
        db.rollback()
        db.refresh(row)
        if row.status == "CANCELLED":
            return pipeline_model(row)
        row.status = "FAILED"
        update_stage(
            row,
            "push",
            "FAILED",
            "The push stopped safely. Review the audit and retry when ready.",
        )
        emit_event(db, batch_id, "agent_failed", {"agent": "push"})
        db.commit()
        raise


@router.post("/{batch_id}/pipeline/cancel", response_model=PipelineStatus)
def cancel_pipeline(batch_id: str, db: Session = Depends(get_db)) -> PipelineStatus:
    row = _pipeline(db, batch_id)
    if row.status in {"COMPLETED", "COMPLETED_WITHOUT_PUSH"}:
        raise HTTPException(409, "A completed pipeline cannot be stopped")
    stages = stages_from_row(row)
    for stage in stages:
        if stage["status"] in {"QUEUED", "WAITING_APPROVAL", "READY_TO_PUSH", "RUNNING", "NEEDS_REVIEW", "FAILED"}:
            stage["status"] = "SKIPPED"
            stage["detail"] = "Skipped because the migration was stopped."
    row.stages_json = __import__("json").dumps(stages, separators=(",", ":"))
    row.status = "CANCELLED"
    emit_event(db, batch_id, "agent_completed", {"agent": row.current_stage, "decision": "stopped"})
    db.commit()
    return pipeline_model(row)
