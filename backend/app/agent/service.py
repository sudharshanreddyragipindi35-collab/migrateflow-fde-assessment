import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.models import Escalation, EscalationAction, EscalationDecision, WorkflowStatus
from app.agent.policy import evaluate_mapping
from app.db.tables import (
    AuditEventRow,
    EscalationRow,
    MappingProposalRow,
    SourceFileProfileRow,
    TransformedRecordRow,
    WorkflowStateRow,
)
from app.mapping.models import MappingProposal
from app.mapping.schema import load_target_schema
from app.validation.employee import validation_errors


def _audit(db: Session, batch_id: str, actor_type: str, actor_id: str, action: str, entity_type: str, entity_id: str, details: dict) -> None:
    db.add(
        AuditEventRow(
            batch_id=batch_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details_json=json.dumps(details, separators=(",", ":")),
        )
    )


def _status(row: WorkflowStateRow, open_count: int) -> WorkflowStatus:
    state = json.loads(row.state_json)
    return WorkflowStatus(
        batch_id=row.batch_id,
        thread_id=row.thread_id,
        status=row.status,
        applied_mappings=state.get("applied_mappings", {}),
        open_escalations=open_count,
    )


def start_workflow(db: Session, batch_id: str) -> WorkflowStatus:
    existing = db.get(WorkflowStateRow, batch_id)
    if existing is not None and existing.status in {"RUNNING", "PAUSED", "COMPLETED"}:
        count = len(db.scalars(select(EscalationRow).where(EscalationRow.batch_id == batch_id, EscalationRow.status == "OPEN")).all())
        return _status(existing, count)
    rows = db.scalars(select(MappingProposalRow).where(MappingProposalRow.batch_id == batch_id)).all()
    if not rows:
        raise HTTPException(409, "Generate mapping proposals before starting the workflow")
    applied: dict[str, str] = {}
    column_context = {}
    for source in db.scalars(select(SourceFileProfileRow).where(SourceFileProfileRow.batch_id == batch_id)).all():
        profile = json.loads(source.profile_json)
        for column in profile.get("columns", []):
            column_context[(source.safe_name, column["name"])] = column.get("masked_samples", [])
    open_count = 0
    for row in rows:
        proposal = MappingProposal.model_validate_json(row.proposal_json)
        decision = evaluate_mapping(proposal)
        key = f"{proposal.source_file}:{proposal.source_column}"
        if decision.auto_apply and proposal.target_field:
            applied[key] = proposal.target_field
            _audit(db, batch_id, "AGENT", "policy", "mapping.auto_applied", "mapping", key, {"target": proposal.target_field, "confidence": proposal.confidence})
            continue
        escalation_id = str(uuid4())
        db.add(
            EscalationRow(
                id=escalation_id,
                batch_id=batch_id,
                source_context_json=json.dumps({"source_file": proposal.source_file, "source_column": proposal.source_column,
                    "samples": column_context.get((proposal.source_file, proposal.source_column), []),
                    "explanation": proposal.reasoning}),
                suggestion=proposal.target_field,
                alternatives_json=json.dumps(proposal.alternatives),
                confidence_json=proposal.evidence.model_dump_json(),
                reason_code=decision.reason_code,
                allowed_actions_json=json.dumps([item.value for item in EscalationAction]),
            )
        )
        _audit(db, batch_id, "AGENT", "policy", "escalation.created", "escalation", escalation_id, {"reason_code": decision.reason_code})
        open_count += 1
    status = "PAUSED" if open_count else "COMPLETED"
    state = {"applied_mappings": applied, "resume_count": 0}
    workflow = WorkflowStateRow(batch_id=batch_id, thread_id=batch_id, status=status, state_json=json.dumps(state))
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return _status(workflow, open_count)


def escalation_model(row: EscalationRow) -> Escalation:
    return Escalation(
        escalation_id=row.id,
        batch_id=row.batch_id,
        source_context=json.loads(row.source_context_json),
        suggestion=row.suggestion,
        alternatives=json.loads(row.alternatives_json),
        confidence_evidence=json.loads(row.confidence_json),
        reason_code=row.reason_code,
        allowed_actions=json.loads(row.allowed_actions_json),
        status=row.status,
        decision=json.loads(row.decision_json) if row.decision_json else None,
        actor=row.actor,
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )


def _payload_hash(payload: dict) -> str:
    value = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(value.encode()).hexdigest()


def _resolve_record_escalation(
    db: Session,
    row: EscalationRow,
    decision: EscalationDecision,
    context: dict,
) -> WorkflowStatus:
    record = db.get(TransformedRecordRow, context.get("record_id"))
    if record is None or record.batch_id != row.batch_id:
        raise HTTPException(404, "Escalated record not found")
    workflow = db.get(WorkflowStateRow, row.batch_id)
    if workflow is None:
        raise HTTPException(409, "Workflow state is missing")

    before = json.loads(record.transformed_json)
    after = dict(before)
    field = str(context.get("field", ""))
    if decision.action == EscalationAction.CORRECT:
        after[field] = decision.corrected_value
        errors = validation_errors(after)
        field_errors = [error for error in errors if error.startswith(f"{field}:")]
        if field_errors:
            raise HTTPException(422, field_errors[0])
        if field in {"employee_id", "email"}:
            others = db.scalars(select(TransformedRecordRow).where(
                TransformedRecordRow.batch_id == row.batch_id,
                TransformedRecordRow.id != record.id,
                TransformedRecordRow.status != "REJECTED",
            )).all()
            if any(str(json.loads(other.transformed_json).get(field, "")).casefold() == str(after.get(field, "")).casefold() for other in others):
                raise HTTPException(422, "That identifier already belongs to another record. Enter a verified unique identifier, or reject this duplicate.")
        provenance = json.loads(record.provenance_json)
        provenance.append(
            {
                "field": field,
                "original_value": before.get(field),
                "new_value": decision.corrected_value,
                "rule": "human_correction",
                "confidence": 1.0,
                "actor": decision.actor,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": row.reason_code,
            }
        )
        record.provenance_json = json.dumps(provenance, default=str)
        record.transformed_json = json.dumps(after, default=str)
        record.errors_json = json.dumps(errors)
        record.status = "ESCALATION" if errors else "VALID"
    elif decision.action == EscalationAction.APPROVE:
        if context.get("kind") == "record_conflict":
            raise HTTPException(422, "Choose a unique employee ID or reject this duplicate record.")
        errors = validation_errors(after)
        if errors:
            raise HTTPException(422, "Invalid record cannot be approved; correct or reject it")
        record.errors_json = "[]"
        record.status = "VALID"
    else:
        record.status = "REJECTED"
        record.errors_json = json.dumps([f"Rejected by {decision.actor}: {row.reason_code}"])

    row.status = "RESOLVED"
    row.decision_json = decision.model_dump_json()
    row.actor = decision.actor
    row.resolved_at = datetime.now(timezone.utc)
    if decision.action == EscalationAction.REJECT:
        siblings = db.scalars(
            select(EscalationRow).where(
                EscalationRow.batch_id == row.batch_id,
                EscalationRow.status == "OPEN",
                EscalationRow.id != row.id,
            )
        ).all()
        for sibling in siblings:
            sibling_context = json.loads(sibling.source_context_json)
            if sibling_context.get("record_id") == record.id:
                sibling.status = "RESOLVED"
                sibling.decision_json = decision.model_dump_json()
                sibling.actor = decision.actor
                sibling.resolved_at = row.resolved_at

    db.flush()
    remaining = len(
        db.scalars(
            select(EscalationRow).where(
                EscalationRow.batch_id == row.batch_id,
                EscalationRow.status == "OPEN",
                EscalationRow.id != row.id,
            )
        ).all()
    )
    workflow.status = "PAUSED" if remaining else "COMPLETED"
    _audit(
        db,
        row.batch_id,
        "HUMAN",
        decision.actor,
        "record_escalation.resolved",
        "record",
        record.id,
        {
            "action": decision.action.value,
            "field": field,
            "before_hash_or_masked": _payload_hash(before),
            "after_hash_or_masked": _payload_hash(after),
            "reason_code": row.reason_code,
        },
    )
    db.commit()
    db.refresh(workflow)
    return _status(workflow, remaining)


def resolve_escalation(db: Session, row: EscalationRow, decision: EscalationDecision) -> WorkflowStatus:
    if row.status != "OPEN":
        raise HTTPException(409, "Escalation has already been resolved")
    allowed_actions = set(json.loads(row.allowed_actions_json))
    if decision.action.value not in allowed_actions:
        raise HTTPException(422, f"{decision.action.value} is not allowed for this escalation")
    context = json.loads(row.source_context_json)
    if str(context.get("kind", "")).startswith("record_"):
        return _resolve_record_escalation(db, row, decision, context)
    target_fields = {item.name for item in load_target_schema().fields}
    selected = row.suggestion
    if decision.action == EscalationAction.CORRECT:
        selected = decision.corrected_value
        if selected not in target_fields:
            raise HTTPException(422, "Correction must be a target schema field")
    workflow = db.get(WorkflowStateRow, row.batch_id)
    if workflow is None:
        raise HTTPException(409, "Workflow state is missing")
    state = json.loads(workflow.state_json)
    key = f"{context['source_file']}:{context['source_column']}"
    if decision.action in {EscalationAction.APPROVE, EscalationAction.CORRECT} and selected:
        duplicate = next((source for source, target in state.get("applied_mappings", {}).items()
                          if source != key and source.startswith(f"{context['source_file']}:") and target == selected), None)
        if duplicate:
            raise HTTPException(409, f"{selected} already uses {duplicate.split(':', 1)[1]}. Reject this mapping or choose a different destination field.")
    row.status = "RESOLVED"
    row.decision_json = decision.model_dump_json()
    row.actor = decision.actor
    row.resolved_at = datetime.now(timezone.utc)
    workflow = db.get(WorkflowStateRow, row.batch_id)
    if workflow is None:
        raise HTTPException(409, "Workflow state is missing")
    state = json.loads(workflow.state_json)
    key = f"{context['source_file']}:{context['source_column']}"
    if decision.action in {EscalationAction.APPROVE, EscalationAction.CORRECT} and selected:
        state.setdefault("applied_mappings", {})[key] = selected
    else:
        state.setdefault("rejected_mappings", {})[key] = row.reason_code
    state["resume_count"] = state.get("resume_count", 0) + 1
    workflow.state_json = json.dumps(state)
    remaining = len(
        db.scalars(
            select(EscalationRow).where(
                EscalationRow.batch_id == row.batch_id,
                EscalationRow.status == "OPEN",
                EscalationRow.id != row.id,
            )
        ).all()
    )
    workflow.status = "PAUSED" if remaining else "COMPLETED"
    _audit(
        db, row.batch_id, "HUMAN", decision.actor, "escalation.resolved", "escalation", row.id,
        {"action": decision.action.value, "selected": selected},
    )
    db.commit()
    db.refresh(workflow)
    return _status(workflow, remaining)
