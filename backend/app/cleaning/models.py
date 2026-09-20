from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FieldProvenance(BaseModel):
    field: str
    original_value: Any
    new_value: Any
    rule: str
    confidence: float = Field(ge=0, le=1)
    actor: str
    timestamp: datetime
    reason: str


class RecordPreview(BaseModel):
    record_id: str
    source_file: str
    source_record_id: str
    original: dict[str, Any]
    transformed: dict[str, Any]
    provenance: list[FieldProvenance]
    status: str
    errors: list[str]
    attempt_count: int


class ReconciliationResult(BaseModel):
    records: list[dict[str, Any]]
    exact_merges: int
    probable_conflicts: list[dict[str, Any]]

