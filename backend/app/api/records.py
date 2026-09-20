import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.cleaning.models import RecordPreview
from app.cleaning.service import clean_record, reconcile_records
from app.db.database import get_db
from app.db.tables import EscalationRow, SourceFileProfileRow, TransformedRecordRow, WorkflowStateRow
from app.events.service import emit_event
from app.ingestion.profiler import read_source
from app.validation.employee import DEPARTMENTS, STATUSES, validation_errors

router = APIRouter(prefix="/api/batches", tags=["records"])


def _error_field(error: str) -> str:
    return error.split(":", 1)[0]


def _alternatives(field: str) -> list[str]:
    if field == "department":
        return sorted(DEPARTMENTS)
    if field == "employment_status":
        return sorted(STATUSES)
    return []


def _remove_old_record_escalations(db: Session, batch_id: str) -> None:
    rows = db.scalars(select(EscalationRow).where(EscalationRow.batch_id == batch_id)).all()
    for row in rows:
        context = json.loads(row.source_context_json)
        if str(context.get("kind", "")).startswith("record_"):
            db.delete(row)


def _record_escalation(
    batch_id: str,
    preview: RecordPreview,
    *,
    kind: str,
    reason_code: str,
    field: str,
    errors: list[str],
    allowed_actions: list[str],
    details: dict | None = None,
) -> EscalationRow:
    current = preview.transformed.get(field)
    return EscalationRow(
        id=str(uuid4()),
        batch_id=batch_id,
        source_context_json=json.dumps(
            {
                "kind": kind,
                "record_id": preview.record_id,
                "source_file": preview.source_file,
                "source_record_id": preview.source_record_id,
                "field": field,
                "current_value": current,
                "errors": errors,
                "conflicting_values": details or {},
            },
            default=str,
        ),
        suggestion=str(current) if current is not None else None,
        alternatives_json=json.dumps(_alternatives(field)),
        confidence_json=json.dumps({"validation_attempts": 0.0}),
        reason_code=reason_code,
        allowed_actions_json=json.dumps(allowed_actions),
    )


@router.post("/{batch_id}/records/transform", response_model=list[RecordPreview])
def transform(batch_id: str, db: Session = Depends(get_db)) -> list[RecordPreview]:
    workflow = db.get(WorkflowStateRow, batch_id)
    if workflow is None or workflow.status != "COMPLETED":
        raise HTTPException(409, "Resolve mapping review before transforming records")
    applied = json.loads(workflow.state_json).get("applied_mappings", {})
    existing = db.scalars(select(TransformedRecordRow).where(TransformedRecordRow.batch_id == batch_id)).all()
    if existing:
        return list_previews(batch_id, db)
    sources = db.scalars(
        select(SourceFileProfileRow).where(SourceFileProfileRow.batch_id == batch_id).order_by(SourceFileProfileRow.id)
    ).all()

    candidates: list[dict[str, Any]] = []
    for source in sources:
        frame, _, _ = read_source(Path(source.storage_path))
        mapping = {
            key.split(":", 1)[1]: target
            for key, target in applied.items()
            if key.startswith(f"{source.safe_name}:")
        }
        for number, record in enumerate(frame.to_dict(orient="records"), start=1):
            preview = clean_record(source.safe_name, str(number), record, mapping)
            candidate: dict[str, Any] = dict(preview.transformed)
            candidate.update(
                {
                    "_record_id": preview.record_id,
                    "_source": preview.source_file,
                    "_source_record_id": preview.source_record_id,
                    "_source_records": [
                        {
                            "source_file": preview.source_file,
                            "source_record_id": preview.source_record_id,
                            "original": preview.original,
                        }
                    ],
                    "_provenance": [item.model_dump(mode="json") for item in preview.provenance],
                    "_attempt_count": preview.attempt_count,
                }
            )
            candidates.append(candidate)

    reconciliation = reconcile_records(candidates)
    conflicting_ids = {
        str(conflict["records"][1].get("_record_id")) for conflict in reconciliation.probable_conflicts
    }
    previews: list[RecordPreview] = []
    db.execute(delete(TransformedRecordRow).where(TransformedRecordRow.batch_id == batch_id))
    _remove_old_record_escalations(db, batch_id)

    for record in reconciliation.records:
        transformed = {key: value for key, value in record.items() if not key.startswith("_")}
        errors = validation_errors(transformed)
        record_id = str(record["_record_id"])
        source_records = list(record.get("_source_records", []))
        conflict = record_id in conflicting_ids
        preview = RecordPreview(
            record_id=record_id,
            source_file=", ".join(dict.fromkeys(record.get("_sources", [record.get("_source", "unknown")]))),
            source_record_id=", ".join(str(item.get("source_record_id", "")) for item in source_records),
            original=(
                source_records[0]["original"]
                if len(source_records) == 1
                else {"reconciled_sources": source_records}
            ),
            transformed=transformed,
            provenance=record.get("_provenance", []),
            status="ESCALATION" if errors or conflict else "VALID",
            errors=errors + (["identity: conflicting record found across source files"] if conflict else []),
            attempt_count=max(2 if errors else 1, int(record.get("_attempt_count", 1))),
        )
        previews.append(preview)
        db.add(
            TransformedRecordRow(
                id=preview.record_id,
                batch_id=batch_id,
                source_file=preview.source_file,
                source_record_id=preview.source_record_id,
                original_json=json.dumps(preview.original, default=str),
                transformed_json=json.dumps(preview.transformed, default=str),
                provenance_json=json.dumps(
                    [item.model_dump(mode="json") for item in preview.provenance], default=str
                ),
                status=preview.status,
                errors_json=json.dumps(preview.errors),
                attempt_count=preview.attempt_count,
            )
        )
        for error in errors:
            field = _error_field(error)
            db.add(
                _record_escalation(
                    batch_id,
                    preview,
                    kind="record_validation",
                    reason_code="VALIDATION_FAILED_TWICE",
                    field=field,
                    errors=[error],
                    allowed_actions=["CORRECT", "REJECT"],
                )
            )
        if conflict:
            identity_field = "employee_id" if transformed.get("employee_id") else "email"
            db.add(
                _record_escalation(
                    batch_id,
                    preview,
                    kind="record_conflict",
                    reason_code="IDENTITY_CONFLICT",
                    field=identity_field,
                    errors=["Conflicting non-empty values were found for the same identity"],
                    allowed_actions=["CORRECT", "REJECT"],
                    details=next((item["conflicts"] for item in reconciliation.probable_conflicts
                                  if str(item["records"][1].get("_record_id")) == record_id), {}),
                )
            )
        emit_event(
            db,
            batch_id,
            "record_validated",
            {"record_id": preview.record_id, "status": preview.status},
        )

    open_count = sum(1 for preview in previews if preview.status == "ESCALATION")
    state = json.loads(workflow.state_json)
    state["reconciliation"] = {
        "input_records": len(candidates),
        "output_records": len(previews),
        "exact_merges": reconciliation.exact_merges,
        "probable_conflicts": len(reconciliation.probable_conflicts),
    }
    workflow.state_json = json.dumps(state)
    workflow.status = "PAUSED" if open_count else "COMPLETED"
    emit_event(db, batch_id, "reconciliation_completed", state["reconciliation"])
    if open_count:
        emit_event(db, batch_id, "workflow_paused", {"status": "PAUSED", "record_escalations": open_count})
    db.commit()
    return previews


@router.get("/{batch_id}/records", response_model=list[RecordPreview])
def list_previews(batch_id: str, db: Session = Depends(get_db)) -> list[RecordPreview]:
    rows = db.scalars(select(TransformedRecordRow).where(TransformedRecordRow.batch_id == batch_id)).all()
    return [
        RecordPreview(
            record_id=row.id,
            source_file=row.source_file,
            source_record_id=row.source_record_id,
            original=json.loads(row.original_json),
            transformed=json.loads(row.transformed_json),
            provenance=json.loads(row.provenance_json),
            status=row.status,
            errors=json.loads(row.errors_json),
            attempt_count=row.attempt_count,
        )
        for row in rows
    ]
