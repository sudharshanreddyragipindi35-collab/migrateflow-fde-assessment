import csv, io, json
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.audit.models import AuditEvent
from app.db.database import get_db
from app.db.tables import AuditEventRow
router = APIRouter(prefix="/api/batches", tags=["audit"])
def _events(db: Session, batch_id: str) -> list[AuditEvent]:
    rows = db.scalars(select(AuditEventRow).where(AuditEventRow.batch_id == batch_id).order_by(AuditEventRow.id)).all(); events=[]
    for row in rows:
        details=json.loads(row.details_json); events.append(AuditEvent(event_id=row.id, actor_type=row.actor_type, actor_id=row.actor_id, action=row.action, entity_type=row.entity_type, entity_id=row.entity_id, before_hash_or_masked=details.get("before_hash_or_masked"), after_hash_or_masked=details.get("after_hash_or_masked"), rule_or_model=details.get("rule_or_model"), confidence=details.get("confidence"), reason=details.get("reason") or details.get("reason_code"), batch_id=row.batch_id, timestamp=row.created_at))
    return events
@router.get("/{batch_id}/audit")
def export_audit(batch_id: str, format: str = Query("json", pattern="^(json|csv)$"), db: Session = Depends(get_db)):
    events=_events(db,batch_id)
    if format == "json": return [item.model_dump(mode="json") for item in events]
    output=io.StringIO(); fieldnames=list(AuditEvent.model_fields); writer=csv.DictWriter(output, fieldnames=fieldnames); writer.writeheader()
    for item in events: writer.writerow(item.model_dump(mode="json"))
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{batch_id}-audit.csv"'})
