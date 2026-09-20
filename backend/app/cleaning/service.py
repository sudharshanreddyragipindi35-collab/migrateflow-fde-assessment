from __future__ import annotations

import re
import math
import unicodedata
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from app.cleaning.models import FieldProvenance, RecordPreview, ReconciliationResult
from app.validation.employee import DEPARTMENTS, STATUSES, validation_errors

DATE_FORMATS = [
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "%Y-%m-%d"),
    (re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$"), "%d-%b-%Y"),
]


def _transform(field: str, value: Any) -> tuple[Any, str, str]:
    if value is None or isinstance(value, float) and math.isnan(value):
        return None, "none", "Source value is null"
    if field in {"date_of_birth", "hire_date"} and isinstance(value, (datetime, date)):
        return (value.date() if isinstance(value, datetime) else value).isoformat(), "typed_excel_date", "Excel date converted to YYYY-MM-DD"
    if isinstance(value, str):
        normalized = unicodedata.normalize("NFKC", value).strip()
        if normalized == "":
            return None, "empty_to_null", "Empty strings normalize to null"
        if field == "email":
            return normalized.lower(), "email_lowercase", "Email comparison is case-insensitive"
        if field == "phone":
            digits = re.sub(r"\D", "", normalized)
            return (f"+{digits}" if normalized.startswith("+") else digits), "phone_digits", "Configured phone normalization"
        if field in {"first_name", "last_name"}:
            return normalized.title(), "person_name_case", "Configured name casing"
        if field in {"department", "employment_status"}:
            choices = DEPARTMENTS if field == "department" else STATUSES
            canonical = next((item for item in choices if item.casefold() == normalized.casefold()), None)
            if canonical:
                return canonical, "known_value_case", "Matched the spelling of an allowed destination value"
        if field in {"date_of_birth", "hire_date"}:
            for pattern, date_format in DATE_FORMATS:
                if pattern.match(normalized):
                    try:
                        return datetime.strptime(normalized, date_format).date().isoformat(), "unambiguous_iso_date", "Unambiguous date converted to ISO"
                    except ValueError:
                        return normalized, "invalid_date_unchanged", "Invalid calendar date requires human correction"
            if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", normalized):
                first, second, _ = map(int, normalized.split("/"))
                slash_format = "%d/%m/%Y" if first > 12 or first == second else "%m/%d/%Y" if second > 12 else None
                if slash_format:
                    try:
                        return datetime.strptime(normalized, slash_format).date().isoformat(), "unambiguous_iso_date", "Only one calendar interpretation is valid"
                    except ValueError:
                        pass
            return normalized, "ambiguous_date_unchanged", "Ambiguous date is not guessed"
        return normalized, "unicode_trim", "Unicode normalized and surrounding whitespace removed"
    return value, "identity", "Typed value preserved"


def clean_record(source_file: str, source_record_id: str, original: dict[str, Any], mapping: dict[str, str]) -> RecordPreview:
    transformed: dict[str, Any] = {}
    provenance: list[FieldProvenance] = []
    now = datetime.now(timezone.utc)
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Two source columns cannot write to the same destination field")
    for source_field, target_field in mapping.items():
        value = original.get(source_field)
        new_value, rule, reason = _transform(target_field, value)
        transformed[target_field] = new_value
        provenance.append(
            FieldProvenance(
                field=target_field, original_value=value, new_value=new_value, rule=rule,
                confidence=1.0 if rule != "ambiguous_date_unchanged" else 0.0,
                actor="deterministic_cleaner", timestamp=now, reason=reason,
            )
        )
    errors = validation_errors(transformed)
    attempt_count = 1
    if errors:
        attempt_count = 2
        errors = validation_errors(transformed)
    return RecordPreview(
        record_id=str(uuid4()), source_file=source_file, source_record_id=source_record_id,
        original=dict(original), transformed=transformed, provenance=provenance,
        status="VALID" if not errors else "ESCALATION", errors=errors, attempt_count=attempt_count,
    )


def reconcile_records(records: list[dict[str, Any]]) -> ReconciliationResult:
    merged: list[dict[str, Any]] = []
    index: dict[str, dict[str, Any]] = {}
    exact_merges = 0
    conflicts: list[dict[str, Any]] = []
    for record in records:
        key = str(record.get("employee_id") or "").casefold() or str(record.get("email") or "").casefold()
        if not key or key not in index:
            clone = dict(record)
            clone.setdefault("_sources", []).append(record.get("_source", "unknown"))
            index[key or f"row:{len(merged)}"] = clone
            merged.append(clone)
            continue
        current = index[key]
        differing = {
            field: [current.get(field), record.get(field)]
            for field in set(current) | set(record)
            if not field.startswith("_") and current.get(field) not in (None, "") and record.get(field) not in (None, "") and current.get(field) != record.get(field)
        }
        if differing:
            conflicts.append({"identity": key, "conflicts": differing, "records": [current, record]})
            clone = dict(record)
            clone.setdefault("_sources", []).append(record.get("_source", "unknown"))
            index[f"{key}:conflict:{len(merged)}"] = clone
            merged.append(clone)
            continue
        for field, value in record.items():
            if not field.startswith("_") and current.get(field) in (None, ""):
                current[field] = value
        current.setdefault("_sources", []).append(record.get("_source", "unknown"))
        if "_source_records" in record:
            current.setdefault("_source_records", []).extend(record["_source_records"])
        if "_provenance" in record:
            current.setdefault("_provenance", []).extend(record["_provenance"])
        exact_merges += 1
    return ReconciliationResult(records=merged, exact_merges=exact_merges, probable_conflicts=conflicts)
