import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.db.database import get_db
from app.agent.pipeline import ExecutionMode, initial_stages
from app.db.tables import IngestionBatchRow, PipelineRunRow, SourceFileProfileRow
from app.events.service import emit_event
from app.ingestion.models import IngestionBatch, SourceFileProfile
from app.ingestion.profiler import ALLOWED_EXTENSIONS, IngestionError, profile_file, profile_to_json, sanitize_filename

router = APIRouter(prefix="/api/batches", tags=["batches"])


@router.post("", response_model=IngestionBatch, status_code=status.HTTP_201_CREATED)
async def create_batch(
    files: list[UploadFile] = File(...),
    execution_mode: str = Form(ExecutionMode.HUMAN_IN_LOOP.value),
    db: Session = Depends(get_db),
) -> IngestionBatch:
    settings = get_settings()
    try:
        mode = ExecutionMode(execution_mode)
    except ValueError as exc:
        raise HTTPException(422, "execution_mode must be AUTOPILOT or HUMAN_IN_LOOP") from exc
    if not files or len(files) > settings.max_upload_files:
        raise HTTPException(400, f"Upload between 1 and {settings.max_upload_files} files")
    batch_id = str(uuid4())
    batch_dir = Path(settings.upload_root).resolve() / batch_id
    batch_dir.mkdir(parents=True, exist_ok=False)
    profiles: list[SourceFileProfile] = []
    seen: set[str] = set()
    try:
        for upload in files:
            safe_name = sanitize_filename(upload.filename or "")
            if safe_name.casefold() in seen:
                raise IngestionError(f"Duplicate filename: {safe_name}")
            seen.add(safe_name.casefold())
            if Path(safe_name).suffix.lower() not in ALLOWED_EXTENSIONS:
                raise IngestionError("Only .csv and .xlsx files are supported")
            content = await upload.read(settings.max_upload_bytes + 1)
            if not content:
                raise IngestionError(f"{safe_name} is empty")
            if len(content) > settings.max_upload_bytes:
                raise IngestionError(f"{safe_name} exceeds the upload size limit")
            stored = batch_dir / safe_name
            stored.write_bytes(content)
            profile = await run_in_threadpool(profile_file, stored, safe_name)
            profiles.append(profile)
        row = IngestionBatchRow(id=batch_id, status="PROFILED", file_count=len(profiles))
        db.add(row)
        db.flush()
        db.add(
            PipelineRunRow(
                batch_id=batch_id,
                execution_mode=mode.value,
                status="ACTIVE",
                current_stage="analyze",
                stages_json=json.dumps(initial_stages(mode), separators=(",", ":")),
            )
        )
        for profile in profiles:
            db.add(
                SourceFileProfileRow(
                    batch_id=batch_id,
                    safe_name=profile.file_name,
                    storage_path=str(batch_dir / profile.file_name),
                    profile_json=profile_to_json(profile),
                )
            )
        emit_event(
            db,
            batch_id,
            "agent_completed",
            {"agent": "upload", "message": f"Profiled {len(profiles)} source file(s)."},
        )
        db.commit()
        db.refresh(row)
        if mode == ExecutionMode.AUTOPILOT:
            from app.agent.jobs import enqueue
            enqueue(db, batch_id)
        return IngestionBatch(batch_id=row.id, status=row.status, created_at=row.created_at, profiles=profiles)
    except IngestionError as exc:
        db.rollback()
        for child in batch_dir.glob("*"):
            child.unlink(missing_ok=True)
        batch_dir.rmdir()
        raise HTTPException(422, str(exc)) from exc


@router.get("/{batch_id}/profiles", response_model=IngestionBatch)
def get_profiles(batch_id: str, db: Session = Depends(get_db)) -> IngestionBatch:
    batch = db.get(IngestionBatchRow, batch_id)
    if batch is None:
        raise HTTPException(404, "Batch not found")
    rows = db.scalars(
        select(SourceFileProfileRow).where(SourceFileProfileRow.batch_id == batch_id).order_by(SourceFileProfileRow.id)
    ).all()
    return IngestionBatch(
        batch_id=batch.id,
        status=batch.status,
        created_at=batch.created_at,
        profiles=[SourceFileProfile.model_validate(json.loads(row.profile_json)) for row in rows],
    )
