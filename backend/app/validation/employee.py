import re
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

DEPARTMENTS = {"Engineering", "Finance", "Human Resources", "Operations", "Sales", "Support"}
STATUSES = {"Active", "Inactive", "Leave", "Terminated"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATE_FIELDS = {"date_of_birth", "hire_date"}


def _friendly_error(item: dict[str, Any]) -> str:
    field = ".".join(str(part) for part in item["loc"])
    error_type = str(item.get("type", ""))
    if field in DATE_FIELDS:
        return f"{field}: Enter a real date in YYYY-MM-DD format, for example 2024-01-15"
    if error_type == "missing":
        return f"{field}: This required value is missing"
    if field == "employee_id" and error_type == "string_type":
        return "employee_id: Enter the employee ID as text, for example EM202"
    if field == "email":
        return "email: Enter a complete email address, for example name@company.com"
    if field == "department":
        return f"department: Choose one of: {', '.join(sorted(DEPARTMENTS))}"
    if field == "employment_status":
        return f"employment_status: Choose one of: {', '.join(sorted(STATUSES))}"
    return f"{field}: {item['msg']}"


class EmployeeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: str
    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    date_of_birth: date | None = None
    hire_date: date
    department: str
    employment_status: str
    manager_id: str | None = None
    source_system: str | None = None

    @field_validator("employee_id", "first_name", "last_name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("required value cannot be blank")
        return value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        if not EMAIL_RE.match(value):
            raise ValueError("invalid email")
        return value

    @field_validator("department")
    @classmethod
    def valid_department(cls, value: str) -> str:
        if value not in DEPARTMENTS:
            raise ValueError("invalid department")
        return value

    @field_validator("employment_status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        if value not in STATUSES:
            raise ValueError("invalid employment status")
        return value


def validation_errors(payload: dict[str, Any]) -> list[str]:
    try:
        EmployeeRecord.model_validate(payload)
    except Exception as exc:
        if hasattr(exc, "errors"):
            return [_friendly_error(item) for item in exc.errors()]
        return [str(exc)]
    return []
