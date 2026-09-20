from typing import Any

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool
    details: Any = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody

