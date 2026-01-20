"""Home Assistant webhook integration."""

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class WebhookClient:
    """Client for sending webhooks to Home Assistant."""

    ha_url: str
    webhook_id: str
    token: str = ""
    _session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
            self._session = None

    @property
    def webhook_url(self) -> str:
        """Get the full webhook URL."""
        base = self.ha_url.rstrip("/")
        return f"{base}/api/webhook/{self.webhook_id}"

    async def send(self, event_type: str, data: dict[str, Any]) -> bool:
        """Send data to Home Assistant webhook.

        Args:
            event_type: Type of event (profile, activities, world)
            data: Event data payload

        Returns:
            True if successful, False otherwise
        """
        if not self._session:
            logger.error("Webhook client session not initialized")
            return False

        payload = {
            "event_type": event_type,
            "data": data,
        }

        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            async with self._session.post(
                self.webhook_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    logger.debug("Webhook sent: %s", event_type)
                    return True
                else:
                    text = await resp.text()
                    logger.warning(
                        "Webhook failed: %d - %s (event=%s)",
                        resp.status,
                        text,
                        event_type,
                    )
                    return False
        except Exception as e:
            logger.error("Webhook error: %s (event=%s)", e, event_type)
            return False

    async def send_profile(self, profile_data: dict[str, Any]) -> bool:
        """Send profile update to Home Assistant."""
        return await self.send("zwift_profile_update", profile_data)

    async def send_activities(self, activities_data: list[dict[str, Any]]) -> bool:
        """Send activities update to Home Assistant."""
        return await self.send("zwift_activities_update", activities_data)

    async def send_world(self, world_data: dict[str, Any]) -> bool:
        """Send world/live status update to Home Assistant."""
        return await self.send("zwift_world_update", world_data)

    async def send_status(self, online: bool, world_id: int | None = None) -> bool:
        """Send online status update to Home Assistant."""
        return await self.send(
            "zwift_status_update",
            {"online": online, "world_id": world_id},
        )
