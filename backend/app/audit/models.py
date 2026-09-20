from datetime import datetime
from pydantic import BaseModel
class AuditEvent(BaseModel):
    event_id: int; actor_type: str; actor_id: str; action: str; entity_type: str; entity_id: str
    before_hash_or_masked: str | None = None; after_hash_or_masked: str | None = None; rule_or_model: str | None = None
    confidence: float | None = None; reason: str | None = None; batch_id: str; timestamp: datetime
