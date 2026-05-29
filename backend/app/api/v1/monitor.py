import asyncio
import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ...core.config import get_settings
from ...services.overview_service import build_overview, load_events

router = APIRouter(tags=["monitor"])


@router.get("/overview")
def overview(brand: str = "") -> dict[str, Any]:
    settings = get_settings()
    return build_overview(settings.state_file, settings.event_file, brand_filter=brand)


@router.get("/plan")
def plan(brand: str = "") -> dict[str, Any]:
    settings = get_settings()
    data = build_overview(settings.state_file, settings.event_file, brand_filter=brand)
    return {"updated_at": data["updated_at"], "plan": data["plan"]}


@router.get("/events")
def events(limit: int = 80, brand: str = "") -> dict[str, Any]:
    settings = get_settings()
    rows = load_events(settings.event_file, limit=max(1, min(limit, 500)))
    selected_brand = str(brand or "").strip()
    if selected_brand:
        rows = [row for row in rows if str(row.get("brand", "")).strip() == selected_brand]
    return {"events": rows}


@router.get("/events/stream")
async def events_stream(request: Request) -> StreamingResponse:
    settings = get_settings()
    selected_brand = str(request.query_params.get("brand", "")).strip()

    async def event_generator():
        last_sig = ""
        while True:
            if await request.is_disconnected():
                break

            payload = build_overview(settings.state_file, settings.event_file, brand_filter=selected_brand)
            sig = f"{payload.get('updated_at')}:{len(payload.get('inflight') or [])}:{len(payload.get('events') or [])}"
            if sig != last_sig:
                data = json.dumps(payload, ensure_ascii=False)
                yield f"event: overview\ndata: {data}\n\n"
                last_sig = sig
            else:
                yield "event: ping\ndata: {}\n\n"

            await asyncio.sleep(3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
