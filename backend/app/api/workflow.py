from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.models import Escalation, EscalationDecision, WorkflowStatus
from app.agent.service import escalation_model, resolve_escalation, start_workflow
from app.db.database import get_db
from app.db.tables import EscalationRow, WorkflowStateRow
from app.events.service import emit_event

router = APIRouter(prefix="/api", tags=["workflow"])


@router.post("/batches/{batch_id}/workflow/start", response_model=WorkflowStatus)
def start(batch_id: str, db: Session = Depends(get_db)) -> WorkflowStatus:
    emit_event(db, batch_id, "node_started", {"node": "mapping_policy"})
    result = start_workflow(db, batch_id)
    emit_event(db, batch_id, "node_completed", {"node": "mapping_policy"})
    emit_event(db, batch_id, "workflow_paused" if result.status == "PAUSED" else "progress", {"status": result.status})
    db.commit()
    from app.db.tables import PipelineJobRow
    if result.status == "COMPLETED" and db.get(PipelineJobRow, batch_id) is not None:
        from app.agent.jobs import enqueue
        enqueue(db, batch_id)
    return result


@router.get("/batches/{batch_id}/workflow/status", response_model=WorkflowStatus)
def status(batch_id: str, db: Session = Depends(get_db)) -> WorkflowStatus:
    row = db.get(WorkflowStateRow, batch_id)
    if row is None:
        raise HTTPException(404, "Workflow not found")
    open_count = len(db.scalars(select(EscalationRow).where(EscalationRow.batch_id == batch_id, EscalationRow.status == "OPEN")).all())
    state = __import__("json").loads(row.state_json)
    return WorkflowStatus(batch_id=batch_id, thread_id=row.thread_id, status=row.status, applied_mappings=state.get("applied_mappings", {}), open_escalations=open_count)


@router.get("/batches/{batch_id}/escalations", response_model=list[Escalation])
def list_escalations(batch_id: str, db: Session = Depends(get_db)) -> list[Escalation]:
    rows = db.scalars(select(EscalationRow).where(EscalationRow.batch_id == batch_id).order_by(EscalationRow.created_at)).all()
    return [escalation_model(row) for row in rows]


@router.post("/escalations/{escalation_id}/resolve", response_model=WorkflowStatus)
def resolve(escalation_id: str, decision: EscalationDecision, db: Session = Depends(get_db)) -> WorkflowStatus:
    row = db.get(EscalationRow, escalation_id)
    if row is None:
        raise HTTPException(404, "Escalation not found")
    batch_id = row.batch_id
    result = resolve_escalation(db, row, decision)
    emit_event(
        db,
        batch_id,
        "workflow_resumed" if result.status == "COMPLETED" else "progress",
        {"status": result.status, "action": decision.action.value, "open_escalations": result.open_escalations},
    )
    db.commit()
    from app.db.tables import PipelineJobRow
    if result.status == "COMPLETED" and db.get(PipelineJobRow, batch_id) is not None:
        from app.agent.jobs import enqueue
        enqueue(db, batch_id)
    return result
