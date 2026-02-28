import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def notify(title: str, message: str, priority: str = "default", tags: str | None = None):
    """Send a push notification via ntfy.sh."""
    if not settings.ntfy_topic:
        return

    headers = {"Title": title, "Priority": priority}
    if tags:
        headers["Tags"] = tags

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.ntfy_server}/{settings.ntfy_topic}",
                headers=headers,
                content=message,
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("Notification sent: %s", title)
    except Exception:
        logger.exception("Failed to send notification: %s", title)
