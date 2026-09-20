from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class EscalationAction(StrEnum):
    APPROVE = "APPROVE"
    CORRECT = "CORRECT"
    REJECT = "REJECT"


class Escalation(BaseModel):
    escalation_id: str
    batch_id: str
    source_context: dict[str, Any]
    suggestion: str | None
    alternatives: list[str]
    confidence_evidence: dict[str, float]
    reason_code: str
    allowed_actions: list[EscalationAction]
    status: str
    decision: dict[str, Any] | None = None
    actor: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class EscalationDecision(BaseModel):
    action: EscalationAction
    corrected_value: str | None = None
    actor: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def correction_requires_value(self) -> "EscalationDecision":
        if self.action == EscalationAction.CORRECT and not self.corrected_value:
            raise ValueError("CORRECT requires corrected_value")
        return self


class WorkflowStatus(BaseModel):
    batch_id: str
    thread_id: str
    status: str
    applied_mappings: dict[str, str]
    open_escalations: int

