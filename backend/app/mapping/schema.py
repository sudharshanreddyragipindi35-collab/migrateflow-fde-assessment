from pathlib import Path

import yaml  # type: ignore[import-untyped]

from app.mapping.models import TargetField, TargetSchema


def default_schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "target_schema" / "employee.yaml"


def load_target_schema(path: Path | None = None) -> TargetSchema:
    payload = yaml.safe_load((path or default_schema_path()).read_text(encoding="utf-8"))
    fields = [TargetField(name=name, **definition) for name, definition in payload["fields"].items()]
    return TargetSchema(name=payload["name"], version=payload["version"], fields=fields)
