import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.tables import WorkflowEventRow


class WorkflowEvent(BaseModel):
    event_id: int
    batch_id: str
    timestamp: datetime
    level: str
    event_type: str
    payload: dict[str, Any]


def emit_event(db: Session, batch_id: str, event_type: str, payload: dict[str, Any] | None = None, level: str = "INFO") -> WorkflowEventRow:
    row = WorkflowEventRow(
        batch_id=batch_id, event_type=event_type, level=level,
        payload_json=json.dumps(payload or {}, separators=(",", ":"), default=str),
    )
    db.add(row)
    db.flush()
    return row


def list_events(db: Session, batch_id: str, after_id: int = 0) -> list[WorkflowEvent]:
    rows = db.scalars(
        select(WorkflowEventRow)
        .where(WorkflowEventRow.batch_id == batch_id, WorkflowEventRow.id > after_id)
        .order_by(WorkflowEventRow.id)
    ).all()
    return [
        WorkflowEvent(
            event_id=row.id, batch_id=row.batch_id, timestamp=row.created_at,
            level=row.level, event_type=row.event_type, payload=json.loads(row.payload_json),
        )
        for row in rows
    ]

