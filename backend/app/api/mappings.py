import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db
from app.db.tables import IngestionBatchRow, MappingProposalRow, SourceFileProfileRow
from app.ingestion.models import SourceFileProfile
from app.events.service import emit_event
from app.mapping.engine import (
    AnthropicMappingAdapter,
    DeterministicFallback,
    InvalidModelOutput,
    MappingModel,
    ModelUnavailable,
    OllamaMappingAdapter,
    propose_mappings,
)
from app.mapping.models import MappingProposal
from app.mapping.schema import load_target_schema

router = APIRouter(prefix="/api/batches", tags=["mapping"])


def _profiles(db: Session, batch_id: str) -> list[SourceFileProfile]:
    rows = db.scalars(select(SourceFileProfileRow).where(SourceFileProfileRow.batch_id == batch_id)).all()
    return [SourceFileProfile.model_validate_json(row.profile_json) for row in rows]


@router.post("/{batch_id}/mapping-proposals", response_model=list[MappingProposal])
def create_mapping_proposals(
    batch_id: str, fallback: bool = Query(False), db: Session = Depends(get_db)
) -> list[MappingProposal]:
    if db.get(IngestionBatchRow, batch_id) is None:
        raise HTTPException(404, "Batch not found")
    existing = db.scalars(select(MappingProposalRow).where(MappingProposalRow.batch_id == batch_id)).all()
    if existing:
        return [MappingProposal.model_validate_json(item.proposal_json) for item in existing]
    settings = get_settings()
    adapter: MappingModel
    failover_adapter: MappingModel | None = None
    if fallback or settings.model_mode == "fallback":
        adapter = DeterministicFallback()
    else:
        try:
            if settings.model_mode == "ollama":
                adapter = OllamaMappingAdapter(
                    settings.ollama_base_url,
                    settings.ollama_model,
                    settings.llm_request_timeout_seconds,
                )
                failover_provider = settings.llm_failover_provider.strip().lower()
                if failover_provider not in {"anthropic", "fallback", "none"}:
                    raise HTTPException(
                        422,
                        "LLM_FAILOVER_PROVIDER must be one of: anthropic, fallback, none",
                    )
                if failover_provider == "anthropic" and settings.anthropic_api_key.strip():
                    try:
                        failover_adapter = AnthropicMappingAdapter(
                            settings.anthropic_api_key,
                            settings.anthropic_model,
                            settings.llm_request_timeout_seconds,
                            settings.llm_max_retries,
                        )
                    except ModelUnavailable:
                        # The deterministic safety net remains available when the
                        # optional external provider cannot be initialized.
                        failover_adapter = None
            elif settings.model_mode == "anthropic":
                adapter = AnthropicMappingAdapter(
                    settings.anthropic_api_key,
                    settings.anthropic_model,
                    settings.llm_request_timeout_seconds,
                    settings.llm_max_retries,
                )
            else:
                raise HTTPException(
                    422,
                    "MODEL_MODE must be one of: ollama, anthropic, fallback",
                )
        except ModelUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
    emit_event(
        db,
        batch_id,
        "node_started",
        {
            "node": "mapping_generation",
            "provider": adapter.provider,
            "failover_provider": failover_adapter.provider if failover_adapter else "deterministic_fallback",
        },
    )
    db.commit()
    try:
        proposals = propose_mappings(
            _profiles(db, batch_id),
            load_target_schema(),
            adapter,
            parallel_workers=settings.llm_parallel_workers,
            failover_model=failover_adapter,
            fast_path=settings.mapping_fast_path,
        )
    except (ModelUnavailable, InvalidModelOutput) as exc:
        emit_event(db, batch_id, "workflow_failed", {"node": "mapping_generation", "message": str(exc)})
        db.commit()
        raise HTTPException(503 if isinstance(exc, ModelUnavailable) else 502, str(exc)) from exc
    db.execute(delete(MappingProposalRow).where(MappingProposalRow.batch_id == batch_id))
    for proposal in proposals:
        db.add(
            MappingProposalRow(
                batch_id=batch_id,
                source_file=proposal.source_file,
                source_column=proposal.source_column,
                proposal_json=proposal.model_dump_json(),
            )
        )
    db.commit()
    emit_event(
        db,
        batch_id,
        "node_completed",
        {
            "node": "mapping_generation",
            "proposal_count": len(proposals),
            "provider": adapter.provider,
            "failover_provider": failover_adapter.provider if failover_adapter else "deterministic_fallback",
            "parallel_workers": settings.llm_parallel_workers,
        },
    )
    db.commit()
    return proposals


@router.get("/{batch_id}/mapping-proposals", response_model=list[MappingProposal])
def get_mapping_proposals(batch_id: str, db: Session = Depends(get_db)) -> list[MappingProposal]:
    rows = db.scalars(
        select(MappingProposalRow).where(MappingProposalRow.batch_id == batch_id).order_by(MappingProposalRow.id)
    ).all()
    if not rows and db.get(IngestionBatchRow, batch_id) is None:
        raise HTTPException(404, "Batch not found")
    return [MappingProposal.model_validate(json.loads(row.proposal_json)) for row in rows]
