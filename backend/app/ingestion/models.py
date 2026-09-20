from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ColumnProfile(BaseModel):
    name: str
    inferred_type: str
    null_ratio: float = Field(ge=0, le=1)
    unique_ratio: float = Field(ge=0, le=1)
    masked_samples: list[Any]
    likely_identifier: bool
    date_patterns: list[str]


class SourceFileProfile(BaseModel):
    file_name: str
    sheet_name: str | None
    row_count: int = Field(ge=0)
    columns: list[ColumnProfile]
    duplicate_row_count: int = Field(ge=0)
    encoding: str | None


class IngestionBatch(BaseModel):
    batch_id: str
    status: str
    created_at: datetime
    profiles: list[SourceFileProfile]

