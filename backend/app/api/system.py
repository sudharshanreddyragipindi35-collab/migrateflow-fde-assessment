import json
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(prefix="/api/system", tags=["system"])


class ModelRuntimeStatus(BaseModel):
    mode: str
    provider: str
    model: str | None
    status: str
    parallel_workers: int
    failover_provider: str | None
    failover_status: str


def _failover_status(provider: str, api_key: str) -> tuple[str | None, str]:
    selected = provider.strip().lower()
    if selected == "anthropic":
        return "Anthropic", "configured" if api_key.strip() else "not configured"
    if selected == "fallback":
        return "Deterministic fallback", "ready"
    if selected == "none":
        return None, "disabled"
    return "Unknown", "misconfigured"


def _ollama_status(base_url: str, model: str) -> str:
    try:
        with urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=2) as response:  # noqa: S310
            payload = json.load(response)
    except (OSError, URLError, ValueError):
        return "unavailable"
    installed = {item.get("name") for item in payload.get("models", [])}
    return "ready" if model in installed else "model_missing"


@router.get("/model", response_model=ModelRuntimeStatus)
def model_runtime() -> ModelRuntimeStatus:
    settings = get_settings()
    if settings.model_mode == "ollama":
        failover_provider, failover_status = _failover_status(
            settings.llm_failover_provider, settings.anthropic_api_key
        )
        return ModelRuntimeStatus(
            mode="ollama",
            provider="Ollama",
            model=settings.ollama_model,
            status=_ollama_status(settings.ollama_base_url, settings.ollama_model),
            parallel_workers=settings.llm_parallel_workers,
            failover_provider=failover_provider,
            failover_status=failover_status,
        )
    if settings.model_mode == "anthropic":
        return ModelRuntimeStatus(
            mode="anthropic",
            provider="Anthropic",
            model=settings.anthropic_model,
            status="configured" if settings.anthropic_api_key.strip() else "misconfigured",
            parallel_workers=settings.llm_parallel_workers,
            failover_provider=None,
            failover_status="disabled",
        )
    if settings.model_mode == "fallback":
        return ModelRuntimeStatus(
            mode="fallback",
            provider="Deterministic fallback",
            model=None,
            status="ready",
            parallel_workers=1,
            failover_provider=None,
            failover_status="disabled",
        )
    return ModelRuntimeStatus(
        mode=settings.model_mode,
        provider="Unknown",
        model=None,
        status="misconfigured",
        parallel_workers=settings.llm_parallel_workers,
        failover_provider=None,
        failover_status="disabled",
    )
