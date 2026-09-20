import contextvars
import logging
from uuid import uuid4
from fastapi import Request
from app.security import mask_text
correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")
class SafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str: return mask_text(super().format(record))
async def correlation_middleware(request: Request, call_next):
    identifier = request.headers.get("X-Correlation-ID") or str(uuid4()); token = correlation_id.set(identifier)
    try:
        response = await call_next(request); response.headers["X-Correlation-ID"] = identifier; return response
    finally: correlation_id.reset(token)
