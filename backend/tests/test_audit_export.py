from uuid import uuid4
from fastapi.testclient import TestClient
from app.db.database import SessionLocal
from app.db.tables import AuditEventRow
from app.main import app
def test_audit_exports_json_and_csv() -> None:
    batch=str(uuid4())
    with SessionLocal() as db:
        db.add(AuditEventRow(batch_id=batch, actor_type="AGENT", actor_id="policy", action="mapping.auto_applied", entity_type="mapping", entity_id="x", details_json='{"confidence":0.99,"rule_or_model":"policy-v1"}')); db.commit()
    client=TestClient(app); response=client.get(f"/api/batches/{batch}/audit"); assert response.status_code==200; assert response.json()[0]["confidence"]==0.99
    csv_response=client.get(f"/api/batches/{batch}/audit?format=csv"); assert csv_response.status_code==200; assert "actor_type" in csv_response.text and "mapping.auto_applied" in csv_response.text
