import asyncio
import json

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.events.service import list_events

router = APIRouter(prefix="/api/batches", tags=["events"])


@router.get("/{batch_id}/events")
async def events(
    batch_id: str,
    snapshot: bool = Query(False),
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    start = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

    async def stream():
        cursor = start
        idle = 0
        while True:
            items = list_events(db, batch_id, cursor)
            # Release the connection between polls rather than holding a pool slot
            # for the lifetime of every browser tab.
            db.rollback()
            for item in items:
                cursor = item.event_id
                data = item.model_dump(mode="json")
                yield f"id: {item.event_id}\nevent: {item.event_type}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"
            if snapshot:
                break
            idle += 1
            if idle % 15 == 0:
                yield ": keep-alive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
