import asyncio
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.config import settings
from app.services.bambu_mqtt import mqtt_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/printer/{printer_id}/status")
async def printer_status_ws(
    websocket: WebSocket,
    printer_id: int,
    token: str = Query(...),
):
    if token != settings.foundry_api_token:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()
    logger.info("WebSocket connected for printer %d", printer_id)

    queue: asyncio.Queue[dict] = asyncio.Queue()

    async def on_status(data: dict):
        await queue.put(data)

    mqtt_service.add_subscriber(printer_id, on_status)

    try:
        # Send current cached status immediately if available
        current = mqtt_service.get_status(printer_id)
        if current:
            await websocket.send_json(current)

        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(data)
            except asyncio.TimeoutError:
                # Send a ping/keepalive
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for printer %d", printer_id)
    except Exception:
        logger.exception("WebSocket error for printer %d", printer_id)
    finally:
        mqtt_service.remove_subscriber(printer_id, on_status)
