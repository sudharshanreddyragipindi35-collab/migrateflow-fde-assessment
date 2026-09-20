import json
from enum import StrEnum

from pydantic import BaseModel

from app.db.tables import PipelineRunRow


class ExecutionMode(StrEnum):
    AUTOPILOT = "AUTOPILOT"
    HUMAN_IN_LOOP = "HUMAN_IN_LOOP"


class PipelineStage(BaseModel):
    stage_id: str
    agent: str
    title: str
    description: str
    status: str
    detail: str


class PipelineStatus(BaseModel):
    batch_id: str
    execution_mode: ExecutionMode
    status: str
    current_stage: str
    stages: list[PipelineStage]
    requires_action: bool
    action_message: str


STAGE_DEFINITIONS = [
    ("upload", "Upload agent", "Read and profile files", "Checks CSV and Excel files, profiles columns, and masks samples."),
    ("analyze", "Analyze agent", "Match your columns", "Recognizes familiar fields immediately and asks AI about unfamiliar labels."),
    ("review", "Review agent", "Check uncertain matches", "Accepts clear matches and asks you only when a choice needs confirmation."),
    ("preview", "Validation agent", "Clean and validate records", "Reconciles duplicates, cleans values, and validates every record."),
    ("push", "Integration agent", "Send employees", "Sends valid records to the demo destination and keeps a record of every result."),
]


def initial_stages(mode: ExecutionMode) -> list[dict[str, str]]:
    stages = []
    for stage_id, agent, title, description in STAGE_DEFINITIONS:
        status = "COMPLETED" if stage_id == "upload" else "QUEUED"
        detail = "Files uploaded and profiled successfully." if stage_id == "upload" else "Waiting for the previous agent."
        stages.append(
            {
                "stage_id": stage_id,
                "agent": agent,
                "title": title,
                "description": description,
                "status": status,
                "detail": detail,
            }
        )
    stages[1]["status"] = "QUEUED" if mode == ExecutionMode.AUTOPILOT else "WAITING_APPROVAL"
    stages[1]["detail"] = (
        "Autopilot will start analysis automatically."
        if mode == ExecutionMode.AUTOPILOT
        else "Waiting for your approval to analyze the uploaded files."
    )
    return stages


def stages_from_row(row: PipelineRunRow) -> list[dict[str, str]]:
    return json.loads(row.stages_json)


def update_stage(row: PipelineRunRow, stage_id: str, status: str, detail: str) -> None:
    stages = stages_from_row(row)
    for stage in stages:
        if stage["stage_id"] == stage_id:
            stage["status"] = status
            stage["detail"] = detail
            break
    row.stages_json = json.dumps(stages, separators=(",", ":"))


def pipeline_model(row: PipelineRunRow) -> PipelineStatus:
    stages = [PipelineStage.model_validate(item) for item in stages_from_row(row)]
    current = next((item for item in stages if item.stage_id == row.current_stage), stages[-1])
    requires_action = current.status in {
        "WAITING_APPROVAL", "NEEDS_REVIEW", "READY_TO_PUSH", "FAILED"
    }
    messages = {
        "WAITING_APPROVAL": f"Approve {current.agent.lower()} to continue, or stop the migration.",
        "NEEDS_REVIEW": "Resolve the highlighted uncertain cases before the agents can continue.",
        "READY_TO_PUSH": "Review the validated preview, then choose Push or Do not push.",
        "RUNNING": f"{current.agent} is working now.",
        "FAILED": f"{current.agent} stopped safely. Retry when ready.",
        "COMPLETED": "The migration pipeline is complete.",
        "SKIPPED": "The migration finished without pushing to the target.",
    }
    if row.execution_mode == ExecutionMode.AUTOPILOT and current.status == "READY_TO_PUSH":
        messages["READY_TO_PUSH"] = "Checks are complete. Sending approved records automatically."
        requires_action = False
    if row.status == "PARTIAL_FAILURE":
        messages[current.status] = "Some employees were not sent. Open Results to retry temporary failures."
    if row.status == "ROLLED_BACK":
        messages[current.status] = "Sent records have been undone. Start a new migration to send again."
    return PipelineStatus(
        batch_id=row.batch_id,
        execution_mode=ExecutionMode(row.execution_mode),
        status=row.status,
        current_stage=row.current_stage,
        stages=stages,
        requires_action=requires_action,
        action_message=messages.get(current.status, current.detail),
    )
