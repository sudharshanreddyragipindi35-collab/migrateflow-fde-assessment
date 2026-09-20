import hashlib
import re
from typing import Any
from app.ingestion.models import ColumnProfile
INJECTION_PATTERNS = re.compile(r"(?i)(ignore\s+(all\s+)?previous|system\s+prompt|developer\s+message|tool\s+call|execute\s+command|jailbreak)")
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")
def mask_text(value: str) -> str: return PHONE_RE.sub("[MASKED_PHONE]", EMAIL_RE.sub("[MASKED_EMAIL]", value))
def safe_sample(value: Any) -> Any:
    if not isinstance(value, str): return value
    if INJECTION_PATTERNS.search(value): return "[REDACTED_UNTRUSTED_INSTRUCTION]"
    return mask_text(value)[:80]
def model_safe_column(column: ColumnProfile) -> dict[str, Any]:
    payload = column.model_dump(mode="json")
    payload["name"] = safe_sample(column.name)
    # Aggregate type/date statistics carry semantics; arbitrary text can contain
    # names, addresses, salaries or free-form HR notes even in unknown columns.
    payload["masked_samples"] = [
        "[REDACTED_UNTRUSTED_INSTRUCTION]" if isinstance(item, str) and INJECTION_PATTERNS.search(item)
        else "[MASKED_EMAIL]" if isinstance(item, str) and EMAIL_RE.search(item)
        else "[MASKED_PHONE]" if isinstance(item, str) and PHONE_RE.search(item)
        else "[MASKED_VALUE]" if item is not None else None
        for item in column.masked_samples[:3]
    ]
    return payload
def value_hash(value: Any) -> str: return hashlib.sha256(repr(value).encode()).hexdigest()
