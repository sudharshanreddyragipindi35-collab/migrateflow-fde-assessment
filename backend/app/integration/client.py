"""HTTP connector boundary. The bundled stub uses an in-process ASGI transport.

Set MOCK_TARGET_BASE_URL for the same contract over a real network. No Python
target service functions are called by the orchestration layer.
"""
import asyncio

import httpx
from fastapi import HTTPException

from app.config import get_settings
from app.integration.models import PushResult


def push_batch(batch_id: str) -> list[PushResult]:
    base_url = get_settings().mock_target_base_url
    path = f"/mock-target/migrations/{batch_id}/push-valid"
    try:
        if base_url:
            with httpx.Client(base_url=base_url, timeout=30) as client:
                response = client.post(path)
        else:
            from app.main import app

            async def invoke():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://mock-target") as client:
                    return await client.post(path)

            response = asyncio.run(invoke())
        if response.is_error:
            raise HTTPException(response.status_code, "Destination rejected the request. Check reviews and results before retrying.")
        return [PushResult.model_validate(item) for item in response.json()]
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Destination is unavailable. Your progress is saved; retry from Results.") from exc
