from enum import StrEnum

from pydantic import BaseModel, Field


class PushStatus(StrEnum):
    SUCCESS = "SUCCESS"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"
    ROLLED_BACK = "ROLLED_BACK"


class PushRequest(BaseModel):
    batch_id: str
    record_id: str
    source_record_id: str
    idempotency_key: str = Field(min_length=8, max_length=255)
    payload_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class PushResult(BaseModel):
    target_write_id: str
    batch_id: str
    source_record_id: str
    idempotency_key: str
    payload_hash: str
    status: PushStatus
    retry_count: int
    idempotent_replay: bool = False

